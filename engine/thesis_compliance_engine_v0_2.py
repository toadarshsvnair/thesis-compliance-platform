
"""
Thesis Compliance Validation Engine v0.2
Alliance University PhD thesis MVP.

v0.2 expands deterministic validation against the supplied Annexure 18
Ph.D. Thesis Template and Annexure 19 Guidelines for Thesis Preparation.

Important:
- The original DOCX is never modified.
- Deterministic checks are separated from rendered-layout checks.
- Some checks remain advisory because DOCX XML does not expose final
  Word pagination/layout with complete fidelity.
- AI is not used in this engine.
"""

from pathlib import Path
from collections import Counter, defaultdict
import argparse, hashlib, json, re, subprocess, shutil, sys, zipfile, xml.etree.ElementTree as ET
from docx import Document
from docx.oxml.ns import qn
from docx.enum.text import WD_ALIGN_PARAGRAPH

EXPECTED = {
    "page_width_in": 8.27,
    "page_height_in": 11.69,
    "margins_in": {"left": 1.50, "right": 1.00, "top": 1.00, "bottom": 1.00},
    "font": "Times New Roman",
    "preliminary": [
        "DECLARATION", "CERTIFICATE", "DEDICATION", "ACKNOWLEDGEMENT",
        "ABSTRACT", "PREFACE", "TABLE OF CONTENTS", "LIST OF TABLES",
        "LIST OF FIGURES", "LIST OF ABBREVIATIONS", "LIST OF APPENDICES"
    ],
}

# Maps each tracked preliminary section to its own catalogue rule ID (Rule
# Catalogue v0.2). Previously every missing section was reported under the
# single generic "PRE-001", which meant a reviewer looking up "PRE-001" in the
# approved catalogue saw "Title Page" no matter which section was actually
# missing. PRE-001 itself is handled separately below (see the PRE-001..015
# block) since the catalogue defines it specifically as title-page presence,
# which none of these eleven tracked sections represent.
PRELIM_RULE_IDS = {
    "DECLARATION": "PRE-002",
    "CERTIFICATE": "PRE-003",
    "DEDICATION": "PRE-004",
    "ACKNOWLEDGEMENT": "PRE-005",
    "ABSTRACT": "PRE-006",
    "PREFACE": "PRE-007",
    "TABLE OF CONTENTS": "PRE-008",
    "LIST OF TABLES": "PRE-009",
    "LIST OF FIGURES": "PRE-010",
    "LIST OF ABBREVIATIONS": "PRE-011",
    "LIST OF APPENDICES": "PRE-012",
}

# Anchored at both ends (only "CHAPTER N", optionally with a trailing colon or
# period) so a heading like "CHAPTER 2" isn't confused with body prose that
# happens to start the same way, e.g. a "structure of the thesis" paragraph
# such as "Chapter 2 – The comprehensive literature review discusses...".
# The original, looser pattern (matched as a prefix) counted both as the same
# kind of thing, which could make CHAP-001's sequential-numbering check see
# duplicate/out-of-order numbers that were really just narrative mentions.
CHAPTER_HEADING_RE = re.compile(r"^CHAPTER\s+(\d+)\s*[:.]?\s*$", re.I)

SEVERITY = {"Critical": 4, "Major": 3, "Review": 2, "Minor": 1}

def clean(s):
    return re.sub(r"\s+", " ", (s or "")).strip()

def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", clean(s).lower()).strip()

def inches(v):
    return None if v is None else float(v) / 914400.0

def add(findings, rule_id, category, severity, location, expected, actual,
        message, auto_fix=False, confidence=1.0, basis="Annexure 18/19"):
    findings.append({
        "rule_id": rule_id, "category": category, "severity": severity,
        "location": location, "expected": expected, "actual": actual,
        "message": message, "auto_fix": "Yes" if auto_fix else "No",
        "confidence": round(confidence, 2), "basis": basis
    })

def paragraph_runs(p):
    return [r for r in p.runs if clean(r.text)]

def run_font_names(p):
    vals = []
    for r in paragraph_runs(p):
        vals.append((r.font.name or "", r.font.size.pt if r.font.size else None))
    return vals

def paragraph_is_heading(p):
    st = (p.style.name or "").lower() if p.style else ""
    return st.startswith("heading") or bool(re.match(r"^(chapter\s+\d+|[1-9]\d*(?:\.\d+){0,3}\s+)", clean(p.text), re.I))

def is_caption(text, kind):
    if kind == "table":
        return re.match(r"^Table\s+\d+\.\d+\s*(?:[:.-]|$)", text, re.I) is not None
    return re.match(r"^(?:Figure|Fig\.?)\s*\.?\s*\d+\.\d+\s*(?:[:.-]|$)", text, re.I) is not None

def caption_number(text, kind):
    if kind == "table":
        m = re.match(r"^Table\s+(\d+\.\d+)\s*(?:[:.-]|$)", text, re.I)
    else:
        m = re.match(r"^(?:Figure|Fig\.?)\s*\.?\s*(\d+\.\d+)\s*(?:[:.-]|$)", text, re.I)
    return m.group(1) if m else None

