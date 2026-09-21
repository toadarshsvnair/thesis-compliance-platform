from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from sqlalchemy import select
from ..models import Submission, DocumentVersion, ComplianceDecision, Finding, RuleSet, University, Faculty, DocumentType

CERT_DIR = Path('/tmp/thesis-compliance-certificates')
CERT_DIR.mkdir(parents=True, exist_ok=True)

def build_certificate(db, submission: Submission) -> tuple[Path, str]:
    if not submission.current_version_id:
        raise ValueError('Submission has no current version')
    decision = db.scalars(select(ComplianceDecision).where(
        ComplianceDecision.submission_id == submission.id,
        ComplianceDecision.document_version_id == submission.current_version_id,
        ComplianceDecision.decision == 'compliant'
    ).order_by(ComplianceDecision.created_at.desc())).first()
    if not decision:
        raise ValueError('A compliant human decision is required before certificate generation')
    version = db.get(DocumentVersion, submission.current_version_id)
    university = db.get(University, submission.university_id)
    faculty = db.get(Faculty, submission.faculty_id) if submission.faculty_id else None
    dtype = db.get(DocumentType, submission.document_type_id) if submission.document_type_id else None
    ruleset = db.get(RuleSet, submission.rule_set_id)
    findings = db.scalars(select(Finding).where(Finding.document_version_id == version.id)).all()
    open_blockers = [f for f in findings if f.status in {'open','revalidation_failed'} and f.severity in {'critical','major'}]
    if open_blockers:
        raise ValueError('Certificate cannot be generated while unresolved critical/major findings remain')
    cert_id = f"TC-{submission.university_id}-{submission.id}-V{version.version_number}"
    out = CERT_DIR / f"{cert_id}.pdf"
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(out), pagesize=A4, rightMargin=18*mm, leftMargin=18*mm, topMargin=18*mm, bottomMargin=18*mm)
    story = [Paragraph('Thesis Compliance Certificate', styles['Title']), Spacer(1, 8*mm)]
    rows = [
        ['Certificate ID', cert_id], ['University', university.name if university else str(submission.university_id)],
        ['Student', submission.student_name], ['Registration Number', submission.registration_number],
        ['Programme', submission.programme or ''], ['Faculty', faculty.name if faculty else ''],
        ['Document Type', dtype.name if dtype else ''], ['Document Version', f'v{version.version_number}'],
        ['SHA-256', version.sha256], ['Rule Set', f'{ruleset.name} ({ruleset.version})' if ruleset else str(submission.rule_set_id)],
        ['Decision', 'COMPLIANT'], ['Decision By', decision.actor_id], ['Decision Date', decision.created_at.isoformat()],
    ]
    t = Table(rows, colWidths=[45*mm, 125*mm])
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.5,colors.grey),('FONTNAME',(0,0),(-1,-1),'Helvetica'),('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('VALIGN',(0,0),(-1,-1),'TOP'),('PADDING',(0,0),(-1,-1),5)]))
    story += [t, Spacer(1, 8*mm), Paragraph('This certificate records the human compliance decision for the identified document version and rule-set version. It is not an academic assessment and does not attest to the originality, authorship, or scholarly merit of the work.', styles['BodyText']), Spacer(1, 5*mm), Paragraph(f'Officer comment: {decision.comment}', styles['BodyText'])]
    doc.build(story)
    return out, cert_id
