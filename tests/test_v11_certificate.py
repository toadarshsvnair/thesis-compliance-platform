from pathlib import Path
from types import SimpleNamespace
import tempfile
from app.services.certificate import build_certificate

def test_certificate_requires_current_version_and_compliant_decision():
    class FakeDB:
        def scalars(self, *a, **k):
            class R:
                def first(self): return None
            return R()
        def get(self, cls, ident): return SimpleNamespace(id=ident, version_number=1, sha256='a'*64, original_filename='x.docx', created_by='u', change_summary=None, name='Name', version='1.0')
    s=SimpleNamespace(id=1,current_version_id=1,university_id=1,faculty_id=None,document_type_id=None,rule_set_id=1,student_name='Student',registration_number='R1',programme='P')
    try:
        build_certificate(FakeDB(), s)
        assert False
    except ValueError as e:
        assert 'compliant human decision' in str(e)
