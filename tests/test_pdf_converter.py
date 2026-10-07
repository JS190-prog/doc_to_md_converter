import sys
import types

import pytest

fitz = pytest.importorskip("fitz")

from src.converters.pdf_converter import convert_pdf_with_report

LONG_TEXT = "This page has a genuine embedded text layer with plenty of characters. " * 3


def _make_pdf(path, pages):
    doc = fitz.open()
    for text in pages:
        page = doc.new_page()
        if text:
            page.insert_textbox(fitz.Rect(40, 40, 550, 800), text, fontsize=11)
    doc.save(str(path))
    doc.close()


def _fake_ocr(monkeypatch, fn):
    mod = types.ModuleType("src.converters.ocr_engine")
    mod.get_ocr_text = fn
    monkeypatch.setitem(sys.modules, "src.converters.ocr_engine", mod)


def test_text_layer_pages_skip_ocr(tmp_path, monkeypatch):
    def no_ocr(*a, **k):
        raise AssertionError("OCR must not run on digital pages")

    _fake_ocr(monkeypatch, no_ocr)
    pdf = tmp_path / "d.pdf"
    _make_pdf(pdf, [LONG_TEXT, LONG_TEXT])
    report = convert_pdf_with_report(str(pdf))
    assert report.text_pages == 2 and report.ocr_pages == 0
    assert report.failed_pages == []


def test_failed_ocr_page_is_reported_not_dropped(tmp_path, monkeypatch):
    calls = []

    def flaky(img, paragraph=False):
        calls.append(1)
        raise RuntimeError("paddle exploded")

    _fake_ocr(monkeypatch, flaky)
    pdf = tmp_path / "m.pdf"
    _make_pdf(pdf, [LONG_TEXT, None, LONG_TEXT])  # middle page is blank -> OCR
    report = convert_pdf_with_report(str(pdf), dpi=50)
    assert report.failed_pages == [2]
    assert "<!-- OCR failed: page 2 -->" in report.markdown
    assert report.markdown.count("---") == 2  # all three pages kept, in order


def test_all_pages_failing_raises(tmp_path, monkeypatch):
    def boom(img, paragraph=False):
        raise RuntimeError("x")

    _fake_ocr(monkeypatch, boom)
    pdf = tmp_path / "s.pdf"
    _make_pdf(pdf, [None])
    with pytest.raises(RuntimeError):
        convert_pdf_with_report(str(pdf), dpi=50)


def test_ocr_text_is_used_for_scanned_page(tmp_path, monkeypatch):
    _fake_ocr(monkeypatch, lambda img, paragraph=False: "스캔된 페이지 본문")
    pdf = tmp_path / "o.pdf"
    _make_pdf(pdf, [None])
    report = convert_pdf_with_report(str(pdf), dpi=50)
    assert report.markdown == "스캔된 페이지 본문"
    assert report.ocr_pages == 1