def paragraph_format_snapshot(p):
    pf = p.paragraph_format
    return {
        "style": p.style.name if p.style else "",
        "alignment": str(p.alignment) if p.alignment is not None else None,
        "left_indent_in": inches(pf.left_indent),
        "right_indent_in": inches(pf.right_indent),
        "first_line_indent_in": inches(pf.first_line_indent),
        "space_before_pt": pf.space_before.pt if pf.space_before else 0,
        "space_after_pt": pf.space_after.pt if pf.space_after else 0,
        "line_spacing": str(pf.line_spacing) if pf.line_spacing is not None else None,
    }

def extract_body_elements(doc):
    body = doc._element.body
    for child in body.iterchildren():
        if child.tag == qn("w:p"):
            yield ("p", child)
        elif child.tag == qn("w:tbl"):
            yield ("tbl", child)

def element_paragraph_text(el):
    return clean("".join(t.text or "" for t in el.iter(qn("w:t"))))

def document_text(doc):
    parts = []
    for kind, el in extract_body_elements(doc):
        if kind == "p":
            parts.append(element_paragraph_text(el))
        else:
            for p in el.iter(qn("w:p")):
                txt = element_paragraph_text(p)
                if txt:
                    parts.append(txt)
    return "\n".join(x for x in parts if x)

def parse_captions_and_body_refs(doc):
    captions = {"table": [], "figure": []}
    refs = {"table": set(), "figure": set()}
    paras = list(doc.paragraphs)
    for idx, p in enumerate(paras, 1):
        t = clean(p.text)
        for kind in ("table", "figure"):
            n = caption_number(t, kind)
            if n:
                captions[kind].append((n, idx, p))
        # Avoid counting a caption as its own body reference.
        body = t
        if is_caption(body, "table"):
            body = ""
        if is_caption(body, "figure"):
            body = ""
        refs["table"].update(re.findall(r"\bTable\s+(\d+\.\d+)\b", body, re.I))
        refs["figure"].update(re.findall(r"\b(?:Figure|Fig\.?)\s*\.?\s*(\d+\.\d+)\b", body, re.I))
    return captions, refs

def locate_section(paragraphs, names):
    wanted = {norm(x) for x in names}
    for i, p in enumerate(paragraphs):
        if norm(p.text) in wanted:
            return i
    return None

def heading_records(doc):
    recs = []
    for i, p in enumerate(doc.paragraphs, 1):
        t = clean(p.text)
        if not t:
            continue
        st = p.style.name if p.style else ""
        m = re.match(r"^(\d+(?:\.\d+){0,3})\s+(.+)$", t)
        if m:
            recs.append((i, m.group(1), m.group(2), st))
        elif re.match(r"^Chapter\s+\d+", t, re.I):
            recs.append((i, re.search(r"\d+", t).group(0), t, st))
    return recs

def parse_toc_entries(doc):
    entries = []
    for i, p in enumerate(doc.paragraphs, 1):
        t = clean(p.text)
        if not t:
            continue
        # Common Word TOC text extraction: heading + trailing page number.
        m = re.match(r"^(.*?)(?:\s+|\.{2,}|…+)(\d+)$", t)
        if m:
            label = clean(m.group(1).rstrip("."))
            page = int(m.group(2))
            if len(label) > 2:
                entries.append((label, page, i))
    return entries

def parse_references(doc):
    refs_start = None
    refs_end = len(doc.paragraphs)
    for i, p in enumerate(doc.paragraphs):
        t = norm(p.text)
        if t in {"references", "bibliography"}:
            refs_start = i + 1
            break
    if refs_start is None:
        return None, []
    # Stop at first appendix heading after references.
    for j in range(refs_start, len(doc.paragraphs)):
        if re.match(r"^(appendix|annexure)\b", clean(doc.paragraphs[j].text), re.I):
            refs_end = j
            break
    refs = [(i+1, p) for i, p in enumerate(doc.paragraphs[refs_start:refs_end], refs_start) if clean(p.text)]
    return refs_start, refs

