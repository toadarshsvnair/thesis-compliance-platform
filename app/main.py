from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import Request
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
import logging
from .db import Base, engine
from .api.health import router as health_router
from .api.submissions import router as submissions_router
from .api.fixes import router as fixes_router
from .api.review import router as review_router
from .api.ai import router as ai_router
from .api.rules import router as rules_router
from .api.universities import router as universities_router
from .api.auth import router as auth_router
from .api.admin_users import router as admin_users_router
from .security.headers import SecurityHeadersMiddleware
from .security.rate_limit import SimpleRateLimitMiddleware
from .security.middleware import RequestSecurityMiddleware
from .config import settings
from .services.observability import instrument
from .api.metrics import router as metrics_router
from .api.certificates import router as certificates_router
from .api.evaluation_report import router as evaluation_report_router

app=FastAPI(title="Thesis Compliance Platform",version="1.1.0",description="Security-hardened university thesis compliance backend.")
origins=[x.strip() for x in settings.allowed_origins.split(",") if x.strip()]
hosts=[x.strip() for x in settings.allowed_hosts.split(",") if x.strip()]
if settings.environment.lower() in {"production","staging"} and not origins:
    raise RuntimeError("ALLOWED_ORIGINS must be configured outside development.")
app.add_middleware(TrustedHostMiddleware, allowed_hosts=hosts or ["*"])
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET","POST","PUT","PATCH","DELETE","OPTIONS"], allow_headers=["Authorization","Content-Type","X-Request-ID","X-User-Id","X-User-Email","X-User-Roles","X-University-Ids"])
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSecurityMiddleware)
app.add_middleware(SimpleRateLimitMiddleware, requests_per_minute=settings.rate_limit_per_minute)
instrument(app)

_logger = logging.getLogger("uvicorn.error")

@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    """Catches anything that isn't a deliberate HTTPException. Without this,
    an unhandled exception escapes all the way to Starlette's default error
    handler (ServerErrorMiddleware) -- the TRUE outermost layer, added by
    Starlette even before CORSMiddleware. Registering a handler for the
    bare Exception class runs INSIDE that same outermost layer (Starlette
    special-cases it to become ServerErrorMiddleware's own handler), and
    that middleware sends the handler's response directly to the ASGI
    server, bypassing every inner middleware including CORSMiddleware
    entirely. So the CORS header has to be added by hand here -- returning
    a plain JSONResponse from this handler would look identical to no
    handler at all, still missing 'Access-Control-Allow-Origin', and the
    browser would still report it as a CORS block even though a real
    server-side crash is the actual cause (exactly what happened when
    deleting a user hit an unexpected database constraint).
    """
    _logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    response = JSONResponse(status_code=500, content={"detail": "An unexpected error occurred. This has been logged."})
    origin = request.headers.get("origin")
    if origin and origin in origins:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response

@app.on_event("startup")
def startup():
    if settings.environment.lower() == "production" and settings.secret_key == "development-only-change-me":
        raise RuntimeError("SECRET_KEY must be changed in production.")
    if settings.environment.lower() == "development":
        Base.metadata.create_all(bind=engine)
        _backfill_new_columns()
    if settings.demo_seed:
        from .db import SessionLocal
        from .seed_rules import seed_demo_university_if_empty, seed_demo_admin_if_configured, seed_faculties_if_missing, seed_document_types_if_missing
        db = SessionLocal()
        try:
            uni = seed_demo_university_if_empty(db)
            if uni:
                seed_demo_admin_if_configured(db, uni.id)
                seed_faculties_if_missing(db, uni.id)
                seed_document_types_if_missing(db, uni.id)
        finally:
            db.close()


def _backfill_new_columns():
    """create_all() only creates missing TABLES, not missing COLUMNS on tables
    that already exist -- which matters here because the live demo database
    was provisioned before password_hash/source_reference existed. This is a
    stand-in for a real `alembic upgrade head` (see
    alembic/versions/0004_auth_and_source_reference.py for the real
    migration); it only runs in development mode, only adds columns that are
    genuinely missing, and is safe to run on every startup."""
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    with engine.begin() as conn:
        user_columns = {c["name"] for c in inspector.get_columns("users")}
        if "password_hash" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(200)"))
        finding_columns = {c["name"] for c in inspector.get_columns("findings")}
        if "source_reference" not in finding_columns:
            conn.execute(text("ALTER TABLE findings ADD COLUMN source_reference VARCHAR(300)"))
        submission_columns = {c["name"] for c in inspector.get_columns("submissions")}
        if "owner_user_id" not in submission_columns:
            conn.execute(text("ALTER TABLE submissions ADD COLUMN owner_user_id INTEGER REFERENCES users(id)"))
        if "expires_at" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN expires_at TIMESTAMPTZ"))
        if "programme" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN programme VARCHAR(250)"))
        if "faculty_id" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN faculty_id INTEGER REFERENCES faculties(id)"))
        if "registration_number" not in user_columns:
            conn.execute(text("ALTER TABLE users ADD COLUMN registration_number VARCHAR(100)"))
        faculty_columns = {c["name"] for c in inspector.get_columns("faculties")}
        if "reference_style" not in faculty_columns:
            conn.execute(text("ALTER TABLE faculties ADD COLUMN reference_style VARCHAR(50)"))

app.include_router(health_router,prefix="/api")
app.include_router(submissions_router,prefix="/api")
app.include_router(fixes_router,prefix="/api")
app.include_router(review_router,prefix="/api")
app.include_router(ai_router,prefix="/api")
app.include_router(rules_router,prefix="/api")
app.include_router(universities_router,prefix="/api")
app.include_router(auth_router,prefix="/api")
app.include_router(admin_users_router,prefix="/api")
app.include_router(metrics_router,prefix="/api")
app.include_router(certificates_router,prefix="/api")
app.include_router(evaluation_report_router,prefix="/api")

@app.get("/review",include_in_schema=False)
def review_dashboard(): return FileResponse("frontend/index.html",media_type="text/html")

@app.get("/",include_in_schema=False)
def root(): return RedirectResponse(url="/review")
