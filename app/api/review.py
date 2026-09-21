from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Submission, DocumentVersion, Finding, AuditEvent, FindingReview, ComplianceDecision
from ..schemas_review import FindingReviewRequest, ComplianceDecisionRequest
from ..services.audit import audit
from ..services.review import compare_versions
from ..services.autofix import SAFE_AUTO_FIX_RULES
from ..security.dependencies import get_principal
from ..security.authorization import authorize_submission

router = APIRouter(prefix="/submissions", tags=["review"])

REVIEW_ROLES = {"research_officer", "university_admin", "super_admin"}


def require_review_role(principal):
    if not principal.has_role(*REVIEW_ROLES):
        raise HTTPException(403, "Human review requires Research Officer, University Admin, or Super Admin role.")


def get_submission(db, submission_id, principal):
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(404, "Submission not found")
    authorize_submission(db, principal, s)
    return s


@router.get("/{submission_id}/review-summary")
def review_summary(submission_id: int, db: Session = Depends(get_db), principal=Depends(get_principal)):
    s = get_submission(db, submission_id, principal)
    current = db.get(DocumentVersion, s.current_version_id) if s.current_version_id else None
    findings = db.scalars(select(Finding).where(
        Finding.submission_id == s.id,
        Finding.document_version_id == current.id if current else False
    ).order_by(Finding.id)).all() if current else []
    counts = {}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    fixable = sum(
        1 for f in findings
        if f.auto_fix_allowed and f.status == "open" and f.rule_id in SAFE_AUTO_FIX_RULES
    )
    decisions = db.scalars(select(ComplianceDecision).where(
        ComplianceDecision.submission_id == s.id
    ).order_by(ComplianceDecision.created_at.desc())).all()
    latest_decision = decisions[0] if decisions else None
    return {
        "submission": {
            "id": s.id,
            "student_name": s.student_name,
            "registration_number": s.registration_number,
            "programme": s.programme,
            "supervisor": s.supervisor,
            "status": s.status,
            "current_version_id": s.current_version_id,
        },
        "current_version": None if not current else {
            "id": current.id,
            "version_number": current.version_number,
            "filename": current.original_filename,
            "sha256": current.sha256,
            "created_by": current.created_by,
            "created_at": current.created_at,
            "change_summary": current.change_summary,
            "parent_version_id": current.parent_version_id,
        },
        "finding_counts": counts,
        "total_findings": len(findings),
        "fixable_open_findings": fixable,
        "latest_compliance_decision": None if not latest_decision else {
            "decision": latest_decision.decision,
            "comment": latest_decision.comment,
            "actor_id": latest_decision.actor_id,
            "created_at": latest_decision.created_at,
        },
    }


@router.get("/{submission_id}/versions")
def versions(submission_id: int, db: Session = Depends(get_db), principal=Depends(get_principal)):
    s = get_submission(db, submission_id, principal)
    rows = db.scalars(select(DocumentVersion).where(
        DocumentVersion.submission_id == s.id
    ).order_by(DocumentVersion.version_number)).all()
    return [{
        "id": v.id,
        "version_number": v.version_number,
        "filename": v.original_filename,
        "sha256": v.sha256,
        "size_bytes": v.size_bytes,
        "parent_version_id": v.parent_version_id,
        "change_summary": v.change_summary,
        "created_by": v.created_by,
        "created_at": v.created_at,
        "is_current": v.id == s.current_version_id,
    } for v in rows]


@router.get("/{submission_id}/versions/{version_id}/findings")
def version_findings(submission_id: int, version_id: int, db: Session = Depends(get_db), principal=Depends(get_principal)):
    s = get_submission(db, submission_id, principal)
    v = db.get(DocumentVersion, version_id)
    if not v or v.submission_id != s.id:
        raise HTTPException(404, "Document version not found")
    rows = db.scalars(select(Finding).where(
        Finding.submission_id == s.id,
        Finding.document_version_id == v.id
    ).order_by(Finding.id)).all()
    return [{
        "id": f.id, "rule_id": f.rule_id, "category": f.category,
        "severity": f.severity, "location": f.location,
        "expected": f.expected, "actual": f.actual,
        "message": f.message, "confidence": f.confidence,
        "auto_fix_allowed": f.auto_fix_allowed, "status": f.status,
    } for f in rows]


