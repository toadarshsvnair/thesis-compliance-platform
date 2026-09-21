from pathlib import Path
import hashlib, os, re, shutil, tempfile
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.orm import Session
from pydantic import ValidationError
from ..db import get_db
from ..models import RuleSet, Rule, Faculty, DocumentType, GuidelineSource, RuleSetApproval
from ..schemas_rules import RuleSetCreate, RuleSetUpdate, RuleCreate, RuleUpdate, StatusChange, CloneRequest
from ..security.dependencies import get_principal, require_university_access
from ..services.audit import audit
from ..services.rule_template import COLUMNS as BULK_UPLOAD_COLUMNS, build_sample_workbook

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
    return [{"id":x.id,"name":x.name,"version":x.version,"status":x.status,"faculty_id":x.faculty_id,"document_type_id":x.document_type_id,"created_at":x.created_at} for x in rows]


@router.patch("/rule-sets/{rule_set_id}")
def update_rule_set(rule_set_id:int, body:RuleSetUpdate, db:Session=Depends(get_db), principal=Depends(get_principal)):
    rs=_get_rs(db,rule_set_id); _admin(principal,rs.university_id); _draft(rs)
    data=body.model_dump(exclude_unset=True); faculty=data.get("faculty_id",rs.faculty_id); dtype=data.get("document_type_id",rs.document_type_id)
    _validate_scope(db,rs.university_id,faculty,dtype)
    for k,v in data.items(): setattr(rs,k,v)
    audit(db,rs.university_id,principal.subject,"rule_set_updated","rule_set",str(rs.id),rule_set_id=rs.id,result="success",metadata_json={"fields":sorted(data)})
    db.commit(); return {"id":rs.id,"status":rs.status}


@router.delete("/rule-sets/{rule_set_id}")
def delete_rule_set(rule_set_id: int, db: Session = Depends(get_db), principal = Depends(get_principal)):
    """Only a draft can be deleted outright -- a published or retired rule
    set may have real submissions pointing at it (Submission.rule_set_id is
    a required foreign key, and a submission can only ever be created
    against a published rule set in the first place, so a draft is
    guaranteed to have none). Retiring is the right way to take a published
    rule set out of use without breaking that history."""
    rs = _get_rs(db, rule_set_id)
    _admin(principal, rs.university_id)
    if rs.status != "draft":
        raise HTTPException(409, "Only a draft rule set can be deleted. Retire a published rule set instead.")
    university_id = rs.university_id
    db.query(Rule).filter(Rule.rule_set_id == rs.id).delete(synchronize_session=False)
    db.query(RuleSetApproval).filter(RuleSetApproval.rule_set_id == rs.id).delete(synchronize_session=False)
    db.query(GuidelineSource).filter(GuidelineSource.rule_set_id == rs.id).delete(synchronize_session=False)
    db.delete(rs)
    audit(db, university_id, principal.subject, "rule_set_deleted", "rule_set", str(rule_set_id),
          rule_set_id=rule_set_id, result="deleted")
    db.commit()
    return {"status": "deleted", "id": rule_set_id}


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


@router.get("/sample-template")
def download_sample_template(principal = Depends(get_principal)):
    """The same bulk-upload template shown in Rule Management, pre-filled
    with the real current Alliance rule catalogue as working reference
    data. Generated fresh from the same column list the upload endpoint
    validates against, so the two can never drift apart."""
    if not principal.roles.intersection(ADMIN_ROLES):
        raise HTTPException(403, "University administrator privileges required")
    tmp_dir = Path(tempfile.mkdtemp())
    path = tmp_dir / "rule_set_bulk_upload_template.xlsx"
    build_sample_workbook(str(path))
    from fastapi.responses import FileResponse
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="rule_set_bulk_upload_template.xlsx",
    )


@router.get("/rule-sets/{rule_set_id}/rules")
def list_rules(rule_set_id: int, db: Session = Depends(get_db), principal = Depends(get_principal)):
    rs = _get_rs(db, rule_set_id)
    _admin(principal, rs.university_id)
    rows = db.scalars(select(Rule).where(Rule.rule_set_id == rs.id).order_by(Rule.id)).all()
    return [{
        "id": r.id, "rule_id": r.rule_id, "category": r.category, "requirement": r.requirement,
        "validation_method": r.validation_method, "severity": r.severity,
        "auto_fix_allowed": r.auto_fix_allowed, "source_reference": r.source_reference, "active": r.active,
    } for r in rows]


