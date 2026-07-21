# Central de Incidentes

A versão 0.8.0 transforma um alerta ou uma observação manual em um registro local com começo, investigação e resolução. O objetivo é documentar o que foi visto sem dar ao HERMES permissão para alterar o computador.

## Fluxo recomendado

1. Em **Monitoramento**, localize um alerta confirmado e clique em **Abrir incidente**.
2. Revise o snapshot criado no mesmo instante.
3. Mude o estado para **Investigando**.
4. Siga o checklist somente de leitura e registre notas curtas.
5. Se a IA local estiver online, use **Analisar com IA** para obter uma interpretação opcional.
6. Exporte o registro em HTML ou PDF quando precisar compartilhar o resultado.
7. Marque como **Resolvido** depois da validação manual.

O mesmo alerta não cria dois incidentes ativos. Depois que o registro for resolvido, um novo ciclo do alerta poderá abrir outro incidente.

## Snapshot

O snapshot contém horário, identificação básica do sistema, resumo do hardware e métricas agregadas disponíveis. Para preservar privacidade e manter o escopo defensivo, ele não inclui:

- nomes ou argumentos de processos;
- conteúdo de arquivos;
- janelas, teclado ou área de transferência;
- pacotes ou conteúdo de rede;
- comandos executados pelo usuário.

## Dados e limites

- Banco: `data/hermes-incidents.db`.
- Limite: 500 incidentes; registros resolvidos antigos podem ser removidos para liberar capacidade.
- Título: até 180 caracteres.
- Descrição: até 8.000 caracteres.
- Nota ou análise: até 12.000 caracteres por evento.
- Snapshot: até 96 KB.

O banco não é criptografado. Use **Configurações → Backup e restauração** para criar uma cópia e proteja o ZIP como um relatório técnico.

## Exportações

O HTML é autocontido e escapa títulos, descrições e eventos antes de montar a página. O PDF usa uma fonte interna padrão e é gerado pela própria aplicação, sem enviar dados a serviços externos.

## Notificações

O botão **Ativar avisos** solicita a permissão do navegador. Somente novos alertas confirmados depois da ativação geram uma notificação. Negar a permissão não afeta o monitor nem a Central de Incidentes.
