# Windows equivalent of setup-lite.sh. Run: powershell -File setup-lite.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
function Invoke-LabPython {
    & "$PSScriptRoot/.venv/Scripts/python.exe" @args
    if ($LASTEXITCODE -ne 0) { throw "Python command failed: $args" }
}
if (-not (Test-Path '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Virtualenv creation failed' }
}
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$env:FASTEMBED_CACHE_PATH = "$PSScriptRoot/.model-cache"
$env:HF_HOME = "$PSScriptRoot/.model-cache/huggingface"
Invoke-LabPython -m ensurepip --upgrade
Invoke-LabPython -m pip install -r requirements.txt
$needsOverride = Invoke-LabPython -c 'import sys; print(int(sys.version_info >= (3,14)))'
if ($needsOverride -eq '1') { Invoke-LabPython -m pip install 'dill>=0.4,<1.0' }
if (-not (Test-Path '.env')) { Copy-Item '.env.example' '.env' }
Invoke-LabPython scripts/seed_corpus.py
Invoke-LabPython scripts/gen_agent_queries.py
Invoke-LabPython scripts/gen_spend.py
Invoke-LabPython scripts/verify_lite.py
Invoke-LabPython -m pytest -q
Write-Host 'Ready. Execute notebooks: .venv/Scripts/python.exe scripts/execute_notebooks.py'
