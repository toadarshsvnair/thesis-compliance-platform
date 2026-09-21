"""Full compliance evaluation report: every finding on the current document
version, each marked against its guideline reference -- distinct from the
one-page certificate (services/certificate.py), which only exists after a
compliant decision. This report is available at any point in the review
process, compliant or not, since its purpose is to document the evaluation
itself, not certify an outcome.

Column widths below were chosen by actually rendering the table with
realistic and adversarial data (short hyphenated rule IDs, long messages)
and inspecting the output as an image -- the original widths caused rule IDs
like "PAGE-002" to break mid-word ("PAGE-0" / "02") because the column was
narrower than the token. Do not narrow the Rule/Severity columns again
without re-checking that.
"""
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_LEFT
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart
from sqlalchemy import select
from ..models import Submission, DocumentVersion, Finding, ComplianceDecision, RuleSet, University, Faculty, DocumentType, User

REPORT_DIR = Path('/tmp/thesis-compliance-evaluation-reports')
REPORT_DIR.mkdir(parents=True, exist_ok=True)

NAVY = colors.HexColor("#1E3A5F")
NAVY_DEEP = colors.HexColor("#122238")
BRICK = colors.HexColor("#8C3B2E")
OCHRE = colors.HexColor("#A67C3D")
FOREST = colors.HexColor("#2F6B4F")
MUTED_GREY = colors.HexColor("#6B6558")
PAPER = colors.HexColor("#FAF8F3")

SEVERITY_ORDER = ["Critical", "Major", "Review", "Minor"]
SEVERITY_COLOR = {"Critical": BRICK, "Major": BRICK, "Review": NAVY, "Minor": OCHRE}

# A finding's *marking* is derived from its review status, not just severity --
# a Major finding that's been reviewed and waived should read as resolved for
# reporting purposes, not as an outstanding failure.
_MARKING = {
    "open": ("Non-Compliant", BRICK),
    "reviewed": ("Reviewed", NAVY),
    "waived": ("Waived", OCHRE),
    "rejected": ("Rejected by reviewer", MUTED_GREY),
    "fix_approved": ("Fix applied", FOREST),
    "fixed": ("Resolved", FOREST),
    "revalidation_failed": ("Fix did not resolve", BRICK),
}


def _marking_for(status: str):
    return _MARKING.get(status, (status.replace("_", " ").title(), colors.grey))


