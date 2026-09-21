
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

def effective_paragraph_format_value(paragraph, attr_name, fall_back_to_normal=True):
    """The paragraph-format value that will actually apply, falling through
    from the paragraph's own direct setting to its style chain (up through
    base styles) when the paragraph itself doesn't override it directly --
    the same kind of inheritance already handled for run fonts
    (effective_run_font_name), now applied to indentation/spacing
    properties. These are just as commonly set once on a style (e.g. a
    custom "Reference Entry" style's hanging indent, confirmed against a
    real thesis) as repeated on every paragraph; checking only the direct
    paragraph value reports a correctly-styled paragraph as having no
    indent/spacing at all.

    fall_back_to_normal governs whether to keep falling through to the
    Normal style specifically when the paragraph's own style chain runs out
    without setting a value (python-docx exposes no base_style at all for
    some real styles, e.g. a thesis's "Chapter Body Text" -- Word still
    treats Normal as the implicit parent there). This is the right call for
    a property meant to be document-wide by default, like font name or
    paragraph spacing (both confirmed correct against a real thesis this
    way). It is the WRONG call for line spacing specifically: a style like
    "Reference Entry" deliberately leaving line spacing unset does not mean
    "inherit the body text's double spacing" -- references are
    conventionally single-spaced regardless of body spacing, so falling
    through to Normal's spacing there produced a confident but wrong
    answer. Callers checking line spacing on anything other than plain
    body text should pass False."""
    value = getattr(paragraph.paragraph_format, attr_name, None)
    if value is not None:
        return value
    style = paragraph.style
    seen = set()
    while style is not None and id(style) not in seen:
        seen.add(id(style))
        style_value = getattr(style.paragraph_format, attr_name, None)
        if style_value is not None:
            return style_value
        style = getattr(style, "base_style", None)
    if fall_back_to_normal:
        try:
            normal = paragraph.part.document.styles["Normal"]
            normal_value = getattr(normal.paragraph_format, attr_name, None)
            if normal_value is not None:
                return normal_value
        except (KeyError, AttributeError):
            pass
    return None

def line_spacing_multiple(paragraph, fall_back_to_normal=False):
    """Line spacing as a float multiplier (1.0 = single, 2.0 = double),
    resolved through the paragraph's style chain (see
    effective_paragraph_format_value), or None when it can't be determined
    this way -- unset/inherited with no style setting it either, or an
    exact-point spacing value (a Length, not a multiplier; Length is
    actually an int subclass in python-docx, so it must be excluded
    explicitly rather than relying on isinstance(x, (int, float))).
    Defaults to NOT falling through to Normal -- see
    effective_paragraph_format_value's docstring for why that matters
    specifically for line spacing. Pass True only when checking plain body
    text, where inheriting the document's general spacing is actually the
    correct question to ask."""
    from docx.shared import Length
    ls = effective_paragraph_format_value(paragraph, "line_spacing", fall_back_to_normal=fall_back_to_normal)
    if ls is None or isinstance(ls, Length):
        return None
    return float(ls)

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

def find_list_section_range(paras_with_text, heading_norms):
    """The [start, end) index range (into the given sequence) covered by a
    preliminary "List of X" index page -- identified by its heading text,
    ending at the next stopper heading (another List-of-X, Abstract,
    References, or a Chapter heading) or the end of the sequence.

    `paras_with_text` is a sequence of (norm_text) strings in document
    order, matching the caller's own indexing scheme -- kept as a parameter
    rather than assuming a specific paragraph list, since different callers
    here use different sequences (doc.paragraphs vs. a mixed
    paragraph+table body sequence) with different indices."""
    start = None
    for i, t in enumerate(paras_with_text):
        if t in heading_norms:
            start = i
            break
    if start is None:
        return None
    stoppers = {"list of tables", "list of figures", "list of abbreviations",
                "list of appendices", "abstract", "references", "bibliography"}
    end = len(paras_with_text)
    for j in range(start + 1, len(paras_with_text)):
        tj = paras_with_text[j]
        if tj and (tj in stoppers or re.match(r"^chapter\s+\d+\b", tj)):
            end = j
            break
    return (start, end)


