# HERMES Security Portable

Assistente portátil de IA local para diagnóstico defensivo de infraestrutura, suporte técnico e uso offline.

## O que faz

- conversa com um modelo local via `llama.cpp`;
- coleta diagnóstico básico da máquina;
- gera relatórios JSON;
- auxilia troubleshooting;
- pode ser empacotado em `.exe` com PyInstaller.

## Uso rápido

Coloque:

```text
tools/llama.cpp/llama-server.exe
models/model.gguf
```

Depois rode:

```bat
scripts\windows\01-iniciar-servidor-ia.bat
scripts\windows\02-iniciar-hermes.bat
```

## Segurança

Use apenas em laboratório ou ambiente autorizado. Não publique senhas, tokens, IPs reais, logs reais, modelos ou executáveis de terceiros.
