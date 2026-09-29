@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
cd /d "%ROOT%"
set "PYTHONPATH=%ROOT%\src\backend;%ROOT%\src\agent"
"%ROOT%\.venv\Scripts\python.exe" -m pytest -q tests
