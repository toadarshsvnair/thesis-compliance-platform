"""Full compliance evaluation report: every finding on the current document
version, each marked against its guideline reference -- distinct from the
one-page certificate (services/certificate.py), which only exists after a
compliant decision. This report is available at any point in the review
process, compliant or not, since its purpose is to document the evaluation
itself, not certify an outcome.
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT
from sqlalchemy import select
from ..models import Submission, DocumentVersion, Finding, ComplianceDecision, RuleSet, University, Faculty, DocumentType

REPORT_DIR = Path('/tmp/thesis-compliance-evaluation-reports')
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# A finding's *marking* is derived from its review status, not just severity --
# a Major finding that's been reviewed and waived should read as resolved for
# reporting purposes, not as an outstanding failure.
_MARKING = {
    "open": ("Non-Compliant", colors.HexColor("#8C3B2E")),
    "reviewed": ("Reviewed", colors.HexColor("#1E3A5F")),
    "waived": ("Waived", colors.HexColor("#A67C3D")),
    "rejected": ("Rejected by reviewer", colors.HexColor("#6B6558")),
    "fix_approved": ("Fix applied", colors.HexColor("#2F6B4F")),
    "fixed": ("Resolved", colors.HexColor("#2F6B4F")),
    "revalidation_failed": ("Fix did not resolve", colors.HexColor("#8C3B2E")),
}


def _marking_for(status: str):
    return _MARKING.get(status, (status.replace("_", " ").title(), colors.grey))


def build_evaluation_report(db, submission: Submission) -> tuple[Path, str]:
    if not submission.current_version_id:
        raise ValueError("Submission has no current version")
    version = db.get(DocumentVersion, submission.current_version_id)
    university = db.get(University, submission.university_id)
    faculty = db.get(Faculty, submission.faculty_id) if submission.faculty_id else None
    dtype = db.get(DocumentType, submission.document_type_id) if submission.document_type_id else None
    ruleset = db.get(RuleSet, submission.rule_set_id)
    findings = db.scalars(
        select(Finding).where(Finding.document_version_id == version.id).order_by(Finding.id)
    ).all()
    decision = db.scalars(select(ComplianceDecision).where(
        ComplianceDecision.submission_id == submission.id,
        ComplianceDecision.document_version_id == version.id,
    ).order_by(ComplianceDecision.created_at.desc())).first()

    report_id = f"EVAL-{submission.university_id}-{submission.id}-V{version.version_number}"
    out = REPORT_DIR / f"{report_id}.pdf"

    styles = getSampleStyleSheet()
    cell_style = ParagraphStyle("cell", parent=styles["BodyText"], fontSize=8.5, leading=11, alignment=TA_LEFT)
    header_style = ParagraphStyle("cellHeader", parent=styles["BodyText"], fontSize=8.5, leading=11,
                                   textColor=colors.white, fontName="Helvetica-Bold")

    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        rightMargin=14 * mm, leftMargin=14 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
    )
    story = [
        Paragraph("Thesis Compliance Evaluation Report", styles["Title"]),
        Paragraph(
            "This report documents the deterministic formatting-compliance evaluation of the identified "
            "document version against the referenced rule-set version. It records findings and their "
            "current review status; it is not the compliance certificate and does not itself certify "
            "compliance, originality, authorship, or scholarly merit.",
            styles["BodyText"],
        ),
        Spacer(1, 6 * mm),
    ]

    meta_rows = [
        ["Report ID", report_id],
        ["University", university.name if university else str(submission.university_id)],
        ["Student", submission.student_name],
        ["Registration Number", submission.registration_number],
        ["Programme", submission.programme or "—"],
        ["Faculty", faculty.name if faculty else "—"],
        ["Document Type", dtype.name if dtype else "—"],
        ["Document Version", f"v{version.version_number}"],
        ["SHA-256", version.sha256],
        ["Rule Set", f"{ruleset.name} ({ruleset.version})" if ruleset else str(submission.rule_set_id)],
    ]
    meta_table = Table(meta_rows, colWidths=[45 * mm, 125 * mm])
    meta_table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [meta_table, Spacer(1, 6 * mm)]

    severity_counts: dict = {}
    open_major_or_critical = 0
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
        if f.status in {"open", "revalidation_failed"} and f.severity in {"Critical", "Major"}:
            open_major_or_critical += 1
    if findings:
        summary_line = "Total findings: " + str(len(findings)) + ". By severity: " + ", ".join(
            f"{sev} {count}" for sev, count in sorted(severity_counts.items())
        )
    else:
        summary_line = "No findings were recorded against this document version."
    story.append(Paragraph(summary_line, styles["BodyText"]))
    story.append(Paragraph(
        f"Unresolved Critical/Major findings: {open_major_or_critical}"
        + (" — a compliance certificate cannot be issued while this is nonzero." if open_major_or_critical else " — none outstanding."),
        styles["BodyText"],
    ))
    story.append(Spacer(1, 6 * mm))

    if findings:
        header = [Paragraph(h, header_style) for h in
                   ["Rule", "Severity", "Marking", "Location", "Requirement", "Expected / Actual", "Guideline"]]
        rows = [header]
        for f in findings:
            marking_text, marking_color = _marking_for(f.status)
            marking_style = ParagraphStyle("marking", parent=cell_style, textColor=marking_color, fontName="Helvetica-Bold")
            rows.append([
                Paragraph(f.rule_id, cell_style),
                Paragraph(f.severity, cell_style),
                Paragraph(marking_text, marking_style),
                Paragraph(f.location, cell_style),
                Paragraph(f.message, cell_style),
                Paragraph(f"<b>Expected:</b> {f.expected}<br/><b>Actual:</b> {f.actual}", cell_style),
                Paragraph(f.source_reference or "—", cell_style),
            ])
        col_widths = [16 * mm, 16 * mm, 22 * mm, 22 * mm, 38 * mm, 40 * mm, 22 * mm]
        findings_table = Table(rows, colWidths=col_widths, repeatRows=1)
        findings_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1E3A5F")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAF8F3")]),
        ]))
        story.append(findings_table)
    story.append(Spacer(1, 6 * mm))

    if decision:
        story.append(Paragraph(
            f"<b>Latest human compliance decision:</b> {decision.decision.upper()} — "
            f"recorded by {decision.actor_id} on {decision.created_at.strftime('%Y-%m-%d %H:%M UTC')}.",
            styles["BodyText"],
        ))
        story.append(Paragraph(f"Rationale: {decision.comment}", styles["BodyText"]))
    else:
        story.append(Paragraph("No human compliance decision has been recorded for this document version yet.", styles["BodyText"]))

    doc.build(story)
    return out, report_id
