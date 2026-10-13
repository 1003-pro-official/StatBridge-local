@echo off
setlocal DisableDelayedExpansion
call "%~dp0START_STATBRIDGE.cmd" --check %*
exit /b %errorlevel%
