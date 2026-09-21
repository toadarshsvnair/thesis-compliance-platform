import os
from pathlib import Path
import pytest

from app.config import settings
from app.security.identity import principal_from_dev_headers
from app.security.validation import validate_docx_package
from app.services.security import malware_scan


def test_dev_identity_helper_still_works():
    p=principal_from_dev_headers('u1','u@example.edu','research_officer','1,2')
    assert p.subject=='u1' and p.has_role('research_officer') and p.university_ids==frozenset({1,2})


def test_docx_package_limits():
    # Existing repository sample produced during v0.5 testing.
    path=Path(__file__).parents[1]/'test_autofix_output.docx'
    if not path.exists(): pytest.skip('sample DOCX unavailable')
    result=validate_docx_package(str(path))
    assert result['valid'] is True


def test_production_requires_malware_scan(monkeypatch):
    monkeypatch.setattr(settings,'environment','production')
    monkeypatch.setattr(settings,'clamav_enabled',False)
    monkeypatch.setattr(settings,'malware_scan_fail_closed',True)
    with pytest.raises(RuntimeError): malware_scan('/tmp/nonexistent.docx')
