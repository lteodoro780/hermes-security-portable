@echo off
setlocal
cd /d "%~dp0..\.."
if exist "tools\llama.cpp\llama-server.exe" if exist "models\model.gguf" (
  start "HERMES llama.cpp server" cmd /k scripts\windows\01-iniciar-servidor-ia.bat
  timeout /t 4 /nobreak >nul
) else (
  echo [AVISO] IA local nao encontrada. HERMES abrira com monitoramento e busca offline.
)
call scripts\windows\04-iniciar-webui.bat
endlocal
