
from fastapi import HTTPException
from sqlalchemy.orm import Session
from ..models import Submission
from .identity import Principal

# Roles that can see every submission within their own university (already
# enforced by the university_id check below) rather than only their own.
_BROAD_ACCESS_ROLES = {"research_officer", "university_admin"}


def _principal_user_id(principal: Principal) -> int | None:
    """The numeric database User.id, when the principal came from a real
    login (self-issued token's subject is str(user.id)). Returns None for
    dev-header or third-party-OIDC principals that don't map to a local
    account -- ownership checks then fail closed (deny) rather than guess."""
    try:
        return int(principal.subject)
    except (TypeError, ValueError):
        return None


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

    if principal.has_role(*_BROAD_ACCESS_ROLES):
        return

    if principal.has_role("student"):
        owner_id = _principal_user_id(principal)
        if owner_id is None or submission.owner_user_id != owner_id:
            raise HTTPException(403, "You can only access your own submissions.")

# Compatibility alias used by API modules.
require_submission_access = authorize_submission