def _severity_summary_chart(severity_counts: dict):
    """A quick-glance bar chart ahead of the detailed table, so a reader sees
    the shape of the evaluation before the line-by-line detail."""
    present = [s for s in SEVERITY_ORDER if severity_counts.get(s)]
    extra = [s for s in severity_counts if s not in SEVERITY_ORDER and severity_counts.get(s)]
    present += extra
    if not present:
        return None
    values = [severity_counts[s] for s in present]
    top = max(values)

    drawing = Drawing(480, 130)
    chart = VerticalBarChart()
    chart.x, chart.y = 45, 20
    chart.width, chart.height = 420, 95
    chart.data = [values]
    chart.categoryAxis.categoryNames = present
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 9
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = top + 1
    chart.valueAxis.valueStep = 1 if top <= 10 else max(1, (top + 1) // 8)
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 8
    chart.barWidth = 16
    chart.groupSpacing = 22
    chart.barLabels.fontName = "Helvetica-Bold"
    chart.barLabels.fontSize = 9
    chart.barLabelFormat = "%d"
    chart.barLabels.nudge = 8
    for i, sev in enumerate(present):
        chart.bars[(0, i)].fillColor = SEVERITY_COLOR.get(sev, MUTED_GREY)
    drawing.add(chart)
    return drawing


def build_evaluation_report(db, submission: Submission) -> tuple[Path, str]:
    if not submission.current_version_id:
        raise ValueError("Submission has no current version")
    version = db.get(DocumentVersion, submission.current_version_id)
    university = db.get(University, submission.university_id)
    owner = db.get(User, submission.owner_user_id) if submission.owner_user_id else None
    faculty_id = (owner.faculty_id if owner and owner.faculty_id else submission.faculty_id)
    faculty = db.get(Faculty, faculty_id) if faculty_id else None
    programme = (owner.programme if owner and owner.programme else submission.programme)
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
    title_style = ParagraphStyle("reportTitle", parent=styles["Title"], textColor=NAVY_DEEP, fontSize=18, spaceAfter=2)
    subtitle_style = ParagraphStyle("reportSubtitle", parent=styles["BodyText"], textColor=MUTED_GREY, fontSize=9.5, spaceAfter=0)
    section_style = ParagraphStyle("section", parent=styles["Heading2"], textColor=NAVY_DEEP, fontSize=12.5, spaceBefore=4, spaceAfter=6)
    body_style = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=13)
    cell_style = ParagraphStyle("cell", parent=styles["BodyText"], fontSize=8.5, leading=11, alignment=TA_LEFT)
    header_style = ParagraphStyle("cellHeader", parent=styles["BodyText"], fontSize=8.5, leading=11,
                                   textColor=colors.white, fontName="Helvetica-Bold")

    doc = SimpleDocTemplate(
        str(out), pagesize=A4,
        rightMargin=14 * mm, leftMargin=14 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
    )
    story = [
        Paragraph("Thesis Compliance Evaluation Report", title_style),
        Paragraph(
            "Deterministic formatting-compliance evaluation against the referenced rule-set version. "
            "This records findings and their current review status; it is not the compliance "
            "certificate and does not itself certify compliance, originality, authorship, or "
            "scholarly merit.",
            subtitle_style,
        ),
        Spacer(1, 5 * mm),
    ]

    meta_rows = [
        ["Report ID", report_id],
        ["University", university.name if university else str(submission.university_id)],
        ["Student", submission.student_name],
        ["Registration Number", submission.registration_number],
        ["Programme", programme or "—"],
        ["Faculty", faculty.name if faculty else "—"],
        ["Document Type", dtype.name if dtype else "—"],
        ["Document Version", f"v{version.version_number}"],
        ["SHA-256", version.sha256],
        ["Rule Set", f"{ruleset.name} ({ruleset.version})" if ruleset else str(submission.rule_set_id)],
    ]
    meta_table = Table(meta_rows, colWidths=[45 * mm, 125 * mm])
    meta_table.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#DAD5C8")),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), NAVY_DEEP),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#DAD5C8")),
    ]))
    story += [meta_table, Spacer(1, 7 * mm)]

    severity_counts: dict = {}
    open_major_or_critical = 0
    for f in findings:
        severity_counts[f.severity] = severity_counts.get(f.severity, 0) + 1
        if f.status in {"open", "revalidation_failed"} and f.severity in {"Critical", "Major"}:
            open_major_or_critical += 1

    story.append(Paragraph("Summary", section_style))
    if findings:
        chart = _severity_summary_chart(severity_counts)
        if chart:
            story.append(chart)
        summary_line = f"Total findings: {len(findings)} across {len(severity_counts)} severity level(s)."
    else:
        summary_line = "No findings were recorded against this document version."
    story.append(Paragraph(summary_line, body_style))
    status_note = (
        f"<b>Unresolved Critical/Major findings: {open_major_or_critical}</b>"
        + (" — a compliance certificate cannot be issued while this is nonzero."
           if open_major_or_critical else " — none outstanding.")
    )
    story.append(Paragraph(status_note, body_style))
    story.append(Spacer(1, 7 * mm))

    if findings:
        story.append(Paragraph("Findings Detail", section_style))
        header = [Paragraph(h, header_style) for h in
                   ["Rule", "Severity", "Marking", "Location", "Requirement", "Expected / Actual", "Guideline"]]
        rows = [header]
        for f in sorted(findings, key=lambda x: (SEVERITY_ORDER.index(x.severity) if x.severity in SEVERITY_ORDER else 99, x.id)):
            marking_text, marking_color = _marking_for(f.status)
            marking_style = ParagraphStyle(f"marking{f.id}", parent=cell_style, textColor=marking_color, fontName="Helvetica-Bold")
            rows.append([
                Paragraph(f.rule_id, cell_style),
                Paragraph(f.severity, cell_style),
                Paragraph(marking_text, marking_style),
                Paragraph(f.location, cell_style),
                Paragraph(f.message, cell_style),
                Paragraph(f"<b>Expected:</b> {f.expected}<br/><b>Actual:</b> {f.actual}", cell_style),
                Paragraph(f.source_reference or "—", cell_style),
            ])
        # Widths verified by rendering to an image and inspecting -- see the
        # module docstring. Total = 182mm = A4 width minus this doc's margins.
        # The Marking column needs real width because it's bold text, which
        # is wider per character than the body text elsewhere in the table.
        col_widths = [20 * mm, 16 * mm, 30 * mm, 20 * mm, 34 * mm, 34 * mm, 24 * mm]
        findings_table = Table(rows, colWidths=col_widths, repeatRows=1)
        findings_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY_DEEP),
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, NAVY_DEEP),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#DAD5C8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PAPER]),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#DAD5C8")),
        ]))
        story.append(findings_table)
    story.append(Spacer(1, 7 * mm))

    story.append(Paragraph("Compliance Decision", section_style))
    if decision:
        story.append(Paragraph(
            f"<b>Latest human compliance decision:</b> {decision.decision.replace('_', ' ').upper()} — "
            f"recorded by {decision.actor_id} on {decision.created_at.strftime('%Y-%m-%d %H:%M UTC')}.",
            body_style,
        ))
        story.append(Paragraph(f"Rationale: {decision.comment}", body_style))
    else:
        story.append(Paragraph("No human compliance decision has been recorded for this document version yet.", body_style))

    doc.build(story)
    return out, report_id
