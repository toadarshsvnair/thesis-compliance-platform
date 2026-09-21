from pathlib import Path
from zipfile import ZipFile, BadZipFile
MAX_UNCOMPRESSED_RATIO=100
MAX_ENTRIES=10000
MAX_UNCOMPRESSED_BYTES=200*1024*1024

def validate_docx_package(path: str):
    try:
        with ZipFile(path) as z:
            infos=z.infolist()
            if len(infos)>MAX_ENTRIES: raise ValueError("DOCX contains too many ZIP entries.")
            total_compressed=sum(i.compress_size for i in infos) or 1
            total_uncompressed=sum(i.file_size for i in infos)
            if total_uncompressed>MAX_UNCOMPRESSED_BYTES: raise ValueError("DOCX package exceeds uncompressed safety limit.")
            if total_uncompressed/total_compressed>MAX_UNCOMPRESSED_RATIO: raise ValueError("DOCX compression ratio is suspicious.")
            names=[i.filename for i in infos]
            if not {"[Content_Types].xml","word/document.xml"}.issubset(names): raise ValueError("DOCX package structure is invalid.")
            for name in names:
                if name.startswith("/") or ".." in Path(name).parts: raise ValueError("Unsafe ZIP entry path.")
        return {"valid":True,"entries":len(infos),"uncompressed_bytes":total_uncompressed}
    except BadZipFile as exc: raise ValueError("Uploaded file is not a valid ZIP/OOXML package.") from exc


MAX_PDF_BYTES = 200 * 1024 * 1024

def validate_pdf_package(path: str):
    """Structural sanity check for an uploaded PDF -- not a full parse, just
    enough to reject something that isn't really a PDF or is unreasonably
    large before it's stored and later opened by other tools (LibreOffice's
    conversion, PyMuPDF, etc.)."""
    p = Path(path)
    size = p.stat().st_size
    if size > MAX_PDF_BYTES:
        raise ValueError("PDF exceeds the maximum allowed size.")
    with open(path, "rb") as f:
        head = f.read(5)
        if head != b"%PDF-":
            raise ValueError("Uploaded file is not a valid PDF.")
        f.seek(max(0, size - 2048))
        tail = f.read()
    if b"%%EOF" not in tail:
        raise ValueError("PDF is missing its end-of-file marker and may be truncated or corrupted.")
    return {"valid": True, "size_bytes": size}
