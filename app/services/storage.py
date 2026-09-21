from pathlib import Path
from hashlib import sha256
from .security import safe_filename
from ..config import settings

class StorageService:
    def __init__(self):
        self.root=Path(settings.storage_root)
        (self.root/"uploads").mkdir(parents=True,exist_ok=True)
        (self.root/"versions").mkdir(parents=True,exist_ok=True)
    def save_upload(self,file_obj,submission_id:int,version:int,filename:str):
        filename=safe_filename(filename)
        target_dir=self.root/"versions"/str(submission_id); target_dir.mkdir(parents=True,exist_ok=True)
        target=target_dir/f"v{version}_{filename}"
        h=sha256(); size=0; max_bytes=settings.max_upload_mb*1024*1024
        with target.open("wb") as out:
            while chunk:=file_obj.read(1024*1024):
                size+=len(chunk)
                if size>max_bytes:
                    target.unlink(missing_ok=True); raise ValueError(f"Upload exceeds {settings.max_upload_mb} MB limit.")
                h.update(chunk); out.write(chunk)
        return str(target),size,h.hexdigest()
