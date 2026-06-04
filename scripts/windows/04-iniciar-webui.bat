@echo off
setlocal
cd /d "%~dp0..\.."
set HERMES_WEB_HOST=127.0.0.1
set HERMES_WEB_PORT=8765
set HERMES_OPEN_BROWSER=1
set HERMES_LLAMACPP_URL=http://127.0.0.1:8080/completion
python src\hermes\hermes_web.py
pause
endlocal
