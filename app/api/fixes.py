from pathlib import Path
from tempfile import NamedTemporaryFile
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Submission, DocumentVersion, Finding, FixApproval
from ..schemas import FixRequest, FixPreviewOut, FixPreviewItem, FixApplyOut
from ..security.dependencies import get_principal
from ..security.authorization import authorize_submission
from ..services.autofix import SAFE_AUTO_FIX_RULES, apply_safe_fixes
from ..services.audit import audit
from ..services.processing import ProcessingService

router = APIRouter(prefix="/submissions", tags=["controlled-auto-fix"])

ALLOWED_ROLES = ("research_officer", "university_admin", "super_admin")

def _require_fix_role(principal):
    if not principal.has_role(*ALLOWED_ROLES):
        raise HTTPException(403, "Only Research Officer, University Admin, or Super Admin can approve fixes.")

def _current_submission(db, submission_id, principal):
    submission = db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(404, "Submission not found")
    authorize_submission(db, principal, submission)
    if not submission.current_version_id:
        raise HTTPException(409, "Submission has no current document version")
    version = db.get(DocumentVersion, submission.current_version_id)
    if not version:
        raise HTTPException(404, "Current document version not found")
    return submission, version

@router.get("/{submission_id}/fixable-findings")
def list_fixable_findings(submission_id: int, db: Session = Depends(get_db), principal = Depends(get_principal)):
    submission, version = _current_submission(db, submission_id, principal)
    rows = db.scalars(select(Finding).where(
        Finding.submission_id == submission.id,
        Finding.document_version_id == version.id,
        Finding.status == "open",
        Finding.auto_fix_allowed.is_(True),
        Finding.rule_id.in_(list(SAFE_AUTO_FIX_RULES.keys())),
    ).order_by(Finding.id)).all()
    return [{
        "id": x.id, "rule_id": x.rule_id, "location": x.location,
        "expected": x.expected, "actual": x.actual, "message": x.message,
        "operation": SAFE_AUTO_FIX_RULES[x.rule_id]
    } for x in rows]

@router.post("/{submission_id}/fixes/preview", response_model=FixPreviewOut)
def preview_fixes(submission_id: int, request: FixRequest, db: Session = Depends(get_db), principal = Depends(get_principal)):
    _require_fix_role(principal)
    submission, version = _current_submission(db, submission_id, principal)
    rows = db.scalars(select(Finding).where(
        Finding.submission_id == submission.id,
        Finding.document_version_id == version.id,
        Finding.id.in_(request.finding_ids)
    )).all()
    found_ids = {x.id for x in rows}
    missing = sorted(set(request.finding_ids) - found_ids)
    if missing:
        raise HTTPException(404, f"Finding(s) not found on current version: {missing}")
    items = []
    blocked = []
    for f in rows:
        if f.rule_id not in SAFE_AUTO_FIX_RULES or not f.auto_fix_allowed or f.status != "open":
            blocked.append(f.id)
            continue
        items.append(FixPreviewItem(
            finding_id=f.id, rule_id=f.rule_id, location=f.location,
            operation=SAFE_AUTO_FIX_RULES[f.rule_id],
            risk_note="Formatting-only allow-listed fix; visible document text is verified unchanged before version creation."
        ))
    return FixPreviewOut(submission_id=submission.id, source_version_id=version.id, items=items, blocked_finding_ids=blocked)

