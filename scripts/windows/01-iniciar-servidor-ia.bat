@echo off
cd /d "%~dp0..\.."
set LLAMA_SERVER=tools\llama.cpp\llama-server.exe
set MODEL=models\model.gguf

if not exist "%LLAMA_SERVER%" (
  echo [ERRO] Falta %LLAMA_SERVER%
  pause
  exit /b 1
)

if not exist "%MODEL%" (
  echo [ERRO] Falta %MODEL%
  pause
  exit /b 1
)

"%LLAMA_SERVER%" -m "%MODEL%" --host 127.0.0.1 --port 8080
pause
