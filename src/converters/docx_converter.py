import os
import re

from src.utils.md_helpers import md_header, md_bold, md_italic
from src.utils.md_table import rows_to_markdown

# "Heading 1", "heading1", Korean Word "제목 1", plus the document "Title".
_HEADING_RE = re.compile(r"^(?:heading|제목)\s*(\d+)$")


def get_font_name(run):
    """
    Extracts font name, checking specifically for East Asia fonts (Korean).
    """
    from docx.oxml.ns import qn
    rPr = run._element.rPr
    if rPr is None:
        return None

    # Check for eastAsia font (common for Korean like Malgun Gothic)
    if rPr.rFonts is not None:
        east_asia = rPr.rFonts.get(qn('w:eastAsia'))
        if east_asia:
            return east_asia
        ascii_font = rPr.rFonts.get(qn('w:ascii'))
        if ascii_font:
            return ascii_font
    return None


def _heading_level(style_name):
    """Return the Markdown heading level for a Word style name, or None."""
    name = (style_name or "").strip().lower()
    if name in ("title", "제목"):
        return 1
    m = _HEADING_RE.match(name)
    if m:
        return max(1, min(6, int(m.group(1))))
    return None


def _is_list_paragraph(para, style_name):
    if "list" in style_name or "목록" in style_name:
        return True
    pPr = para._element.pPr
    return pPr is not None and pPr.numPr is not None


def _runs_to_text(para):
    parts = []
    for run in para.runs:
        content = run.text
        if not content:
            continue
        # Wrapping whitespace-only runs in ** / * produces broken Markdown.
        if content.strip():
            lead = content[: len(content) - len(content.lstrip())]
            trail = content[len(content.rstrip()):]
            core = content.strip()
            if run.bold:
                core = md_bold(core)
            if run.italic:
                core = md_italic(core)
            content = f"{lead}{core}{trail}"
        parts.append(content)
    return "".join(parts)


def _paragraph_to_md(para):
    style_name = para.style.name.lower() if para.style is not None else ""
    para_text = _runs_to_text(para) or para.text
    if not para_text.strip():
        return ""

    level = _heading_level(style_name)
    if level is not None:
        return md_header(para.text.strip(), level)
    if _is_list_paragraph(para, style_name):
        return f"- {para_text.strip()}\n"
    return f"{para_text.strip()}\n\n"


def _table_to_md(table):
    """Render a table, de-duplicating merged cells.

    python-docx returns the same cell object for every grid column a merged
    cell spans (horizontally) and for every row it spans (vertically); emit
    the text once and leave the covered positions empty.
    """
    rows = []
    previous_tcs = []
    for row in table.rows:
        cells = []
        tcs = []
        for idx, cell in enumerate(row.cells):
            tc = cell._tc
            covered_h = bool(tcs) and tcs[-1] is tc
            covered_v = idx < len(previous_tcs) and previous_tcs[idx] is tc
            tcs.append(tc)
            cells.append("" if covered_h or covered_v else cell.text.strip())
        previous_tcs = tcs
        rows.append(cells)
    if not rows:
        return ""
    return rows_to_markdown(rows)


def convert_docx_to_md(file_path):
    """
    Converts a .docx file to Markdown, keeping paragraphs and tables in
    document order.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    doc = docx.Document(file_path)
    md_lines = []

    for element in doc.element.body:
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "p":
            text = _paragraph_to_md(Paragraph(element, doc))
            if text:
                md_lines.append(text)
        elif tag == "tbl":
            table_md = _table_to_md(Table(element, doc))
            if table_md:
                md_lines.append(table_md)

    return "".join(md_lines)
