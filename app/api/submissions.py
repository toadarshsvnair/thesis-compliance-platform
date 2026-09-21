from pathlib import Path
import json
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Submission, DocumentVersion, Finding, RuleSet, ProcessingJob
from ..schemas import SubmissionOut
from ..config import settings
from ..services.storage import StorageService
from ..services.object_storage import ObjectStorage
from ..services.security import validate_magic, validate_docx_package, malware_scan
from ..services.audit import audit
from ..security.dependencies import get_principal, require_university_access
from ..security.authorization import authorize_submission

router = APIRouter(prefix="/submissions", tags=["submissions"])
storage = StorageService()
object_storage = ObjectStorage()


def _start_validation(db: Session, background_tasks: BackgroundTasks, university_id: int,
                       actor_id: str, submission_id: int, version_id: int, rule_set_id: int) -> str:
    """Queue validation via Redis+worker if configured, otherwise run it as an
    in-process background task. See app/services/inline_processing.py."""
    if settings.redis_url:
        from ..services.processing_queue import enqueue_validation
        job_id = enqueue_validation(db, submission_id, version_id)
        audit(db, university_id, actor_id, "VALIDATION_QUEUED", "processing_job", job_id,
              document_version_id=version_id, rule_set_id=rule_set_id, result="queued")
        return job_id
    from ..services.inline_processing import process_validation_job
    background_tasks.add_task(process_validation_job, submission_id, version_id)
    audit(db, university_id, actor_id, "VALIDATION_QUEUED", "processing_job", "inline",
          document_version_id=version_id, rule_set_id=rule_set_id, result="queued",
          metadata_json={"mode": "inline_background_task"})
    return "inline"


@router.get("", response_model=list[SubmissionOut])
def list_submissions(
    university_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    principal = Depends(get_principal),
):
    query = select(Submission)
    if principal.has_role("super_admin"):
        if university_id is not None:
            query = query.where(Submission.university_id == university_id)
    else:
        if not principal.university_ids:
            return []
        allowed = set(principal.university_ids)
        if university_id is not None:
            if university_id not in allowed:
                raise HTTPException(403, "University access denied.")
            allowed = {university_id}
        query = query.where(Submission.university_id.in_(allowed))
    if status:
        query = query.where(Submission.status == status)
    query = query.order_by(Submission.id.desc()).offset(max(offset, 0)).limit(max(1, min(limit, 200)))
    rows = db.scalars(query).all()
    out = []
    for s in rows:
        count = db.scalar(select(func.count()).select_from(Finding).where(Finding.submission_id == s.id)) or 0
        out.append(SubmissionOut(
            id=s.id, status=s.status, student_name=s.student_name,
            registration_number=s.registration_number,
            current_version_id=s.current_version_id, findings_count=count,
        ))
    return out


@router.post("", response_model=SubmissionOut)
def create_submission(
    background_tasks: BackgroundTasks,
    university_id: int = Form(...),
    faculty_id: int | None = Form(None),
    document_type_id: int | None = Form(None),
    rule_set_id: int = Form(...),
    student_name: str = Form(...),
    registration_number: str = Form(...),
    programme: str | None = Form(None),
    supervisor: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    principal = Depends(get_principal),
):
    require_university_access(principal, university_id)
    rule_set = db.get(RuleSet, rule_set_id)
    if not rule_set or rule_set.university_id != university_id:
        raise HTTPException(400, "Rule set does not belong to this university.")
    if rule_set.status != "published":
        raise HTTPException(409, "New submissions must use a published rule-set version.")
    if rule_set.faculty_id is not None and rule_set.faculty_id != faculty_id:
        raise HTTPException(400, "Rule set is not mapped to the selected faculty.")
    if rule_set.document_type_id is not None and rule_set.document_type_id != document_type_id:
        raise HTTPException(400, "Rule set is not mapped to the selected document type.")
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "Only DOCX uploads are supported.")
    submission = Submission(
        university_id=university_id,
        faculty_id=faculty_id,
        document_type_id=document_type_id,
        rule_set_id=rule_set_id,
        student_name=student_name,
        registration_number=registration_number,
        programme=programme,
        supervisor=supervisor,
        status="uploaded",
    )
    db.add(submission)
    db.flush()

    version = DocumentVersion(
        submission_id=submission.id,
        version_number=1,
        original_filename=file.filename,
        storage_path="pending",
        sha256="pending",
        mime_type=file.content_type,
        size_bytes=0,
    )
    db.add(version)
    db.flush()

    path, size, digest = storage.save_upload(file.file, submission.id, 1, file.filename)
    if not validate_magic(path):
        Path(path).unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(400, "Uploaded file is not a valid DOCX package.")
    try:
        package = validate_docx_package(path)
        scan = malware_scan(path)
    except Exception as exc:
        Path(path).unlink(missing_ok=True)
        db.rollback()
        raise HTTPException(400, str(exc))
    version.storage_path = path
    version.object_uri = object_storage.put_file(path, f"universities/{university_id}/submissions/{submission.id}/v1/{Path(path).name}")
    version.size_bytes = size
    version.sha256 = digest
    submission.current_version_id = version.id
    submission.status = "queued"

    audit(db, university_id, principal.subject, "UPLOAD", "submission", submission.id,
          document_version_id=version.id, rule_set_id=rule_set_id,
          metadata_json={"filename": file.filename, "sha256": digest, "scan": scan, "package": package})
    _start_validation(db, background_tasks, university_id, principal.subject,
                       submission.id, version.id, rule_set_id)
    db.commit()
    db.refresh(submission)

    return SubmissionOut(
        id=submission.id,
        status=submission.status,
        student_name=submission.student_name,
        registration_number=submission.registration_number,
        current_version_id=submission.current_version_id,
        findings_count=0,
    )

@router.get("/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: int, db: Session = Depends(get_db), principal = Depends(get_principal)):
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(404, "Submission not found")
    authorize_submission(db, principal, s)
    count = db.scalar(select(func.count()).select_from(Finding).where(Finding.submission_id == submission_id)) or 0
    return SubmissionOut(
        id=s.id, status=s.status, student_name=s.student_name,
        registration_number=s.registration_number,
        current_version_id=s.current_version_id, findings_count=count
    )

@router.get("/{submission_id}/findings")
def get_findings(submission_id: int, db: Session = Depends(get_db), principal = Depends(get_principal)):
    submission = db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(404, "Submission not found")
    authorize_submission(db, principal, submission)
    rows = db.scalars(select(Finding).where(Finding.submission_id == submission_id).order_by(Finding.id)).all()
    return [
        {"id": x.id, "rule_id": x.rule_id, "category": x.category, "severity": x.severity,
         "location": x.location, "expected": x.expected, "actual": x.actual,
         "message": x.message, "confidence": x.confidence, "source_reference": x.source_reference,
         "auto_fix_allowed": x.auto_fix_allowed, "status": x.status}
        for x in rows
    ]


@router.post("/{submission_id}/validate")
def validate_submission(submission_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db), principal = Depends(get_principal)):
    submission = db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(404, "Submission not found")
    authorize_submission(db, principal, submission)
    if not submission.current_version_id:
        raise HTTPException(409, "Submission has no document version")
    version = db.get(DocumentVersion, submission.current_version_id)
    if not version:
        raise HTTPException(404, "Current document version not found")
    submission.status = "queued"
    job_id = _start_validation(db, background_tasks, submission.university_id, principal.subject,
                                submission.id, version.id, submission.rule_set_id)
    db.commit()
    return {"submission_id": submission.id, "version_id": version.id, "status": submission.status, "job_id": job_id}
