import os
import re
import subprocess
import sys
from src.converters.docx_converter import convert_docx_to_md
from src.converters.hwp_converter import convert_hwp_to_md
from src.converters.hwpx_converter import convert_hwpx_to_md
from src.converters.kordoc_converter import convert_with_kordoc
from src.converters.markitdown_converter import convert_with_markitdown
from src.converters.pdf_converter import convert_pdf_to_md
from src.converters.pptx_converter import convert_pptx_to_md
from src.converters.xls_converter import convert_xls_to_md
from src.converters.xlsx_converter import convert_xlsx_to_md
from src.utils.md_helpers import save_markdown
# import win32com.client as win32 # moved to function


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

def convert_doc_using_word(file_path):
    """
    Converts .doc to .docx using Word Interop, then reads .docx.
    """
    word = None
    try:
        import win32com.client as win32
        # DispatchEx starts a dedicated Word instance, so Quit() below can
        # never close a Word window the user has open.
        word = win32.DispatchEx("Word.Application")
        word.Visible = False

        # WE NEED ABSOLUTE PATH (Normalizes forward slashes to backslashes)
        abs_path = os.path.abspath(file_path)
        doc = word.Documents.Open(abs_path)

        new_path = abs_path + "x" # .doc -> .docx
        doc.SaveAs2(new_path, FileFormat=16) # 16 = wdFormatXMLDocument
        doc.Close()

        return new_path
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass


def _normalize_markdown(markdown_content):
    if not markdown_content:
        return ""

    normalized = markdown_content.replace("\r\n", "\n").replace("\r", "\n")
    normalized = normalized.replace("\xa0", " ")
    return normalized.strip()


def _is_usable_markdown(markdown_content, file_ext):
    normalized = _normalize_markdown(markdown_content)
    if not normalized:
        return False

    compact = "".join(normalized.split())
    if len(compact) < 40:
        return False

    lower_compact = compact.lower()
    if file_ext in (".xlsx", ".xls"):
        bad_tokens = lower_compact.count("unnamed:") + lower_compact.count("nan")
        return bad_tokens * 10 < max(len(compact), 1)

    if file_ext == ".pdf":
        image_only = normalized.count("![](") > 0 and len(compact) < 200
        if image_only:
            return False

    return True


_PDF_PAGE_MARKER_RE = re.compile(
    r"^[\s\ufeff]*\[PDF\s+page\s+(\d+)\b[^\]]*\]",
    re.IGNORECASE | re.MULTILINE,
)
_PDF_MIN_PAGE_COVERAGE = 0.95
_PDF_SPARSE_COVER_MIN_CHARS = 10


def _pdf_page_coverage(markdown_content, file_path):
    """Return a fail-closed page-preservation check for generated PDF Markdown.

    Some PDF routers return a large, plausible-looking Markdown document while
    silently omitting most pages.  The ingest pipeline requires page provenance,
    so character count alone is not sufficient evidence of a successful PDF
    conversion.
    """
    try:
        import fitz

        with fitz.open(file_path) as document:
            expected = len(document)
    except Exception as exc:
        return {"status": "fail", "expected_pages": None, "observed_pages": 0, "ratio": 0.0, "error": str(exc)}

    observed = {
        int(match.group(1))
        for match in _PDF_PAGE_MARKER_RE.finditer(markdown_content or "")
    }
    valid = {page for page in observed if 1 <= page <= expected}
    ratio = len(valid) / expected if expected else 0.0
    return {
        "status": "pass" if expected and ratio >= _PDF_MIN_PAGE_COVERAGE else "fail",
        "expected_pages": expected,
        "observed_pages": len(valid),
        "ratio": ratio,
        "missing_pages": max(0, expected - len(valid)),
    }


def _usable_pdf_markdown(markdown_content, file_path):
    coverage = _pdf_page_coverage(markdown_content, file_path)
    if coverage.get("status") != "pass":
        return False, coverage
    if not _is_usable_markdown(markdown_content, ".pdf"):
        matches = list(_PDF_PAGE_MARKER_RE.finditer(markdown_content or ""))
        body = markdown_content[matches[0].end():] if len(matches) == 1 else ""
        body_chars = len("".join(body.split()))
        sparse_cover = (
            coverage.get("expected_pages") == 1
            and coverage.get("observed_pages") == 1
            and body_chars >= _PDF_SPARSE_COVER_MIN_CHARS
        )
        if not sparse_cover:
            return False, {"status": "fail", "reason": "low_quality_markdown", **coverage}
        coverage = {
            **coverage,
            "sparse_cover_accepted": True,
            "sparse_cover_body_chars": body_chars,
        }
    return True, coverage


def _convert_docx_with_router(file_path):
    errors = []

    try:
        markdown = convert_with_markitdown(file_path)
        if _is_usable_markdown(markdown, ".docx"):
            print("[engine] docx -> markitdown")
            return markdown
        errors.append("markitdown produced low-quality output")
    except Exception as exc:
        errors.append(f"markitdown: {exc}")

    try:
        markdown = convert_with_kordoc(file_path)
        if _is_usable_markdown(markdown, ".docx"):
            print("[engine] docx -> kordoc fallback")
            return markdown
        errors.append("kordoc produced low-quality output")
    except Exception as exc:
        errors.append(f"kordoc: {exc}")

    try:
        markdown = convert_docx_to_md(file_path)
        if _is_usable_markdown(markdown, ".docx"):
            print("[engine] docx -> python-docx fallback")
            return markdown
        errors.append("python-docx converter produced low-quality output")
    except Exception as exc:
        errors.append(f"python-docx: {exc}")

    raise RuntimeError("DOCX conversion failed. " + " | ".join(errors))


