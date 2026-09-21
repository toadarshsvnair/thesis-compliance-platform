
from fastapi import HTTPException
from sqlalchemy.orm import Session
from ..models import Submission
from .identity import Principal

def authorize_submission(
    db: Session,
    principal: Principal,
    submission: Submission,
):
    """
    Object-level authorization.

    Every endpoint that receives a submission ID must call this before
    returning or modifying submission data.
    """
    if principal.has_role("super_admin"):
        return

    if submission.university_id not in principal.university_ids:
        raise HTTPException(403, "Submission belongs to another university.")

    # Students can only access their own submission when the application
    # has mapped the authenticated subject to the submission owner.
    # v0.4 keeps that mapping explicit rather than guessing identity.
    if principal.has_role("student"):
        raise HTTPException(
            403,
            "Student ownership mapping is not configured for this submission."
        )

# Compatibility alias used by API modules.
require_submission_access = authorize_submission
