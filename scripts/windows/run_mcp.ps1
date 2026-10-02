$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location -LiteralPath $projectRoot
$env:PYTHONPATH = Join-Path $projectRoot "src/backend"
& (Join-Path $projectRoot ".venv/Scripts/python.exe") (Join-Path $projectRoot "src/backend/server.py")
