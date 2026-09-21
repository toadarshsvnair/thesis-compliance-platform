import time
from collections import defaultdict
from threading import Lock
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from ..config import settings

class SimpleRateLimitMiddleware(BaseHTTPMiddleware):
    """Local limiter for development/single-instance deployments. Production should use gateway/Redis rate limiting."""
    def __init__(self, app, requests_per_minute: int | None = None):
        super().__init__(app); self.limit = requests_per_minute or settings.rate_limit_per_minute; self.events=defaultdict(list); self.lock=Lock()
    async def dispatch(self, request: Request, call_next):
        key=request.client.host if request.client else "unknown"; now=time.time()
        with self.lock:
            values=[t for t in self.events[key] if now-t<60]
            if len(values)>=self.limit: raise HTTPException(429,"Rate limit exceeded.")
            values.append(now); self.events[key]=values
        return await call_next(request)
