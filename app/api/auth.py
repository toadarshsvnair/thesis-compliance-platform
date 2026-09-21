"""Real username/password authentication.

Replaces the dev-header placeholder for anyone who logs in through here: this
issues a genuinely signed token (see app/security/identity.py) backed by a
hashed password stored in the database, not a client-side role picker. It is
deliberately NOT the OIDC/OAuth2 integration the handoff docs describe for a
university SSO rollout -- that's a separate, larger piece of work requiring an
actual identity provider account. This is the practical middle ground: no
external service to configure, real credentials, real verification.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..config import settings
from ..models import User, UserRole
from ..security.identity import Principal, issue_self_signed_token
from ..security.passwords import hash_password, verify_password
from ..security.dependencies import get_principal_optional

router = APIRouter(prefix="/auth", tags=["auth"])

VALID_ROLES = {"student", "research_officer", "university_admin", "super_admin"}

# A plain, deliberately permissive stdlib regex rather than Pydantic's EmailStr,
# which needs the separate `email-validator` package -- not in requirements.txt,
# and this sandbox has no way to verify a new pip dependency installs cleanly
# before it ships. This one check is a shape check, not full RFC validation;
# login itself is the real verification (a malformed address just won't match
# a real account).
_EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterRequest(BaseModel):
    email: str = Field(pattern=_EMAIL_RE, max_length=320)
    password: str = Field(min_length=8, max_length=200)
    display_name: str = Field(min_length=1, max_length=250)
    role: str
    university_id: int

    @field_validator("email")
    @classmethod
    def _lowercase_email(cls, v: str) -> str:
        return v.strip().lower()


class LoginRequest(BaseModel):
    email: str = Field(pattern=_EMAIL_RE, max_length=320)
    password: str = Field(min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def _lowercase_email(cls, v: str) -> str:
        return v.strip().lower()


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def _user_roles_and_universities(db: Session, user: User) -> tuple[list[str], list[int]]:
    rows = db.scalars(select(UserRole).where(UserRole.user_id == user.id)).all()
    roles = sorted({r.role for r in rows})
    universities = sorted({r.university_id for r in rows if r.university_id is not None})
    return roles, universities


@router.post("/register", response_model=AuthResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db), principal: Principal | None = Depends(get_principal_optional)):
    if body.role not in VALID_ROLES:
        raise HTTPException(400, f"role must be one of {sorted(VALID_ROLES)}")
    if not settings.demo_seed:
        # Outside demo mode, only an existing admin can create accounts for
        # others -- open self-registration is a demo-only convenience.
        if not principal or not principal.has_role("university_admin", "super_admin"):
            raise HTTPException(
                403,
                "Account creation requires an existing University Admin or Super Admin outside of demo mode.",
            )
    if db.scalar(select(User).where(User.email == body.email)):
        raise HTTPException(409, "An account with this email already exists.")

    user = User(
        external_subject=f"local:{body.email}",
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, university_id=body.university_id, role=body.role))
    db.commit()

    token = issue_self_signed_token(settings.secret_key, str(user.id), user.email, [body.role], [body.university_id])
    return AuthResponse(access_token=token, user={
        "id": user.id, "email": user.email, "display_name": user.display_name,
        "roles": [body.role], "university_ids": [body.university_id],
    })


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email))
    # Deliberately identical error for "no such user" and "wrong password" --
    # distinguishing them lets an attacker enumerate which emails have
    # accounts.
    if not user or not user.active or not user.password_hash or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Incorrect email or password.")
    roles, universities = _user_roles_and_universities(db, user)
    if not roles:
        raise HTTPException(403, "This account has no assigned role. Contact a University Admin.")
    token = issue_self_signed_token(settings.secret_key, str(user.id), user.email, roles, universities)
    return AuthResponse(access_token=token, user={
        "id": user.id, "email": user.email, "display_name": user.display_name,
        "roles": roles, "university_ids": universities,
    })


@router.get("/me")
def me(db: Session = Depends(get_db), principal: Principal | None = Depends(get_principal_optional)):
    if not principal:
        raise HTTPException(401, "Not authenticated.")
    return {
        "subject": principal.subject, "email": principal.email,
        "roles": sorted(principal.roles), "university_ids": sorted(principal.university_ids),
    }
