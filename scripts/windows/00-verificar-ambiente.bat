@echo off
cd /d "%~dp0..\.."
echo === Python ===
python --version
echo.
echo === llama.cpp ===
if exist "tools\llama.cpp\llama-server.exe" (echo OK llama-server.exe) else (echo FALTA tools\llama.cpp\llama-server.exe)
echo.
echo === Modelo ===
if exist "models\model.gguf" (echo OK models\model.gguf) else (echo FALTA models\model.gguf)
pause
