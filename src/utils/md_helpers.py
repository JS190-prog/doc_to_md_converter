import re
import os

def clean_text(text):
    """Cleans text from excessive whitespace."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def md_header(text, level=1):
    return f"{'#' * level} {text}\n\n"

def md_bold(text):
    return f"**{text}**"

def md_italic(text):
    return f"*{text}*"

def md_image(alt_text, image_path):
    return f"![{alt_text}]({image_path})\n\n"

def _bom_enabled():
    return os.environ.get("DOC2MD_UTF8_BOM", "1").strip().lower() not in ("0", "false", "no", "off")


def save_markdown(content, output_path, bom=None):
    """Save Markdown as UTF-8. A BOM (helps Windows Notepad) is written by
    default; pass ``bom=False`` or set DOC2MD_UTF8_BOM=0 for BOM-less output
    (better for RAG ingestion and strict Markdown tooling)."""
    if bom is None:
        bom = _bom_enabled()
    with open(output_path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="\n") as f:
        f.write(content)
