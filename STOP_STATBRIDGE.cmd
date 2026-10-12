@echo off
call "%~dp0scripts\windows\STOP_STATBRIDGE.cmd" %*
exit /b %errorlevel%
