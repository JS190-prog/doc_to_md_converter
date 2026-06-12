import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from src.gui import App
from src.utils.offline_ocr_assets import prepare_offline_ocr_assets

if __name__ == "__main__":
    # First-run setup: copy bundled OCR models into a writable local directory.
    prepare_offline_ocr_assets()
    app = App()
    app.mainloop()
