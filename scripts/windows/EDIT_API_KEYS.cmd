@echo off
setlocal
for %%I in ("%~dp0..\..") do set "ROOT=%%~fI"
if not exist "%ROOT%\.env" copy /y "%ROOT%\.env.example" "%ROOT%\.env" >nul
echo Edit OPENAI_API_KEY and JEV_API_KEY in this project's .env.
echo Save the file, then restart START_STATBRIDGE.cmd.
start "" notepad.exe "%ROOT%\.env"