def validate(path, rendered_pdf=None):
    path = Path(path)
    doc = Document(path)
    findings = []
    paragraphs = [p for p in doc.paragraphs if clean(p.text)]
    texts = [clean(p.text) for p in paragraphs]

    # PAGE-001..005
    for n, sec in enumerate(doc.sections, 1):
        w, h = inches(sec.page_width), inches(sec.page_height)
        if abs(w-EXPECTED["page_width_in"]) > .03 or abs(h-EXPECTED["page_height_in"]) > .03:
            add(findings, "PAGE-001", "Page/Layout", "Major", f"section {n}",
                "A4 (8.27 × 11.69 in)", f"{w:.2f} × {h:.2f} in",
                "Section page size is not A4.", True)
        for rid, label, actual, exp in [
            ("PAGE-002","left margin",sec.left_margin,1.5),
            ("PAGE-003","right margin",sec.right_margin,1.0),
            ("PAGE-004","top margin",sec.top_margin,1.0),
            ("PAGE-005","bottom margin",sec.bottom_margin,1.0)]:
            a = inches(actual)
            if a is not None and abs(a-exp) > .02:
                add(findings, rid, "Page/Layout", "Major", f"section {n}",
                    f"{exp:.2f} in", f"{a:.2f} in",
                    f"{label.title()} does not match the prescribed value.", True)

    # FONT-001..003
    font_counts = Counter()
    non_tnr = []
    indented = 0
    spacing_counts = Counter()
    for i, p in enumerate(paragraphs, 1):
        for r in paragraph_runs(p):
            font_counts[(r.font.name or "", r.font.size.pt if r.font.size else None)] += len(clean(r.text))
            if r.font.name and r.font.name.lower() != EXPECTED["font"].lower():
                non_tnr.append((i, r.font.name, clean(r.text)[:60]))
        fi = inches(p.paragraph_format.first_line_indent)
        if fi and fi > .01:
            indented += 1
        sa = p.paragraph_format.space_after.pt if p.paragraph_format.space_after else 0
        spacing_counts[round(sa,1)] += 1
    if font_counts:
        dominant_name = Counter()
        for (name, size), count in font_counts.items():
            dominant_name[name or "(unspecified)"] += count
        dom = dominant_name.most_common(1)[0][0]
        if dom.lower() != EXPECTED["font"].lower():
            add(findings, "FONT-001", "Typography", "Major", "document",
                "Times New Roman", dom,
                "Dominant run font differs from Times New Roman.", True)
    if indented:
        add(findings, "FONT-002", "Paragraph", "Minor", "body paragraphs",
            "No first-line indentation", f"{indented} paragraphs have first-line indentation",
            "First-line indentation is present; review against the guideline's body-text rule.", True,
            basis="Annexure 19 p.6")
    # 30 pt vertical space is a guideline expectation; report dominant deviation, not every paragraph.
    near_30 = sum(v for k,v in spacing_counts.items() if 27 <= k <= 33)
    if paragraphs and near_30 / len(paragraphs) < 0.50:
        dom_space = spacing_counts.most_common(1)[0][0] if spacing_counts else 0
        add(findings, "FONT-003", "Paragraph", "Review", "body paragraphs",
            "About 30 pt vertical space between paragraphs",
            f"Only {near_30}/{len(paragraphs)} non-empty paragraphs have ~30 pt after-spacing; dominant observed after-spacing={dom_space} pt",
            "Paragraph spacing differs from the stated guideline expectation; inspect by document region.", True)

    # PRE-001..015
    positions = {}
    for expected in EXPECTED["preliminary"]:
        aliases = [expected]
        if expected == "LIST OF ABBREVIATIONS":
            aliases += ["LIST OF ABBREVIATION"]
        pos = locate_section(paragraphs, aliases)
        if pos is None:
            add(findings, PRELIM_RULE_IDS[expected], "Preliminary structure", "Major", "document",
                f"Section '{expected}' exists", "Not detected",
                f"Required preliminary section '{expected}' was not detected.", False)
        else:
            positions[expected] = pos
    if positions and min(positions.values()) == 0:
        earliest = min(positions, key=positions.get)
        add(findings, "PRE-001", "Preliminary structure", "Major", "document",
            "Distinct title-page content precedes the first preliminary section",
            "No content detected before the first preliminary section",
            f"'{earliest}' appears to be the very first content in the document; no distinct title-page content was detected ahead of it.",
            False, 0.7)
    if len(positions) == len(EXPECTED["preliminary"]):
        actual_order = sorted(positions, key=lambda k: positions[k])
        if actual_order != EXPECTED["preliminary"]:
            add(findings, "PRE-013", "Preliminary structure", "Major", "preliminary pages",
                " → ".join(EXPECTED["preliminary"]),
                " → ".join(actual_order),
                "Preliminary-section sequence differs from the supplied template.", False)
    if "LIST OF ABBREVIATIONS" in positions:
        idx = positions["LIST OF ABBREVIATIONS"]
        after = [p.text for p in paragraphs[idx+1:idx+8] if clean(p.text)]
        if not after:
            add(findings, "PRE-014", "Preliminary structure", "Major",
                "List of Abbreviations", "Actual abbreviation entries", "Heading detected but no nearby content detected",
                "List of Abbreviations appears to lack entries.", False)

    # INTRO-001/002: style of each preliminary-section heading itself, and the
    # body text immediately following it. ("Introductory" in the catalogue
    # covers the preliminary pages as a category -- Declaration, Abstract,
    # Acknowledgement, etc. -- not a single standalone "introduction" section.)
    intro_heading_issues = []
    intro_body_issues = []
    for name, idx in positions.items():
        hp = paragraphs[idx]
        runs = paragraph_runs(hp)
        sizes = [r.font.size.pt for r in runs if r.font.size]
        bad = []
        if sizes and abs(max(sizes) - 14) > 0.5:
            bad.append(f"size={sizes}")
        if runs and any(r.bold is False for r in runs):
            bad.append("not bold")
        if hp.alignment is not None and hp.alignment != WD_ALIGN_PARAGRAPH.CENTER:
            bad.append(f"alignment={hp.alignment}")
        if bad:
            intro_heading_issues.append((name, "; ".join(bad)))
        if idx + 1 < len(paragraphs):
            bp = paragraphs[idx + 1]
            brs = paragraph_runs(bp)
            bsizes = [r.font.size.pt for r in brs if r.font.size]
            bbad = []
            if bsizes and abs(max(bsizes) - 12) > 0.5:
                bbad.append(f"size={bsizes}")
            if bp.alignment is not None and bp.alignment != WD_ALIGN_PARAGRAPH.JUSTIFY:
                bbad.append(f"alignment={bp.alignment}")
            if bbad:
                intro_body_issues.append((name, "; ".join(bbad)))
    if intro_heading_issues:
        add(findings, "INTRO-001", "Introductory", "Major", "preliminary section headings",
            "14 pt bold, centered", "; ".join(f"{n}: {i}" for n, i in intro_heading_issues[:6]),
            "One or more preliminary-section headings differ from the prescribed style.", True, 0.7)
    if intro_body_issues:
        add(findings, "INTRO-002", "Introductory", "Major", "preliminary section body text",
            "12 pt regular, justified", "; ".join(f"{n}: {i}" for n, i in intro_body_issues[:6]),
            "Body text immediately following one or more preliminary-section headings differs from the prescribed style.", True, 0.6)

    # Title page style checks (TITLE-001..003) — use first meaningful paragraphs.
    meaningful = [(i+1,p) for i,p in enumerate(paragraphs[:30])]
    title_candidates = [x for x in meaningful if len(clean(x[1].text)) > 10]
    if title_candidates:
        title_i, title_p = title_candidates[0]
        title = clean(title_p.text)
        runs = paragraph_runs(title_p)
        sizes = [r.font.size.pt for r in runs if r.font.size]
        if sizes and abs(max(sizes)-16) > 0.5:
            add(findings, "TITLE-001", "Title", "Major", f"paragraph {title_i}",
                "16 pt Times New Roman, bold, centered, all caps, double-spaced",
                f"observed sizes={sizes}, alignment={title_p.alignment}",
                "First title-page candidate does not match the prescribed title style.", True)
        if title != title.upper():
            add(findings, "TITLE-001", "Title", "Major", f"paragraph {title_i}",
                "All caps", title, "Thesis title is not all caps.", True)

    # TITLE-002 (author/course line) is intentionally not implemented as a
    # deterministic check. The catalogue models it as a single styled line,
    # but real theses split this across several distinct lines (a degree
    # line, a "by" line, the author's name, department, college) with no
    # reliable positional marker distinguishing "the" author/course line from
    # the others -- forcing a positional heuristic here risks confidently
    # flagging the wrong line. This is better suited to the AI-assisted
    # semantic layer (or a documented catalogue revision) than a guess here.

    # TITLE-003: institution name/address, found by content rather than
    # position (the title-page region varies in line count between theses).
    # Restricted to an all-caps line so an incidental mention like "Thesis
    # submitted to Alliance University" isn't mistaken for the formal
    # all-caps institution-name display line the guideline actually means.
    title_region_end = min(positions.values()) if positions else 30
    university_candidates = [(i+1, p) for i, p in enumerate(paragraphs[:title_region_end])
                              if re.search(r"\bUNIVERSITY\b", p.text, re.I)
                              and clean(p.text) == clean(p.text).upper()]
    if university_candidates:
        uni_i, uni_p = university_candidates[0]
        runs = paragraph_runs(uni_p)
        sizes = [r.font.size.pt for r in runs if r.font.size]
        issues = []
        if sizes and abs(max(sizes) - 12) > 0.5:
            issues.append(f"size={sizes}")
        if runs and any(r.bold is True for r in runs):
            issues.append("bold (expected regular)")
        if issues:
            add(findings, "TITLE-003", "Title", "Major", f"paragraph {uni_i}",
                "12 pt regular, single-spaced, all caps, centered",
                f"'{clean(uni_p.text)}': " + "; ".join(issues),
                "University name/address line style differs from the guideline.", True, 0.6)

    # Headings / chapter structure
    heads = heading_records(doc)
    explicit_chapters = []
    for i,p in enumerate(paragraphs,1):
        t=clean(p.text)
        m=CHAPTER_HEADING_RE.match(t)
        if m:
            explicit_chapters.append((i,int(m.group(1)),t,p))
    nums=[x[1] for x in explicit_chapters]
    if nums:
        expected=list(range(min(nums), max(nums)+1))
        if nums != expected:
            add(findings, "CHAP-001", "Chapter", "Major", "chapter headings",
                "Sequential chapter numbering", str(nums),
                "Chapter numbering is not sequential.", False)

    # CHAP-002: the chapter-heading title on the paragraph immediately
    # following "CHAPTER N" (e.g. "CHAPTER 1" / "INTRODUCTION" as two lines).
    for (i, num, text, p) in explicit_chapters:
        if i < len(paragraphs):
            heading_p = paragraphs[i]
            runs = paragraph_runs(heading_p)
            sizes = [r.font.size.pt for r in runs if r.font.size]
            issues = []
            if sizes and abs(max(sizes) - 14) > 0.5:
                issues.append(f"size={sizes}")
            if runs and any(r.bold is False for r in runs):
                issues.append("not bold")
            if heading_p.alignment is not None and heading_p.alignment != WD_ALIGN_PARAGRAPH.CENTER:
                issues.append(f"alignment={heading_p.alignment}")
            if issues:
                add(findings, "CHAP-002", "Chapter", "Major", f"paragraph {i+1}",
                    "14 pt bold, centered chapter heading",
                    f"'{clean(heading_p.text)}': " + "; ".join(issues),
                    "Chapter heading style differs from the guideline.", True, 0.75)

    # SEC-001/002/003: section/subsection/sub-subsection heading style, keyed
    # by numbering depth (1.1 = section, 1.1.1 = subsection, 1.2.2.1 =
    # sub-subsection). Uses doc.paragraphs directly (not the pre-filtered
    # `paragraphs` list) purely for a simple, self-contained loop.
    SEC_RULE_BY_DEPTH = {1: "SEC-001", 2: "SEC-002", 3: "SEC-003"}
    SEC_EXPECTED_STYLE = {1: "12 pt bold", 2: "12 pt bold italic", 3: "12 pt italic (not bold)"}
    SEC_LABEL = {1: "section", 2: "subsection", 3: "sub-subsection"}
    sec_issues = defaultdict(list)
    for p in doc.paragraphs:
        t = clean(p.text)
        if not t:
            continue
        m = re.match(r"^(\d+(?:\.\d+){1,3})\s+\S", t)
        if not m:
            continue
        depth = m.group(1).count(".")
        if depth not in SEC_RULE_BY_DEPTH:
            continue
        runs = paragraph_runs(p)
        if not runs:
            continue
        sizes = [r.font.size.pt for r in runs if r.font.size]
        bolds = [r.bold for r in runs]
        italics = [r.italic for r in runs]
        bad = []
        if sizes and abs(max(sizes) - 12) > 0.5:
            bad.append(f"size={sizes}")
        if depth in (1, 2) and any(b is False for b in bolds):
            bad.append("not bold")
        if depth in (2, 3) and any(it is False for it in italics):
            bad.append("not italic")
        if depth == 1 and any(it is True for it in italics):
            bad.append("unexpectedly italic")
        if bad:
            sec_issues[depth].append((m.group(1), "; ".join(bad)))
    for depth, entries in sec_issues.items():
        add(findings, SEC_RULE_BY_DEPTH[depth], "Sections", "Major", "section headings",
            SEC_EXPECTED_STYLE[depth], f"{len(entries)} heading(s) differ; examples={entries[:5]}",
            f"One or more {SEC_LABEL[depth]} headings differ from the prescribed style.", True, 0.75)

    # Tables/figures and cross references.
    # DOCX paragraph extraction misses some captions embedded in text boxes/shapes
    # or table cells. When a rendered PDF is available, use its visible text as
    # a second evidence surface.
    captions, refs = parse_captions_and_body_refs(doc)

    if rendered_pdf and Path(rendered_pdf).exists():
        try:
            import fitz
            pdf=fitz.open(rendered_pdf)
            page_text=[p.get_text("text") for p in pdf]
            chapter_start=next((i for i,t in enumerate(page_text) if re.search(r"\bCHAPTER\s+1\b",t,re.I)),0)
            # Find visible captions in the thesis body, excluding preliminary lists.
            rendered_caps={"table":{}, "figure":{}}
            rendered_refs={"table":set(), "figure":set()}
            for pi in range(chapter_start, len(page_text)):
                for raw in page_text[pi].splitlines():
                    line=clean(raw)
                    if not line: continue
                    mt=re.match(r"^Table\s+(\d+\.\d+)\s*(?:[:.-]|\s+)(.+)$",line,re.I)
                    mf=re.match(r"^(?:Figure|Fig\.)\s*\.?\s*(\d+\.\d+)\s*(?:[:.-]|\s+)(.+)$",line,re.I)
                    if mf and re.match(r"^(?:following|shows|displays|illustrates|depicts|display|shows how|is shown|was shown)\b", mf.group(2), re.I):
                        mf=None
                    if mt:
                        rendered_caps["table"].setdefault(mt.group(1),(pi+1,line))
                        continue
                    if mf:
                        rendered_caps["figure"].setdefault(mf.group(1),(pi+1,line))
                        continue
                    # Body references: ignore lines that are themselves captions.
                    rendered_refs["table"].update(re.findall(r"\bTable\s+(\d+\.\d+)\b",line,re.I))
                    rendered_refs["figure"].update(re.findall(r"\b(?:Figure|Fig\.)\s*\.?\s*(\d+\.\d+)\b",line,re.I))
            # Merge rendered caption evidence with DOCX evidence.
            for kind in ("table","figure"):
                existing={x[0] for x in captions[kind]}
                for n,(page,line) in rendered_caps[kind].items():
                    if n not in existing:
                        captions[kind].append((n, f"rendered page {page}", page))
            # Rendered body references are stronger for text-box captions and
            # cross-references that are not represented in doc.paragraphs.
            refs["table"].update(rendered_refs["table"])
            refs["figure"].update(rendered_refs["figure"])
        except Exception as e:
            add(findings, "XREF-003", "Tables/Figures", "Review", "rendered document",
                "Rendered caption/reference extraction", "Parser error",
                f"Rendered tables/figures cross-reference extraction could not be completed: {e}",
                False, 0.5)

    for kind, rid in [("table","TAB-001"),("figure","FIG-001")]:
        nums=[x[0] for x in captions[kind]]
        if len(nums) != len(set(nums)):
            add(findings, rid, "Tables/Figures", "Major", f"{kind} captions",
                "Unique chapter-wise numbers", str(nums),
                f"Duplicate {kind} caption numbers detected.", False)
        for n, idx, p in captions[kind]:
            if isinstance(p, int):
                # Rendered caption; style cannot be reliably inspected from PDF text alone.
                continue
            runs=paragraph_runs(p)
            sizes=[r.font.size.pt for r in runs if r.font.size]
            if sizes and max(abs(s-11) for s in sizes) > .5:
                add(findings, "TAB-003" if kind=="table" else "FIG-003",
                    "Tables/Figures", "Major", f"paragraph {idx}",
                    "11 pt italic, single-spaced, centered",
                    f"sizes={sizes}; bold={any(r.bold for r in runs)}; italic={all((r.italic is True) for r in runs) if runs else None}",
                    f"{kind.title()} caption style differs from the guideline.", True)
            try:
                ch, seq = map(int, n.split("."))
                if seq < 1: raise ValueError
            except Exception:
                add(findings, rid, "Tables/Figures", "Major", f"paragraph {idx}",
                    "Chapter-wise number such as 4.1", n,
                    f"Unparseable {kind} numbering.", False)

        cap_nums={x[0] for x in captions[kind]}
        for n, idx, _ in captions[kind]:
            if n not in refs[kind]:
                add(findings, "TAB-005" if kind=="table" else "FIG-004",
                    "Tables/Cross-reference" if kind=="table" else "Figures/Cross-reference",
                    "Major", f"paragraph {idx}",
                    f"{kind.title()} {n} referenced in body", "No matching body reference detected",
                    f"{kind.title()} {n} appears to lack a body-text reference.", False)
        for n in sorted(refs[kind]-cap_nums):
            add(findings, "XREF-001" if kind=="table" else "XREF-002",
                "Cross-reference", "Major", "body text",
                f"{kind.title()} {n} exists", "No matching caption detected",
                f"Broken {kind} reference: {kind.title()} {n}.", False)

    # TAB-002/FIG-002: caption position relative to its table/figure.
    # Table captions are expected immediately above the table; figure
    # captions immediately below the figure. Real documents sometimes have a
    # paragraph or two of spacing around a figure, so FIG-002 checks a small
    # trailing window rather than requiring strict adjacency; TAB-002 checks
    # strict adjacency since that's the only pattern observed in practice.
    body_seq = list(extract_body_elements(doc))
    tab002_bad, fig002_bad = [], []
    for idx, (kind, el) in enumerate(body_seq):
        if kind != "p":
            continue
        t = clean(element_paragraph_text(el))
        if is_caption(t, "table"):
            nxt = body_seq[idx + 1] if idx + 1 < len(body_seq) else None
            if not (nxt and nxt[0] == "tbl"):
                tab002_bad.append(t[:60])
        elif is_caption(t, "figure"):
            window = body_seq[max(0, idx - 3):idx]
            has_image = any(
                k == "p" and (e.findall(".//" + qn("w:drawing")) or e.findall(".//" + qn("w:pict")))
                for k, e in window
            )
            if not has_image:
                fig002_bad.append(t[:60])
    if tab002_bad:
        add(findings, "TAB-002", "Tables", "Major", "table captions",
            "Caption positioned immediately above its table",
            f"{len(tab002_bad)} caption(s) not immediately followed by a table; examples={tab002_bad[:5]}",
            "One or more table captions are not positioned immediately above the table.", False, 0.75)
    if fig002_bad:
        add(findings, "FIG-002", "Figures", "Major", "figure captions",
            "Caption positioned immediately below its figure",
            f"{len(fig002_bad)} caption(s) with no image detected nearby; examples={fig002_bad[:5]}",
            "One or more figure captions are not positioned near an image.", False, 0.6)

    # APP-001/002: appendix presence/consistency and body cross-references.
    # Mirrors the same pattern already proven for TAB-005/FIG-004 above.
    appendix_headings = []
    for i, p in enumerate(paragraphs, 1):
        m = re.match(r"^(Appendix|Annexure)\s+([A-Z0-9]+)\b", clean(p.text), re.I)
        if m:
            appendix_headings.append((i, f"{m.group(1).title()} {m.group(2)}"))
    has_list_of_appendices = "LIST OF APPENDICES" in positions
    if has_list_of_appendices and not appendix_headings:
        add(findings, "APP-001", "Appendices", "Major", "document",
            "Appendix content corresponding to the List of Appendices",
            "List of Appendices section present but no Appendix headings detected in the body",
            "A List of Appendices section exists but no corresponding appendix content was detected.", False, 0.7)
    elif appendix_headings and not has_list_of_appendices:
        add(findings, "APP-001", "Appendices", "Major", "document",
            "List of Appendices section listing the detected appendix content",
            f"{len(appendix_headings)} appendix heading(s) detected but no List of Appendices section found",
            "Appendix content exists in the body but no List of Appendices preliminary section was detected.", False, 0.7)
    if appendix_headings:
        appendix_index_set = {i for i, _ in appendix_headings}
        ref_labels = set()
        for i, p in enumerate(paragraphs, 1):
            if i in appendix_index_set:
                continue
            for m in re.finditer(r"\b(?:Appendix|Annexure)\s+([A-Z0-9]+)\b", clean(p.text), re.I):
                ref_labels.add(m.group(1).upper())
        unreferenced = [lbl for i, lbl in appendix_headings if lbl.split()[-1].upper() not in ref_labels]
        if unreferenced:
            add(findings, "APP-002", "Appendices", "Major", "body text",
                "Every appendix referenced in the body", f"No body reference detected for: {', '.join(unreferenced)}",
                "One or more appendices do not appear to be referenced in the body text.", False, 0.65)

    # Check table content font minimum.
    for ti, tbl in enumerate(doc.tables, 1):
        small = []
        for row in tbl.rows:
            for cell in row.cells:
                for p in cell.paragraphs:
                    for r in paragraph_runs(p):
                        if r.font.size and r.font.size.pt < 10:
                            small.append(round(r.font.size.pt,1))
        if small:
            add(findings, "TAB-004", "Tables", "Major", f"table {ti}",
                "Table content not smaller than 10 pt",
                f"smallest observed={min(small)} pt",
                "Table content contains text below the 10 pt minimum.", True)

    # TOC structural and page-number checks.
    # Word stores the live TOC as fields/tables; rendered PDF is the reliable MVP
    # surface for comparing displayed TOC page numbers with rendered headings.
    toc_entries=[]
    rendered_toc_pages=[]
    if rendered_pdf and Path(rendered_pdf).exists():
        try:
            import fitz
            pdf=fitz.open(rendered_pdf)
            page_text=[p.get_text("text") for p in pdf]
            toc_start=next((i for i,t in enumerate(page_text) if "TABLE OF CONTENTS" in t.upper()),None)
            toc_end=next((i for i,t in enumerate(page_text) if i>toc_start and "LIST OF TABLES" in t.upper()),None) if toc_start is not None else None
            if toc_start is not None:
                if toc_end is None: toc_end=min(toc_start+8,len(page_text))
                rendered_toc_pages=list(range(toc_start,toc_end))
                for pi in rendered_toc_pages:
                    raw_lines=[x for x in page_text[pi].splitlines() if clean(x)]
                    for raw_line in raw_lines:
                        line=clean(raw_line)
                        # Keep only plausible TOC entries with a trailing page number.
                        m=re.match(r"^\s*(.*?)(?:[.…]{2,}|\s{2,})(\d+)\s*$",raw_line)
                        if m:
                            label=clean(m.group(1).rstrip("."))
                            page=int(m.group(2))
                            if page < 180 and len(label)>3 and not re.match(r"^(Table|Figure)\s+No\b",label,re.I):
                                toc_entries.append((label,page,pi+1))
            # Heading page map: chapter/section heading text -> first rendered page.
            heading_page_map={}
            for pi,t in enumerate(page_text,1):
                for line in [clean(x) for x in t.splitlines() if clean(x)]:
                    if re.match(r"^(?:CHAPTER\s+\d+|\d+(?:\.\d+){1,3}\s+.+)$",line,re.I):
                        heading_page_map.setdefault(norm(line),pi)
            # Compare displayed TOC page numbers with rendered heading locations.
            mismatches=[]
            for label,listed,_ in toc_entries:
                key=norm(label)
                found=None
                # Exact label or TOC line containing a numbered heading.
                for hk,hp in heading_page_map.items():
                    if key == hk or key in hk or hk in key:
                        found=hp; break
                if found is not None and found != listed:
                    mismatches.append((label,listed,found))
            if mismatches:
                add(findings, "TOC-002", "TOC", "Major", "rendered Table of Contents",
                    "TOC page numbers match rendered document",
                    f"{len(mismatches)} likely mismatch(es); examples={mismatches[:8]}",
                    "Some displayed TOC page numbers do not match the first rendered page where the corresponding heading was found.",
                    True, 0.85, "Annexure 19 + rendered comparison")
            # Coverage: compare numbered headings to TOC labels.
            if toc_entries:
                toc_labels=[norm(x[0]) for x in toc_entries]
                missing=[]
                for i,num,title,st in heads:
                    if not re.match(r"^\d+(?:\.\d+){1,3}$",num):
                        continue
                    target=norm(f"{num} {title}")
                    if not any(target==tl or target in tl or tl in target for tl in toc_labels):
                        missing.append(f"{num} {title}")
                if missing:
                    add(findings, "TOC-001", "TOC", "Major", "rendered Table of Contents",
                        "Detected numbered headings represented in TOC",
                        f"{len(missing)} likely missing; examples={missing[:8]}",
                        "Some detected numbered headings were not matched to the rendered TOC.", False, 0.85)
        except Exception as e:
            add(findings, "TOC-001", "TOC", "Review", "rendered Table of Contents",
                "Readable rendered TOC", "Parser error",
                f"TOC rendered comparison could not be completed: {e}", False, 0.5)

    # References.
    refs_start, refs = parse_references(doc)
    if refs_start is None:
        add(findings, "REF-001", "References", "Major", "document",
            "References section exists", "Not detected",
            "A References/Bibliography heading was not detected.", False)
    else:
        bad_indent=0; bad_spacing=0
        for idx,p in refs:
            fi=inches(p.paragraph_format.left_indent)
            first=inches(p.paragraph_format.first_line_indent)
            if not (fi is not None and first is not None and abs(fi-0.5)<0.05 and abs(first+0.5)<0.05):
                bad_indent+=1
            ls=p.paragraph_format.line_spacing
            if isinstance(ls,float) and abs(ls-1.0)>0.05:
                bad_spacing+=1
            elif str(ls).lower() not in {"none","1.0"} and ls is not None:
                # python-docx may expose line spacing as numeric or None.
                bad_spacing+=1
        if bad_indent:
            add(findings, "REF-002", "References", "Major", "References section",
                "0.5-inch hanging indent", f"{bad_indent}/{len(refs)} reference paragraphs differ",
                "Reference formatting does not consistently use the prescribed hanging indent.", True)
        if bad_spacing:
            add(findings, "REF-002", "References", "Major", "References section",
                "Single-spaced", f"{bad_spacing}/{len(refs)} reference paragraphs differ",
                "Reference formatting does not consistently use single spacing.", True)

    # Rendered PDF checks are delegated to LibreOffice if supplied.
    render_metrics={}
    if rendered_pdf and Path(rendered_pdf).exists():
        try:
            import fitz
            pdf=fitz.open(rendered_pdf)
            render_metrics["pages"]=len(pdf)
            # Extract page text and locate selected headings.
            page_text=[p.get_text("text") for p in pdf]
            render_metrics["nonempty_pages"]=sum(bool(t.strip()) for t in page_text)
            # Footer/page number presence heuristic.
            page_num_hits=0
            for t in page_text:
                if re.search(r"(?m)^\s*\d+\s*$", t):
                    page_num_hits+=1
            render_metrics["pages_with_standalone_numbers"]=page_num_hits
            # TOC page accuracy: compare parsed numeric TOC page with first page containing label.
            if toc_entries:
                mismatches=[]
                for label, listed, _ in toc_entries:
                    nl=norm(label)
                    if len(nl)<4: continue
                    found=None
                    for pi,t in enumerate(page_text,1):
                        if nl in norm(t):
                            found=pi; break
                    if found and abs(found-listed)>0:
                        mismatches.append((label,listed,found))
                render_metrics["toc_mismatches"]=len(mismatches)
                render_metrics["toc_mismatch_examples"]=mismatches[:10]
                if mismatches:
                    add(findings, "TOC-002", "TOC", "Major", "rendered Table of Contents",
                        "TOC page numbers match rendered document",
                        f"{len(mismatches)} likely mismatch(es); examples={mismatches[:5]}",
                        "Some TOC page numbers do not match the first rendered page where the entry text was found.",
                        True, 0.75, "Annexure 19 p.6/p.8 + rendered comparison")
        except Exception as e:
            render_metrics["error"]=str(e)

    # Summary metrics.
    counts=Counter(f["severity"] for f in findings)
    return {
        "engine_version":"0.2",
        "document":path.name,
        "sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
        "metrics":{
            "sections":len(doc.sections),
            "paragraphs":len(doc.paragraphs),
            "tables":len(doc.tables),
            "inline_shapes":len(doc.inline_shapes),
            "table_captions":len(captions["table"]),
            "figure_captions":len(captions["figure"]),
            "toc_entries":len(toc_entries),
            "reference_paragraphs":len(refs) if refs is not None else 0,
            "severity_counts":dict(counts),
            "rendered":render_metrics,
        },
        "findings":findings
    }

if __name__=="__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("--pdf", default=None)
    ap.add_argument("--output", default="validation_results_v0_2.json")
    a=ap.parse_args()
    result=validate(a.docx,a.pdf)
    Path(a.output).write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(f"Validation complete: {len(result['findings'])} findings")
