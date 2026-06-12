# Offline EXE Build (Windows)

This project now supports an offline one-folder `.exe` build.

## What is included
- `dist/DocToMdConverter/DocToMdConverter.exe`
- Python runtime + package dependencies
- Bundled PaddleOCR model files in `runtime_assets/paddle_models`

On first launch, the app copies bundled OCR model files to:
- `%LOCALAPPDATA%/doc_to_md_converter/paddle_models`

This is the "self-install" step. No network is required at runtime.

## Build command
Run from project root:

```powershell
.\build_offline_exe.ps1
```

If `python` command is not your main interpreter, pass it explicitly:

```powershell
.\build_offline_exe.ps1 -PythonExe "C:\Path\To\python.exe"
```

## Notes
- `.doc` conversion still requires Microsoft Word installed on the target PC.
- The first build must run in an environment where PaddleOCR packages can be installed.
- `scripts/prepare_offline_assets.py` prepares model files under `offline_assets/paddle_models` for bundling.

