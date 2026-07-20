@echo off
setlocal
cd /d "%~dp0..\.."
set "PYTHON_CMD="
where python >nul 2>&1 && set "PYTHON_CMD=python"
if not defined PYTHON_CMD where py >nul 2>&1 && set "PYTHON_CMD=py -3"
if not defined PYTHON_CMD (
  echo [ERRO] Python 3 nao encontrado.
  pause
  exit /b 1
)
set HERMES_WEB_HOST=127.0.0.1
set HERMES_WEB_PORT=8765
set HERMES_OPEN_BROWSER=1
set HERMES_LLAMACPP_URL=http://127.0.0.1:8080/completion
set PYTHONPATH=%CD%\src
%PYTHON_CMD% -m hermes.hermes_web
pause
endlocal
