# Doc to Markdown Converter

Windows-friendly document conversion utilities for producing Markdown from
office documents, spreadsheets, presentations, HWP/HWPX files, and PDFs.

The project provides a small GUI entry point plus scriptable conversion
commands. PDF conversion prefers existing text layers when available and falls
back to OCR for scanned pages.

## Supported Inputs

- Word: `.docx`, `.doc`
- PowerPoint: `.pptx`
- Excel: `.xlsx`, `.xls`
- Korean word processor files: `.hwp`, `.hwpx`
- PDF: digital text PDFs and scanned PDFs with OCR

## Quick Start

Install Python dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the GUI:

```powershell
python -m src.main
```

Or on Windows, double-click `run.bat`. If you need a specific Python
interpreter, set `DOC_TO_MD_PYTHON` first:

```powershell
$env:DOC_TO_MD_PYTHON = "C:\Path\To\python.exe"
.\run.bat
```

## CLI Usage

Convert one or more files from PowerShell:

```powershell
python .\scripts\convert_to_md_cli.py --json .\sample\123.pdf
```

The converter writes Markdown next to each input file using the
`*_converted.md` suffix.

For bridge integrations, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run_doc_to_md_bridge.ps1 --json .\sample\123.pdf
```

If you use a conda environment and need its DLL directories at runtime, either
activate the environment first or set `DOC_TO_MD_CONDA_PREFIX`.

## OCR Notes

PDF handling uses PyMuPDF for page inspection/rendering and PaddleOCR for
image-based pages. Large scanned PDFs can take a while, especially on CPU-only
systems.

## Bundled Tooling

The `tools/hwp2md.exe` binary is bundled as a fallback converter for HWP/HWPX
documents. Its upstream license is included at `tools/LICENSE`.

## License

No repository-level license has been declared yet. Check third-party tool
licenses before redistributing bundled binaries.
