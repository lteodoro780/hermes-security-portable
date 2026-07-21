@echo off
cd /d "%~dp0..\.."
set HERMES_LLAMACPP_URL=http://127.0.0.1:8080/v1/chat/completions
if exist "dist\hermes-security.exe" (
  dist\hermes-security.exe
) else (
  python src\hermes\hermes_security.py
)
pause
