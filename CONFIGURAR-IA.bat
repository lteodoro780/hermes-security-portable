@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title HERMES 0.8.0 - Configuracao da IA local

echo ================================================================
echo HERMES Security Portable 0.8.0
echo Assistente para instalar llama.cpp e um modelo Qwen3 oficial
echo ================================================================
echo.

set "LLAMA_OK=0"
if exist "tools\llama.cpp\llama-server.exe" set "LLAMA_OK=1"
where llama-server.exe >nul 2>&1 && set "LLAMA_OK=1"
where llama.exe >nul 2>&1 && set "LLAMA_OK=1"

if "%LLAMA_OK%"=="0" (
  echo llama.cpp ainda nao foi encontrado.
  where winget >nul 2>&1
  if errorlevel 1 (
    echo [AVISO] WinGet nao esta disponivel.
    echo Baixe os binarios em: https://github.com/ggml-org/llama.cpp/releases
    echo Depois copie llama-server.exe e suas DLLs para tools\llama.cpp\
    echo.
  ) else (
    choice /C SN /N /M "Instalar llama.cpp agora pelo WinGet? [S/N]: "
    if errorlevel 2 goto escolher_modelo
    winget install llama.cpp --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
      echo [AVISO] A instalacao do llama.cpp nao foi concluida.
      echo Voce ainda pode baixar o modelo e instalar o servidor depois.
    ) else (
      echo [OK] llama.cpp instalado. Se nao for detectado agora, reinicie o HERMES.
    )
  )
) else (
  echo [OK] llama.cpp encontrado.
)

:escolher_modelo
echo.
echo Escolha o perfil que deseja baixar:
echo.
echo   [1] Rapido      - Qwen3 1.7B Q8_0     - aprox. 1,83 GB
echo   [2] Balanceado - Qwen3 4B Q4_K_M     - aprox. 2,50 GB
echo   [3] Qualidade  - Qwen3 8B Q4_K_M     - aprox. 5,03 GB
echo   [Q] Sair sem baixar
echo.
choice /C 123Q /N /M "Opcao [1/2/3/Q]: "
if errorlevel 4 goto fim
if errorlevel 3 goto modelo_qualidade
if errorlevel 2 goto modelo_balanceado

:modelo_rapido
set "PROFILE=fast"
set "MODEL_FILE=Qwen3-1.7B-Q8_0.gguf"
set "MODEL_URL=https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q8_0.gguf?download=true"
goto baixar

:modelo_balanceado
set "PROFILE=balanced"
set "MODEL_FILE=Qwen3-4B-Q4_K_M.gguf"
set "MODEL_URL=https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf?download=true"
goto baixar

:modelo_qualidade
set "PROFILE=quality"
set "MODEL_FILE=Qwen3-8B-Q4_K_M.gguf"
set "MODEL_URL=https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf?download=true"

:baixar
echo.
echo Fonte: organizacao oficial Qwen no Hugging Face
echo Licenca do modelo: Apache-2.0
echo Destino: models\%MODEL_FILE%
echo.
if exist "models\%MODEL_FILE%" (
  echo [OK] Este modelo ja esta presente. Nenhum download necessario.
  goto salvar_perfil
)

where curl.exe >nul 2>&1
if errorlevel 1 (
  echo [ERRO] curl.exe nao foi encontrado neste Windows.
  echo Abra o endereco abaixo no navegador e salve o arquivo na pasta models:
  echo %MODEL_URL%
  goto fim_com_pausa
)

choice /C SN /N /M "Iniciar o download grande agora? [S/N]: "
if errorlevel 2 goto fim
if not exist "models" mkdir "models"
echo.
echo O download pode demorar. Ele tentara continuar se for interrompido.
curl.exe --location --fail --retry 3 --continue-at - --output "models\%MODEL_FILE%.part" "%MODEL_URL%"
if errorlevel 1 (
  echo.
  echo [ERRO] O download nao foi concluido.
  echo Execute CONFIGURAR-IA.bat novamente para tentar continuar.
  goto fim_com_pausa
)
move /Y "models\%MODEL_FILE%.part" "models\%MODEL_FILE%" >nul
if errorlevel 1 (
  echo [ERRO] Nao foi possivel finalizar o arquivo do modelo.
  goto fim_com_pausa
)

:salvar_perfil
if exist ".venv\Scripts\python.exe" (
  set "PYTHONUTF8=1"
  ".venv\Scripts\python.exe" src\hermes\hermes_profiles.py --set-profile %PROFILE%
)
echo.
echo [OK] Perfil local preparado.
echo Agora execute INICIAR-HERMES.bat.

:fim_com_pausa
echo.
pause

:fim
endlocal
