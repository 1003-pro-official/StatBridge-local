@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
cd /d "%ROOT%"
set "VECTOR_PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%VECTOR_PY%" (
    echo [ERROR] Run START_STATBRIDGE.cmd first to prepare the Python environment.
    pause
    exit /b 1
)
"%VECTOR_PY%" tools\build_stat_vector_index.py
pause
