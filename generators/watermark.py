"""Diagonal watermark for DOCX exports (trial users).

Inserts a Word VML "PowerPlusWaterMarkObject" shape into each section header,
so the text appears diagonally across every page of the document.
"""

from docx.oxml import parse_xml

_WATERMARK_XML = (
    '<w:pict xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
    'xmlns:v="urn:schemas-microsoft-com:vml" '
    'xmlns:o="urn:schemas-microsoft-com:office:office">'
    '<v:shape id="PowerPlusWaterMarkObject" type="#_x0000_t136" '
    'style="position:absolute;margin-left:0;margin-top:0;width:500pt;height:260pt;'
    'z-index:-251658240;mso-wrap-edited:f;" '
    'o:allowincell="f" filled="t" fillcolor="#C0C0C0" stroked="f">'
    '<v:fill on="t" color2="#C0C0C0" angle="0" opacity="0.4"/>'
    '<v:textpath style="font-family:\'Arial\';font-size:1pt;font-style:italic;'
    'font-weight:bold;visibility:hidden" string="LAMDAG TRIAL VERSION"/>'
    '</v:shape></w:pict>'
)


def add_docx_watermark(doc, text="LAMDAG TRIAL VERSION"):
    """Add a diagonal watermark to every section header of `doc`."""
    for section in doc.sections:
        try:
            header = section.header
            header.is_linked_to_previous = False
            p = header.add_paragraph()
            p.text = ""
            xml = _WATERMARK_XML.replace("LAMDAG TRIAL VERSION", text)
            pict = parse_xml(xml)
            p._p.append(pict)
        except Exception:
            continue
