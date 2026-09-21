from pathlib import Path
import hashlib, os, re, shutil, tempfile
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import RuleSet, Rule, Faculty, DocumentType, GuidelineSource, RuleSetApproval
from ..schemas_rules import RuleSetCreate, RuleSetUpdate, RuleCreate, RuleUpdate, StatusChange, CloneRequest
from ..security.dependencies import get_principal, require_university_access
from ..services.audit import audit

router = APIRouter(prefix="/rule-management", tags=["rule-management"])
ADMIN_ROLES = {"super_admin", "university_admin"}
PUBLISH_ROLES = {"super_admin", "university_admin"}
MAX_GUIDELINE_BYTES = 25 * 1024 * 1024
ALLOWED_EXT = {".pdf", ".docx"}


def _admin(principal, university_id: int):
    if not principal.roles.intersection(ADMIN_ROLES):
        raise HTTPException(403, "University administrator privileges required")
    require_university_access(principal, university_id)


def _get_rs(db, rule_set_id):
    rs = db.get(RuleSet, rule_set_id)
    if not rs: raise HTTPException(404, "Rule set not found")
    return rs


def _draft(rs):
    if rs.status != "draft":
        raise HTTPException(409, "Published/in-review rule sets are immutable. Clone to a new draft version before editing.")


def _validate_scope(db, university_id, faculty_id, document_type_id):
    if faculty_id is not None:
        f = db.get(Faculty, faculty_id)
        if not f or f.university_id != university_id: raise HTTPException(400, "Faculty is outside this university")
    if document_type_id is not None:
        d = db.get(DocumentType, document_type_id)
        if not d or d.university_id != university_id: raise HTTPException(400, "Document type is outside this university")


@router.post("/rule-sets")
def create_rule_set(body: RuleSetCreate, db: Session=Depends(get_db), principal=Depends(get_principal)):
    _admin(principal, body.university_id); _validate_scope(db, body.university_id, body.faculty_id, body.document_type_id)
    duplicate = db.scalar(select(RuleSet).where(RuleSet.university_id==body.university_id, RuleSet.version==body.version, RuleSet.faculty_id==body.faculty_id, RuleSet.document_type_id==body.document_type_id))
    if duplicate: raise HTTPException(409, "Rule-set version already exists for this scope")
    rs=RuleSet(**body.model_dump(), status="draft"); db.add(rs); db.flush()
    audit(db, body.university_id, principal.subject, "rule_set_created", "rule_set", str(rs.id), rule_set_id=rs.id, result="success", metadata_json={"version":rs.version})
    db.commit(); db.refresh(rs); return {"id":rs.id,"status":rs.status,"version":rs.version}


@router.get("/rule-sets")
def list_rule_sets(university_id:int, db:Session=Depends(get_db), principal=Depends(get_principal)):
    _admin(principal, university_id)
    rows=db.scalars(select(RuleSet).where(RuleSet.university_id==university_id).order_by(RuleSet.id.desc())).all()
    return [{"id":x.id,"name":x.name,"version":x.version,"status":x.status,"faculty_id":x.faculty_id,"document_type_id":x.document_type_id} for x in rows]


@router.patch("/rule-sets/{rule_set_id}")
def update_rule_set(rule_set_id:int, body:RuleSetUpdate, db:Session=Depends(get_db), principal=Depends(get_principal)):
    rs=_get_rs(db,rule_set_id); _admin(principal,rs.university_id); _draft(rs)
    data=body.model_dump(exclude_unset=True); faculty=data.get("faculty_id",rs.faculty_id); dtype=data.get("document_type_id",rs.document_type_id)
    _validate_scope(db,rs.university_id,faculty,dtype)
    for k,v in data.items(): setattr(rs,k,v)
    audit(db,rs.university_id,principal.subject,"rule_set_updated","rule_set",str(rs.id),rule_set_id=rs.id,result="success",metadata_json={"fields":sorted(data)})
    db.commit(); return {"id":rs.id,"status":rs.status}


@router.post("/rule-sets/{rule_set_id}/rules")
def add_rule(rule_set_id:int, body:RuleCreate, db:Session=Depends(get_db), principal=Depends(get_principal)):
    rs=_get_rs(db,rule_set_id); _admin(principal,rs.university_id); _draft(rs)
    if db.scalar(select(Rule).where(Rule.rule_set_id==rs.id,Rule.rule_id==body.rule_id)): raise HTTPException(409,"Rule ID already exists in this rule set")
    rule=Rule(rule_set_id=rs.id,**body.model_dump()); db.add(rule); db.flush()
    audit(db,rs.university_id,principal.subject,"rule_created","rule",str(rule.id),rule_set_id=rs.id,result="success",metadata_json={"rule_id":rule.rule_id})
    db.commit(); return {"id":rule.id,"rule_id":rule.rule_id}


