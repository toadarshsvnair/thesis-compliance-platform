"""Read-only reference-data endpoints.

None of this existed before: the API previously assumed the caller already
knew a university_id, faculty_id, document_type_id and rule_set_id to create
a submission, with no way to discover any of them short of an admin calling
the rule-management endpoints directly. A real frontend needs to populate its
own dropdowns, so this module exposes the minimum needed to do that -- scoped
to what the calling principal can actually access, not admin-only.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..db import get_db
from ..models import University, Faculty, DocumentType, RuleSet
from ..security.dependencies import get_principal

router = APIRouter(prefix="/universities", tags=["reference-data"])


def _visible_university_ids(principal, db: Session) -> set[int] | None:
    """None means 'no restriction' (super_admin); otherwise the exact set of
    university IDs the principal may see."""
    if principal.has_role("super_admin"):
        return None
    return set(principal.university_ids)


@router.get("")
def list_universities(db: Session = Depends(get_db), principal = Depends(get_principal)):
    visible = _visible_university_ids(principal, db)
    query = select(University).where(University.active.is_(True)).order_by(University.name)
    if visible is not None:
        if not visible:
            return []
        query = query.where(University.id.in_(visible))
    rows = db.scalars(query).all()
    return [{"id": u.id, "name": u.name, "code": u.code} for u in rows]


def _require_university_visible(principal, db: Session, university_id: int) -> University:
    uni = db.get(University, university_id)
    if not uni or not uni.active:
        raise HTTPException(404, "University not found")
    visible = _visible_university_ids(principal, db)
    if visible is not None and university_id not in visible:
        raise HTTPException(403, "University access denied.")
    return uni


@router.get("/{university_id}/faculties")
def list_faculties(university_id: int, db: Session = Depends(get_db), principal = Depends(get_principal)):
    _require_university_visible(principal, db, university_id)
    rows = db.scalars(select(Faculty).where(
        Faculty.university_id == university_id, Faculty.active.is_(True)
    ).order_by(Faculty.name)).all()
    return [{"id": f.id, "name": f.name, "code": f.code} for f in rows]


@router.get("/{university_id}/document-types")
def list_document_types(university_id: int, db: Session = Depends(get_db), principal = Depends(get_principal)):
    _require_university_visible(principal, db, university_id)
    rows = db.scalars(select(DocumentType).where(
        DocumentType.university_id == university_id, DocumentType.active.is_(True)
    ).order_by(DocumentType.name)).all()
    return [{"id": d.id, "name": d.name, "code": d.code} for d in rows]


@router.get("/{university_id}/rule-sets")
def list_published_rule_sets(
    university_id: int,
    faculty_id: int | None = None,
    document_type_id: int | None = None,
    db: Session = Depends(get_db),
    principal = Depends(get_principal),
):
    """Published rule sets only -- this is the discovery endpoint any
    authenticated user needs to create a submission. The admin-only
    /rule-management/rule-sets endpoint (which also lists draft/retired
    versions) stays admin-gated; this is deliberately narrower and open to
    any principal with access to the university."""
    _require_university_visible(principal, db, university_id)
    query = select(RuleSet).where(
        RuleSet.university_id == university_id, RuleSet.status == "published"
    )
    if faculty_id is not None:
        query = query.where((RuleSet.faculty_id == faculty_id) | (RuleSet.faculty_id.is_(None)))
    if document_type_id is not None:
        query = query.where((RuleSet.document_type_id == document_type_id) | (RuleSet.document_type_id.is_(None)))
    rows = db.scalars(query.order_by(RuleSet.id.desc())).all()
    return [{
        "id": r.id, "name": r.name, "version": r.version,
        "faculty_id": r.faculty_id, "document_type_id": r.document_type_id,
    } for r in rows]
