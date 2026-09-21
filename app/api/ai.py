from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
import hashlib, json
from ..db import get_db
from ..models import Submission, DocumentVersion, Rule, Finding, AuditEvent
from ..security.dependencies import get_current_principal
from ..security.authorization import require_submission_access
from ..services.ai import get_provider, extract_semantic_evidence, build_prompt, validate_response, AI_PROMPT_VERSION
from ..services.audit import record_audit

router = APIRouter(prefix="/submissions/{submission_id}/ai", tags=["ai"])
AI_RULE_PREFIXES = ("AI-", "SEM-")


def ai_rules(db: Session, submission: Submission):
    rows = db.scalars(select(Rule).where(Rule.rule_set_id == submission.rule_set_id, Rule.active == True)).all()
    return [r for r in rows if r.rule_id.startswith(AI_RULE_PREFIXES) or "AI" in (r.validation_method or "").upper()]

@router.post("/analyze")
def analyze(submission_id: int, db: Session = Depends(get_db), principal=Depends(get_current_principal)):
    submission = db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(404, "Submission not found")
    require_submission_access(db, principal, submission)
    version = db.get(DocumentVersion, submission.current_version_id)
    if not version:
        raise HTTPException(409, "Submission has no current document version")
    rules = ai_rules(db, submission)
    if not rules:
        return {"status": "no_ai_rules", "findings_created": 0, "message": "No AI/semantic rules are active for this rule set."}
    evidence = extract_semantic_evidence(version.storage_path)
    allowed = {r.rule_id for r in rules}
    prompt = build_prompt(evidence, [{"rule_id": r.rule_id, "requirement": r.requirement, "severity": r.severity} for r in rules])
    provider = get_provider()
    try:
        findings, raw_response = provider.analyze(prompt, allowed)
    except Exception as exc:
        record_audit(db, submission.university_id, principal.subject, "ai_analysis_failed", "submission", str(submission.id), version.id, submission.rule_set_id, "failed", {"error": type(exc).__name__})
        db.commit()
        raise HTTPException(502, "AI analysis failed") from exc
    created = []
    for item in findings:
        f = Finding(submission_id=submission.id, document_version_id=version.id, rule_id=item["rule_id"], category="AI/Semantic", severity=item["severity"], location=item["location"], expected=item["expected"], actual=item["actual"], message=item["message"], confidence=item["confidence"], auto_fix_allowed=False, status="open", source_type="ai", ai_provider=provider.name, ai_model=provider.model, ai_prompt_version=AI_PROMPT_VERSION, ai_evidence=item.get("evidence"), requires_human_review=True)
        db.add(f); created.append(f)
    response_hash = hashlib.sha256(raw_response.encode("utf-8")).hexdigest()
    record_audit(db, submission.university_id, principal.subject, "ai_analysis_completed", "submission", str(submission.id), version.id, submission.rule_set_id, "success", {"provider": provider.name, "model": provider.model, "prompt_version": AI_PROMPT_VERSION, "input_sha256": evidence["input_sha256"], "response_sha256": response_hash, "findings_created": len(created)})
    db.commit()
    return {"status": "completed", "provider": provider.name, "model": provider.model, "prompt_version": AI_PROMPT_VERSION, "input_sha256": evidence["input_sha256"], "response_sha256": response_hash, "findings_created": len(created)}