@router.get("/{submission_id}/versions/{source_version_id}/compare/{target_version_id}")
def compare(submission_id: int, source_version_id: int, target_version_id: int, db: Session = Depends(get_db), principal=Depends(get_principal)):
    s = get_submission(db, submission_id, principal)
    source = db.get(DocumentVersion, source_version_id)
    target = db.get(DocumentVersion, target_version_id)
    if not source or not target or source.submission_id != s.id or target.submission_id != s.id:
        raise HTTPException(404, "Document version not found")
    return compare_versions(source, target)


@router.get("/{submission_id}/versions/{version_id}/download")
def download_version(submission_id: int, version_id: int, db: Session = Depends(get_db), principal=Depends(get_principal)):
    s = get_submission(db, submission_id, principal)
    v = db.get(DocumentVersion, version_id)
    if not v or v.submission_id != s.id:
        raise HTTPException(404, "Document version not found")
    path = Path(v.storage_path)
    if not path.is_file():
        raise HTTPException(404, "Stored document not found")
    return FileResponse(path, filename=f"v{v.version_number}_{v.original_filename}", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@router.get("/{submission_id}/audit")
def audit_trail(submission_id: int, db: Session = Depends(get_db), principal=Depends(get_principal)):
    s = get_submission(db, submission_id, principal)
    rows = db.scalars(select(AuditEvent).where(
        AuditEvent.university_id == s.university_id,
        AuditEvent.resource_type.in_(["submission", "document_version"]),
        ((AuditEvent.resource_type == "submission") & (AuditEvent.resource_id == str(s.id))) |
        ((AuditEvent.resource_type == "document_version") & (AuditEvent.document_version_id.in_(
            select(DocumentVersion.id).where(DocumentVersion.submission_id == s.id)
        )))
    ).order_by(AuditEvent.id)).all()
    return [{
        "id": e.id, "actor_id": e.actor_id, "action": e.action,
        "resource_type": e.resource_type, "resource_id": e.resource_id,
        "document_version_id": e.document_version_id,
        "result": e.result, "metadata": e.metadata_json,
        "previous_hash": e.previous_hash, "event_hash": e.event_hash,
        "created_at": e.created_at,
    } for e in rows]


@router.post("/{submission_id}/findings/{finding_id}/review")
def review_finding(submission_id: int, finding_id: int, request: FindingReviewRequest, db: Session = Depends(get_db), principal=Depends(get_principal)):
    require_review_role(principal)
    s = get_submission(db, submission_id, principal)
    f = db.get(Finding, finding_id)
    if not f or f.submission_id != s.id:
        raise HTTPException(404, "Finding not found")
    if f.document_version_id != s.current_version_id:
        raise HTTPException(409, "Only findings on the current document version can be reviewed.")
    if request.action == "reviewed":
        f.status = "reviewed"
    elif request.action == "rejected":
        f.status = "rejected"
    elif request.action == "waived":
        f.status = "waived"
    db.add(FindingReview(
        submission_id=s.id, finding_id=f.id, document_version_id=f.document_version_id,
        actor_id=principal.subject, action=request.action, comment=request.comment,
    ))
    audit(db, s.university_id, principal.subject, "FINDING_REVIEWED", "submission", s.id,
          document_version_id=f.document_version_id, rule_set_id=s.rule_set_id,
          result=request.action, metadata_json={"finding_id": f.id, "rule_id": f.rule_id, "comment": request.comment})
    db.commit()
    return {"finding_id": f.id, "status": f.status}


@router.post("/{submission_id}/review/decision")
def compliance_decision(submission_id: int, request: ComplianceDecisionRequest, db: Session = Depends(get_db), principal=Depends(get_principal)):
    require_review_role(principal)
    s = get_submission(db, submission_id, principal)
    if not s.current_version_id:
        raise HTTPException(409, "Submission has no current version")
    # This endpoint records the human decision; it deliberately does not infer or replace it.
    decision = ComplianceDecision(
        submission_id=s.id, document_version_id=s.current_version_id,
        actor_id=principal.subject, decision=request.decision, comment=request.comment,
    )
    db.add(decision)
    s.status = "compliant" if request.decision == "compliant" else "returned"
    audit(db, s.university_id, principal.subject, "COMPLIANCE_DECISION", "submission", s.id,
          document_version_id=s.current_version_id, rule_set_id=s.rule_set_id,
          result=request.decision, metadata_json={"comment": request.comment})
    db.commit()
    return {"submission_id": s.id, "version_id": s.current_version_id, "decision": request.decision, "status": s.status}
