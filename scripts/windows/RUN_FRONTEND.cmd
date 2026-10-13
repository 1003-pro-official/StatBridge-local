@echo off
setlocal DisableDelayedExpansion
call "%~dp0START_STATBRIDGE.cmd" %*
exit /b %errorlevel%
