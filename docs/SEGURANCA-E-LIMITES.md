# Segurança

Use apenas em ambiente autorizado. A IA pode errar. Revise comandos antes de executar.

- O histórico do chat fica em `data/chat-history.json`; use **Limpar histórico** antes de compartilhar a pasta.
- Relatórios HTML podem conter nomes do host, endereços e evidências. Revise antes de enviar.
- O gerenciador aceita somente os perfis e endereços oficiais definidos no HERMES.
- Downloads incompletos permanecem com extensão `.part` e não são iniciados como modelos.
- “Analisar com IA” envia o resumo apenas ao servidor local configurado em `127.0.0.1`.
- Recomendações da IA não são executadas automaticamente.
- A comparação principal é determinística e funciona com a IA desligada.
- O plano de correção nunca executa comandos; oferece apenas verificações conhecidas de leitura para copiar.
- Serviços desconhecidos não recebem comandos gerados ou improvisados.
- A Base Local aceita somente `.txt`, `.md`, `.json` e `.log`, sem gravar o nome recebido como caminho no disco.
- Cada documento é limitado a 2 MB; a base aceita até 500 documentos e 64 MB de conteúdo.
- Documentos são tratados como conteúdo não confiável e não podem substituir as instruções do sistema para a IA.
- A pergunta usa no máximo os trechos locais recuperados e sempre devolve a lista de fontes consultadas.
- `data/hermes-knowledge.db` não é criptografado. Proteja a pasta portátil e use **Limpar toda a base** antes de compartilhá-la.
- O monitor registra apenas percentuais de CPU, memória e disco e taxas agregadas de rede; ele não captura pacotes ou conteúdo da comunicação.
- O monitor não lê nomes de processos, arquivos, janelas, teclado ou comandos executados.
- O padrão exige 3 coletas consecutivas antes de abrir, escalar ou resolver um alerta.
- O histórico usa no máximo 50.000 amostras e mantém no máximo 2.000 alertas resolvidos.
- A retenção configurável vai de 24 horas a 30 dias e também limita automaticamente dados antigos.
- `data/hermes-monitor.db` não é criptografado. Use **Limpar histórico** antes de compartilhar a pasta.
- Pausar a coleta não apaga o histórico; fechar o HERMES interrompe a thread com segurança.
- Se o usuário deixar o monitor ativo, ele poderá retomar na próxima inicialização local.
- Alertas do monitor nunca encerram processos, alteram configurações ou executam correções.
- Incidentes guardam somente o snapshot agregado disponível no HERMES; não adicionam listas de processos, conteúdo de rede ou arquivos.
- Checklists de incidente são orientações de verificação e nunca são executados automaticamente.
- A análise de incidente é opcional e usa apenas o servidor de IA local em `127.0.0.1`.
- Os relatórios HTML escapam conteúdo não confiável; os PDFs são gerados localmente.
- Notificações do sistema só são ativadas após permissão explícita no navegador.
- O backup exclui `models`, `tools` e executáveis e tem limite de 96 MB.
- A restauração rejeita caminhos desconhecidos, travessia de diretório, links simbólicos, ZIP criptografado, JSON inválido e SQLite sem integridade.
- `data/hermes-incidents.db` e os backups não são criptografados; proteja-os como qualquer relatório técnico.
- O `.exe` de teste não é assinado digitalmente; valide o SHA-256 antes de executá-lo em outra máquina.
