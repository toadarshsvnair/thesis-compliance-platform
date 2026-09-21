from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "sqlite:///./thesis_compliance.db"
    storage_root: str = "./storage"
    max_upload_mb: int = 50
    allowed_extensions: str = ".docx,.pdf"
    environment: str = "development"
    oidc_issuer: str = ""
    oidc_audience: str = ""
    oidc_jwks_url: str = ""
    oidc_required: bool = False
    allowed_origins: str = ""
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    clamav_enabled: bool = False
    clamav_command: str = "clamdscan"
    clamav_host: str = "127.0.0.1"
    clamav_port: int = 3310
    malware_scan_fail_closed: bool = True
    redis_url: str = ""
    rate_limit_per_minute: int = 120
    request_body_limit_mb: int = 60
    secret_key: str = "development-only-change-me"
    s3_enabled: bool = False
    s3_endpoint: str = ""
    s3_bucket: str = "thesis-documents"
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_region: str = "us-east-1"
    processing_worker_required: bool = False
    demo_seed: bool = False
    demo_admin_email: str = "admin@demo.edu"
    demo_admin_password: str = ""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

settings = Settings()
