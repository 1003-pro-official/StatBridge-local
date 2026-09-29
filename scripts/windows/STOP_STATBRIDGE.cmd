@echo off
for %%T in ("StatBridge API" "StatBridge Frontend") do taskkill /FI "WINDOWTITLE eq %%~T*" /T /F >nul 2>nul
echo StatBridge windows stopped.
