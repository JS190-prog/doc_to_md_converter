# Shared doc-to-md bridge entry point.
# Called by the Claude `doc-to-md-bridge` skill and the `md` shorthand hook:
#   powershell -ExecutionPolicy Bypass -File run_doc_to_md_bridge.ps1 --json <file-path>
# Arguments are passed through to convert_to_md_cli.py unchanged.

$ErrorActionPreference = 'Stop'

$python = 'C:\Users\USER\miniconda3\python.exe'
$cli = Join-Path $PSScriptRoot 'convert_to_md_cli.py'

# Same runtime environment as run.bat (conda DLLs + paddle/torch coexistence).
$env:PATH = 'C:\Users\USER\miniconda3;C:\Users\USER\miniconda3\Library\bin;C:\Users\USER\miniconda3\Scripts;' + $env:PATH
$env:KMP_DUPLICATE_LIB_OK = 'TRUE'
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = 'True'
$env:PYTHONIOENCODING = 'utf-8'

& $python $cli @args
exit $LASTEXITCODE
