# Shared doc-to-md bridge entry point.
# Called by the Claude `doc-to-md-bridge` skill and the `md` shorthand hook:
#   powershell -ExecutionPolicy Bypass -File run_doc_to_md_bridge.ps1 --json <file-path>
# Arguments are passed through to convert_to_md_cli.py unchanged.

$ErrorActionPreference = 'Stop'

$python = if ($env:DOC_TO_MD_PYTHON) { $env:DOC_TO_MD_PYTHON } else { 'python' }
$cli = Join-Path $PSScriptRoot 'convert_to_md_cli.py'

# Same runtime environment as run.bat (paddle/torch coexistence). If a conda
# prefix is active or provided, expose its DLL directories to child processes.
$condaPrefix = if ($env:DOC_TO_MD_CONDA_PREFIX) { $env:DOC_TO_MD_CONDA_PREFIX } else { $env:CONDA_PREFIX }
if ($condaPrefix) {
    $env:PATH = "$condaPrefix;$condaPrefix\Library\bin;$condaPrefix\Scripts;" + $env:PATH
}
$env:KMP_DUPLICATE_LIB_OK = 'TRUE'
$env:PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK = 'True'
$env:PYTHONIOENCODING = 'utf-8'

& $python $cli @args
exit $LASTEXITCODE
