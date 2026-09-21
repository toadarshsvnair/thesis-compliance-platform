from pathlib import Path
import shutil
import json
import subprocess
import tempfile
from sqlalchemy.orm import Session

from ..models import Submission, DocumentVersion, Finding
from .validator import run_validation

class ProcessingService:
    def __init__(self):
        self.work_root = Path("/tmp/thesis-compliance-worker")
        self.work_root.mkdir(parents=True, exist_ok=True)

    def render_pdf(self, docx_path: str, work_dir: Path) -> str:
        out_dir = work_dir / "rendered"
        out_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "libreoffice", "--headless",
                "--convert-to", "pdf",
                "--outdir", str(out_dir),
                str(docx_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        pdf = out_dir / (Path(docx_path).stem + ".pdf")
        if not pdf.exists():
            raise RuntimeError("LibreOffice did not produce a PDF.")
        return str(pdf)

    def validate(self, db: Session, submission: Submission, version: DocumentVersion):
        work_dir = self.work_root / f"submission-{submission.id}-version-{version.version_number}"
        if work_dir.exists():
            shutil.rmtree(work_dir)
        work_dir.mkdir(parents=True)

        result_json = work_dir / "validation.json"
        pdf_path = self.render_pdf(version.storage_path, work_dir)

        run_validation(version.storage_path, pdf_path, str(result_json))
        result = json.loads(result_json.read_text(encoding="utf-8"))

        # Idempotent revalidation: remove findings for this exact version first.
        db.query(Finding).filter(
            Finding.submission_id == submission.id,
            Finding.document_version_id == version.id
        ).delete(synchronize_session=False)

        for item in result.get("findings", []):
            db.add(Finding(
                submission_id=submission.id,
                document_version_id=version.id,
                rule_id=item["rule_id"],
                category=item["category"],
                severity=item["severity"],
                location=str(item["location"]),
                expected=item["expected"],
                actual=item["actual"],
                message=item["message"],
                confidence=item.get("confidence"),
                source_reference=item.get("basis"),
                auto_fix_allowed=item.get("auto_fix") == "Yes",
                status="open",
            ))

        submission.status = "validated"
        db.commit()

        return result
