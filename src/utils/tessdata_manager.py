import os
import requests
import shutil
import sys

# URL for Tesseract 4.0.0+ best data (most accurate)
KOR_DATA_URL = "https://github.com/tesseract-ocr/tessdata_best/raw/main/kor.traineddata"
ENG_DATA_URL = "https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata"

def get_writable_tessdata_dir():
    """
    Returns a writable directory path for tessdata.
    Usually user's local app data if Program Files is locked.
    """
    local_app_data = os.getenv('LOCALAPPDATA', os.path.expanduser('~'))
    tess_dir = os.path.join(local_app_data, 'doc_to_md_converter', 'tessdata')
    os.makedirs(tess_dir, exist_ok=True)
    return tess_dir

def download_file(url, dest_path):
    print(f"Downloading {os.path.basename(dest_path)} from internet...")
    try:
        # Add timeout (10s connect, 60s read)
        response = requests.get(url, stream=True, timeout=(10, 60))
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                downloaded += len(chunk)
                # Optional: minimal progress indicator (dots)
                # print(".", end="", flush=True) 
        
        print(f"\nDownload complete: {os.path.basename(dest_path)}")
        return True
    except Exception as e:
        print(f"\nFailed to download {os.path.basename(dest_path)}: {e}")
        # Clean up partial file
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False

def ensure_kor_data(tesseract_cmd_path):
    """
    Ensures kor.traineddata exists.
    Returns the path to the tessdata directory to be used.
    """
    # 1. Check default tessdata directory (relative to executable)
    tess_install_dir = os.path.dirname(tesseract_cmd_path)
    default_tessdata = os.path.join(tess_install_dir, 'tessdata')
    
    kor_path_default = os.path.join(default_tessdata, 'kor.traineddata')
    
    # If it exists in default location, easy.
    if os.path.exists(kor_path_default):
        return default_tessdata

    print("Korean language data not found in default location.")
    
    # 2. Skip trying to write to Program Files (triggers UAC/Permission errors on Windows)
    # We will go directly to local user storage which is safe.
    print("Code 200: Preparing local storage for OCR data...")

    # 3. Fallback: Use local directory
    local_tessdata = get_writable_tessdata_dir()
    kor_path_local = os.path.join(local_tessdata, 'kor.traineddata')
    eng_path_local = os.path.join(local_tessdata, 'eng.traineddata')
    
    # We also need English for 'kor+eng' mode
    if not os.path.exists(eng_path_local):
        print("English data needs update...")
        # Try copying from default if available, else download
        eng_path_default = os.path.join(default_tessdata, 'eng.traineddata')
        if os.path.exists(eng_path_default):
            try:
                shutil.copy2(eng_path_default, eng_path_local)
            except:
                download_file(ENG_DATA_URL, eng_path_local)
        else:
             download_file(ENG_DATA_URL, eng_path_local)

    if not os.path.exists(kor_path_local):
        if not download_file(KOR_DATA_URL, kor_path_local):
             print("\n" + "="*60)
             print(" [ERROR] Failed to download Korean language data.")
             print("Please install manually:")
             print(f" 1. Download: {KOR_DATA_URL}")
             print(f" 2. Copy to: {local_tessdata}")
             print("   (Or your Tesseract installation folder's tessdata)")
             print("="*60 + "\n")
             return local_tessdata # Return anyway (will fail later but user sees msg)
        
    return local_tessdata
