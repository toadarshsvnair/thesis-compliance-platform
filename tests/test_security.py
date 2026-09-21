from pathlib import Path
import pytest
from app.services.security import safe_filename, validate_magic

def test_filename_is_sanitized():
    assert safe_filename("../../thesis.docx") == "thesis.docx"

def test_non_docx_rejected():
    with pytest.raises(ValueError):
        safe_filename("malware.exe")
