import subprocess
import os
import ctypes
import sys

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def install_tesseract():
    """
    Attempts to install Tesseract OCR using winget.
    """
    print("Attempting to install Tesseract OCR via winget...")
    
    # Winget command
    # -e: Exact match
    # --id: Package ID
    # --silent: Try to be less intrusive (might still prompt UAC)
    # --accept-source-agreements --accept-package-agreements: Automate prompts
    cmd = [
        "winget", "install", "-e", "--id", "UB-Mannheim.TesseractOCR",
        "--accept-source-agreements", "--accept-package-agreements"
    ]

    try:
        # Run winget
        # Note: This often requires a UAC prompt. If shell=True, it pops up in a new window or inline.
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        if result.returncode == 0:
            print("Tesseract installed successfully.")
            return True
        else:
            print(f"Winget install failed: {result.stderr}")
            # Fallback or specific error handling?
            return False
            
    except Exception as e:
        print(f"Error running winget: {e}")
        return False
