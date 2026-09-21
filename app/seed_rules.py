from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import RuleSet, Rule, University, User, UserRole
from .config import settings
from .security.passwords import hash_password

# Initial Alliance University PhD thesis MVP catalogue.
# This is intentionally a small seed; the full catalogue remains configurable
# through the university administration layer.
RULES = [
    ("PRE-001","Preliminary structure","Required preliminary sections exist","deterministic","Major",False,"Annexure 18/19"),
    ("PRE-013","Preliminary structure","Preliminary sections follow prescribed sequence","deterministic","Major",False,"Annexure 18"),
    ("PAGE-001","Page/Layout","A4 page size","deterministic","Major",True,"Annexure 19"),
    ("PAGE-002","Page/Layout","Left margin 1.5 inch","deterministic","Major",True,"Annexure 19"),
    ("PAGE-003","Page/Layout","Right margin 1 inch","deterministic","Major",True,"Annexure 19"),
    ("PAGE-004","Page/Layout","Top margin 1 inch","deterministic","Major",True,"Annexure 19"),
    ("PAGE-005","Page/Layout","Bottom margin 1 inch","deterministic","Major",True,"Annexure 19"),
    ("FONT-001","Typography","Times New Roman","deterministic","Major",True,"Annexure 19"),
    ("TITLE-001","Title","Prescribed title-page title formatting","deterministic","Major",True,"Annexure 19"),
    ("TAB-001","Tables","Chapter-wise table numbering","deterministic","Major",False,"Annexure 19"),
    ("TAB-003","Tables","Table caption style","deterministic","Major",True,"Annexure 19"),
    ("TAB-005","Tables/Cross-reference","Every table referenced in body","deterministic","Major",False,"Institutional rule"),
    ("FIG-001","Figures","Chapter-wise figure numbering","deterministic","Major",False,"Annexure 19"),
    ("FIG-003","Figures","Figure caption style","deterministic","Major",True,"Annexure 19"),
    ("FIG-004","Figures/Cross-reference","Every figure referenced in body","deterministic","Major",False,"Institutional rule"),
    ("XREF-002","Cross-reference","Broken figure references","deterministic","Major",False,"Institutional rule"),
    ("TOC-002","TOC","TOC page numbers correspond to rendered document","rendered","Major",True,"Annexure 19"),
    ("REF-002","References","Reference hanging indent and spacing","deterministic","Major",True,"Annexure 19"),
]
def seed(db: Session, university_id: int):
    rs = RuleSet(
        university_id=university_id,
        version="0.3-mvp",
        name="Alliance PhD Thesis MVP",
        status="published",
        source_metadata={"sources":["Annexure 18","Annexure 19"]},
    )
    db.add(rs)
    db.flush()
    for rid,cat,req,method,sev,fix,source in RULES:
        db.add(Rule(
            rule_set_id=rs.id, rule_id=rid, category=cat,
            requirement=req, validation_method=method,
            severity=sev, auto_fix_allowed=fix,
            source_reference=source,
        ))
    db.commit()
    return rs

def seed_demo_university_if_empty(db: Session) -> University | None:
    """Create one demo University + published rule set for a fresh, empty
    deployment (e.g. a lightweight/free hosting demo with no admin UI yet to
    configure this by hand). No-op if any University already exists.

    Guarded by the DEMO_SEED setting (see app/config.py) — never runs unless
    explicitly enabled, and is meant for disposable demo data only.
    """
    existing = db.scalar(select(University))
    if existing:
        return existing
    uni = University(name="Demo University", code="DEMO")
    db.add(uni)
    db.flush()
    seed(db, uni.id)
    return uni


def seed_demo_admin_if_configured(db: Session, university_id: int) -> None:
    """Creates exactly one Super Admin account so a fresh deployment isn't
    locked out: since account creation now always requires an existing admin
    (no open self-registration), a brand-new database has no admin to create
    anyone with. Only runs when DEMO_ADMIN_PASSWORD is explicitly set --
    render.yaml generates this as a real secret, never a hardcoded default,
    since this becomes a genuine working login. No-op once any user exists,
    so this never re-runs or resets the password on later restarts."""
    if not settings.demo_admin_password:
        return
    if db.scalar(select(User)):
        return
    user = User(
        external_subject=f"local:{settings.demo_admin_email}",
        email=settings.demo_admin_email,
        display_name="Demo Administrator",
        password_hash=hash_password(settings.demo_admin_password),
        active=True,
    )
    db.add(user)
    db.flush()
    db.add(UserRole(user_id=user.id, university_id=university_id, role="super_admin"))
    db.commit()


# v0.7 AI semantic rules (human-review only; no auto-fix)
AI_SEMANTIC_RULES = [
    ("AI-001", "Semantic", "Check that headings and section labels follow the configured institutional sequence where deterministic matching is ambiguous.", "AI-assisted", "Review", False),
    ("AI-002", "Citations", "Check that citation-like in-text references have a plausible corresponding entry in the reference evidence supplied to the model.", "AI-assisted", "Review", False),
    ("AI-003", "References", "Check for semantically ambiguous reference-list entries that cannot be resolved reliably by deterministic parsing.", "AI-assisted", "Review", False),
    ("AI-004", "Abbreviations", "Check for potentially undefined or inconsistently expanded abbreviations when deterministic matching is insufficient.", "AI-assisted", "Review", False),
]
