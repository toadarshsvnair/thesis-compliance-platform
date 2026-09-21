from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# The lightweight /review dashboard (frontend/index.html) is a small
# self-contained page that relies on an inline <style> block, an inline
# <script> block, and onclick="..." attribute handlers to work at all. A
# strict CSP without 'unsafe-inline' silently blocks every one of those in a
# standards-compliant browser -- not just the visual styling but the actual
# JavaScript, which is why buttons stop working. Relax the policy only for
# that one HTML page; every JSON API response keeps the strict default below.
_RELAXED_CSP_PATHS = {"/review"}

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        if request.url.path in _RELAXED_CSP_PATHS:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                "script-src 'self' 'unsafe-inline'; frame-ancestors 'none'; base-uri 'self'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; frame-ancestors 'none'; base-uri 'self'"
            )
        return response