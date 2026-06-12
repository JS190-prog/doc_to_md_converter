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

def save_markdown(content, output_path):
    """Saves content to a markdown file with UTF-8 encoding (with BOM for Windows)."""
    with open(output_path, 'w', encoding='utf-8-sig') as f:
        f.write(content)
