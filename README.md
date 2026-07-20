# HERMES Security Portable 0.7.0

Assistente portátil de IA local para diagnóstico defensivo de infraestrutura, suporte técnico e uso offline.

## Recursos

- chat local via `llama.cpp` e modelo GGUF;
- diagnóstico de rede;
- detecção automática de hardware;
- perfis `fast`, `balanced` e `quality`;
- base de conhecimento TXT, MD, JSON e LOG;
- leitura opcional de PDF;
- busca local mesmo sem IA;
- monitoramento de CPU, memória, disco e rede;
- gráficos, alertas e histórico SQLite;
- backup local;
- nenhuma correção automática.

## Início rápido no Windows

Coloque, opcionalmente:

```text
tools/llama.cpp/llama-server.exe
models/model.gguf
```

Execute:

```bat
Iniciar-HERMES.bat
```

A interface abre em `http://127.0.0.1:8765`.

Sem o modelo, o monitoramento e a busca na base continuam funcionando.

## Dependências opcionais

```bat
scripts\windows\00-instalar-dependencias-opcionais.bat
```

- `psutil`: métricas e rede detalhadas;
- `pypdf`: extração de texto de PDFs.

O programa não deve deixar de abrir quando essas bibliotecas estiverem ausentes.

## Base de conhecimento

Coloque documentos em `knowledge/`. Subpastas viram coleções. Na interface, abra **Conhecimento** e clique em **Reindexar pasta**.

## Dados locais

- `data/hermes.db`: histórico, alertas e documentos;
- `reports/`: diagnósticos gerados;
- `backups/`: cópias de segurança;
- `config/runtime.json`: seleção opcional de perfil.

## Segurança

Use somente em equipamentos próprios ou ambientes autorizados. O HERMES 0.7.0 não executa correções automáticas nem comandos arbitrários gerados pela IA.

Consulte [`docs/VERSAO-0.7.0.md`](docs/VERSAO-0.7.0.md) para o histórico consolidado.
