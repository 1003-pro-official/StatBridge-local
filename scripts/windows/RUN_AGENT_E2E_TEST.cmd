@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
cd /d "%ROOT%"
"%ROOT%\.venv\Scripts\python.exe" tests\TEST_AGENT_FLOW.py
