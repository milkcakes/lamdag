"""Pure-Python PDF fallback (fpdf2) for the official DepEd Strengthened Senior
High School Lesson Exemplar (LE): portrait, 8.5in x 13in long bond paper,
sections I-VIII with a two-column PROCEDURES | ANNOTATIONS table.

Used when WeasyPrint (GTK) is not available on the machine.
"""

import os
from fpdf import FPDF

from generators import exemplar_layout as L

# Prefer bundled/system Segoe UI on Windows, fall back to common Linux font
# dirs (Render/Railway). add_font() below silently skips missing files.
FONT_DIR = "C:/Windows/Fonts"
if not os.path.isdir(FONT_DIR):
    for _cand in (
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/truetype/liberation",
        "/usr/share/fonts",
    ):
        if os.path.isdir(_cand):
            FONT_DIR = _cand
            break

_FONT_FILES = (
    ("segoeui.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"),
    ("segoeuib.ttf", "DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf"),
    ("segoeuii.ttf", "DejaVuSans-Oblique.ttf", "LiberationSans-Italic.ttf"),
    ("segoeuiz.ttf", "DejaVuSans-BoldOblique.ttf", "LiberationSans-BoldItalic.ttf"),
)

# Page: 8.5in x 13in in mm
PAGE_W = 215.9
PAGE_H = 330.2
M_LEFT = 25.4
M_RIGHT = 20.6
M_TOP = 25.4
M_BOTTOM = 25.4

LH10 = 4.6   # line height for 10pt text (mm)
LH8 = 3.6    # line height for 8pt text (mm)
PAD = 1.8    # cell padding (mm)
GRAY = (191, 191, 191)
LIGHT = (217, 217, 217)
PHASE = (221, 235, 247)
BORDER = (0, 0, 0)

TABLE_W = PAGE_W - M_LEFT - M_RIGHT
LABEL_W = 55.0
VALUE_W = TABLE_W - LABEL_W


class ExemplarPDF(FPDF):
    def __init__(self):
        super().__init__(orientation="P", unit="mm", format=(PAGE_W, PAGE_H))
        self.set_margins(M_LEFT, M_TOP, M_RIGHT)
        self.set_auto_page_break(auto=False)
        self._font = "Helvetica"
        for i, (name, style) in enumerate((("Body", ""), ("Body", "B"), ("Body", "I"), ("Body", "BI"))):
            for _f in _FONT_FILES[i]:
                _p = os.path.join(FONT_DIR, _f)
                if os.path.exists(_p):
                    try:
                        self.add_font(name, style, _p)
                        self._font = "Body"
                        break
                    except Exception:
                        continue

    def sanitize(self, text):
        if self._font != "Helvetica":
            return text
        replacements = {
            "\u2014": "-", "\u2013": "-", "\u2018": "'", "\u2019": "'",
            "\u201c": '"', "\u201d": '"', "\u2022": "*", "\u2026": "...",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        return text.encode("latin-1", "replace").decode("latin-1")


def _lh(size):
    return LH10 if size >= 10 else LH8


def _wrap(pdf, text, w, size, style=""):
    """Wrapped lines of text at the given width/font."""
    text = pdf.sanitize(text or "")
    pdf.set_font(pdf._font, style, size)
    lines = pdf.multi_cell(w, _lh(size), text, dry_run=True, output="LINES")
    return lines or [""]


def _avail(pdf):
    return PAGE_H - M_BOTTOM - pdf.get_y()


def _full_page_avail():
    return PAGE_H - M_BOTTOM - M_TOP


def _rects(pdf, y, h):
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.25)
    x = M_LEFT
    pdf.rect(x, y, LABEL_W, h)
    pdf.rect(x + LABEL_W, y, VALUE_W, h)


def _put_lines(pdf, x, y, w, lines, size, style=""):
    pdf.set_font(pdf._font, style, size)
    lh = _lh(size)
    for i, line in enumerate(lines):
        pdf.set_xy(x, y + i * lh)
        pdf.cell(w, lh, line)
    return y + len(lines) * lh


