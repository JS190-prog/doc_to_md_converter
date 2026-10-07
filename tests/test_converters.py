import io
import sys
import types
import zipfile

import pytest

from src.utils.md_table import escape_md_cell, format_cell, rows_to_markdown


# ---- md_table ------------------------------------------------------------

def test_format_cell_numbers_and_dates():
    import datetime as dt

    assert format_cell(1.0) == "1"
    assert format_cell(1.5) == "1.5"
    assert format_cell(True) == "TRUE"
    assert format_cell(dt.datetime(2026, 1, 2)) == "2026-01-02"
    assert format_cell(dt.datetime(2026, 1, 2, 3, 4)) == "2026-01-02 03:04:00"


def test_escape_pipes_and_newlines():
    assert escape_md_cell("a|b\nc") == "a\\|b<br>c"


def test_rows_to_markdown_trims_and_pads():
    md = rows_to_markdown([["h1", "h2", None], ["a"], [None, None, None]])
    assert md.splitlines()[0] == "| h1 | h2 |"
    assert "| a |  |" in md
    assert rows_to_markdown([[None]]) == "_(empty sheet)_\n\n"


# ---- docx ----------------------------------------------------------------

def test_docx_headings_lists_and_tables(tmp_path):
    docx = pytest.importorskip("docx")
    from src.converters.docx_converter import _heading_level, convert_docx_to_md

    assert _heading_level("Heading 2") == 2
    assert _heading_level("제목 3") == 3
    assert _heading_level("Title") == 1
    assert _heading_level("Normal") is None

    doc = docx.Document()
    doc.add_heading("개요", level=1)
    p = doc.add_paragraph()
    p.add_run("굵게").bold = True
    p.add_run(" ")  # whitespace-only run must not become "** **"
    p.add_run("보통")
    doc.add_paragraph("항목", style="List Bullet")
    table = doc.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "A|B"
    table.cell(0, 1).text = "H2"
    merged = table.cell(1, 0).merge(table.cell(1, 1))
    merged.text = "merged"
    path = tmp_path / "t.docx"
    doc.save(path)

    md = convert_docx_to_md(str(path))
    assert "# 개요" in md
    assert "**굵게** 보통" in md
    assert "** **" not in md
    assert "- 항목" in md
    assert "| A\\|B | H2 |" in md
    assert md.count("merged") == 1


# ---- xlsx ----------------------------------------------------------------

def test_xlsx_falls_back_to_formula_text_without_cache(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from src.converters.xlsx_converter import convert_xlsx_to_md

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["a", "b"])
    ws.append([1, 2])
    ws["C2"] = "=A2+B2"  # never calculated -> no cached value
    path = tmp_path / "f.xlsx"
    wb.save(path)

    md = convert_xlsx_to_md(str(path))
    assert "## Sheet1" in md
    assert "=A2+B2" in md


# ---- hwpx ----------------------------------------------------------------

def _hwpx(tmp_path, xml):
    path = tmp_path / "t.hwpx"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("Contents/section0.xml", xml)
    return str(path)


def test_hwpx_extracts_paragraphs(tmp_path):
    from src.converters.hwpx_converter import convert_hwpx_to_md

    xml = (
        '<root xmlns:hp="x"><hp:p><hp:run><hp:t>첫째 문단</hp:t></hp:run></hp:p>'
        "<hp:p><hp:run><hp:t>둘째 문단</hp:t></hp:run></hp:p></root>"
    )
    md = convert_hwpx_to_md(_hwpx(tmp_path, xml))
    assert "첫째 문단" in md and "둘째 문단" in md


def test_hwpx_rejects_entity_bomb(tmp_path):
    pytest.importorskip("defusedxml")
    from src.converters.hwpx_converter import convert_hwpx_to_md

    bomb = (
        '<?xml version="1.0"?><!DOCTYPE r [<!ENTITY a "aaaaaaaaaa">'
        '<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;">]><root><p><t>&b;</t></p></root>'
    )
    with pytest.raises(Exception):
        convert_hwpx_to_md(_hwpx(tmp_path, bomb))


# ---- hwp -----------------------------------------------------------------

def test_hwp_para_text_skips_extended_control_payload():
    from src.converters.hwp_converter import _decode_para_text

    def wchars(*codes):
        return b"".join(c.to_bytes(2, "little") for c in codes)

    # "가" + table control (code 11 + 7 payload WCHARs) + "나" + paragraph end
    payload = wchars(0xAC00) + wchars(11, 0x1234, 0x5678, 0, 0, 0, 0, 11) + wchars(0xB098, 13)
    assert _decode_para_text(payload) == "가나\n"


def test_hwp_decompress_bomb_is_capped(monkeypatch):
    import zlib

    from src.converters import hwp_converter as h

    monkeypatch.setattr(h, "MAX_DECOMPRESSED_BYTES", 1000)
    comp = zlib.compressobj(wbits=-15)
    data = comp.compress(b"\0" * 100_000) + comp.flush()
    with pytest.raises(h.HWPConversionError):
        h._decompress_if_needed(data, True)


# ---- pptx ----------------------------------------------------------------

def test_pptx_notes_and_assets_dir(tmp_path):
    pptx = pytest.importorskip("pptx")
    from src.converters.pptx_converter import convert_pptx_to_md

    prs = pptx.Presentation()
    s1 = prs.slides.add_slide(prs.slide_layouts[1])
    s1.shapes.title.text = "제목"
    s1.notes_slide.notes_text_frame.text = "발표자 노트"
    prs.slides.add_slide(prs.slide_layouts[6])  # blank, no notes
    path = tmp_path / "d.pptx"
    prs.save(path)

    md = convert_pptx_to_md(str(path), str(tmp_path / "d_converted.md"))
    assert "발표자 노트" in md
    assert "## Slide 2" in md
    assert not (tmp_path / "d_assets").exists()  # nothing extracted -> no empty dir
