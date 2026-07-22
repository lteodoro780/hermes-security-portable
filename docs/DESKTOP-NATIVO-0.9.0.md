# HERMES Desktop Nativo 0.9.0

A versão 0.9.0 substitui o navegador por uma janela própria construída com Qt/PySide6. O executável inicia diretamente o aplicativo desktop e não cria um servidor HTTP para a interface.

## Recursos da janela

- visão geral de CPU, memória, disco e rede agregada;
- diagnósticos de sistema, rede e modo completo;
- histórico e exportação de relatórios;
- monitoramento contínuo e alertas;
- Central de Incidentes, checklist, notas e exportação HTML/PDF;
- conversa com a IA local;
- Base Local com coleções, importação, pesquisa offline e respostas com fontes;
- importação e download de modelos GGUF;
- controle de início e parada do `llama.cpp`;
- backup e restauração dos dados portáteis;
- configurações de contexto, threads e camadas na GPU.

## Modelo personalizado

Na seção **Modelos**, o usuário pode selecionar qualquer arquivo `.gguf` válido. Há duas formas de uso:

1. **Usar no local atual:** grava apenas o caminho do arquivo na configuração.
2. **Copiar para o HERMES:** copia em blocos para `models`, valida tamanho e cabeçalho e só então publica o arquivo final.

Um arquivo existente não é substituído sem confirmação. Remover a seleção não apaga o modelo original.

## Motor de IA

O HERMES procura `llama-server.exe` em `tools/llama.cpp`, no `PATH` do Windows ou no caminho escolhido na tela. O processo iniciado pelo HERMES é encerrado junto com a janela. Um servidor externo já ativo é apenas detectado e não é encerrado pelo aplicativo.

## Primeiro uso

O assistente inicial mostra o hardware e permite selecionar um modelo e o executável do `llama.cpp`. Todos esses passos são opcionais: o restante do programa funciona sem IA.

## Empacotamento

O `HERMES-Portable.spec` usa `hermes_desktop.py` como ponto de entrada, inclui PySide6 e produz um executável Windows x64 sem console. O workflow valida a criação das nove telas com Qt em modo `offscreen`; nenhuma porta local é aberta durante o teste.
