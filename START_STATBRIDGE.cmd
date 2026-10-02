@echo off
setlocal
call "%~dp0scripts\windows\START_STATBRIDGE.cmd"
exit /b %errorlevel%
