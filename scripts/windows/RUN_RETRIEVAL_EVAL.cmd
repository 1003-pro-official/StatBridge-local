@echo off
setlocal EnableExtensions DisableDelayedExpansion
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
cd /d "%ROOT%"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%ROOT%\src\agent;%ROOT%\src\backend"
set "TASK_PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%TASK_PY%" goto :NO_ENV
"%TASK_PY%" tools\evaluate_retrieval.py %*
exit /b %errorlevel%
:NO_ENV
echo [ERROR] Run START_STATBRIDGE.cmd first to prepare this PC environment.
if not defined STATBRIDGE_NO_PAUSE pause
exit /b 1