def _plain_row(pdf, title, value, placeholder="\u2014"):
    """Label (bold, narrow) | value (wide) row."""
    title_lines = _wrap(pdf, title, LABEL_W - 2 * PAD, 10, "B")
    value_lines = _wrap(pdf, value if value else placeholder, VALUE_W - 2 * PAD, 10)
    label_h = len(title_lines) * LH10
    total_h = max(label_h, len(value_lines) * LH10) + 2 * PAD

    if total_h <= _avail(pdf):
        pass
    elif total_h <= _full_page_avail():
        pdf.add_page()
    # else: split below

    if total_h <= _avail(pdf):
        y0 = pdf.get_y()
        _rects(pdf, y0, total_h)
        _put_lines(pdf, M_LEFT + PAD, y0 + PAD, LABEL_W - 2 * PAD, title_lines, 10, "B")
        _put_lines(pdf, M_LEFT + LABEL_W + PAD, y0 + PAD, VALUE_W - 2 * PAD, value_lines, 10)
        pdf.set_y(y0 + total_h)
        return

    # Row taller than a full page: split the value lines across pages.
    remaining = list(value_lines)
    first = True
    while remaining or first:
        if first and label_h + 2 * PAD > _avail(pdf):
            pdf.add_page()
        space = _avail(pdf) - 2 * PAD
        n = max(1, int(space // LH10))
        chunk, remaining = remaining[:n], remaining[n:]
        seg_h = max(label_h if first else 0, len(chunk) * LH10) + 2 * PAD
        y0 = pdf.get_y()
        _rects(pdf, y0, seg_h)
        if first:
            _put_lines(pdf, M_LEFT + PAD, y0 + PAD, LABEL_W - 2 * PAD, title_lines, 10, "B")
        if chunk:
            _put_lines(pdf, M_LEFT + LABEL_W + PAD, y0 + PAD, VALUE_W - 2 * PAD, chunk, 10)
        pdf.set_y(y0 + seg_h)
        first = False
        if remaining:
            pdf.add_page()


def _merged(pdf, text, italic=False, placeholder="\u2014"):
    """Full-width bordered content row."""
    lines = _wrap(pdf, text if text else placeholder, TABLE_W - 2 * PAD, 10, "I" if italic else "")
    total_h = len(lines) * LH10 + 2 * PAD

    if total_h <= _avail(pdf):
        pass
    elif total_h <= _full_page_avail():
        pdf.add_page()
    # else: split below

    if total_h <= _avail(pdf):
        y0 = pdf.get_y()
        pdf.set_draw_color(*BORDER)
        pdf.set_line_width(0.25)
        pdf.rect(M_LEFT, y0, TABLE_W, total_h)
        _put_lines(pdf, M_LEFT + PAD, y0 + PAD, TABLE_W - 2 * PAD, lines, 10, "I" if italic else "")
        pdf.set_y(y0 + total_h)
        return

    remaining = list(lines)
    while remaining:
        if _avail(pdf) <= 2 * PAD:
            pdf.add_page()
        space = _avail(pdf) - 2 * PAD
        n = max(1, int(space // LH10))
        chunk, remaining = remaining[:n], remaining[n:]
        seg_h = len(chunk) * LH10 + 2 * PAD
        y0 = pdf.get_y()
        pdf.set_draw_color(*BORDER)
        pdf.set_line_width(0.25)
        pdf.rect(M_LEFT, y0, TABLE_W, seg_h)
        _put_lines(pdf, M_LEFT + PAD, y0 + PAD, TABLE_W - 2 * PAD, chunk, 10, "I" if italic else "")
        pdf.set_y(y0 + seg_h)
        if remaining:
            pdf.add_page()


def _header_row(pdf, text):
    lines = _wrap(pdf, text, TABLE_W - 2 * PAD, 10, "B")
    h = len(lines) * LH10 + 2 * PAD
    if h > _avail(pdf):
        pdf.add_page()
    y0 = pdf.get_y()
    pdf.set_fill_color(*GRAY)
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.25)
    pdf.rect(M_LEFT, y0, TABLE_W, h, style="DF")
    _put_lines(pdf, M_LEFT + PAD, y0 + PAD, TABLE_W - 2 * PAD, lines, 10, "B")
    pdf.set_y(y0 + h)


def _proc_header(pdf):
    """Official two-column header row: IV. PROCEDURES | ANNOTATIONS."""
    h = LH10 + 2 * PAD
    if h > _avail(pdf):
        pdf.add_page()
    y0 = pdf.get_y()
    pdf.set_fill_color(*GRAY)
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.25)
    pdf.rect(M_LEFT, y0, VALUE_W, h, style="DF")
    pdf.rect(M_LEFT + VALUE_W, y0, LABEL_W, h, style="DF")
    pdf.set_font(pdf._font, "B", 10)
    pdf.set_xy(M_LEFT, y0)
    pdf.cell(VALUE_W, h, L.HEADER_PROCEDURES, align="C")
    pdf.set_xy(M_LEFT + VALUE_W, y0)
    pdf.cell(LABEL_W, h, L.HEADER_ANN_COL, align="C")
    pdf.set_y(y0 + h)


def _proc_step(pdf, phase_name, idx, step):
    """Procedure step: content (wide, left) | phase label + annotation
    (narrow, right). Steps are renumbered within each phase and the phase
    label (A./B./C.) sits in the ANNOTATIONS column, as in the official LE."""
    title_lines = _wrap(pdf, f"{idx}. {step['title']}", VALUE_W - 2 * PAD, 10, "B")
    content_lines = _wrap(pdf, step["content"] or "\u2014", VALUE_W - 2 * PAD, 10)

    ann_segments = []
    if idx == 1 and phase_name:
        ann_segments.append((phase_name, "BI"))
    if step["annotation"]:
        ann_segments.append((step["annotation"], "I"))
    right_segs = []
    for text, style in ann_segments:
        right_segs.append((_wrap(pdf, text, LABEL_W - 2 * PAD, 9, style), style))
    right_n = sum(len(seg) for seg, _ in right_segs)

    left_h = (len(title_lines) + len(content_lines)) * LH10 + 2 * PAD
    right_h = right_n * _lh(9) + 2 * PAD
    total_h = max(left_h, right_h)

    if total_h > _avail(pdf):
        pdf.add_page()
    y0 = pdf.get_y()
    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.25)
    pdf.rect(M_LEFT, y0, VALUE_W, total_h)
    pdf.rect(M_LEFT + VALUE_W, y0, LABEL_W, total_h)
    _put_lines(pdf, M_LEFT + PAD, y0 + PAD, VALUE_W - 2 * PAD, title_lines, 10, "B")
    ty = y0 + PAD + len(title_lines) * LH10
    _put_lines(pdf, M_LEFT + PAD, ty, VALUE_W - 2 * PAD, content_lines, 10)
    ry = y0 + PAD
    for seg_lines, style in right_segs:
        if seg_lines and any(s.strip() for s in seg_lines):
            ry = _put_lines(pdf, M_LEFT + VALUE_W + PAD, ry, LABEL_W - 2 * PAD, seg_lines, 9, style)
    pdf.set_y(y0 + total_h)


def _add_letterhead(pdf, data):
    y = M_TOP

    region = pdf.sanitize(data.get("region") or "Region VII - Central Visayas")
    division = pdf.sanitize(data.get("letterhead_division") or "")
    school = pdf.sanitize(data.get("letterhead_school") or "")

    lines = [
        ("Republic of the Philippines", "B", 12),
        ("Department of Education", "B", 13),
        (region, "I", 10.5),
    ]
    if division:
        lines.append((division, "B", 11))
    if school:
        lines.append((school, "B", 11))

    lh = 5.0
    ty = y + 1
    for text, style, size in lines:
        pdf.set_font(pdf._font, style, size)
        pdf.set_xy(M_LEFT, ty)
        pdf.cell(TABLE_W, lh, text, align="C")
        ty += lh

    rule_y = max(ty, y + 2) + 3
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.5)
    pdf.line(M_LEFT, rule_y, PAGE_W - M_RIGHT, rule_y)
    pdf.set_y(rule_y + 6)


