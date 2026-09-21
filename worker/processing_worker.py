import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import SessionLocal
from app.models import Submission, DocumentVersion, ProcessingJob
from app.services.queue import JobQueue
from app.services.processing import ProcessingService
from app.services.audit import audit
from app.services.observability import PROCESSING


def main():
    queue = JobQueue()
    print("processing worker started", flush=True)
    while True:
        job = queue.dequeue(timeout=10)
        if not job:
            continue
        db = SessionLocal()
        record = None
        try:
            payload = job["payload"]
            record = db.query(ProcessingJob).filter_by(job_id=payload["job_id"]).one_or_none()
            if record:
                record.status = "processing"
                db.commit()
            submission = db.get(Submission, int(payload["submission_id"]))
            version = db.get(DocumentVersion, int(payload["version_id"]))
            if not submission or not version or submission.current_version_id != version.id:
                raise RuntimeError("Queued validation references an invalid or stale document version.")
            submission.status = "processing"
            audit(db, submission.university_id, "processing-worker", "VALIDATION_STARTED", "submission", submission.id,
                  document_version_id=version.id, rule_set_id=submission.rule_set_id, result="processing")
            db.commit()
            result = ProcessingService().validate(db, submission, version)
            audit(db, submission.university_id, "processing-worker", "VALIDATION_COMPLETED", "submission", submission.id,
                  document_version_id=version.id, rule_set_id=submission.rule_set_id, result="completed",
                  metadata_json={"finding_count": len(result.get("findings", []))})
            if record:
                record.status = "completed"
                db.commit()
            PROCESSING.labels(job["job_type"], "completed").inc()
        except Exception as exc:
            if record:
                record.status = "failed"
                record.error = type(exc).__name__
            if 'submission' in locals() and submission:
                submission.status = "validation_failed"
                audit(db, submission.university_id, "processing-worker", "VALIDATION_FAILED", "submission", submission.id,
                      document_version_id=getattr(version, "id", None), rule_set_id=submission.rule_set_id,
                      result="failed", metadata_json={"error_type": type(exc).__name__})
            db.commit()
            PROCESSING.labels(job.get("job_type", "unknown"), "failed").inc()
        finally:
            db.close()

if __name__ == "__main__":
    main()
