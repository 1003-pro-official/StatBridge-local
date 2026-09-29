@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
cd /d "%ROOT%\src\agent\frontend"
call pnpm dev --host 127.0.0.1 --port 5173
