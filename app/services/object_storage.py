from pathlib import Path
import boto3
from botocore.client import Config
from ..config import settings

class ObjectStorage:
    def __init__(self):
        self.bucket = settings.s3_bucket
        self.local_root = Path(settings.storage_root)
        self.local_root.mkdir(parents=True, exist_ok=True)
        self.s3 = None
        if settings.s3_enabled:
            self.s3 = boto3.client(
                "s3", endpoint_url=settings.s3_endpoint or None,
                aws_access_key_id=settings.s3_access_key,
                aws_secret_access_key=settings.s3_secret_key,
                region_name=settings.s3_region,
                config=Config(signature_version="s3v4"),
            )

    def put_file(self, local_path: str, key: str) -> str:
        if not self.s3:
            target = self.local_root / "object-store" / key
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(Path(local_path).read_bytes())
            return str(target)
        self.s3.upload_file(local_path, self.bucket, key, ExtraArgs={"ServerSideEncryption": "AES256"})
        return f"s3://{self.bucket}/{key}"
