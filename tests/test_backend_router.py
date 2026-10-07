import os

import pytest

from src import backend
from src.backend import (
    _is_usable_markdown,
    _run_chain,
    convert_file,
    default_output_path,
)


# ---- _is_usable_markdown -------------------------------------------------

def test_usable_rejects_empty_and_short():
    assert not _is_usable_markdown("", ".docx")
    assert not _is_usable_markdown("짧음", ".docx")
    assert _is_usable_markdown("짧음", ".docx", min_chars=1)


def test_nan_check_ignores_words_containing_nan():
    text = "| Finance | Hannan | Banana |\n| --- | --- | --- |\n" + "| revenue | 100 | 200 |\n" * 5
    assert _is_usable_markdown(text, ".xlsx")


def test_nan_check_flags_pandas_garbage():
    text = "| Unnamed: 0 | nan | nan |\n" * 10
    assert not _is_usable_markdown(text, ".xlsx")


def test_pdf_image_only_rejected():
    assert not _is_usable_markdown("![](a.png)\n" + "x" * 60, ".pdf")


# ---- default_output_path -------------------------------------------------

def test_output_path_plain(tmp_path):
    f = tmp_path / "report.docx"
    f.write_bytes(b"")
    assert default_output_path(str(f)) == str(tmp_path / "report_converted.md")


def test_output_path_disambiguates_same_stem(tmp_path):
    (tmp_path / "report.docx").write_bytes(b"")
    (tmp_path / "report.pdf").write_bytes(b"")
    assert default_output_path(str(tmp_path / "report.docx")).endswith("report_docx_converted.md")
    assert default_output_path(str(tmp_path / "report.pdf")).endswith("report_pdf_converted.md")


def test_output_path_ignores_unrelated_siblings(tmp_path):
    (tmp_path / "report.docx").write_bytes(b"")
    (tmp_path / "report.txt").write_bytes(b"")
    assert default_output_path(str(tmp_path / "report.docx")).endswith("report_converted.md")


# ---- _run_chain ----------------------------------------------------------

GOOD = "내용이 충분히 긴 정상 변환 결과입니다. " * 5


def test_chain_falls_back_after_exception():
    def boom():
        raise RuntimeError("engine down")

    md, engine = _run_chain("docx", ".docx", [("a", boom), ("b", lambda: GOOD)])
    assert engine == "b" and md == GOOD


def test_chain_skips_low_quality_then_uses_next():
    md, engine = _run_chain("docx", ".docx", [("a", lambda: "x"), ("b", lambda: GOOD)])
    assert engine == "b"


def test_chain_returns_short_output_when_nothing_better():
    md, engine = _run_chain("docx", ".docx", [("a", lambda: "짧은 공문")])
    assert engine == "a" and md == "짧은 공문"


def test_chain_raises_when_all_fail():
    def boom():
        raise RuntimeError("nope")

    with pytest.raises(RuntimeError, match="DOCX conversion failed.*nope"):
        _run_chain("docx", ".docx", [("a", boom), ("b", lambda: "")])


# ---- convert_file --------------------------------------------------------

def test_convert_file_unsupported(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("hi")
    result = convert_file(str(f))
    assert not result.success and "Unsupported" in result.message


def test_same_stem_conversions_do_not_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(backend, "_convert_docx_with_router", lambda p, **k: ("DOCX BODY", "stub"))
    monkeypatch.setattr(backend, "_convert_pdf_with_router", lambda p, w: ("PDF BODY", "stub"))
    (tmp_path / "r.docx").write_bytes(b"")
    (tmp_path / "r.pdf").write_bytes(b"")

    r1 = convert_file(str(tmp_path / "r.docx"))
    r2 = convert_file(str(tmp_path / "r.pdf"))

    assert r1.output_path != r2.output_path
    assert open(r1.output_path, encoding="utf-8-sig").read() == "DOCX BODY"
    assert open(r2.output_path, encoding="utf-8-sig").read() == "PDF BODY"


def test_pdf_failed_pages_surface_as_warning(tmp_path, monkeypatch):
    from src.converters.pdf_converter import PdfConversion

    monkeypatch.setattr(backend, "_pdf_digital_page_ratio", lambda p: 0.0)
    monkeypatch.setattr(
        backend,
        "convert_pdf_with_report",
        lambda p: PdfConversion(markdown=GOOD, failed_pages=[2, 5]),
    )
    pdf = tmp_path / "scan.pdf"
    pdf.write_bytes(b"")
    result = convert_file(str(pdf))
    assert result.success
    assert result.warnings == ["OCR failed on page(s): 2, 5"]
    assert "WARNING" in result.message


def test_doc_temp_docx_is_not_left_next_to_source(tmp_path, monkeypatch):
    seen = {}

    def fake_word(path, out_dir=None):
        seen["out_dir"] = out_dir
        target = os.path.join(out_dir, "old.docx")
        open(target, "wb").close()
        return target

    monkeypatch.setattr(backend, "convert_doc_using_word", fake_word)
    monkeypatch.setattr(backend, "_convert_docx_with_router", lambda p, **k: (GOOD, "stub"))
    src = tmp_path / "old.doc"
    src.write_bytes(b"")
    assert convert_file(str(src)).success
    assert not (tmp_path / "old.docx").exists()
    assert seen["out_dir"] != str(tmp_path)
