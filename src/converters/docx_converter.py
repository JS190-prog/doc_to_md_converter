import os
# import docx  <-- Moved to lazy import in function
from src.utils.md_helpers import md_header, md_bold, md_italic, clean_text

def get_font_name(run):
    """
    Extracts font name, checking specifically for East Asia fonts (Korean).
    """
    from docx.oxml.ns import qn
    rPr = run._element.rPr
    if rPr is None:
        return None
    
    # Check for eastAsia font (common for Korean like Malgun Gothic)
    if rPr.rFonts is not None:
        east_asia = rPr.rFonts.get(qn('w:eastAsia'))
        if east_asia:
            return east_asia
        ascii_font = rPr.rFonts.get(qn('w:ascii'))
        if ascii_font:
            return ascii_font
    return None

def convert_docx_to_md(file_path):
    """
    Converts a .docx file to Markdown.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    import docx
    doc = docx.Document(file_path)
    md_lines = []

    # Process Paragraphs
    for para in doc.paragraphs:
        style_name = para.style.name.lower()
        text = ""
        
        # Heading processing
        if 'heading' in style_name:
            try:
                level = int(style_name.replace('heading', '').strip())
                text = md_header(para.text, level)
            except ValueError:
                text = para.text + "\n\n"
        
        # Normal text with Run processing (Bold/Italic/Font checks)
        else:
            para_text = ""
            for run in para.runs:
                content = run.text
                if not content:
                    continue
                
                # Font check (debug/logging logic could go here)
                # font_name = get_font_name(run) # Used for debugging specific font handling if needed
                
                if run.bold:
                    content = md_bold(content)
                if run.italic:
                    content = md_italic(content)
                
                para_text += content
            
            # List item detection
            if 'list' in style_name:
                text = f"- {para_text}\n"
            else:
                text = f"{para_text}\n\n"
        
        if text.strip():
            md_lines.append(text)

    # Process Tables
    # Note: docx.Document.iter_inner_content() is ideal but complex to interleave perfectly.
    # For simplicity in this v1, we append tables at the end or try to define position if possible.
    # Standard python-docx doesn't easily give strict linear order of tables vs paragraphs without iter_inner_content 
    # (which is available in newer versions or via XML parsing).
    # We will use a simplified approach: Parse document body elements in order.
    
    md_lines = [] # Reset to do robust body iteration
    
    for element in doc.element.body:
        if element.tag.endswith('p'): # Paragraph
            para = docx.text.paragraph.Paragraph(element, doc)
            style_name = para.style.name.lower()
            
            # (Reuse logic from above)
            para_text = ""
            for run in para.runs:
                content = run.text
                if not content: continue
                if run.bold: content = md_bold(content)
                if run.italic: content = md_italic(content)
                para_text += content
            
            final_text = ""
            if 'heading' in style_name:
                try:
                    level = int(style_name.replace('heading', '').split()[0]) # strict parsing
                    final_text = md_header(para_text, level)
                except:
                    final_text = f"{para_text}\n\n"
            elif 'list' in style_name:
                final_text = f"- {para_text}\n"
            else:
                final_text = f"{para_text}\n\n"
            
            if final_text.strip():
                md_lines.append(final_text)
                
        elif element.tag.endswith('tbl'): # Table
            table = docx.table.Table(element, doc)
            # Convert table to MD
            # 1. Header
            rows = table.rows
            if not rows: continue
            
            # Get first row as header (assumption)
            headers = [cell.text.strip().replace('\n', ' ') for cell in rows[0].cells]
            md_lines.append("| " + " | ".join(headers) + " |\n")
            md_lines.append("| " + " | ".join(['---'] * len(headers)) + " |\n")
            
            # Data rows
            for row in rows[1:]:
                cells = [cell.text.strip().replace('\n', '<br>') for cell in row.cells]
                md_lines.append("| " + " | ".join(cells) + " |\n")
            md_lines.append("\n")

    return "".join(md_lines)
