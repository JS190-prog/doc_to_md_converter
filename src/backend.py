import logging
import os
import re
import subprocess
import sys
import tempfile
from src.converters.docx_converter import convert_docx_to_md
from src.converters.hwp_converter import convert_hwp_to_md
from src.converters.hwpx_converter import convert_hwpx_to_md
from src.converters.kordoc_converter import convert_with_kordoc
from src.converters.markitdown_converter import convert_with_markitdown
from src.converters.pdf_converter import convert_pdf_with_report
from src.converters.pptx_converter import convert_pptx_to_md
from src.converters.xls_converter import convert_xls_to_md
from src.converters.xlsx_converter import convert_xlsx_to_md
from src.result import ConversionResult
from src.utils.md_helpers import save_markdown

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = (
    ".docx", ".doc", ".pdf", ".pptx", ".xlsx", ".xls", ".hwp", ".hwpx",
)


def _find_hwp2md_exe():
    """Locate hwp2md.exe bundled in tools/ directory."""
    # When running as PyInstaller exe, use sys._MEIPASS
    if getattr(sys, "frozen", False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    exe = os.path.join(base, "tools", "hwp2md.exe")
    if os.path.isfile(exe):
        return exe
    return None


def convert_hwp_with_hwp2md(file_path):
    """Convert HWP/HWPX using external hwp2md CLI tool.
    Returns markdown string on success, raises on failure."""
    exe = _find_hwp2md_exe()
    if exe is None:
        raise FileNotFoundError("hwp2md.exe not found in tools/ directory")

    result = subprocess.run(
        [exe, os.path.abspath(file_path), "-q"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"hwp2md failed (exit {result.returncode}): {stderr}")

    md = result.stdout
    if not md or not md.strip():
        raise RuntimeError("hwp2md produced empty output")
    return md

def convert_doc_using_word(file_path, out_dir=None):
    """
    Converts .doc to .docx using Word Interop and returns the .docx path
    (None on failure). The .docx is written to ``out_dir`` (a temp directory
    by the caller) so it never overwrites a file next to the source.
    """
    word = None
    try:
        import win32com.client as win32
        # DispatchEx starts a dedicated Word instance, so Quit() below can
        # never close a Word window the user has open.
        word = win32.DispatchEx("Word.Application")
        word.Visible = False

        # Word needs an absolute, backslash-normalized path.
        abs_path = os.path.abspath(file_path)
        doc = word.Documents.Open(abs_path)

        target_dir = out_dir or os.path.dirname(abs_path)
        stem = os.path.splitext(os.path.basename(abs_path))[0]
        new_path = os.path.join(target_dir, stem + ".docx")
        try:
            doc.SaveAs2(new_path, FileFormat=16)  # 16 = wdFormatXMLDocument
        finally:
            doc.Close()

        return new_path
    except Exception:
        logger.exception("Word interop failed for %s", file_path)
        return None
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass


def default_output_path(file_path):
    """Output path for ``file_path``: ``<stem>_converted.md`` next to it.

    If another supported document with the same stem sits in the folder
    (e.g. ``report.docx`` + ``report.pdf``) the source extension is added
    (``report_pdf_converted.md``) so the conversions cannot overwrite each other.
    """
    folder = os.path.dirname(os.path.abspath(file_path))
    stem, ext = os.path.splitext(os.path.basename(file_path))
    ext = ext.lower()
    try:
        siblings = os.listdir(folder)
    except OSError:
        siblings = []
    clash = any(
        os.path.splitext(name)[0].lower() == stem.lower()
        and os.path.splitext(name)[1].lower() in SUPPORTED_EXTENSIONS
        and os.path.splitext(name)[1].lower() != ext
        for name in siblings
    )
    suffix = f"_{ext.lstrip('.')}" if clash else ""
    return os.path.join(folder, f"{stem}{suffix}_converted.md")


def _normalize_markdown(markdown_content):
    if not markdown_content:
        return ""

    normalized = markdown_content.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\xa0", " ")
    return normalized.strip()


_BAD_SHEET_TOKEN = re.compile(r"unnamed:|\bnan\b", re.IGNORECASE)


def _is_usable_markdown(markdown_content, file_ext, min_chars=40):
    normalized = _normalize_markdown(markdown_content)
    if not normalized:
        return False

    compact = "".join(normalized.split())
    if len(compact) < min_chars:
        return False

    if file_ext in (".xlsx", ".xls"):
        bad_tokens = len(_BAD_SHEET_TOKEN.findall(normalized))
        return bad_tokens * 10 < max(len(compact), 1)

    if file_ext == ".pdf":
        image_only = normalized.count("![](") > 0 and len(compact) < 200
        if image_only:
            return False

    return True


def _run_chain(label, file_ext, steps, errors=None):
    """Try ``steps`` ([(engine, callable)]) in order; return (markdown, engine).

    The first output that passes the quality check wins. If none does but some
    engine produced non-empty text (e.g. a genuinely short document), the
    longest such output is returned instead of failing the conversion.
    """
    errors = [] if errors is None else errors
    best = None
    for engine, fn in steps:
        try:
            markdown = fn()
        except Exception as exc:
            logger.info("%s: %s failed: %s", label, engine, exc)
            errors.append(f"{engine}: {exc}")
            continue
        if _is_usable_markdown(markdown, file_ext):
            logger.info("[engine] %s -> %s", label, engine)
            return markdown, engine
        if _is_usable_markdown(markdown, file_ext, min_chars=1):
            if best is None or len(markdown) > len(best[0]):
                best = (markdown, engine)
        errors.append(f"{engine} produced low-quality output")

    if best is not None:
        logger.warning("%s: using short/low-quality output from %s", label, best[1])
        return best[0], best[1]
    raise RuntimeError(f"{label.upper()} conversion failed. " + " | ".join(errors))


def _convert_docx_with_router(file_path, asset_origin=None):
    return _run_chain(
        "docx",
        ".docx",
        [
            ("markitdown", lambda: convert_with_markitdown(file_path)),
            ("kordoc", lambda: convert_with_kordoc(file_path, asset_origin=asset_origin)),
            ("python-docx", lambda: convert_docx_to_md(file_path)),
        ],
    )


def _pdf_digital_page_ratio(file_path):
    """Fraction of pages that carry a real text layer (0.0 ~ 1.0)."""
    import fitz

    with fitz.open(file_path) as doc:
        total = len(doc)
        if total == 0:
            return 0.0
        digital = 0
        for page in doc:
            compact = "".join(page.get_text("text").split())
            if len(compact) >= 50:
                digital += 1
        return digital / total


def _convert_pdf_with_router(file_path, warnings):
    errors = []

    # kordoc reconstructs table structure from digital PDFs, but converts
    # the whole file at once — only trust it when (almost) every page has
    # a text layer, so scanned pages are never silently dropped.
    try:
        digital_ratio = _pdf_digital_page_ratio(file_path)
    except Exception as exc:
        digital_ratio = 0.0
        errors.append(f"text-layer probe: {exc}")

    def ocr_step():
        report = convert_pdf_with_report(file_path)
        if report.failed_pages:
            pages = ", ".join(str(p) for p in report.failed_pages)
            warnings.append(f"OCR failed on page(s): {pages}")
        return report.markdown

    steps = []
    if digital_ratio >= 0.9:
        steps.append(("kordoc (digital)", lambda: convert_with_kordoc(file_path)))
    steps.append(("text-layer/ocr", ocr_step))
    steps.append(("markitdown", lambda: convert_with_markitdown(file_path)))
    return _run_chain("pdf", ".pdf", steps, errors)


def _convert_hwp_with_router(file_path, file_ext):
    # kordoc first: best table fidelity (merged cells, nested tables) and
    # widest HWP coverage (3.x, distribution HWP).
    builtin = convert_hwp_to_md if file_ext == ".hwp" else convert_hwpx_to_md
    return _run_chain(
        "hwp",
        file_ext,
        [
            ("kordoc", lambda: convert_with_kordoc(file_path)),
            ("hwp2md", lambda: convert_hwp_with_hwp2md(file_path)),
            ("builtin", lambda: builtin(file_path)),
        ],
    )


def _convert_sheet_with_router(file_path, file_ext, primary):
    return _run_chain(
        file_ext.lstrip("."),
        file_ext,
        [
            ("openpyxl/xlrd", lambda: primary(file_path)),
            ("kordoc", lambda: convert_with_kordoc(file_path)),
        ],
    )


def _convert_doc_with_word(file_path, warnings):
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_docx = convert_doc_using_word(file_path, tmpdir)
        if not temp_docx or not os.path.exists(temp_docx):
            raise RuntimeError("Failed to convert .doc (Word Interop Error)")
        # Pass the user's original path so kordoc images land next to it,
        # not in the soon-deleted temp directory.
        return _convert_docx_with_router(temp_docx, asset_origin=file_path)


def convert_file(file_path, output_path=None):
    """
    Main entry point for converting files; returns a ConversionResult.
    """
    file_ext = os.path.splitext(file_path)[1].lower()
    output_path = output_path or default_output_path(file_path)
    warnings = []

    try:
        if file_ext == ".docx":
            markdown_content, engine = _convert_docx_with_router(file_path)
        elif file_ext == ".doc":
            markdown_content, engine = _convert_doc_with_word(file_path, warnings)
        elif file_ext == ".pdf":
            markdown_content, engine = _convert_pdf_with_router(file_path, warnings)
        elif file_ext == ".pptx":
            markdown_content, engine = convert_pptx_to_md(file_path, output_path), "python-pptx"
        elif file_ext == ".xlsx":
            markdown_content, engine = _convert_sheet_with_router(
                file_path, file_ext, convert_xlsx_to_md
            )
        elif file_ext == ".xls":
            markdown_content, engine = _convert_sheet_with_router(
                file_path, file_ext, convert_xls_to_md
            )
        elif file_ext in (".hwp", ".hwpx"):
            markdown_content, engine = _convert_hwp_with_router(file_path, file_ext)
        else:
            return ConversionResult(False, "Unsupported file format")

        if os.path.exists(output_path):
            logger.info("Overwriting existing %s", os.path.basename(output_path))
        save_markdown(markdown_content, output_path)
    except Exception as exc:
        logger.error("Conversion failed for %s: %s", file_path, exc)
        return ConversionResult(False, str(exc), warnings=warnings)

    message = f"Saved to {os.path.basename(output_path)}"
    if warnings:
        message += " (WARNING: " + "; ".join(warnings) + ")"
    return ConversionResult(
        True, message, output_path=output_path, engine=engine, warnings=warnings
    )


def process_file(file_path):
    """Legacy wrapper: returns ``(success: bool, message: str)``."""
    return convert_file(file_path).as_tuple()
