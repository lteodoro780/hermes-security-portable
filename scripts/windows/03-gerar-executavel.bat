@echo off
setlocal
cd /d "%~dp0..\.."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt || goto :erro
python -m unittest discover -s tests -v || goto :erro
python -m PyInstaller --noconfirm --clean HERMES-Portable.spec || goto :erro
echo.
echo Executavel criado em:
echo dist\HERMES-Security-Portable-0.8.0.exe
echo.
echo Ele inclui Python, psutil e a interface Web. Modelos GGUF nao sao incluidos.
pause
exit /b 0

:erro
echo.
echo [ERRO] A compilacao nao foi concluida. Revise a mensagem acima.
pause
exit /b 1
