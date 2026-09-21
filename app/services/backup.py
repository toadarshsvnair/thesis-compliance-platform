from datetime import datetime, timezone
from pathlib import Path
import subprocess
from ..config import settings

def backup_database(output_dir: str = "./backups") -> str:
    if settings.environment.lower() == "development":
        raise RuntimeError("Use an explicit database backup tool in development rather than this production helper.")
    if not settings.database_url.startswith("postgresql"):
        raise RuntimeError("Automated backup helper currently supports PostgreSQL URLs only.")
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = Path(output_dir) / f"thesis_compliance_{stamp}.dump"
    # DATABASE_URL is intentionally not interpolated into a shell command.
    raise RuntimeError("Configure pg_dump credentials through the deployment secret manager before enabling this helper.")
