"""Pure-Python PDF fallback (fpdf2) matching the official DepEd ILAW lesson plan
template: single 2-column table, portrait, 8.5in x 13in long bond paper.

Used when WeasyPrint (GTK) is not available on the machine.
"""

import os
from fpdf import FPDF

from generators import ilaw_layout as L

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
LH8 = 3.6    # line height for 8pt guidance text (mm)
PAD = 1.8    # cell padding (mm)
GRAY = (191, 191, 191)
BORDER = (0, 0, 0)

TABLE_W = PAGE_W - M_LEFT - M_RIGHT
LABEL_W = 55.0
VALUE_W = TABLE_W - LABEL_W


class ILAWPDF(FPDF):
    def __init__(self, watermark=False):
        super().__init__(orientation="P", unit="mm", format=(PAGE_W, PAGE_H))
        self.set_margins(M_LEFT, M_TOP, M_RIGHT)
        self.set_auto_page_break(auto=False)
        self._font = "Helvetica"
        self._watermark = watermark
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

    def add_page(self):
        super().add_page()
        if self._watermark:
            self._stamp_watermark()

    def _stamp_watermark(self):
        try:
            self.set_font(self._font, "B", 40)
            self.set_text_color(200, 200, 200)
            with self.rotation(45, x=PAGE_W / 2, y=PAGE_H / 2):
                self.set_xy(10, PAGE_H / 2 - 15)
                self.cell(PAGE_W - 20, 30, "LAMDAG TRIAL", align="C")
            self.set_text_color(0, 0, 0)
        except Exception:
            pass

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


def _rects(pdf, y, h, split=False):
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


def _label_height(pdf, title_lines, guide_lines):
    h = len(title_lines) * LH10
    if guide_lines and any(s.strip() for s in guide_lines):
        h += 1.0 + len(guide_lines) * LH8
    return h


def _draw_label(pdf, x, y, title_lines, guide_lines, info_style):
    style = "BI" if info_style else "I"
    yy = _put_lines(pdf, x, y, LABEL_W - 2 * PAD, title_lines, 10, style)
    if not info_style:
        # underline the field title manually
        pdf.set_draw_color(60, 60, 60)
        pdf.set_line_width(0.15)
        pdf.set_font(pdf._font, "I", 10)
        for i, line in enumerate(title_lines):
            lw = pdf.get_string_width(line)
            ly = y + (i + 1) * LH10 - 1.0
            pdf.line(x, ly, x + min(lw, LABEL_W - 2 * PAD), ly)
    if guide_lines and any(s.strip() for s in guide_lines):
        pdf.set_text_color(70, 70, 70)
        _put_lines(pdf, x, yy + 1.0, LABEL_W - 2 * PAD, guide_lines, 8, "I")
        pdf.set_text_color(0, 0, 0)


def _row(pdf, title, guidance, value, info_style=False, placeholder="\u2014"):
    title_lines = _wrap(pdf, title, LABEL_W - 2 * PAD, 10, "BI" if info_style else "I")
    guide_lines = _wrap(pdf, guidance, LABEL_W - 2 * PAD, 8, "I") if guidance else []
    value_lines = _wrap(pdf, value if value else placeholder, VALUE_W - 2 * PAD, 10)

    label_h = _label_height(pdf, title_lines, guide_lines)
    total_h = max(label_h, len(value_lines) * LH10) + 2 * PAD

    if total_h <= _avail(pdf):
        pass
    elif total_h <= _full_page_avail():
        pdf.add_page()
    # else: multi-page row handled below

    if total_h <= _avail(pdf):
        y0 = pdf.get_y()
        _rects(pdf, y0, total_h)
        _draw_label(pdf, M_LEFT + PAD, y0 + PAD, title_lines, guide_lines, info_style)
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
            _draw_label(pdf, M_LEFT + PAD, y0 + PAD, title_lines, guide_lines, info_style)
        if chunk:
            _put_lines(pdf, M_LEFT + LABEL_W + PAD, y0 + PAD, VALUE_W - 2 * PAD, chunk, 10)
        pdf.set_y(y0 + seg_h)
        first = False
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


def generate_ilaw_pdf(data, output_path, watermark=False):
    pdf = ILAWPDF(watermark=watermark)
    pdf.add_page()

    _add_letterhead(pdf, data)

    # --- Info rows ---
    for label, guidance, key in L.INFO_ROWS:
        _row(pdf, label, guidance, data.get(key, ""), info_style=True)

    # --- Intentions ---
    _header_row(pdf, L.HEADER_INTENTIONS)
    _row(pdf, "Learning Competency:", L.GUIDE_COMPETENCY, data.get("competency_full", ""))
    _row(pdf, "Learning Objectives:", L.GUIDE_OBJECTIVES, data.get("objectives", ""))
    _row(pdf, "Learner Context:", L.GUIDE_LEARNER_CONTEXT, data.get("learner_context", ""))

    # --- Learning Experience ---
    _header_row(pdf, L.HEADER_EXPERIENCE)
    _row(pdf, "Pre-lesson:", L.GUIDE_PRE_LESSON, data.get("pre_lesson", ""))
    _row(pdf, "Flow:", L.GUIDE_FLOW, L.flow_text(data))
    _row(pdf, "Learning Resources:", L.GUIDE_RESOURCES, data.get("learning_resources", ""))
    _row(pdf, "Opportunities for integration:", L.GUIDE_INTEGRATION,
         data.get("integration", ""), placeholder="N/A")

    # --- Assessment ---
    _header_row(pdf, L.HEADER_ASSESSMENT)
    _row(pdf, "Formative Assessment:", L.GUIDE_FORMATIVE, data.get("formative_assessment", ""))

    # --- Ways Forward ---
    _header_row(pdf, L.HEADER_WAYS_FORWARD)
    _row(pdf, "Extended learning opportunities:", L.GUIDE_EXTENDED, data.get("extended_learning", ""))
    _row(pdf, "Reflections:", L.GUIDE_REFLECTIONS, data.get("reflection", ""))

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

    # Names (printed above the signature line)
    pdf.set_font(pdf._font, "", 10)
    pdf.set_xy(M_LEFT, y0 + 7)
    pdf.cell(half, 5, teacher_name, align="C")
    pdf.set_xy(M_LEFT + half, y0 + 7)
    pdf.cell(half, 5, head_name, align="C")

    # Signature lines
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
