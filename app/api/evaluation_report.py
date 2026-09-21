from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Submission
from ..services.evaluation_report import build_evaluation_report
from ..security.dependencies import get_principal
from ..security.authorization import authorize_submission

router = APIRouter(prefix='/submissions', tags=['evaluation-report'])


@router.get('/{submission_id}/evaluation-report')
def download_evaluation_report(submission_id: int, db: Session = Depends(get_db), principal=Depends(get_principal)):
    """Unlike the certificate, this is available at any point -- compliant,
    returned, or not yet decided -- since it documents the evaluation itself
    rather than certifying an outcome."""
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(404, 'Submission not found')
    authorize_submission(db, principal, s)
    try:
        path, report_id = build_evaluation_report(db, s)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return FileResponse(path, filename=f'{report_id}.pdf', media_type='application/pdf')
