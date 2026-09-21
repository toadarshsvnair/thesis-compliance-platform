"""Admin user management: the actual console for what app/api/auth.py's
register() only exposes as a raw endpoint. Scoped so a University Admin can
only manage accounts that hold a role at their own university; a Super Admin
can manage anyone.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import User, UserRole, Submission
from ..security.identity import Principal
from ..security.dependencies import get_principal
from ..security.authorization import _principal_user_id
from ..security.passwords import hash_password

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

VALID_ROLES = {"student", "research_officer", "university_admin", "super_admin"}
_EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def _require_admin(principal: Principal) -> None:
    if not principal.has_role("university_admin", "super_admin"):
        raise HTTPException(403, "Requires a University Admin or Super Admin role.")


def _manageable_university_ids(principal: Principal) -> set[int] | None:
    """None means unrestricted (Super Admin)."""
    if principal.has_role("super_admin"):
        return None
    return set(principal.university_ids)


def _user_roles(db: Session, user_id: int) -> list[UserRole]:
    return list(db.scalars(select(UserRole).where(UserRole.user_id == user_id)).all())


def _is_active_super_admin(db: Session, user: User) -> bool:
    if not user.active:
        return False
    return any(r.role == "super_admin" for r in _user_roles(db, user.id))


def _active_super_admin_count(db: Session, exclude_user_id: int | None = None) -> int:
    """The system-wide count of active accounts holding super_admin -- not
    scoped to a university, since super_admin itself isn't. Used to block
    any action that would leave zero, which nothing but a database edit
    could then recover from."""
    super_admin_user_ids = {r.user_id for r in db.scalars(
        select(UserRole).where(UserRole.role == "super_admin")
    ).all() if r.user_id != exclude_user_id}
    if not super_admin_user_ids:
        return 0
    active_users = db.scalars(
        select(User).where(User.id.in_(super_admin_user_ids), User.active.is_(True))
    ).all()
    return len(active_users)


def _assert_can_manage(db: Session, principal: Principal, user: User) -> None:
    scope = _manageable_university_ids(principal)
    if scope is None:
        return
    roles = _user_roles(db, user.id)
    if not any(r.university_id in scope for r in roles):
        raise HTTPException(403, "You can only manage accounts at your own university.")


def _assert_not_self_destructive(principal: Principal, user: User, action: str) -> None:
    """An admin can still edit their own name, programme, etc. -- but cannot
    suspend, delete, or demote their own account. Self-service account
    recovery isn't a thing here, so a mistaken self-action would be
    permanent for that session."""
    own_id = _principal_user_id(principal)
    if own_id is not None and own_id == user.id:
        raise HTTPException(400, f"You can't {action} your own account. Ask another admin to do this for you.")


def _serialize(db: Session, user: User) -> dict:
    roles = _user_roles(db, user.id)
    return {
        "id": user.id,
        "email": user.email,
        "display_name": user.display_name,
        "active": user.active,
        "expires_at": user.expires_at,
        "created_at": user.created_at,
        "programme": user.programme,
        "faculty_id": user.faculty_id,
        "roles": [{"role": r.role, "university_id": r.university_id} for r in roles],
    }


class CreateUserRequest(BaseModel):
    email: str = Field(pattern=_EMAIL_RE, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=250)
    role: str
    university_id: int
    expires_at: datetime | None = None
    programme: str | None = Field(default=None, max_length=250)
    faculty_id: int | None = None

    @field_validator("email")
    @classmethod
    def _lowercase_email(cls, v: str) -> str:
        return v.strip().lower()


class UpdateUserRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=250)
    active: bool | None = None
    expires_at: datetime | None = None
    clear_expiry: bool = False  # explicit flag, since expires_at=None is ambiguous with "don't change"
    role: str | None = None
    programme: str | None = None
    faculty_id: int | None = None
    clear_faculty: bool = False


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=200)


def _apply_expiry_transitions(db: Session, users: list[User]) -> None:
    """Same lazy transition as login() -- if an admin is looking at this list,
    that's as good a moment as any to bring stored `active` up to date with
    any end date that has since passed."""
    changed = False
    now = datetime.now(timezone.utc)
    for u in users:
        if u.active and u.expires_at and u.expires_at < now:
            u.active = False
            changed = True
    if changed:
        db.commit()


@router.get("")
def list_users(university_id: int | None = None, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_admin(principal)
    scope = _manageable_university_ids(principal)
    if university_id is not None:
        if scope is not None and university_id not in scope:
            raise HTTPException(403, "University access denied.")
        target_scope = {university_id}
    else:
        target_scope = scope  # None (all) for super_admin, else the admin's own universities

    if target_scope is None:
        users = db.scalars(select(User).order_by(User.id)).all()
    else:
        user_ids = {r.user_id for r in db.scalars(
            select(UserRole).where(UserRole.university_id.in_(target_scope))
        ).all()}
        users = db.scalars(select(User).where(User.id.in_(user_ids)).order_by(User.id)).all() if user_ids else []
    _apply_expiry_transitions(db, users)
    return [_serialize(db, u) for u in users]


@router.post("")
def create_user(body: CreateUserRequest, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_admin(principal)
    if body.role not in VALID_ROLES:
        raise HTTPException(400, f"role must be one of {sorted(VALID_ROLES)}")
    scope = _manageable_university_ids(principal)
    if scope is not None and body.university_id not in scope:
        raise HTTPException(403, "You can only create accounts at your own university.")
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "An account with this email already exists.")

    user = User(
        external_subject=f"local:{body.email}",
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        active=True,
        expires_at=body.expires_at,
        programme=body.programme,
        faculty_id=body.faculty_id,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, university_id=body.university_id, role=body.role))
    db.commit()
    return _serialize(db, user)


@router.patch("/{user_id}")
def update_user(user_id: int, body: UpdateUserRequest, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_admin(principal)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    _assert_can_manage(db, principal, user)

    is_being_suspended = body.active is False
    is_being_demoted = body.role is not None and body.role != "super_admin"
    if is_being_suspended:
        _assert_not_self_destructive(principal, user, "suspend")
    if is_being_demoted:
        _assert_not_self_destructive(principal, user, "change the role of")
    if (is_being_suspended or is_being_demoted) and _is_active_super_admin(db, user):
        if _active_super_admin_count(db, exclude_user_id=user.id) == 0:
            raise HTTPException(
                409,
                "This is the last active Super Admin account. Promote another account to "
                "Super Admin first, or this system would have no admin left at all.",
            )

    if body.display_name is not None:
        user.display_name = body.display_name
    if body.active is not None:
        user.active = body.active
    if body.clear_expiry:
        user.expires_at = None
    elif body.expires_at is not None:
        user.expires_at = body.expires_at
    if body.programme is not None:
        user.programme = body.programme
    if body.clear_faculty:
        user.faculty_id = None
    elif body.faculty_id is not None:
        user.faculty_id = body.faculty_id
    if body.role is not None:
        if body.role not in VALID_ROLES:
            raise HTTPException(400, f"role must be one of {sorted(VALID_ROLES)}")
        roles = _user_roles(db, user.id)
        scope = _manageable_university_ids(principal)
        relevant = [r for r in roles if scope is None or r.university_id in scope] or roles
        for r in relevant:
            r.role = body.role
    db.commit()
    return _serialize(db, user)


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, body: ResetPasswordRequest, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_admin(principal)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    _assert_can_manage(db, principal, user)
    user.password_hash = hash_password(body.new_password)
    db.commit()
    return {"status": "password_reset", "email": user.email}


@router.delete("/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), principal: Principal = Depends(get_principal)):
    _require_admin(principal)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    _assert_can_manage(db, principal, user)
    _assert_not_self_destructive(principal, user, "delete")
    if _is_active_super_admin(db, user) and _active_super_admin_count(db, exclude_user_id=user.id) == 0:
        raise HTTPException(
            409,
            "This is the last active Super Admin account and can't be deleted -- "
            "promote another account to Super Admin first.",
        )
    if db.scalar(select(Submission).where(Submission.owner_user_id == user.id)):
        raise HTTPException(
            409,
            "This account owns one or more submissions and can't be deleted outright "
            "(that would orphan audit history). Suspend the account instead.",
        )
    for r in _user_roles(db, user.id):
        db.delete(r)
    db.delete(user)
    db.commit()
    return {"status": "deleted", "id": user_id}