@router.patch("/rule-sets/{rule_set_id}/rules/{rule_pk}")
def update_rule(rule_set_id:int, rule_pk:int, body:RuleUpdate, db:Session=Depends(get_db), principal=Depends(get_principal)):
    rs=_get_rs(db,rule_set_id); _admin(principal,rs.university_id); _draft(rs)
    rule=db.get(Rule,rule_pk)
    if not rule or rule.rule_set_id!=rs.id: raise HTTPException(404,"Rule not found")
    data=body.model_dump(exclude_unset=True)
    for k,v in data.items(): setattr(rule,k,v)
    audit(db,rs.university_id,principal.subject,"rule_updated","rule",str(rule.id),rule_set_id=rs.id,result="success",metadata_json={"rule_id":rule.rule_id,"fields":sorted(data)})
    db.commit(); return {"id":rule.id,"rule_id":rule.rule_id}


@router.post("/rule-sets/{rule_set_id}/clone")
def clone_rule_set(rule_set_id:int, body:CloneRequest, db:Session=Depends(get_db), principal=Depends(get_principal)):
    source=_get_rs(db,rule_set_id); _admin(principal,source.university_id)
    dup=db.scalar(select(RuleSet).where(RuleSet.university_id==source.university_id,RuleSet.version==body.version,RuleSet.faculty_id==source.faculty_id,RuleSet.document_type_id==source.document_type_id))
    if dup: raise HTTPException(409,"Target version already exists")
    target=RuleSet(university_id=source.university_id,faculty_id=source.faculty_id,document_type_id=source.document_type_id,version=body.version,name=body.name or source.name,status="draft",source_metadata={**(source.source_metadata or {}),"cloned_from_rule_set_id":source.id})
    db.add(target); db.flush()
    for r in db.scalars(select(Rule).where(Rule.rule_set_id==source.id)).all():
        db.add(Rule(rule_set_id=target.id,rule_id=r.rule_id,category=r.category,requirement=r.requirement,validation_method=r.validation_method,severity=r.severity,auto_fix_allowed=r.auto_fix_allowed,source_reference=r.source_reference,active=r.active))
    audit(db,source.university_id,principal.subject,"rule_set_cloned","rule_set",str(target.id),rule_set_id=target.id,result="success",metadata_json={"source_rule_set_id":source.id,"version":body.version})
    db.commit(); return {"id":target.id,"status":"draft","version":target.version}


@router.post("/rule-sets/{rule_set_id}/submit-review")
def submit_review(rule_set_id:int, body:StatusChange, db:Session=Depends(get_db), principal=Depends(get_principal)):
    rs=_get_rs(db,rule_set_id); _admin(principal,rs.university_id); _draft(rs)
    active=db.scalars(select(Rule).where(Rule.rule_set_id==rs.id,Rule.active==True)).all()
    if not active: raise HTTPException(409,"Cannot submit an empty rule set for review")
    missing=[r.rule_id for r in active if not r.source_reference]
    if missing: raise HTTPException(409,detail={"message":"Every active rule requires a source reference before review","rules":missing})
    rs.status="in_review"; db.add(RuleSetApproval(rule_set_id=rs.id,university_id=rs.university_id,actor_id=principal.subject,action="submitted_for_review",comment=body.comment))
    audit(db,rs.university_id,principal.subject,"rule_set_submitted_for_review","rule_set",str(rs.id),rule_set_id=rs.id,result="success")
    db.commit(); return {"id":rs.id,"status":rs.status}


@router.post("/rule-sets/{rule_set_id}/publish")
def publish(rule_set_id:int, body:StatusChange, db:Session=Depends(get_db), principal=Depends(get_principal)):
    rs=_get_rs(db,rule_set_id); _admin(principal,rs.university_id)
    if rs.status!="in_review": raise HTTPException(409,"Only an in-review rule set can be published")
    rs.status="published"; db.add(RuleSetApproval(rule_set_id=rs.id,university_id=rs.university_id,actor_id=principal.subject,action="published",comment=body.comment))
    audit(db,rs.university_id,principal.subject,"rule_set_published","rule_set",str(rs.id),rule_set_id=rs.id,result="success",metadata_json={"version":rs.version})
    db.commit(); return {"id":rs.id,"status":rs.status,"version":rs.version}


