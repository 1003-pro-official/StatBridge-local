@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
set "PYTHON_EXE=%ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
  echo .venv not found. Creating it with the newest available Python 3...
  py -3 -m venv "%ROOT%\.venv" >nul 2>nul
  if not exist "%PYTHON_EXE%" python -m venv "%ROOT%\.venv" >nul 2>nul
  if not exist "%PYTHON_EXE%" (
    echo Python 3 not found. Install any Python 3.12+ from https://www.python.org/downloads/ and run this script again.
    exit /b 1
  )
  "%PYTHON_EXE%" --version
  "%PYTHON_EXE%" -m pip install -r "%ROOT%\src\backend\requirements.txt" pytest
  if errorlevel 1 exit /b 1
)

where pnpm >nul 2>nul
if errorlevel 1 (
  echo pnpm is required. See README.md.
  exit /b 1
)

if not exist "%ROOT%\src\agent\frontend\node_modules\.bin\vite.CMD" (
  echo Installing frontend dependencies...
  pushd "%ROOT%\src\agent\frontend"
  call pnpm install --frozen-lockfile
  if errorlevel 1 ( popd & exit /b 1 )
  popd
)

start "StatBridge API" "%~dp0RUN_AGENT.cmd"
start "StatBridge Frontend" "%~dp0RUN_FRONTEND.cmd"
echo Open http://127.0.0.1:5173
