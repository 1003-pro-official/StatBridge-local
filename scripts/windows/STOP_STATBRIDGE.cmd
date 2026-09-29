@echo off
setlocal
for %%P in (8000 5173) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr LISTENING ^| findstr ":%%P "') do taskkill /F /PID %%A >nul 2>nul
)
echo StatBridge stopped.
