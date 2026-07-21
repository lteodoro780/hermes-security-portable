@echo off
setlocal
cd /d "%~dp0..\.."
echo === Python ===
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" --version
) else (
  python --version
)
echo.
echo === llama.cpp ===
set "LLAMA_OK=0"
if exist "tools\llama.cpp\llama-server.exe" set "LLAMA_OK=1"
where llama-server.exe >nul 2>&1 && set "LLAMA_OK=1"
where llama.exe >nul 2>&1 && set "LLAMA_OK=1"
if "%LLAMA_OK%"=="1" (echo OK llama.cpp encontrado) else (echo FALTA llama.cpp - execute CONFIGURAR-IA.bat)
echo.
echo === Modelos de perfil ===
if exist "models\Qwen3-1.7B-Q8_0.gguf" (echo OK Rapido) else (echo FALTA Rapido)
if exist "models\Qwen3-4B-Q4_K_M.gguf" (echo OK Balanceado) else (echo FALTA Balanceado)
if exist "models\Qwen3-8B-Q4_K_M.gguf" (echo OK Qualidade) else (echo FALTA Qualidade)
if exist "models\model.gguf" echo OK Modelo personalizado legado
echo.
echo === Telemetria da Web UI ===
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -c "import psutil" >nul 2>&1
) else (
  python -c "import psutil" >nul 2>&1
)
if errorlevel 1 (echo FALTA psutil - execute INSTALAR-HERMES.bat) else (echo OK psutil)
echo.
echo === Recomendacao ===
if exist ".venv\Scripts\python.exe" ".venv\Scripts\python.exe" src\hermes\hermes_profiles.py --summary
pause
endlocal
