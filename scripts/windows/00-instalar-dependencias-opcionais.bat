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
%PYTHON_CMD% -m pip install --upgrade pip
%PYTHON_CMD% -m pip install -r requirements-optional.txt
pause
endlocal
