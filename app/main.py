from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from .db import Base, engine
from .api.health import router as health_router
from .api.submissions import router as submissions_router
from .api.fixes import router as fixes_router
from .api.review import router as review_router
from .api.ai import router as ai_router
from .api.rules import router as rules_router
from .api.universities import router as universities_router
from .api.auth import router as auth_router
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

@app.on_event("startup")
def startup():
    if settings.environment.lower() == "production" and settings.secret_key == "development-only-change-me":
        raise RuntimeError("SECRET_KEY must be changed in production.")
    if settings.environment.lower() == "development":
        Base.metadata.create_all(bind=engine)
        _backfill_new_columns()
    if settings.demo_seed:
        from .db import SessionLocal
        from .seed_rules import seed_demo_university_if_empty, seed_demo_admin_if_configured
        db = SessionLocal()
        try:
            uni = seed_demo_university_if_empty(db)
            if uni:
                seed_demo_admin_if_configured(db, uni.id)
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

app.include_router(health_router,prefix="/api")
app.include_router(submissions_router,prefix="/api")
app.include_router(fixes_router,prefix="/api")
app.include_router(review_router,prefix="/api")
app.include_router(ai_router,prefix="/api")
app.include_router(rules_router,prefix="/api")
app.include_router(universities_router,prefix="/api")
app.include_router(auth_router,prefix="/api")
app.include_router(metrics_router,prefix="/api")
app.include_router(certificates_router,prefix="/api")

@app.get("/review",include_in_schema=False)
def review_dashboard(): return FileResponse("frontend/index.html",media_type="text/html")

@app.get("/",include_in_schema=False)
def root(): return RedirectResponse(url="/review")
