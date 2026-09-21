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
