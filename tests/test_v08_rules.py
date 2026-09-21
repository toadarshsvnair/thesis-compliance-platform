from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db import Base, get_db
from app.models import University, Faculty, DocumentType, RuleSet, Rule

engine = create_engine("sqlite://", connect_args={"check_same_thread":False}, poolclass=StaticPool)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(engine)

def override_db():
    db=TestingSession()
    try: yield db
    finally: db.close()
app.dependency_overrides[get_db]=override_db
client=TestClient(app)
HEAD={"X-User-Id":"admin-1","X-User-Roles":"university_admin","X-University-Ids":"1"}

def seed():
    db=TestingSession()
    if not db.get(University,1):
        db.add(University(id=1,name="Test University",code="TU")); db.flush()
        db.add(Faculty(id=1,university_id=1,name="Engineering",code="ENG"))
        db.add(DocumentType(id=1,university_id=1,name="PhD Thesis",code="PHD")); db.commit()
    db.close()

def test_rule_set_governance_and_immutability():
    seed()
    r=client.post('/api/rule-management/rule-sets',headers=HEAD,json={"university_id":1,"faculty_id":1,"document_type_id":1,"version":"2026.1","name":"PhD Thesis Rules"})
    assert r.status_code==200, r.text
    rsid=r.json()['id']
    r=client.post(f'/api/rule-management/rule-sets/{rsid}/rules',headers=HEAD,json={"rule_id":"PAGE-001","category":"Page","requirement":"A4 paper","validation_method":"deterministic","severity":"Major","auto_fix_allowed":True,"source_reference":"Annexure 19, page setup"})
    assert r.status_code==200
    assert client.post(f'/api/rule-management/rule-sets/{rsid}/submit-review',headers=HEAD,json={"comment":"Ready for controlled review"}).json()['status']=='in_review'
    assert client.post(f'/api/rule-management/rule-sets/{rsid}/publish',headers=HEAD,json={"comment":"Approved for institutional use"}).json()['status']=='published'
    # Published versions cannot be edited.
    r=client.patch(f'/api/rule-management/rule-sets/{rsid}',headers=HEAD,json={"name":"Changed"})
    assert r.status_code==409
    # They can be cloned into a new editable version.
    r=client.post(f'/api/rule-management/rule-sets/{rsid}/clone',headers=HEAD,json={"version":"2026.2","name":"PhD Thesis Rules 2026.2"})
    assert r.status_code==200 and r.json()['status']=='draft'

def test_review_requires_source_reference():
    seed()
    r=client.post('/api/rule-management/rule-sets',headers=HEAD,json={"university_id":1,"faculty_id":1,"document_type_id":1,"version":"2026.no-source","name":"Untraced Rules"})
    rsid=r.json()['id']
    client.post(f'/api/rule-management/rule-sets/{rsid}/rules',headers=HEAD,json={"rule_id":"TEST-001","category":"Test","requirement":"A requirement","validation_method":"deterministic","severity":"Review","auto_fix_allowed":False})
    r=client.post(f'/api/rule-management/rule-sets/{rsid}/submit-review',headers=HEAD,json={"comment":"Try review"})
    assert r.status_code==409
