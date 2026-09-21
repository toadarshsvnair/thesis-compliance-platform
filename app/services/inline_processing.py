"""Run validation in-process, without Redis or a separate worker.

Used when REDIS_URL is not configured (e.g. a free/lightweight deployment with a
single web service). Mirrors worker/processing_worker.py's logic exactly, but
runs as a FastAPI BackgroundTask inside the API process instead of a separate
worker process pulling from a queue.

This is a deliberate simplification for low-traffic demo use, not a replacement
for the queue+worker architecture: a single slow validation job here occupies a
worker thread of the same process serving other requests. Re-introduce
REDIS_URL + worker/processing_worker.py (already unmodified and ready to use)
once real concurrent load matters.
"""
from .processing import ProcessingService
from .audit import audit


def process_validation_job(submission_id: int, version_id: int) -> None:
    from ..db import SessionLocal
    from ..models import Submission, DocumentVersion

    db = SessionLocal()
    submission = None
    version = None
    try:
        submission = db.get(Submission, submission_id)
        version = db.get(DocumentVersion, version_id)
        if not submission or not version or submission.current_version_id != version.id:
            return
        submission.status = "processing"
        audit(db, submission.university_id, "inline-processor", "VALIDATION_STARTED", "submission", submission.id,
              document_version_id=version.id, rule_set_id=submission.rule_set_id, result="processing")
        db.commit()

        result = ProcessingService().validate(db, submission, version)

        audit(db, submission.university_id, "inline-processor", "VALIDATION_COMPLETED", "submission", submission.id,
              document_version_id=version.id, rule_set_id=submission.rule_set_id, result="completed",
              metadata_json={"finding_count": len(result.get("findings", []))})
        db.commit()
    except Exception as exc:
        db.rollback()
        if submission is not None:
            submission.status = "validation_failed"
            audit(db, submission.university_id, "inline-processor", "VALIDATION_FAILED", "submission", submission.id,
                  document_version_id=getattr(version, "id", None), rule_set_id=submission.rule_set_id,
                  result="failed", metadata_json={"error_type": type(exc).__name__})
            db.commit()
    finally:
        db.close()
