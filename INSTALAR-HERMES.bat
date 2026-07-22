@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title HERMES Security Portable - Instalacao

echo ================================================================
echo HERMES Security Portable 0.9.0 Desktop
echo Preparacao do ambiente local
echo ================================================================
echo.

set "PYTHON_CMD="
where py >nul 2>&1
if not errorlevel 1 set "PYTHON_CMD=py -3"

if not defined PYTHON_CMD (
  where python >nul 2>&1
  if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
  echo [ERRO] Python 3 nao foi encontrado neste computador.
  echo.
  echo Instale o Python 3.10 ou superior e marque a opcao "Add Python to PATH".
  echo Site oficial: https://www.python.org/downloads/windows/
  echo.
  pause
  exit /b 1
)

%PYTHON_CMD% -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>&1
if errorlevel 1 (
  echo [ERRO] O HERMES requer Python 3.10 ou superior.
  echo Atualize o Python e execute este instalador novamente.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo [1/4] Criando ambiente isolado...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 (
    echo [ERRO] Nao foi possivel criar o ambiente .venv.
    pause
    exit /b 1
  )
) else (
  echo [1/4] Ambiente isolado ja existe.
)

echo [2/4] Atualizando o instalador de pacotes...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade pip

echo [3/4] Instalando interface desktop e telemetria local...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-runtime.txt
if errorlevel 1 (
  echo.
  echo [AVISO] A telemetria nao foi instalada.
  echo A instalacao da interface nao foi concluida. Revise sua conexao e tente novamente.
) else (
  echo.
  echo [OK] Ambiente preparado com sucesso.
)

echo.
echo [4/4] Detectando o perfil recomendado para este computador...
set "PYTHONUTF8=1"
".venv\Scripts\python.exe" src\hermes\hermes_profiles.py --summary

echo.
echo Proximo passo: execute INICIAR-HERMES.bat
echo Para instalar a IA guiada: execute CONFIGURAR-IA.bat
echo.
pause
endlocal
