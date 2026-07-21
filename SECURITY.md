# Security Policy

Não publique senhas, tokens, IPs reais, logs sensíveis, históricos, relatórios exportados, modelos ou binários de terceiros.

O HERMES não executa correções sugeridas. Os comandos do plano de correção pertencem a uma lista fechada de verificações de leitura, aparecem apenas para revisão e cópia e devem ser conferidos antes do uso.

A Base Local fica em `data/hermes-knowledge.db` e não é criptografada. Os documentos são limitados a formatos textuais permitidos, tratados como conteúdo não confiável e nunca são usados como caminhos no sistema de arquivos. Limpe a base antes de compartilhar a pasta portátil.

O monitor fica em `data/hermes-monitor.db` e também não é criptografado. Ele registra somente percentuais agregados de CPU, memória e disco e taxas totais de rede; não captura pacotes, conteúdo, arquivos, nomes de processos ou comandos. Alertas exigem coletas consecutivas e são apenas informativos. Use **Limpar histórico** antes de compartilhar a pasta portátil.
