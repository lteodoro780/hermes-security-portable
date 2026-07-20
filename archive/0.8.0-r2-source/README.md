# HERMES Security Portable 0.8.0-r2

Assistente local e portátil para diagnóstico defensivo, monitoramento, troubleshooting e consulta de documentos. O núcleo funciona offline; a IA é opcional e usa `llama.cpp` com modelo GGUF local.

## Novidades da 0.8.0

- diagnóstico rápido e diagnóstico completo;
- pontuação de saúde de 0 a 100;
- severidades **Normal**, **Atenção**, **Crítico** e **Não verificado**;
- interpretação baseada em dados estruturados, mesmo sem IA;
- explicação opcional pelo modelo local;
- comparação com o diagnóstico anterior;
- processos com CPU, memória, caminho e ações protegidas;
- relatórios automáticos em HTML, JSON e TXT;
- ações permitidas por lista segura;
- monitoramento contínuo com histórico SQLite;
- base de conhecimento local com fontes;
- gerenciador de modelos GGUF;
- download de modelo com pausa e retomada;
- interface totalmente local em `127.0.0.1`.

## Requisitos

- Windows 10 ou 11;
- Python 3.10 ou superior — recomendado Python 3.12;
- aproximadamente 50 MB para o HERMES sem modelo;
- `llama-server.exe` e um modelo GGUF somente para chat e explicação por IA.

## Instalação rápida no Windows

1. Extraia a pasta para um local gravável, por exemplo `C:\HERMES-0.8.0`.
2. Execute `Iniciar-HERMES.bat`. O inicializador tenta instalar `psutil` automaticamente. Se não houver internet ou a instalação falhar, o HERMES abre em modo compatibilidade.
3. A instalação manual em `scripts\windows\00-instalar-dependencias.bat` é opcional.
4. Opcionalmente coloque:

```text
tools\llama.cpp\llama-server.exe
models\model.gguf
```

5. Acesse `http://127.0.0.1:8765` caso o navegador não abra automaticamente.

Sem modelo GGUF, diagnóstico, monitoramento, processos, histórico, relatórios e base de conhecimento continuam funcionando. Sem `psutil`, o modo compatibilidade usa recursos nativos do Windows; algumas ações avançadas de processo ficam indisponíveis.

## Modos de diagnóstico

### Rápido

Verifica CPU, memória, discos, interfaces, internet/DNS e processos. É indicado para uma triagem cotidiana.

### Completo

Adiciona no Windows:

- programas de inicialização;
- serviços automáticos parados;
- eventos críticos e de erro dos últimos três dias;
- perfis do Firewall do Windows;
- atualizações instaladas recentemente.

Algumas verificações podem retornar **Não verificado** quando políticas ou permissões bloquearem a consulta. Isso não é tratado automaticamente como falha.

## Ações seguras

O HERMES não executa comandos arbitrários produzidos pela IA. A versão 0.8.0 permite apenas:

- abrir Gerenciador de Tarefas;
- abrir Aplicativos de Inicialização;
- abrir a localização de um processo;
- solicitar encerramento normal de processo não protegido;
- limpar cache DNS;
- remover itens antigos da pasta temporária do usuário;
- abrir relatórios locais.

Processos críticos possuem bloqueio interno. O encerramento forçado não é utilizado.

## Base de conhecimento

Coloque arquivos `.txt`, `.md`, `.json` ou `.log` em `knowledge\` e clique em **Reindexar pasta**. O conteúdo permanece no banco local:

```text
data\hermes.db
```

## Dados gerados

```text
data\hermes.db       histórico, documentos e diagnósticos
reports\             relatórios HTML, JSON e TXT
logs\                reservado para logs futuros
config\               configurações portáteis
```

Para zerar o histórico, encerre o HERMES e remova `data\hermes.db`. Faça uma cópia antes quando quiser preservar diagnósticos.

## Modelos e configuração da IA

Use `BAIXAR-MODELO.bat` para baixar um arquivo GGUF por URL HTTPS. Um download interrompido permanece como `.part` e continua quando a mesma URL é executada novamente. Use `GERENCIAR-MODELOS.bat` para escolher entre os modelos existentes.

Execute `CONFIGURAR-IA.bat` para detectar RAM e CPU e criar o perfil local. Os perfis disponíveis são:

- `fast`: menor consumo;
- `balanced`: recomendado para 16 GB de RAM;
- `quality`: mais contexto para máquinas com RAM disponível.

O perfil automático usa `balanced` em uma máquina com 16 GB. Camadas de GPU ficam em `0` por segurança e compatibilidade; altere somente ao usar um build do llama.cpp com backend de GPU validado.

## Segurança e privacidade

- servidor vinculado a `127.0.0.1` por padrão;
- sem telemetria implementada;
- sem API externa de IA;
- sem execução de shell arbitrário;
- relatórios podem conter nomes de processos, usuário e configuração da máquina;
- use somente em equipamento próprio ou ambiente autorizado.

## Teste técnico

No diretório raiz:

```bat
set PYTHONPATH=%CD%\src
python -m py_compile src\hermes\*.py
python -m hermes.hermes_web
```

Consulte também `docs\TESTES.md`.