def _add_exemplar_title(pdf, data):
    ty = pdf.get_y()
    pdf.set_font(pdf._font, "B", 14)
    pdf.set_xy(M_LEFT, ty)
    pdf.cell(TABLE_W, 6, "LESSON EXEMPLAR", align="C")

    topic_lines = _wrap(pdf, f"Lesson Title/Topic: {data.get('lesson_name', '')}", TABLE_W, 11, "B")
    y2 = ty + 6.5
    for line in topic_lines:
        pdf.set_font(pdf._font, "B", 11)
        pdf.set_xy(M_LEFT, y2)
        pdf.cell(TABLE_W, _lh(11), line, align="C")
        y2 += _lh(11)

    if data.get("school_year"):
        pdf.set_font(pdf._font, "I", 11)
        pdf.set_xy(M_LEFT, y2)
        pdf.cell(TABLE_W, 5, f"School Year {data['school_year']}", align="C")
        y2 += 5
    pdf.set_y(y2 + 2)


def _objectives_text(data):
    items = data.get("le_objectives") or []
    intro = data.get("le_objectives_intro") or L.OBJECTIVES_INTRO
    if not items:
        return intro
    return intro + "\n" + "\n".join(
        f"{i}. {line}" for i, line in enumerate(items, 1)
    )


