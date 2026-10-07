import logging
from dataclasses import dataclass, field
from typing import List

import fitz  # PyMuPDF
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PdfConversion:
    markdown: str
    failed_pages: List[int] = field(default_factory=list)
    ocr_pages: int = 0
    text_pages: int = 0


def _extract_text_layer(page):
    """Return the embedded text layer if the page has real (digital) text.

    Scanned pages return empty/near-empty text, so a short result means
    the page needs OCR.
    """
    text = page.get_text("text").strip()
    compact = "".join(text.split())
    if len(compact) >= 50:
        return text
    return None


def convert_pdf_with_report(file_path, dpi=300):
    """
    Converts a PDF file to Markdown and reports per-page problems.

    Pages with an embedded text layer are extracted directly (no OCR).
    Scanned pages are rendered as images and processed with PaddleOCR
    using paragraph-aware layout analysis (XY-Cut). A page whose OCR raises
    is recorded in ``failed_pages`` and marked in the output instead of being
    silently dropped.
    """
    from src.converters.ocr_engine import get_ocr_text

    pages_md = []
    failed_pages = []
    ocr_pages = 0
    text_pages = 0

    with fitz.open(file_path) as doc:
        total = len(doc)
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        for i, page in enumerate(doc):
            page_no = i + 1
            text = _extract_text_layer(page)
            if text is not None:
                logger.info("Text layer page %d/%d (OCR skipped)", page_no, total)
                text_pages += 1
            else:
                logger.info("OCR processing page %d/%d...", page_no, total)
                try:
                    pix = page.get_pixmap(matrix=mat, alpha=False)
                    # Wrap the raw pixel buffer directly (RGB) instead of
                    # round-tripping through PNG encode/decode. copy() makes
                    # the array writable for OCR.
                    img = (
                        np.frombuffer(pix.samples, dtype=np.uint8)
                        .reshape(pix.height, pix.width, pix.n)
                        .copy()
                    )
                    text = get_ocr_text(img, paragraph=True)
                    ocr_pages += 1
                except Exception as exc:
                    logger.error("OCR failed on page %d/%d: %s", page_no, total, exc)
                    failed_pages.append(page_no)
                    pages_md.append(f"<!-- OCR failed: page {page_no} -->")
                    continue

            if text and text.strip():
                pages_md.append(text.strip())

    if not any(p for p in pages_md if not p.startswith("<!-- OCR failed")):
        raise RuntimeError(
            f"PDF에서 텍스트를 추출하지 못했습니다: {file_path}"
        )

    return PdfConversion(
        markdown="\n\n---\n\n".join(pages_md),
        failed_pages=failed_pages,
        ocr_pages=ocr_pages,
        text_pages=text_pages,
    )


def convert_pdf_to_md(file_path, dpi=300):
    """Backward-compatible wrapper returning only the Markdown string."""
    return convert_pdf_with_report(file_path, dpi=dpi).markdown
