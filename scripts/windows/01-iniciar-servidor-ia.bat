@echo off
setlocal
cd /d "%~dp0..\.."
set "PYTHONUTF8=1"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" src\hermes\hermes_launcher.py --ai-only
) else (
  python src\hermes\hermes_launcher.py --ai-only
)
pause
endlocal
