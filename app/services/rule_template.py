"""Generates the sample rule-set bulk-upload template: the same column
structure the bulk-upload endpoint expects, pre-populated with the real,
current Alliance University rule set as working reference data -- not just
empty headers."""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

NAVY = "1E3A5F"
PAPER = "FAF8F3"
LINE = "DAD5C8"

COLUMNS = ["Rule ID", "Category", "Requirement", "Validation Method", "Severity", "Auto-Fix Allowed", "Source Reference", "Active"]

# The current, real Alliance PhD Thesis MVP rule catalogue (app/seed_rules.py).
# Tuple order: rule_id, category, requirement, validation_method, severity, auto_fix, source_reference
RULES = [
    ("PRE-001","Preliminary structure","Required preliminary sections exist","deterministic","Major",False,"Annexure 18/19"),
    ("PRE-013","Preliminary structure","Preliminary sections follow prescribed sequence","deterministic","Major",False,"Annexure 18"),
    ("PAGE-001","Page/Layout","A4 page size","deterministic","Major",True,"Annexure 19"),
    ("PAGE-002","Page/Layout","Left margin 1.5 inch","deterministic","Major",True,"Annexure 19"),
    ("PAGE-003","Page/Layout","Right margin 1 inch","deterministic","Major",True,"Annexure 19"),
    ("PAGE-004","Page/Layout","Top margin 1 inch","deterministic","Major",True,"Annexure 19"),
    ("PAGE-005","Page/Layout","Bottom margin 1 inch","deterministic","Major",True,"Annexure 19"),
    ("FONT-001","Typography","Times New Roman","deterministic","Major",True,"Annexure 19"),
    ("TITLE-001","Title","Prescribed title-page title formatting","deterministic","Major",True,"Annexure 19"),
    ("TAB-001","Tables","Chapter-wise table numbering","deterministic","Major",False,"Annexure 19"),
    ("TAB-003","Tables","Table caption style","deterministic","Major",True,"Annexure 19"),
    ("TAB-005","Tables/Cross-reference","Every table referenced in body","deterministic","Major",False,"Institutional rule"),
    ("FIG-001","Figures","Chapter-wise figure numbering","deterministic","Major",False,"Annexure 19"),
    ("FIG-003","Figures","Figure caption style","deterministic","Major",True,"Annexure 19"),
    ("FIG-004","Figures/Cross-reference","Every figure referenced in body","deterministic","Major",False,"Institutional rule"),
    ("XREF-002","Cross-reference","Broken figure references","deterministic","Major",False,"Institutional rule"),
    ("TOC-002","TOC","TOC page numbers correspond to rendered document","rendered","Major",True,"Annexure 19"),
    ("REF-002","References","Reference hanging indent and spacing","deterministic","Major",True,"Annexure 19"),
    ("REF-003","References","Reference list matches the faculty's required citation style","pattern-based","Review",False,"Faculty reference-style requirement"),
]

def build_sample_workbook(path):
    wb = openpyxl.Workbook()

    # ---- Instructions sheet ----
    info = wb.active
    info.title = "Instructions"
    info.sheet_view.showGridLines = False
    info.column_dimensions["A"].width = 100
    title_font = Font(name="Calibri", size=14, bold=True, color=NAVY)
    body_font = Font(name="Calibri", size=11)
    bold_font = Font(name="Calibri", size=11, bold=True)
    lines = [
        ("Rule Set Bulk Upload Template", title_font),
        ("", body_font),
        ("How to use this file:", bold_font),
        ("1. Fill in the 'Rules' sheet -- one row per rule. Do not change the header row or column order.", body_font),
        ("2. The 'Rules' sheet already contains the current Alliance PhD Thesis rule set as a real, working example.", body_font),
        ("   Replace it with your own rules, or edit these and add more below them.", body_font),
        ("3. Upload the saved file from Rule Management. Every row is checked before anything is added --", body_font),
        ("   if any row has a problem, you'll get a list of exactly what to fix, and nothing will be added", body_font),
        ("   until the file is clean.", body_font),
        ("", body_font),
        ("Column reference:", bold_font),
        ("Rule ID           Short unique code, e.g. PAGE-002. Letters, numbers, hyphens, underscores only.", body_font),
        ("Category          A short grouping label, e.g. 'Page/Layout', 'Typography', 'References'.", body_font),
        ("Requirement       The actual rule, in plain language -- this is what a reviewer will read.", body_font),
        ("Validation Method How the rule is checked: 'deterministic' (structural), 'rendered' (needs the", body_font),
        ("                  rendered PDF), 'pattern-based' (a heuristic check), or 'AI-assisted'.", body_font),
        ("Severity          One of: Major, Minor, Review.", body_font),
        ("Auto-Fix Allowed  Yes or No -- whether this is eligible for the controlled auto-fix feature.", body_font),
        ("                  (Only a small, hand-implemented set of rules can actually be auto-fixed", body_font),
        ("                  regardless of this flag -- ask before assuming a new rule can be.)", body_font),
        ("Source Reference  Where this rule comes from, e.g. 'Annexure 19' or 'Institutional rule'. Optional.", body_font),
        ("Active            Yes or No. Leave blank for Yes.", body_font),
    ]
    for i, (text, font) in enumerate(lines, start=1):
        cell = info.cell(row=i, column=1, value=text)
        cell.font = font

    # ---- Rules sheet ----
    ws = wb.create_sheet("Rules")
    ws.sheet_view.showGridLines = False

    header_fill = PatternFill(start_color=NAVY, end_color=NAVY, fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    thin = Side(style="thin", color=LINE)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    body_font2 = Font(name="Calibri", size=10.5)
    wrap = Alignment(wrap_text=True, vertical="top")

    for col_idx, name in enumerate(COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
        cell.alignment = Alignment(vertical="center")
    ws.row_dimensions[1].height = 20

    widths = [14, 22, 46, 18, 12, 16, 26, 10]
    for col_idx, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = w

    for row_idx, (rule_id, category, requirement, method, severity, auto_fix, source) in enumerate(RULES, start=2):
        values = [rule_id, category, requirement, method, severity, "Yes" if auto_fix else "No", source, "Yes"]
        for col_idx, val in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = body_font2
            cell.border = border
            cell.alignment = wrap
        ws.row_dimensions[row_idx].height = 30

    # Data validation dropdowns so a manual edit can't introduce a typo.
    severity_dv = DataValidation(type="list", formula1='"Major,Minor,Review"', allow_blank=False)
    severity_dv.error = "Severity must be one of: Major, Minor, Review."
    severity_dv.errorTitle = "Invalid severity"
    ws.add_data_validation(severity_dv)
    severity_dv.add(f"E2:E{len(RULES)+200}")

    yesno_dv = DataValidation(type="list", formula1='"Yes,No"', allow_blank=True)
    ws.add_data_validation(yesno_dv)
    yesno_dv.add(f"F2:F{len(RULES)+200}")
    yesno_dv.add(f"H2:H{len(RULES)+200}")

    ws.freeze_panes = "A2"
    wb.save(path)

if __name__ == "__main__":
    import sys
    build_sample_workbook(sys.argv[1] if len(sys.argv) > 1 else "rule_set_bulk_upload_template.xlsx")
    print("Saved template with", len(RULES), "example rules")
