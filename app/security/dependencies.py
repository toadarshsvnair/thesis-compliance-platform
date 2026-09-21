from fastapi import Header, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .identity import Principal, principal_from_dev_headers, principal_from_jwt
from ..config import settings

bearer = HTTPBearer(auto_error=False)

def get_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    x_user_id: str | None = Header(default=None),
    x_user_email: str | None = Header(default=None),
    x_user_roles: str | None = Header(default=None),
    x_university_ids: str | None = Header(default=None),
) -> Principal:
    if settings.oidc_required or settings.environment.lower() in {"production", "staging"}:
        if not credentials:
            raise HTTPException(401, "Bearer authentication required.")
        try:
            principal = principal_from_jwt(credentials.credentials, settings.oidc_issuer, settings.oidc_audience, settings.oidc_jwks_url)
        except Exception:
            raise HTTPException(401, "Invalid authentication token.")
    else:
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