def parse_captions_and_body_refs(doc):
    """A "List of Tables"/"List of Figures" preliminary page lists every
    caption together as an index -- correctly, with no table or figure
    immediately after each line, and naturally repeating each number that
    also appears for real later in the body. That is not "the caption for
    this table" that TAB-001/002/005 (etc.) mean, so those index-page
    occurrences are excluded here rather than double-counted alongside the
    real body occurrence (which previously produced both false "caption not
    positioned near its table" findings on the index page, and doubled-up
    "not referenced" findings from counting the same missing reference
    once per occurrence).

    Caption text is read via element_paragraph_text (all descendant w:t
    nodes) rather than Paragraph.text, because Word's native "Insert
    Caption" feature generates the sequence number via a SEQ field (wrapped
    in w:fldSimple); Paragraph.text only aggregates direct-child runs and
    silently drops that field's text, truncating e.g. "Table 2.1" to
    "Table 2." -- which then fails to match a table/figure number pattern
    at all. Caught by testing against a real thesis using native Word
    captions, not a synthetic one built without fields."""
    captions = {"table": [], "figure": []}
    refs = {"table": set(), "figure": set()}
    paras = list(doc.paragraphs)
    para_norms = [norm(element_paragraph_text(p._element)) for p in paras]
    excluded = [r for r in (
        find_list_section_range(para_norms, {"list of tables"}),
        find_list_section_range(para_norms, {"list of figures"}),
    ) if r]

    def in_excluded_range(idx0):
        return any(s <= idx0 < e for s, e in excluded)

    for idx, p in enumerate(paras, 1):
        t = clean(element_paragraph_text(p._element))
        for kind in ("table", "figure"):
            n = caption_number(t, kind)
            if n and not in_excluded_range(idx - 1):
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

# Reference-style checkpoint (REF-003): which citation style a faculty
# requires, and pattern-level signals used to check for a clear mismatch.
# Deliberately conservative -- APA and Chicago Author-Date are both
# parenthetical author-date systems and genuinely hard to tell apart by
# pattern alone, so they are treated as one detectable family here; this
# only flags a *clear* mismatch (e.g. numbered/Vancouver-style or legal
# citations where an author-date style was expected), never a hard
# pass/fail on the APA-vs-Chicago distinction itself. Always Review
# severity: a human confirms the actual style, this only flags a concern.
REFERENCE_STYLE_LABELS = {
    "apa": "APA (latest edition)",
    "chicago_author_date": "Chicago Author-Date",
    "apa_bluebook": "APA/Bluebook (latest edition)",
}
_RE_COMMA_AUTHOR_YEAR = re.compile(r"\([A-Z][A-Za-z\-']+(?:\s+(?:et al\.|&|and)\s+[A-Z][A-Za-z\-']+)?,\s+\d{4}[a-z]?\)")
_RE_NOCOMMA_AUTHOR_YEAR = re.compile(r"\([A-Z][A-Za-z\-']+\s+\d{4}[a-z]?\)")
_RE_NUMBERED_CITATION = re.compile(r"\[\d{1,3}\]")
_RE_BLUEBOOK_MARKERS = re.compile(r"\bv\.\s|§|F\.\s?(2d|3d|4th)\b|F\.\s?Supp|U\.S\.\s+\d|S\.\s?Ct\.|L\.\s?Ed\.\b")

def check_reference_style(body_text, expected_style):
    """Returns a dict {ok, reason, signals} or None if there's nothing to check
    (no expected style configured for this faculty)."""
    if not expected_style or expected_style not in REFERENCE_STYLE_LABELS:
        return None
    signals = {
        "comma_author_year": len(_RE_COMMA_AUTHOR_YEAR.findall(body_text)),
        "nocomma_author_year": len(_RE_NOCOMMA_AUTHOR_YEAR.findall(body_text)),
        "numbered_citation": len(_RE_NUMBERED_CITATION.findall(body_text)),
        "bluebook_markers": len(_RE_BLUEBOOK_MARKERS.findall(body_text)),
    }
    parenthetical_total = signals["comma_author_year"] + signals["nocomma_author_year"]

    if expected_style == "apa_bluebook":
        if parenthetical_total == 0 and signals["bluebook_markers"] == 0:
            return {"ok": False, "signals": signals,
                    "reason": "No APA-style parenthetical citations or Bluebook legal-citation markers were detected."}
        return {"ok": True, "signals": signals}

    if parenthetical_total == 0 and (signals["numbered_citation"] > 0 or signals["bluebook_markers"] > 0):
        other = "numbered/Vancouver-style" if signals["numbered_citation"] > signals["bluebook_markers"] else "legal (Bluebook-style)"
        return {"ok": False, "signals": signals,
                "reason": f"In-text citations appear to use a {other} format rather than the expected "
                          f"{REFERENCE_STYLE_LABELS[expected_style]} author-date style."}
    if parenthetical_total == 0:
        return {"ok": False, "signals": signals,
                "reason": f"No {REFERENCE_STYLE_LABELS[expected_style]}-style parenthetical author-date "
                          f"citations were detected in the body text."}
    return {"ok": True, "signals": signals}

