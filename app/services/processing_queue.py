from ..models import ProcessingJob
from .queue import JobQueue
from sqlalchemy.orm import Session
from uuid import uuid4


def enqueue_validation(db: Session, submission_id: int, version_id: int) -> str:
    job_id = str(uuid4())
    db.add(ProcessingJob(job_id=job_id, submission_id=submission_id, version_id=version_id, job_type="validation", status="queued"))
    db.flush()
    JobQueue().enqueue("validation", {"job_id": job_id, "submission_id": submission_id, "version_id": version_id})
    return job_id
