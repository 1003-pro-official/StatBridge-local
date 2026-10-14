@echo off
setlocal EnableExtensions DisableDelayedExpansion
chcp 65001 >nul
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
cd /d "%ROOT%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "BOOT_PY="
if /I "%~1"=="--check" set "STATBRIDGE_CHECK_ONLY=1"
call :CHECK_PY "%ROOT%\.venv\Scripts\python.exe"
if defined BOOT_PY goto :LAUNCH
call :CHECK_PY py -3.12
if defined BOOT_PY goto :LAUNCH
call :CHECK_PY py -3.11
if defined BOOT_PY goto :LAUNCH
call :CHECK_PY py -3.13
if defined BOOT_PY goto :LAUNCH
call :CHECK_PY python
if defined BOOT_PY goto :LAUNCH
if defined STATBRIDGE_CHECK_ONLY goto :NO_PYTHON
where winget >nul 2>nul
if errorlevel 1 goto :NO_PYTHON
echo [SETUP] Installing 64-bit Python 3.12...
winget install --id Python.Python.3.12 -e --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :NO_PYTHON
call :CHECK_PY "%LocalAppData%\Programs\Python\Python312\python.exe"
if defined BOOT_PY goto :LAUNCH
call :CHECK_PY py -3.12
if not defined BOOT_PY goto :NO_PYTHON
:LAUNCH
%BOOT_PY% "%ROOT%\scripts\windows\bootstrap.py" %*
set "RESULT=%errorlevel%"
if not "%RESULT%"=="0" echo [ERROR] Setup failed. Keep the messages above and run CHECK_STATBRIDGE.cmd.
if not defined STATBRIDGE_NO_PAUSE pause
exit /b %RESULT%
:CHECK_PY
%* -c "import sys,struct;raise SystemExit(0 if sys.version_info[:2] in [(3,11),(3,12),(3,13)] and struct.calcsize('P')==8 else 1)" >nul 2>nul
if not errorlevel 1 set "BOOT_PY=%*"
exit /b 0
:NO_PYTHON
echo [ERROR] Install 64-bit Python 3.12, then run START_STATBRIDGE.cmd again.
if not defined STATBRIDGE_NO_PAUSE pause
exit /b 1
