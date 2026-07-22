@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title HERMES Security Portable 0.9.0

echo ================================================================
echo HERMES Security Portable 0.9.0 - Aplicativo desktop nativo
echo Nenhum navegador ou servidor web sera iniciado.
echo ================================================================
echo.

if not exist ".venv\Scripts\python.exe" (
  echo O ambiente ainda nao foi preparado.
  echo Abrindo o instalador...
  echo.
  call INSTALAR-HERMES.bat
  if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] Instalacao incompleta.
    pause
    exit /b 1
  )
)

set "HERMES_LLAMACPP_URL=http://127.0.0.1:8080/v1/chat/completions"
set "PYTHONUTF8=1"

echo Abrindo a janela do HERMES...
echo.
".venv\Scripts\pythonw.exe" src\hermes\hermes_desktop.py

if errorlevel 1 (
  echo.
  echo [ERRO] O aplicativo desktop foi encerrado com falha.
  pause
)

endlocal