def generate_exemplar_pdf(data, output_path):
    pdf = ExemplarPDF()
    pdf.add_page()

    _add_letterhead(pdf, data)
    _add_exemplar_title(pdf, data)

    # --- Lesson details ---
    for label, key in L.INFO_ROWS:
        _plain_row(pdf, label, data.get(key, ""))

    # --- I. OBJECTIVES ---
    _header_row(pdf, L.HEADER_OBJECTIVES)
    _plain_row(pdf, "A. Content Standard", data.get("content_standard", ""))
    _plain_row(pdf, "B. Performance Standard", data.get("performance_standard", ""))
    _plain_row(pdf, "C. Learning Competencies", data.get("le_competencies_text", ""))

    # --- II. REFERENCES and MATERIALS ---
    _header_row(pdf, L.HEADER_REFERENCES)
    _plain_row(pdf, "References", data.get("references", ""))
    _plain_row(pdf, "Materials", data.get("learning_resources", ""))

    # --- III. CONTENT ---
    _header_row(pdf, L.HEADER_CONTENT)
    _merged(pdf, data.get("le_content", ""))

    # --- IV. OBJECTIVES ---
    _header_row(pdf, L.HEADER_OBJECTIVES2)
    _merged(pdf, _objectives_text(data))

    # --- IV. PROCEDURES (official two-column header, no full-width row) ---
    _proc_header(pdf)
    for phase in data.get("le_phases", []):
        for i, step in enumerate(phase["steps"], 1):
            _proc_step(pdf, phase["name"], i, step)

    # --- VI. ASSESSMENT ---
    _header_row(pdf, L.HEADER_ASSESSMENT)
    _plain_row(pdf, "A. Paper and Pen", data.get("le_quiz", ""))
    _plain_row(pdf, "B. Performance Task", data.get("le_perf_overview", ""))
    _plain_row(pdf, "Directions to the Learners", data.get("le_perf_directions", ""))
    _plain_row(pdf, "Scoring Rubrics", data.get("le_perf_rubric", ""))

    # --- VII. REFLECTION ---
    _header_row(pdf, L.HEADER_REFLECTION)
    _merged(pdf, L.REFLECTION_DIRECTIONS, italic=True)
    _plain_row(pdf, "Reflection", data.get("reflection", ""))

    # --- VIII. USE OF GENERATIVE AI ---
    _header_row(pdf, L.HEADER_GENAI)
    _merged(pdf, data.get("le_ai_declaration", ""))

    # --- Signature block ---
    if _avail(pdf) < 40:
        pdf.add_page()
    y0 = pdf.get_y() + 8
    half = TABLE_W / 2

    designation = pdf.sanitize(data.get("designation", "") or "Teacher")
    head_designation = pdf.sanitize(data.get("school_head_designation", "") or "School Head / Principal")
    teacher_name = pdf.sanitize(data.get("teacher", "") or "")
    head_name = pdf.sanitize(data.get("school_head", "") or "")

    pdf.set_font(pdf._font, "B", 10)
    pdf.set_xy(M_LEFT, y0)
    pdf.cell(half, 5, "Prepared by:", align="C")
    pdf.set_xy(M_LEFT + half, y0)
    pdf.cell(half, 5, "Reviewed & Checked by:", align="C")

    pdf.set_font(pdf._font, "", 10)
    pdf.set_xy(M_LEFT, y0 + 7)
    pdf.cell(half, 5, teacher_name, align="C")
    pdf.set_xy(M_LEFT + half, y0 + 7)
    pdf.cell(half, 5, head_name, align="C")

    line_y = y0 + 13.5
    pdf.set_draw_color(0, 0, 0)
    pdf.set_line_width(0.4)
    pdf.line(M_LEFT + 4, line_y, M_LEFT + half - 4, line_y)
    pdf.line(M_LEFT + half + 4, line_y, PAGE_W - M_RIGHT - 4, line_y)

    pdf.set_font(pdf._font, "", 9)
    pdf.set_xy(M_LEFT, y0 + 17)
    pdf.cell(half, 5, designation, align="C")
    pdf.set_xy(M_LEFT + half, y0 + 17)
    pdf.cell(half, 5, head_designation, align="C")

    pdf.output(output_path)
    return output_path