def _parse_bool_cell(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in {"yes", "y", "true", "1"}


@router.post("/rule-sets/{rule_set_id}/rules/bulk-upload")
def bulk_upload_rules(rule_set_id: int, upload: UploadFile = File(...), db: Session = Depends(get_db), principal = Depends(get_principal)):
    """Adds every rule in an uploaded Excel workbook to this (draft) rule
    set. Validates every row before writing anything: either the whole
    sheet is added, or nothing is -- a partially-imported spreadsheet with
    silent gaps is worse than a clear list of what to fix and re-upload.
    Expects the same column layout as the sample template
    (services/rule_template.py's build_sample_workbook): one header row,
    then one rule per row, columns in the order in BULK_UPLOAD_COLUMNS."""
    rs = _get_rs(db, rule_set_id)
    _admin(principal, rs.university_id)
    _draft(rs)

    original = Path(upload.filename or "rules.xlsx").name
    if not original.lower().endswith(".xlsx"):
        raise HTTPException(415, "Only .xlsx workbooks are accepted for bulk rule upload.")

    try:
        import openpyxl
    except ImportError:
        raise HTTPException(500, "Excel support is not available on this server.")

    try:
        workbook = openpyxl.load_workbook(upload.file, data_only=True, read_only=True)
    except Exception as exc:
        raise HTTPException(400, f"Could not read this file as an Excel workbook: {exc}")
    sheet = workbook.worksheets[0]

    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        raise HTTPException(400, "The workbook has no rows.")
    header = [str(c).strip() if c is not None else "" for c in rows[0]]
    expected = BULK_UPLOAD_COLUMNS
    if header[:len(expected)] != expected:
        raise HTTPException(
            400,
            f"Header row does not match the expected template. Expected columns "
            f"{expected} in that exact order (extra columns after these are fine).",
        )

    existing_rule_ids = {
        r.rule_id for r in db.scalars(select(Rule).where(Rule.rule_set_id == rs.id)).all()
    }
    seen_in_file: set[str] = set()
    parsed: list[RuleCreate] = []
    errors: list[str] = []

    for row_num, row in enumerate(rows[1:], start=2):
        if row is None or all(c is None or str(c).strip() == "" for c in row):
            continue  # skip a fully blank row rather than erroring on it
        cells = list(row) + [None] * (len(expected) - len(row))
        raw = dict(zip(expected, cells))
        try:
            candidate = RuleCreate(
                rule_id=str(raw["Rule ID"]).strip() if raw["Rule ID"] is not None else "",
                category=str(raw["Category"]).strip() if raw["Category"] is not None else "",
                requirement=str(raw["Requirement"]).strip() if raw["Requirement"] is not None else "",
                validation_method=str(raw["Validation Method"]).strip() if raw["Validation Method"] is not None else "",
                severity=str(raw["Severity"]).strip() if raw["Severity"] is not None else "",
                auto_fix_allowed=_parse_bool_cell(raw["Auto-Fix Allowed"]),
                source_reference=(str(raw["Source Reference"]).strip() if raw["Source Reference"] not in (None, "") else None),
                active=_parse_bool_cell(raw["Active"]) if raw["Active"] is not None else True,
            )
        except ValidationError as exc:
            first = exc.errors()[0]
            field = first["loc"][0] if first["loc"] else "?"
            errors.append(f"Row {row_num}: {field} — {first['msg']}")
            continue
        if candidate.rule_id in existing_rule_ids:
            errors.append(f"Row {row_num}: Rule ID '{candidate.rule_id}' already exists in this rule set.")
            continue
        if candidate.rule_id in seen_in_file:
            errors.append(f"Row {row_num}: Rule ID '{candidate.rule_id}' is duplicated within this file.")
            continue
        seen_in_file.add(candidate.rule_id)
        parsed.append(candidate)

    if errors:
        raise HTTPException(400, detail={"message": "Fix the following and re-upload; nothing was added.", "errors": errors})
    if not parsed:
        raise HTTPException(400, "No rule rows were found below the header.")

    for candidate in parsed:
        db.add(Rule(rule_set_id=rs.id, **candidate.model_dump()))
    audit(db, rs.university_id, principal.subject, "rules_bulk_uploaded", "rule_set", str(rs.id),
          rule_set_id=rs.id, result="success",
          metadata_json={"filename": original, "rule_count": len(parsed)})
    db.commit()
    return {"added": len(parsed), "rule_ids": [c.rule_id for c in parsed]}


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