@router.post("/{submission_id}/fixes/apply", response_model=FixApplyOut)
def apply_fixes(submission_id: int, request: FixRequest, db: Session = Depends(get_db), principal = Depends(get_principal)):
    _require_fix_role(principal)
    submission, version = _current_submission(db, submission_id, principal)
    if not request.confirm:
        raise HTTPException(400, "Explicit confirmation is required to apply approved fixes.")

    # Lock the submission row on PostgreSQL so two fix operations cannot create
    # competing child versions from the same current version.
    locked = db.execute(select(Submission).where(Submission.id == submission.id).with_for_update()).scalar_one()
    if locked.current_version_id != version.id:
        raise HTTPException(409, "The submission changed while this fix request was prepared. Refresh findings and retry.")

    rows = db.scalars(select(Finding).where(
        Finding.submission_id == submission.id,
        Finding.document_version_id == version.id,
        Finding.id.in_(request.finding_ids)
    )).all()
    by_id = {x.id: x for x in rows}
    missing = sorted(set(request.finding_ids) - set(by_id))
    if missing:
        raise HTTPException(404, f"Finding(s) not found on current version: {missing}")
    blocked = [f.id for f in rows if f.rule_id not in SAFE_AUTO_FIX_RULES or not f.auto_fix_allowed or f.status != "open"]
    if blocked:
        raise HTTPException(400, f"Finding(s) are not eligible for controlled auto-fix: {blocked}")

    next_version = (db.scalar(select(func.max(DocumentVersion.version_number)).where(
        DocumentVersion.submission_id == submission.id
    )) or 0) + 1
    target_dir = Path(version.storage_path).parent
    target_path = target_dir / f"v{next_version}_{Path(version.original_filename).name}"

    try:
        result = apply_safe_fixes(version.storage_path, str(target_path), [f.rule_id for f in rows])
        new_version = DocumentVersion(
            submission_id=submission.id,
            version_number=next_version,
            original_filename=version.original_filename,
            storage_path=str(target_path),
            sha256=result["sha256"],
            mime_type=version.mime_type,
            size_bytes=target_path.stat().st_size,
            parent_version_id=version.id,
            change_summary="Controlled formatting fixes: " + ", ".join(result["operations"]),
            created_by=principal.subject,
        )
        db.add(new_version)
        db.flush()
        submission.current_version_id = new_version.id
        submission.status = "processing"

        for f in rows:
            f.status = "fix_approved"
            db.add(FixApproval(
                submission_id=submission.id,
                finding_id=f.id,
                source_version_id=version.id,
                target_version_id=new_version.id,
                actor_id=principal.subject,
                action="apply",
                status="applied",
            ))

        audit(db, submission.university_id, principal.subject, "FIX_APPROVED",
              "submission", submission.id, document_version_id=version.id,
              rule_set_id=submission.rule_set_id,
              result="approved",
              metadata_json={"finding_ids": request.finding_ids, "rules": [f.rule_id for f in rows]})
        audit(db, submission.university_id, principal.subject, "VERSION_CREATED",
              "document_version", new_version.id, document_version_id=new_version.id,
              rule_set_id=submission.rule_set_id,
              result="created",
              metadata_json={"parent_version_id": version.id, "sha256": new_version.sha256, "change_summary": new_version.change_summary})
        db.commit()

        # Revalidation is deliberately automatic, but it is performed against the
        # newly-created immutable version only. The source version is untouched.
        try:
            result_validation = ProcessingService().validate(db, submission, new_version)
            db.commit()
        except Exception as exc:
            submission.status = "validation_failed"
            audit(db, submission.university_id, principal.subject, "FIX_REVALIDATION_FAILED",
                  "document_version", new_version.id, document_version_id=new_version.id,
                  rule_set_id=submission.rule_set_id, result="failed",
                  metadata_json={"error_type": type(exc).__name__, "source_version_id": version.id})
            db.commit()
            raise HTTPException(500, f"Fix was versioned, but revalidation failed ({type(exc).__name__}: {exc}); the new version was retained for review.")

        new_rules = {x.rule_id for x in db.scalars(select(Finding).where(
            Finding.document_version_id == new_version.id,
            Finding.submission_id == submission.id,
        )).all()}
        for f in rows:
            f.status = "revalidation_failed" if f.rule_id in new_rules else "fixed"
        db.commit()

        audit(db, submission.university_id, principal.subject, "FIX_REVALIDATED",
              "document_version", new_version.id, document_version_id=new_version.id,
              rule_set_id=submission.rule_set_id,
              result="completed",
              metadata_json={"source_version_id": version.id, "finding_count": len(result_validation.get("findings", []))})
        db.commit()

        return FixApplyOut(
            submission_id=submission.id,
            source_version_id=version.id,
            target_version_id=new_version.id,
            target_version_number=new_version.version_number,
            applied_finding_ids=request.finding_ids,
            revalidation_finding_count=len(result_validation.get("findings", [])),
            revalidation_status="completed",
        )
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        target_path.unlink(missing_ok=True)
        audit(db, submission.university_id, principal.subject, "FIX_FAILED",
              "submission", submission.id, document_version_id=version.id,
              rule_set_id=submission.rule_set_id,
              result="failed", metadata_json={"error_type": type(exc).__name__})
        db.commit()
        raise HTTPException(500, f"Controlled auto-fix failed ({type(exc).__name__}: {exc}); original version was retained.")
