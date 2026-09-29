@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
cd /d "%ROOT%"
"%ROOT%\.venv\Scripts\python.exe" tools\evaluate_retrieval.py
