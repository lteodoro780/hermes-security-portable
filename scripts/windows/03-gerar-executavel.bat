@echo off
cd /d "%~dp0..\.."
python -m pip install --upgrade pip
python -m pip install pyinstaller
python -m PyInstaller --onefile --name hermes-security src\hermes\hermes_security.py
echo Executavel em dist\hermes-security.exe
pause
