param([switch]$Reload)
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create .venv and install backend requirements first.' }
if ($Reload) { & $pythonPath -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload }
else { & $pythonPath -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 }
