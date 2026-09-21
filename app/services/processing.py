from pathlib import Path
import shutil
import json
import subprocess
import tempfile
from sqlalchemy.orm import Session

from ..models import Submission, DocumentVersion, Finding, Faculty, User
from .validator import run_validation


def _enrich_locations_with_pages(findings: list, rendered_pdf_path: str) -> None:
    """Best-effort: append a page number to a finding's location by searching
    the rendered PDF for a distinctive snippet of the finding's observed
    ("actual") text. Deliberately conservative -- structural checks (margins,
    page size) apply to the whole section, not one page, so those are left
    alone; checks that already carry a page-specific rendered location (TOC,
    captions) are left alone too. Never fabricates a page number: if no
    confident text match is found, the location is left unchanged."""
    try:
        import fitz
    except ImportError:
        return
    if not rendered_pdf_path or not Path(rendered_pdf_path).exists():
        return
    try:
        doc = fitz.open(rendered_pdf_path)
        page_texts = [page.get_text() for page in doc]
        doc.close()
    except Exception:
        return

    for item in findings:
        location = str(item.get("location", ""))
        if "(p." in location or "page" in location.lower():
            continue
        candidate = str(item.get("actual", "")).strip()
        if len(candidate) < 12:
            continue
        snippet = candidate[:60]
        for page_num, text in enumerate(page_texts, start=1):
            if snippet in text:
                item["location"] = f"{location} (p. {page_num})"
                break


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

        is_pdf = version.original_filename.lower().endswith(".pdf")

        # Idempotent revalidation: remove findings for this exact version first
        # (shared by both branches below).
        db.query(Finding).filter(
            Finding.submission_id == submission.id,
            Finding.document_version_id == version.id
        ).delete(synchronize_session=False)

        if is_pdf:
            # The deterministic engine is built entirely on python-docx's
            # object model (paragraphs, runs, sections, fonts) -- there is no
            # reliable way to recover that structure from a PDF, so automated
            # formatting checks genuinely cannot run against one. Recording
            # one clear informational finding is honest; silently skipping
            # validation, or pretending to check a PDF the same way, is not.
            result = {"findings": [{
                "rule_id": "PDF-SUBMITTED", "category": "Submission Format", "severity": "Review",
                "location": "document", "expected": "DOCX source for automated formatting checks",
                "actual": "PDF submitted",
                "message": "This version was submitted as a PDF. Automated formatting checks require the "
                           "original DOCX and could not run for this version; a reviewer must manually verify "
                           "formatting compliance against the institutional guidelines.",
                "confidence": None, "basis": "Submission format", "auto_fix": "No",
            }]}
        else:
            result_json = work_dir / "validation.json"
            pdf_path = self.render_pdf(version.storage_path, work_dir)

            # A student's faculty (set on their account, not re-entered per
            # submission) determines which citation style REF-003 checks against.
            reference_style = None
            owner = db.get(User, submission.owner_user_id) if submission.owner_user_id else None
            faculty_id = (owner.faculty_id if owner and owner.faculty_id else submission.faculty_id)
            if faculty_id:
                faculty = db.get(Faculty, faculty_id)
                if faculty:
                    reference_style = faculty.reference_style

            run_validation(version.storage_path, pdf_path, str(result_json), reference_style)
            result = json.loads(result_json.read_text(encoding="utf-8"))
            _enrich_locations_with_pages(result.get("findings", []), pdf_path)

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
