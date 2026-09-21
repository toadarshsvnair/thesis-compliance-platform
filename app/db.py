from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

class Base(DeclarativeBase):
    pass

def _resolve_database_url(raw: str) -> str:
    """Managed Postgres providers (Render, Railway, Heroku-style) commonly hand out a
    bare postgres:// or postgresql:// URL. SQLAlchemy defaults that to the psycopg2
    driver, which requirements.txt does not install (this project uses psycopg v3).
    Upgrade the scheme so the already-installed psycopg v3 driver is used instead.
    A URL that already names a driver (postgresql+psycopg://, sqlite://, ...) is left
    untouched.
    """
    if raw.startswith("postgres://"):
        raw = "postgresql://" + raw[len("postgres://"):]
    if raw.startswith("postgresql://"):
        raw = "postgresql+psycopg://" + raw[len("postgresql://"):]
    return raw

database_url = _resolve_database_url(settings.database_url)
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