def effective_run_font_name(run, paragraph, doc):
    """The font that will actually render for this run, following Word's real
    inheritance chain: explicit run font -> the run's character style ->
    the paragraph's style chain (up through base styles) -> the Normal
    style. A document that sets its font once on the Normal style (the
    normal, clean way to do it) has NO run-level font.name set on any
    individual run at all -- checking only r.font.name, as this engine did
    before, sees every run as "(unspecified)" and false-flags the entire
    document regardless of what font it actually renders in. Caught against
    a real, correctly-formatted thesis whose font was being misreported this
    way."""
    if run.font.name:
        return run.font.name
    if run.style is not None and run.style.font.name:
        return run.style.font.name
    style = paragraph.style
    seen = set()
    while style is not None and id(style) not in seen:
        seen.add(id(style))
        if style.font.name:
            return style.font.name
        style = getattr(style, "base_style", None)
    try:
        normal = doc.styles["Normal"]
        if normal.font.name:
            return normal.font.name
    except KeyError:
        pass
    return None

def validate(path, rendered_pdf=None, reference_style=None):
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
            eff_name = effective_run_font_name(r, p, doc)
            font_counts[(eff_name or "", r.font.size.pt if r.font.size else None)] += len(clean(r.text))
            if eff_name and eff_name.lower() != EXPECTED["font"].lower():
                non_tnr.append((i, eff_name, clean(r.text)[:60]))
        fi = inches(effective_paragraph_format_value(p, "first_line_indent"))
        if fi and fi > .01:
            indented += 1
        sa_raw = effective_paragraph_format_value(p, "space_after")
        sa = sa_raw.pt if sa_raw is not None else 0
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
        hp_spacing = line_spacing_multiple(hp)
        if hp_spacing is not None and abs(hp_spacing - 2.0) > 0.1:
            bad.append(f"line spacing={hp_spacing} (expected double)")
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
            bp_spacing = line_spacing_multiple(bp, fall_back_to_normal=True)
            if bp_spacing is not None and abs(bp_spacing - 2.0) > 0.1:
                bbad.append(f"line spacing={bp_spacing} (expected double)")
            if bbad:
                intro_body_issues.append((name, "; ".join(bbad)))
    if intro_heading_issues:
        add(findings, "INTRO-001", "Introductory", "Major", "preliminary section headings",
            "14 pt bold, centered, double-spaced", "; ".join(f"{n}: {i}" for n, i in intro_heading_issues[:6]),
            "One or more preliminary-section headings differ from the prescribed style.", True, 0.7)
    if intro_body_issues:
        add(findings, "INTRO-002", "Introductory", "Major", "preliminary section body text",
            "12 pt regular, justified, double-spaced", "; ".join(f"{n}: {i}" for n, i in intro_body_issues[:6]),
            "Body text immediately following one or more preliminary-section headings differs from the prescribed style.", True, 0.6)

    # Title page style checks (TITLE-001..003) — use first meaningful paragraphs.
    meaningful = [(i+1,p) for i,p in enumerate(paragraphs[:30])]
    title_candidates = [x for x in meaningful if len(clean(x[1].text)) > 10]
    if title_candidates:
        title_i, title_p = title_candidates[0]
        title = clean(title_p.text)
        runs = paragraph_runs(title_p)
        sizes = [r.font.size.pt for r in runs if r.font.size]
        title_bad = []
        if sizes and abs(max(sizes)-16) > 0.5:
            title_bad.append(f"size={sizes}")
        if runs and any(r.bold is False for r in runs):
            title_bad.append("not bold")
        if title_p.alignment is not None and title_p.alignment != WD_ALIGN_PARAGRAPH.CENTER:
            title_bad.append(f"alignment={title_p.alignment}")
        title_spacing = line_spacing_multiple(title_p)
        if title_spacing is not None and abs(title_spacing - 2.0) > 0.1:
            title_bad.append(f"line spacing={title_spacing} (expected double)")
        if title_bad:
            add(findings, "TITLE-001", "Title", "Major", f"paragraph {title_i}",
                "16 pt Times New Roman, bold, centered, double-spaced",
                f"'{title}': " + "; ".join(title_bad),
                "First title-page candidate does not match the prescribed title style.", True)
        # No all-caps check here: the guideline specifies Title Case for the
        # thesis title itself (see "Title Of Thesis: ... Title Case,
        # Alignment: Centered" in Annexure 19's Paragraph Specification).
        # "All Capital Case" is a separate requirement for the Name Of
        # Author/Course line (TITLE-002), not the title -- a real, correctly
        # Title-Case thesis title was being incorrectly flagged here before
        # this was caught against an actual compliant thesis. Verifying
        # proper Title Case itself (small words like "a"/"for"/"and" staying
        # lowercase, hyphenated compounds, etc.) is a soft, judgment-prone
        # check better left to human review than a naive automated rule.

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
        uni_spacing = line_spacing_multiple(uni_p)
        if uni_spacing is not None and abs(uni_spacing - 1.0) > 0.1:
            issues.append(f"line spacing={uni_spacing} (expected single)")
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
            chap_spacing = line_spacing_multiple(heading_p)
            if chap_spacing is not None and abs(chap_spacing - 2.0) > 0.1:
                issues.append(f"line spacing={chap_spacing} (expected double)")
            if issues:
                add(findings, "CHAP-002", "Chapter", "Major", f"paragraph {i+1}",
                    "14 pt bold, centered, double-spaced chapter heading",
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
    body_seq_norms = [norm(element_paragraph_text(el)) if kind == "p" else "" for kind, el in body_seq]
    excluded_body_seq = [r for r in (
        find_list_section_range(body_seq_norms, {"list of tables"}),
        find_list_section_range(body_seq_norms, {"list of figures"}),
    ) if r]

    def in_excluded_body_seq(idx0):
        return any(s <= idx0 < e for s, e in excluded_body_seq)

    tab002_bad, fig002_bad = [], []
    for idx, (kind, el) in enumerate(body_seq):
        if kind != "p" or in_excluded_body_seq(idx):
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
    appendix_list_range = find_list_section_range([norm(p.text) for p in paragraphs], {"list of appendices"})
    for i, p in enumerate(paragraphs, 1):
        if appendix_list_range and appendix_list_range[0] <= (i - 1) < appendix_list_range[1]:
            continue  # the List of Appendices index page, not a real appendix heading
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
        bad_indent=0; bad_spacing=0; bad_size=0; bad_align=0
        for idx,p in refs:
            fi=inches(effective_paragraph_format_value(p, "left_indent"))
            first=inches(effective_paragraph_format_value(p, "first_line_indent"))
            if not (fi is not None and first is not None and abs(fi-0.5)<0.05 and abs(first+0.5)<0.05):
                bad_indent+=1
            ls=line_spacing_multiple(p)
            if ls is not None and abs(ls-1.0)>0.05:
                bad_spacing+=1
            runs = paragraph_runs(p)
            sizes = [r.font.size.pt for r in runs if r.font.size]
            if sizes and abs(max(sizes) - 12) > 0.5:
                bad_size += 1
            if p.alignment is not None and p.alignment != WD_ALIGN_PARAGRAPH.JUSTIFY:
                bad_align += 1
        if bad_indent:
            add(findings, "REF-002", "References", "Major", "References section",
                "0.5-inch hanging indent", f"{bad_indent}/{len(refs)} reference paragraphs differ",
                "Reference formatting does not consistently use the prescribed hanging indent.", True)
        if bad_spacing:
            add(findings, "REF-002", "References", "Major", "References section",
                "Single-spaced", f"{bad_spacing}/{len(refs)} reference paragraphs differ",
                "Reference formatting does not consistently use single spacing.", True)
        if bad_size:
            add(findings, "REF-002", "References", "Major", "References section",
                "12 pt Times New Roman", f"{bad_size}/{len(refs)} reference paragraphs differ",
                "Reference formatting does not consistently use the prescribed 12 pt font size.", True)
        if bad_align:
            add(findings, "REF-002", "References", "Major", "References section",
                "Justified alignment", f"{bad_align}/{len(refs)} reference paragraphs differ",
                "Reference formatting does not consistently use justified alignment.", True)

        if reference_style:
            style_check = check_reference_style("\n".join(texts), reference_style)
            if style_check and not style_check["ok"]:
                add(findings, "REF-003", "References", "Review", "document",
                    REFERENCE_STYLE_LABELS.get(reference_style, reference_style),
                    "Citation pattern does not clearly match",
                    style_check["reason"] + " This is a pattern-based check, not a full citation-style "
                    "parse -- please confirm the actual reference style during review.",
                    False, 0.6, "Faculty reference-style requirement")

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
    ap.add_argument("--reference-style", default=None, dest="reference_style",
                     help="Faculty's expected citation style: apa, chicago_author_date, or apa_bluebook")
    a=ap.parse_args()
    result=validate(a.docx,a.pdf,a.reference_style)
    Path(a.output).write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(f"Validation complete: {len(result['findings'])} findings")
