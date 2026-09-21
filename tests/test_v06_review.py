from pathlib import Path
from tempfile import TemporaryDirectory
from app.services.review import extract_visible_text, compare_versions
from app.models import DocumentVersion


def test_visible_text_extraction_and_compare():
    source = Path(__file__).resolve().parents[1] / "test_autofix_output.docx"
    assert source.exists()
    lines = extract_visible_text(str(source))
    assert isinstance(lines, list)
    assert len(lines) > 0
    a = DocumentVersion(id=1, submission_id=1, version_number=1, original_filename="a.docx", storage_path=str(source), sha256="a"*64, size_bytes=source.stat().st_size)
    b = DocumentVersion(id=2, submission_id=1, version_number=2, original_filename="b.docx", storage_path=str(source), sha256="b"*64, size_bytes=source.stat().st_size, parent_version_id=1, change_summary="test")
    result = compare_versions(a, b)
    assert result["text_changed"] is False
    assert result["diff_lines"] == []
