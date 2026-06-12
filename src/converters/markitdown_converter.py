from __future__ import annotations

import os


SUPPORTED_MARKITDOWN_EXTENSIONS = {".docx", ".pdf"}


def _clean_markdown(markdown: str) -> str:
    return markdown.replace("\r\n", "\n").replace("\r", "\n").replace("\xa0", " ").strip()


def convert_with_markitdown(file_path: str) -> str:
    """
    Convert supported files to Markdown using MarkItDown.

    MarkItDown returns a result object that may populate either `markdown`
    or `text_content`, depending on the converter.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext not in SUPPORTED_MARKITDOWN_EXTENSIONS:
        raise ValueError(f"MarkItDown is not enabled for {file_ext or 'this file type'}")

    try:
        from markitdown import MarkItDown
    except ImportError as exc:
        raise ImportError(
            "markitdown is not installed. Install markitdown[pdf,docx] to enable this engine."
        ) from exc

    converter = MarkItDown(enable_plugins=False)
    result = converter.convert(file_path)
    markdown = getattr(result, "markdown", "") or getattr(result, "text_content", "") or ""
    markdown = _clean_markdown(markdown)

    if not markdown:
        raise RuntimeError(f"MarkItDown produced empty output for {os.path.basename(file_path)}")

    return markdown + "\n"
