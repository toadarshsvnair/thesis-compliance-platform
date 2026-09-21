from fastapi import Header, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .identity import Principal, principal_from_dev_headers, principal_from_jwt, principal_from_self_issued_jwt
from ..config import settings

bearer = HTTPBearer(auto_error=False)

def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    x_user_roles: str | None = Header(default=None),
    x_university_ids: str | None = Header(default=None),
) -> Principal:
    if credentials:
        # Real, self-issued login (POST /api/auth/login) takes precedence
        # whenever a bearer token is presented, in every environment -- this
        # is genuine authentication, not the dev-header placeholder, and
        # should work whether or not a third-party OIDC provider is also
        # configured.
        try:
            return principal_from_self_issued_jwt(credentials.credentials, settings.secret_key)
        except Exception:
            pass
        try:
            principal = principal_from_jwt(credentials.credentials, settings.oidc_issuer, settings.oidc_audience, settings.oidc_jwks_url)
            if not principal.roles:
                raise HTTPException(401, "Authentication required.")
            return principal
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(401, "Invalid authentication token.")
    if settings.oidc_required or settings.environment.lower() in {"production", "staging"}:
        raise HTTPException(401, "Bearer authentication required.")
    principal = principal_from_dev_headers(x_user_id, x_user_email, x_user_roles, x_university_ids)
    if not principal.roles:
        raise HTTPException(401, "Authentication required.")
    return principal

def require_role(*roles: str):
    def dependency(principal: Principal = Depends(get_principal)):
        if not principal.has_role(*roles): raise HTTPException(403, "Insufficient privileges.")
        return principal
    return dependency

def require_university_access(principal: Principal, university_id: int):
    if principal.has_role("super_admin"): return
    if university_id not in principal.university_ids: raise HTTPException(403, "University access denied.")

get_current_principal = get_principal


def get_principal_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> Principal | None:
    """Like get_principal, but returns None instead of raising when there's no
    credential at all -- used only by /api/auth/register, which needs to
    allow an unauthenticated caller in demo mode."""
    if not credentials:
        return None
    try:
        return get_principal(credentials=credentials, x_user_id=None, x_user_email=None, x_user_roles=None, x_university_ids=None)
    except HTTPException:
        return None
