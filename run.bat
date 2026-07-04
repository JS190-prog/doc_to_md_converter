@echo off
setlocal
echo Starting Doc/PDF to Markdown Converter...

if defined DOC_TO_MD_PYTHON (
    set "PYTHON_EXE=%DOC_TO_MD_PYTHON%"
) else (
    set "PYTHON_EXE=python"
)

set KMP_DUPLICATE_LIB_OK=TRUE
set PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
REM python diagnose.py
"%PYTHON_EXE%" -m src.main
pause
