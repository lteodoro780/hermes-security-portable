# HERMES SOC Dashboard

Interface web local e responsiva do HERMES Security Portable. A versão 0.8.0 reúne monitoramento contínuo, Central de Incidentes, alertas locais, diagnósticos, comparação de evolução, planos seguros, Base de Conhecimento Local, backup, gerenciamento de modelos e benchmark.

Na área **Relatórios**, selecione uma coleta de referência e uma coleta atual. O HERMES calcula localmente alertas novos, resolvidos, piores e melhores, além da variação de CPU, memória e disco quando as métricas estiverem disponíveis. A opção **Interpretar com IA** é complementar.

O botão **Plano seguro** organiza os alertas por prioridade e mostra passos de confirmação e validação. Os comandos disponíveis são somente de leitura e nunca são executados pela interface.

Na área **Base Local**, importe TXT, MD, JSON, LOG ou um relatório existente. **Buscar sem IA** consulta o índice SQLite offline. **Perguntar à IA** recupera os trechos relevantes, restringe a resposta a esse contexto e mostra fontes numeradas.

Na área **Monitoramento**, o usuário inicia ou pausa a coleta, acompanha o gráfico e ajusta intervalo, retenção e limites. Alertas exigem leituras consecutivas e nunca disparam ações automáticas.

Na **Central de Incidentes**, um alerta pode gerar snapshot, checklist e linha do tempo. Notas, análise opcional, HTML e PDF permanecem locais. Em **Configurações**, o backup exporta ou restaura somente dados permitidos.

## Como iniciar

Terminal 1:

```bat
python -m pip install -r requirements.txt
scripts\windows\01-iniciar-servidor-ia.bat
```

Terminal 2:

```bat
scripts\windows\04-iniciar-webui.bat
```

Ou tudo de uma vez:

```bat
scripts\windows\05-iniciar-tudo.bat
```

Acesse:

```text
http://127.0.0.1:8765
```

## Endpoints

```text
GET  /api/health
GET  /api/system
GET  /api/network
GET  /api/reports
GET  /api/reports/<arquivo.json>
GET  /api/monitor
GET  /api/monitor/samples
GET  /api/monitor/alerts
GET  /api/incidents
GET  /api/incidents/<id>
GET  /api/incidents/<id>/html
GET  /api/incidents/<id>/pdf
GET  /api/backup
GET  /api/knowledge
GET  /api/knowledge/documents/<id>
POST /api/chat
POST /api/diagnostics
POST /api/monitor/start
POST /api/monitor/stop
POST /api/monitor/config
POST /api/monitor/alerts/acknowledge
POST /api/incidents
POST /api/incidents/from-alert
POST /api/incidents/<id>/status
POST /api/incidents/<id>/note
POST /api/incidents/<id>/checklist/<item-id>
POST /api/incidents/<id>/analyze
POST /api/backup/restore
POST /api/knowledge/documents
POST /api/knowledge/reports
POST /api/knowledge/search
POST /api/knowledge/ask
DELETE /api/knowledge/documents/<id>
DELETE /api/knowledge
DELETE /api/monitor/history
DELETE /api/incidents/<id>
```

O endpoint de diagnósticos aceita somente os tipos `system`, `network` e `full`. Cada execução gera um relatório JSON local na pasta `reports/`.

## Módulos da interface

- **Visão Geral:** telemetria, estado da IA, alertas e último relatório;
- **Monitoramento:** coleta autorizada, gráfico histórico, limites e alertas sustentados;
- **Incidentes:** snapshot, estados, checklist, notas, linha do tempo e exportações;
- **Diagnósticos:** execução guiada das coletas permitidas;
- **Assistente IA:** conversa local com o modelo GGUF;
- **Base Local:** coleções, documentos, pesquisa offline e respostas com fontes;
- **Relatórios:** histórico, achados, evidências e exportação JSON;
- **Configurações:** endpoints, versão, dependências, backup e restauração.

Por padrão a interface usa `127.0.0.1`, ficando disponível somente na própria máquina.
