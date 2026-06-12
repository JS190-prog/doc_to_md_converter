import os
import subprocess
import sys
from src.converters.docx_converter import convert_docx_to_md
from src.converters.hwp_converter import convert_hwp_to_md
from src.converters.hwpx_converter import convert_hwpx_to_md
from src.converters.markitdown_converter import convert_with_markitdown
from src.converters.pdf_converter import convert_pdf_to_md
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
        markdown = convert_docx_to_md(file_path)
        if _is_usable_markdown(markdown, ".docx"):
            print("[engine] docx -> python-docx fallback")
            return markdown
        errors.append("python-docx converter produced low-quality output")
    except Exception as exc:
        errors.append(f"python-docx: {exc}")

    raise RuntimeError("DOCX conversion failed. " + " | ".join(errors))


def _convert_pdf_with_router(file_path):
    errors = []

    try:
        markdown = convert_pdf_to_md(file_path)
        if _is_usable_markdown(markdown, ".pdf"):
            print("[engine] pdf -> ocr primary")
            return markdown
        errors.append("ocr converter produced low-quality output")
    except Exception as exc:
        errors.append(f"ocr: {exc}")

    try:
        markdown = convert_with_markitdown(file_path)
        if _is_usable_markdown(markdown, ".pdf"):
            print("[engine] pdf -> markitdown fallback")
            return markdown
        errors.append("markitdown produced low-quality output")
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

        elif file_ext == '.xlsx':
            markdown_content = convert_xlsx_to_md(file_path)

        elif file_ext == '.xls':
            markdown_content = convert_xls_to_md(file_path)

        elif file_ext in ('.hwp', '.hwpx'):
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
