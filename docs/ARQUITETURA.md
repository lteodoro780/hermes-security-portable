# Arquitetura

```text
Usuário -> Dashboard local -> API HERMES -> llama.cpp -> modelo GGUF
                |                 |
                |                 +-> perfis e detecção de hardware
                +-> diagnósticos -> relatórios JSON -> comparação e plano seguro
                +-> Base Local -> SQLite/FTS5 -> trechos com fontes
                +-> Monitor -> psutil -> SQLite -> histórico e alertas locais
                +-> Incidentes -> SQLite -> checklist/linha do tempo -> HTML/PDF
                +-> Backup -> ZIP validado -> dados portáteis
```

`hermes_launcher.py` resolve o perfil, configura contexto/threads/GPU, inicia o servidor de IA quando disponível e então abre a interface. O backend permanece restrito a `127.0.0.1` por padrão.

Conversas e o último benchmark ficam em `data/`. Downloads usam `models/*.part` até serem concluídos, evitando que arquivos incompletos sejam iniciados como modelos válidos.

`hermes_intelligence.py` compara achados e métricas de forma determinística, sem depender da IA. O mesmo módulo cria planos revisáveis usando uma lista fechada de comandos conhecidos e somente de leitura; nenhum comando é executado pelo HERMES.

`hermes_knowledge.py` mantém coleções, documentos e trechos em `data/hermes-knowledge.db`. A pesquisa usa SQLite FTS5 quando disponível e um modo compatível como fallback. Somente os trechos recuperados entram no contexto da IA, identificados como fontes locais não confiáveis.

`hermes_monitor.py` possui uma única thread de coleta, iniciada somente após autorização do usuário. Ela registra percentuais agregados e taxas de rede em `data/hermes-monitor.db`, limita retenção e quantidade de linhas e exige leituras consecutivas antes de abrir, escalar ou resolver um alerta. O motor não executa comandos e não depende da IA.

`hermes_incidents.py` mantém incidentes, eventos e checklists em `data/hermes-incidents.db`. Um alerta pode ter somente um incidente ativo; depois de resolvido, um novo ciclo pode ser registrado. Os relatórios HTML escapam conteúdo e o PDF é produzido localmente sem dependências externas.

`hermes_backup.py` cria cópias consistentes dos bancos SQLite e aceita na restauração somente caminhos conhecidos. Todo o ZIP é validado antes da primeira substituição. Modelos, ferramentas e executáveis nunca entram no backup.

`hermes_paths.py` separa recursos empacotados de conteúdo gravável. No `.exe`, a interface é lida da pasta temporária interna do PyInstaller, enquanto `config`, `data`, `models`, `reports` e `tools` permanecem ao lado do executável.
