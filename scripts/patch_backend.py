import os

backend_file = r"c:\Users\USER\.gemini\antigravity\scratch\doc_to_md_converter\src\backend.py"

with open(backend_file, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the doc opening logic
old_code = """
    try:
        import win32com.client as win32
        word = win32.Dispatch("Word.Application")
        word.Visible = False
        doc = word.Documents.Open(file_path)
        
        new_path = file_path + "x" # .doc -> .docx
"""
old_code = old_code.strip()

new_code = """
    try:
        import win32com.client as win32
        word = win32.Dispatch("Word.Application")
        word.Visible = False
        
        # WE NEED ABSOLUTE PATH (Normalizes forward slashes to backslashes)
        abs_path = os.path.abspath(file_path)
        doc = word.Documents.Open(abs_path)
        
        new_path = abs_path + "x" # .doc -> .docx
"""
new_code = new_code.strip()

# Replace exception catching logic for printing
old_except = """
    except Exception as e:
        return None
"""
old_except = old_except.strip()

new_except = """
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None
"""
new_except = new_except.strip()


if old_code in content:
    content = content.replace(old_code, new_code)
    print("Replaced Word opening logic.")
else:
    print("Could not find Word opening logic.")

if old_except in content:
    content = content.replace(old_except, new_except)
    print("Replaced exception logic.")
else:
    print("Could not find exception logic.")

if "temp_docx =" in content:
    # Let's also do a small update on the error message to be more explicit if it fails
    content = content.replace(
        'return False, "Failed to convert .doc (Word required)"',
        'return False, "Failed to convert .doc (Word Interop Error)"'
    )
    print("Replaced process_file error message.")

with open(backend_file, 'w', encoding='utf-8') as f:
    f.write(content)

print("backend.py updated successfully.")
