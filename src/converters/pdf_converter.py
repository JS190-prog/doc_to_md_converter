import fitz  # PyMuPDF
import numpy as np


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


def convert_pdf_to_md(file_path, dpi=300):
    """
    Converts a PDF file to Markdown.

    Pages with an embedded text layer are extracted directly (no OCR).
    Scanned pages are rendered as images and processed with PaddleOCR
    using paragraph-aware layout analysis (XY-Cut).
    """
    from src.converters.ocr_engine import get_ocr_text

    doc = fitz.open(file_path)
    total = len(doc)
    pages_md = []

    mat = fitz.Matrix(dpi / 72, dpi / 72)
    for i, page in enumerate(doc):
        text = _extract_text_layer(page)
        if text is not None:
            print(f"  Text layer page {i + 1}/{total} (OCR skipped)")
        else:
            print(f"  OCR processing page {i + 1}/{total}...")
            pix = page.get_pixmap(matrix=mat, alpha=False)
            # Wrap the raw pixel buffer directly (RGB) instead of round-tripping
            # through PNG encode/decode. copy() makes the array writable for OCR.
            img = (
                np.frombuffer(pix.samples, dtype=np.uint8)
                .reshape(pix.height, pix.width, pix.n)
                .copy()
            )
            text = get_ocr_text(img, paragraph=True)

        if text.strip():
            pages_md.append(text.strip())

    doc.close()

    if not pages_md:
        raise RuntimeError(
            f"PDF에서 텍스트를 추출하지 못했습니다: {file_path}"
        )

    return "\n\n---\n\n".join(pages_md)
