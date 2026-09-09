from __future__ import annotations

import sys
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src import backend  # noqa: E402


def _pdf_with_pages(path: Path, count: int) -> None:
    document = fitz.open()
    for index in range(count):
        page = document.new_page()
        page.insert_text((72, 72), f"Page {index + 1}")
    document.save(path)
    document.close()


def test_pdf_page_coverage_rejects_plausible_partial_markdown(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    _pdf_with_pages(source, 4)

    partial = "\n\n---\n\n".join(
        f"[PDF page {index} TEXT]\nmeaningful drawing text " * 3
        for index in range(1, 2)
    )

    result = backend._pdf_page_coverage(partial, str(source))

    assert result["status"] == "fail"
    assert result["expected_pages"] == 4
    assert result["observed_pages"] == 1
    assert result["missing_pages"] == 3


def test_pdf_page_coverage_counts_bom_before_first_marker(tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    _pdf_with_pages(source, 2)
    markdown = "\ufeff[PDF page 1 TEXT]\nmeaningful drawing text\n[PDF page 2 TEXT]\nmeaningful drawing text"

    result = backend._pdf_page_coverage(markdown, str(source))

    assert result["status"] == "pass"
    assert result["observed_pages"] == 2
    assert result["missing_pages"] == 0


def test_pdf_router_accepts_a_verified_single_page_sparse_cover(tmp_path: Path) -> None:
    source = tmp_path / "cover.pdf"
    _pdf_with_pages(source, 1)
    markdown = "\ufeff[PDF page 1 OCR]\n코스콤 신사옥 소방 표지"

    usable, coverage = backend._usable_pdf_markdown(markdown, str(source))

    assert usable is True
    assert coverage["sparse_cover_accepted"] is True
    assert coverage["sparse_cover_body_chars"] >= 10


def test_pdf_router_falls_back_when_kordoc_drops_pages(monkeypatch, tmp_path: Path) -> None:
    source = tmp_path / "drawing.pdf"
    _pdf_with_pages(source, 2)
    partial = "[PDF page 1 TEXT]\n" + ("meaningful drawing text " * 20)
    complete = "\n\n---\n\n".join(
        f"[PDF page {index} TEXT]\nmeaningful drawing text " * 20
        for index in range(1, 3)
    )

    monkeypatch.setattr(backend, "_pdf_digital_page_ratio", lambda _path: 1.0)
    monkeypatch.setattr(backend, "convert_with_kordoc", lambda _path: partial)
    monkeypatch.setattr(backend, "convert_pdf_to_md", lambda _path: complete)

    result = backend._convert_pdf_with_router(str(source))

    assert result == complete
    assert backend._pdf_page_coverage(result, str(source))["status"] == "pass"
