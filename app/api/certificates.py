from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import Submission
from ..services.certificate import build_certificate
from ..security.dependencies import get_principal
from ..security.authorization import authorize_submission

router = APIRouter(prefix='/submissions', tags=['certificates'])

@router.post('/{submission_id}/certificate')
def generate_certificate(submission_id: int, db: Session = Depends(get_db), principal=Depends(get_principal)):
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(404, 'Submission not found')
    authorize_submission(db, principal, s)
    if not principal.has_role('research_officer','university_admin','super_admin'):
        raise HTTPException(403, 'Certificate generation requires an authorized review role.')
    try:
        path, cert_id = build_certificate(db, s)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return {'certificate_id': cert_id, 'download_url': f'/api/submissions/{submission_id}/certificate/download', 'version_id': s.current_version_id}

@router.get('/{submission_id}/certificate/download')
def download_certificate(submission_id: int, db: Session = Depends(get_db), principal=Depends(get_principal)):
    s = db.get(Submission, submission_id)
    if not s:
        raise HTTPException(404, 'Submission not found')
    authorize_submission(db, principal, s)
    try:
        path, cert_id = build_certificate(db, s)
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return FileResponse(path, filename=f'{cert_id}.pdf', media_type='application/pdf')
