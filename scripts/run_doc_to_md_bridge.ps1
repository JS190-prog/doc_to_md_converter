# Shared doc-to-md bridge entry point.
# Called by the Claude `doc-to-md-bridge` skill and the `md` shorthand hook:
#   powershell -ExecutionPolicy Bypass -File run_doc_to_md_bridge.ps1 --json <file-path>
# Arguments are passed through to convert_to_md_cli.py unchanged.

$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path $PSScriptRoot -Parent
$projectVenvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$python = if ($env:DOC_TO_MD_PYTHON) {
    $env:DOC_TO_MD_PYTHON
} elseif (Test-Path -LiteralPath $projectVenvPython) {
    $projectVenvPython
} else {
    'python'
}
$usingProjectVenv = [System.IO.Path]::GetFullPath($python) -eq [System.IO.Path]::GetFullPath($projectVenvPython)
if ($usingProjectVenv -and -not $env:DOC_TO_MD_PRELOAD_TORCH) {
    # This environment's Paddle GPU runtime must load before Torch; preloading
    # Torch first makes cuBLAS fail with WinError 127 during real inference.
    $env:DOC_TO_MD_PRELOAD_TORCH = '0'
}
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
