# v2.1 확인 노트북용 Jupyter 커널 등록 (한 번만 실행)
# 사용법:  .\eval\reporter-table-discovery-30\v2.1\notebooks\setup_kernel.ps1
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path
$py = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "리포의 .venv 파이썬을 찾지 못했습니다: $py" -ForegroundColor Red
    Write-Host "Windows에서 리포 루트를 기준으로 실행했는지 확인하세요."
    exit 1
}

Write-Host "사용할 인터프리터: $py"
& $py -c "import sys; print('파이썬', sys.version.split()[0], '(커널은 이 버전이어야 합니다)')"

Write-Host "`n[1/2] ipykernel 설치..."
& $py -m pip install --quiet --upgrade ipykernel

Write-Host "[2/2] Jupyter 커널 등록..."
& $py -m ipykernel install --user --name statbridge --display-name "StatBridge .venv"

Write-Host "`n설치 확인:"
& $py -c "import fastapi, langgraph, plotly, pandas; print('런타임 스택 OK')"

Write-Host "`n완료. Jupyter를 다시 열고 커널 목록에서 'StatBridge .venv'를 고른 뒤," -ForegroundColor Green
Write-Host "eval\reporter-table-discovery-30\v2.1\notebooks\verify.ipynb 를 열어 5장부터 실행하세요." -ForegroundColor Green
