@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
chcp 65001 >nul
set "STOP_PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%STOP_PY%" exit /b 0
"%STOP_PY%" "%ROOT%\scripts\windows\portable_runtime.py" stop
echo Done.
pause
