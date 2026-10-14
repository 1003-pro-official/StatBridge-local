@echo off
setlocal DisableDelayedExpansion
call "%~dp0scripts\windows\CHECK_STATBRIDGE.cmd" %*
exit /b %errorlevel%