@router.post("/rule-sets/{rule_set_id}/retire")
def retire(rule_set_id:int, body:StatusChange, db:Session=Depends(get_db), principal=Depends(get_principal)):
    rs=_get_rs(db,rule_set_id); _admin(principal,rs.university_id)
    if rs.status!="published": raise HTTPException(409,"Only a published rule set can be retired")
    rs.status="retired"; db.add(RuleSetApproval(rule_set_id=rs.id,university_id=rs.university_id,actor_id=principal.subject,action="retired",comment=body.comment))
    audit(db,rs.university_id,principal.subject,"rule_set_retired","rule_set",str(rs.id),rule_set_id=rs.id,result="success")
    db.commit(); return {"id":rs.id,"status":rs.status}


@router.post("/rule-sets/{rule_set_id}/guidelines")
def upload_guideline(rule_set_id:int, upload:UploadFile=File(...), db:Session=Depends(get_db), principal=Depends(get_principal)):
    rs=_get_rs(db,rule_set_id); _admin(principal,rs.university_id); _draft(rs)
    original=Path(upload.filename or "guideline").name; ext=Path(original).suffix.lower()
    if ext not in ALLOWED_EXT: raise HTTPException(415,"Only PDF and DOCX guideline sources are accepted")
    root=Path(os.getenv("GUIDELINE_STORAGE_ROOT","./data/guidelines"))/str(rs.university_id)/str(rs.id); root.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=root,suffix=ext); os.close(fd); size=0; h=hashlib.sha256()
    try:
        with open(tmp,"wb") as out:
            while True:
                chunk=upload.file.read(1024*1024)
                if not chunk: break
                size+=len(chunk)
                if size>MAX_GUIDELINE_BYTES: raise HTTPException(413,"Guideline exceeds 25 MB limit")
                h.update(chunk); out.write(chunk)
        # File extension is not trusted. Validate a minimal signature/package shape.
        with open(tmp, "rb") as check:
            sig = check.read(4)
        if ext == ".pdf" and sig != b"%PDF":
            raise HTTPException(400, "File extension/content mismatch: invalid PDF signature")
        if ext == ".docx":
            import zipfile
            if sig[:2] != b"PK":
                raise HTTPException(400, "File extension/content mismatch: invalid DOCX signature")
            try:
                with zipfile.ZipFile(tmp) as z:
                    names=set(z.namelist())
                    if "[Content_Types].xml" not in names or "word/document.xml" not in names:
                        raise HTTPException(400, "Invalid DOCX package")
            except zipfile.BadZipFile:
                raise HTTPException(400, "Invalid DOCX package")
        digest=h.hexdigest(); safe=re.sub(r'[^A-Za-z0-9._-]+','_',original)[:180]; final=root/f"{digest[:16]}_{safe}"
        os.replace(tmp,final)
        source=GuidelineSource(university_id=rs.university_id,rule_set_id=rs.id,original_filename=original,storage_path=str(final),sha256=digest,mime_type=upload.content_type,size_bytes=size,uploaded_by=principal.subject)
        db.add(source); db.flush()
        audit(db,rs.university_id,principal.subject,"guideline_uploaded","guideline_source",str(source.id),rule_set_id=rs.id,result="success",metadata_json={"filename":original,"sha256":digest,"size_bytes":size})
        db.commit(); return {"id":source.id,"original_filename":original,"sha256":digest,"size_bytes":size,"mime_type":upload.content_type}
    except Exception:
        if os.path.exists(tmp): os.unlink(tmp)
        raise


@router.get("/rule-sets/{rule_set_id}/guidelines")
def list_guidelines(rule_set_id:int, db:Session=Depends(get_db), principal=Depends(get_principal)):
    rs=_get_rs(db,rule_set_id); _admin(principal,rs.university_id)
    rows=db.scalars(select(GuidelineSource).where(GuidelineSource.rule_set_id==rs.id).order_by(GuidelineSource.id)).all()
    return [{"id":x.id,"original_filename":x.original_filename,"sha256":x.sha256,"size_bytes":x.size_bytes,"mime_type":x.mime_type} for x in rows]
