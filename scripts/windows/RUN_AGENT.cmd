@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
set "PYTHONPATH=%ROOT%\src\backend;%ROOT%\src\agent"
cd /d "%ROOT%"
"%ROOT%\.venv\Scripts\python.exe" -m uvicorn bridge_api:app --host 127.0.0.1 --port 8000
