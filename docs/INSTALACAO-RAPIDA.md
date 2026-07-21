# Instalação rápida

## Pacote `.exe` para Windows 10/11 x64

1. Extraia o ZIP completo para uma pasta gravável.
2. Execute `HERMES-Security-Portable-0.8.0.exe`.
3. Aguarde a abertura de `http://127.0.0.1:8765`.

Não é necessário instalar Python. O executável de teste não possui assinatura comercial; valide o arquivo com `SHA256SUMS.txt` antes de aceitar um eventual aviso do SmartScreen.

## Execução pelo código-fonte

1. Instale Python 3.10 ou superior.
2. Extraia o ZIP completo.
3. Rode `INSTALAR-HERMES.bat`.
4. Rode `CONFIGURAR-IA.bat` e escolha um perfil.
5. Rode `INICIAR-HERMES.bat`.

Acesse `http://127.0.0.1:8765`. Para 16 GB de RAM, use o perfil Balanceado. A CLI continua disponível em `scripts\windows\02-iniciar-hermes.bat`.

Depois de instalar o `llama.cpp`, também é possível baixar ou continuar modelos em **Configurações → Baixar e trocar modelos**.

O monitoramento não precisa de modelo. Abra **Monitoramento**, revise os limites e clique em **Iniciar monitoramento** quando quiser começar a registrar o histórico local.
