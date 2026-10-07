import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")

from src.gui import App
from src.utils.logging_setup import configure_logging

if __name__ == "__main__":
    configure_logging()
    # OCR models are staged lazily by OCREngine on the first scanned page, so
    # the window opens immediately instead of blocking on a large model copy.
    app = App()
    app.mainloop()
