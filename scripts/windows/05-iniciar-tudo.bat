@echo off
setlocal
cd /d "%~dp0..\.."
if not exist "tools\llama.cpp\llama-server.exe" (
  echo [ERRO] Falta tools\llama.cpp\llama-server.exe
  pause
  exit /b 1
)
if not exist "models\model.gguf" (
  echo [ERRO] Falta models\model.gguf
  pause
  exit /b 1
)
start "HERMES llama.cpp server" cmd /k scripts\windows\01-iniciar-servidor-ia.bat
timeout /t 5 /nobreak >nul
start "HERMES Web UI" cmd /k scripts\windows\04-iniciar-webui.bat
echo HERMES iniciado: http://127.0.0.1:8765
pause
endlocal
