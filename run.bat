@echo off
echo Starting Doc/PDF to Markdown Converter...
call "C:\Users\USER\miniconda3\Scripts\activate.bat"
set "PATH=C:\Users\USER\miniconda3\Library\bin;%PATH%"
set KMP_DUPLICATE_LIB_OK=TRUE
set PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
REM python diagnose.py
python -m src.main
pause
