from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..config import settings
from ..models import University, RuleSet

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
