import os, re, shutil, subprocess
from pathlib import Path
from ..config import settings

ALLOWED = {".docx"}

def safe_filename(name: str) -> str:
    base=Path(name).name
    base=re.sub(r"[^A-Za-z0-9._ -]", "_", base)
    if not base.lower().endswith(".docx"): raise ValueError("Only .docx files are supported.")
    return base[:180]

def validate_magic(path: str) -> bool:
    with open(path,"rb") as f: return f.read(4)==b"PK\x03\x04"

def validate_docx_package(path: str) -> dict:
    from ..security.validation import validate_docx_package as _validate
    return _validate(path)

def malware_scan(path: str) -> dict:
    if not settings.clamav_enabled:
        if settings.environment.lower() in {"production", "staging"} and settings.malware_scan_fail_closed:
            raise RuntimeError("Malware scanning is mandatory but CLAMAV_ENABLED is false.")
        return {"status":"not_configured","provider":"clamav"}
    if settings.clamav_host and settings.clamav_host != "127.0.0.1":
        try:
            import clamd
            scanner = clamd.ClamdNetworkSocket(host=settings.clamav_host, port=settings.clamav_port, timeout=120)
            with open(path, "rb") as fh:
                result = scanner.instream(fh)
            status = next(iter(result.values())) if result else None
            if status and status[0] == "OK":
                return {"status": "clean", "provider": "clamd-network"}
            if status and status[0] == "FOUND":
                raise RuntimeError("Malware scanner detected a threat.")
            raise RuntimeError("Malware scan failed.")
        except ImportError as exc:
            if settings.malware_scan_fail_closed:
                raise RuntimeError("Python ClamAV client is unavailable.") from exc
        except Exception as exc:
            if settings.malware_scan_fail_closed:
                raise RuntimeError("ClamAV network scanner is unavailable or failed.") from exc
    try:
        proc=subprocess.run([settings.clamav_command,"--no-summary",path],capture_output=True,text=True,timeout=120)
    except FileNotFoundError as exc:
        if settings.malware_scan_fail_closed: raise RuntimeError("ClamAV scanner is unavailable.") from exc
        return {"status":"scanner_unavailable","provider":"clamav"}
    if proc.returncode==0: return {"status":"clean","provider":"clamav"}
    if proc.returncode==1: raise RuntimeError("Malware scanner detected a threat.")
    if settings.malware_scan_fail_closed: raise RuntimeError("Malware scan failed.")
    return {"status":"scan_error","provider":"clamav"}

malware_scan_placeholder = malware_scan
