@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title HERMES Security Portable 0.8.0

echo ================================================================
echo HERMES Security Portable 0.8.0 - Incidentes e monitoramento local
echo Dashboard local: http://127.0.0.1:8765
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

set "HERMES_WEB_HOST=127.0.0.1"
set "HERMES_WEB_PORT=8765"
set "HERMES_OPEN_BROWSER=1"
set "HERMES_LLAMACPP_URL=http://127.0.0.1:8080/v1/chat/completions"
set "PYTHONUTF8=1"

echo Detectando hardware e iniciando o perfil configurado...
echo Para encerrar o HERMES e a IA, pressione CTRL+C nesta janela.
echo.
".venv\Scripts\python.exe" src\hermes\hermes_launcher.py

if errorlevel 1 (
  echo.
  echo [ERRO] O servidor web foi encerrado com falha.
  pause
)

endlocal
