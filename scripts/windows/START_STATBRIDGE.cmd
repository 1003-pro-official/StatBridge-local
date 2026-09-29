@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo Python environment missing. Run: py -3.12 -m venv .venv
  exit /b 1
)
where pnpm >nul 2>nul
if errorlevel 1 (
  echo pnpm is required. See README.md.
  exit /b 1
)
start "StatBridge API" "%~dp0RUN_AGENT.cmd"
start "StatBridge Frontend" "%~dp0RUN_FRONTEND.cmd"
echo Open http://127.0.0.1:5173
