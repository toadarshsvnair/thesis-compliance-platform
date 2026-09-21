from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from ..db import get_db
from ..config import settings
from ..models import University, RuleSet, User, UserRole
from ..security.dependencies import get_principal, get_principal_optional
from ..security.identity import Principal

router = APIRouter()

@router.get("/health")
def health():
    return {"status": "ok", "service": "thesis-compliance-api", "version": "1.0"}


@router.get("/dev/bootstrap")
def dev_bootstrap(db: Session = Depends(get_db)):
    """Returns the seeded demo university/rule-set IDs so a bare-bones upload
    form can discover what to submit against, without needing an admin UI.
    Only responds when DEMO_SEED is enabled — 404 otherwise, including in any
    real deployment that hasn't turned this on."""
    if not settings.demo_seed:
        raise HTTPException(404, "Not found")
    uni = db.scalar(select(University).order_by(University.id))
    if not uni:
        raise HTTPException(404, "No demo data seeded yet")
    rule_set = db.scalar(select(RuleSet).where(
        RuleSet.university_id == uni.id, RuleSet.status == "published"
    ).order_by(RuleSet.id))
    return {
        "university_id": uni.id,
        "university_name": uni.name,
        "rule_set_id": rule_set.id if rule_set else None,
        "rule_set_name": rule_set.name if rule_set else None,
    }


@router.get("/dev/list-users")
def list_users(db: Session = Depends(get_db)):
    """Demo-mode-only visibility into what accounts actually exist, so
    bootstrapping (promote-to-super-admin below) doesn't depend on
    remembering an email from earlier testing. Never returns password
    hashes, and never exists outside demo mode."""
    if not settings.demo_seed:
        raise HTTPException(404, "Not found")
    users = db.scalars(select(User).order_by(User.id)).all()
    out = []
    for u in users:
        roles = db.scalars(select(UserRole).where(UserRole.user_id == u.id)).all()
        out.append({
            "id": u.id, "email": u.email, "display_name": u.display_name, "active": u.active,
            "roles": [{"role": r.role, "university_id": r.university_id} for r in roles],
        })
    return out


@router.post("/dev/promote-to-super-admin")
def promote_to_super_admin(email: str, db: Session = Depends(get_db), principal: Principal | None = Depends(get_principal_optional)):
    """One-time bootstrap escape hatch: if a database somehow ends up with
    zero super_admins (e.g. an account created before registration was
    locked down to admin-only), this promotes one existing account -- but
    only while no super_admin exists yet, or when called by an existing one.
    Demo-mode-only."""
    if not settings.demo_seed:
        raise HTTPException(404, "Not found")
    any_super_admin = db.scalar(select(UserRole).where(UserRole.role == "super_admin"))
    if any_super_admin and not (principal and principal.has_role("super_admin")):
        raise HTTPException(403, "A Super Admin already exists; ask them to grant access instead.")
    user = db.scalar(select(User).where(User.email == email))
    if not user:
        raise HTTPException(404, "No account with that email exists yet.")
    if not db.scalar(select(UserRole).where(UserRole.user_id == user.id, UserRole.role == "super_admin")):
        db.add(UserRole(user_id=user.id, university_id=None, role="super_admin"))
        db.commit()
    return {"status": "promoted", "email": user.email}


@router.post("/dev/reset-submissions")
def reset_submissions(db: Session = Depends(get_db), principal=Depends(get_principal)):
    """Clears all submissions and everything derived from them (versions,
    findings, review actions, fix approvals, compliance decisions, processing
    jobs, audit events) -- but leaves users, universities, and rule sets
    untouched. Only available in demo mode, and only to an admin, since this
    is a real, irreversible bulk delete."""
    if not settings.demo_seed:
        raise HTTPException(404, "Not found")
    if not principal.has_role("university_admin", "super_admin"):
        raise HTTPException(403, "Requires a University Admin or Super Admin role.")
    tables = [
        "fix_approvals", "finding_reviews", "compliance_decisions",
        "processing_jobs", "findings", "document_versions", "submissions",
        "audit_events",
    ]
    db.execute(text(f"TRUNCATE TABLE {', '.join(tables)} RESTART IDENTITY CASCADE"))
    db.commit()
    return {"status": "cleared", "tables": tables}