def _pdf_digital_page_ratio(file_path):
    """Fraction of pages that carry a real text layer (0.0 ~ 1.0)."""
    import fitz

    doc = fitz.open(file_path)
    try:
        total = len(doc)
        if total == 0:
            return 0.0
        digital = 0
        for page in doc:
            compact = "".join(page.get_text("text").split())
            if len(compact) >= 50:
                digital += 1
        return digital / total
    finally:
        doc.close()


def _convert_pdf_with_router(file_path):
    errors = []

    # kordoc reconstructs table structure from digital PDFs, but converts
    # the whole file at once — only trust it when (almost) every page has
    # a text layer, so scanned pages are never silently dropped.
    try:
        digital_ratio = _pdf_digital_page_ratio(file_path)
    except Exception as exc:
        digital_ratio = 0.0
        errors.append(f"text-layer probe: {exc}")

    if digital_ratio >= 0.9:
        try:
            markdown = convert_with_kordoc(file_path)
            usable, coverage = _usable_pdf_markdown(markdown, file_path)
            if usable:
                print("[engine] pdf -> kordoc (digital)")
                return markdown
            errors.append(f"kordoc produced incomplete PDF coverage: {coverage}")
        except Exception as exc:
            errors.append(f"kordoc: {exc}")

    try:
        markdown = convert_pdf_to_md(file_path)
        usable, coverage = _usable_pdf_markdown(markdown, file_path)
        if usable:
            print("[engine] pdf -> text-layer/ocr")
            return markdown
        errors.append(f"ocr converter produced incomplete PDF coverage: {coverage}")
    except Exception as exc:
        errors.append(f"ocr: {exc}")

    try:
        markdown = convert_with_markitdown(file_path)
        usable, coverage = _usable_pdf_markdown(markdown, file_path)
        if usable:
            print("[engine] pdf -> markitdown fallback")
            return markdown
        errors.append(f"markitdown produced incomplete PDF coverage: {coverage}")
    except Exception as exc:
        errors.append(f"markitdown: {exc}")

    raise RuntimeError("PDF conversion failed. " + " | ".join(errors))

def process_file(file_path):
    """
    Main entry point for converting files.
    Returns (success: bool, message: str)
    """
    file_ext = os.path.splitext(file_path)[1].lower()
    base_name = os.path.splitext(file_path)[0]
    output_path = f"{base_name}_converted.md"
    
    try:
        markdown_content = ""
        
        if file_ext == '.docx':
            markdown_content = _convert_docx_with_router(file_path)
        
        elif file_ext == '.doc':
            # Try converting to docx first
            temp_docx = convert_doc_using_word(file_path)
            if temp_docx and os.path.exists(temp_docx):
                markdown_content = _convert_docx_with_router(temp_docx)
                # Cleanup temp file? Maybe keep it for user.
                # os.remove(temp_docx)
            else:
                return False, "Failed to convert .doc (Word Interop Error)"
        
        elif file_ext == '.pdf':
            markdown_content = _convert_pdf_with_router(file_path)

        elif file_ext == '.pptx':
            markdown_content = convert_pptx_to_md(file_path, output_path)

        elif file_ext == '.xlsx':
            try:
                markdown_content = convert_xlsx_to_md(file_path)
            except Exception as xlsx_err:
                print(f"[kordoc fallback] xlsx: {xlsx_err}")
                markdown_content = convert_with_kordoc(file_path)

        elif file_ext == '.xls':
            try:
                markdown_content = convert_xls_to_md(file_path)
            except Exception as xls_err:
                print(f"[kordoc fallback] xls: {xls_err}")
                markdown_content = convert_with_kordoc(file_path)

        elif file_ext in ('.hwp', '.hwpx'):
            # kordoc first: best table fidelity (merged cells, nested
            # tables) and widest HWP coverage (3.x, distribution HWP).
            try:
                markdown_content = convert_with_kordoc(file_path)
                print("[engine] hwp -> kordoc")
            except Exception as kordoc_err:
                print(f"[kordoc -> hwp2md fallback] {kordoc_err}")
                try:
                    markdown_content = convert_hwp_with_hwp2md(file_path)
                except Exception as hwp2md_err:
                    # Fallback to built-in converter
                    print(f"[hwp2md fallback] {hwp2md_err}")
                    if file_ext == '.hwp':
                        markdown_content = convert_hwp_to_md(file_path)
                    else:
                        markdown_content = convert_hwpx_to_md(file_path)
        
        else:
            return False, "Unsupported file format"
            
        save_markdown(markdown_content, output_path)
        return True, f"Saved to {os.path.basename(output_path)}"
        
    except Exception as e:
        return False, str(e)
