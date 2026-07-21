# Monitoramento Contínuo

Desde a versão 0.7.0, o HERMES acompanha recursos do computador enquanto está aberto. A coleta é local, não usa a IA e só começa depois de o usuário clicar em **Iniciar monitoramento**. Na 0.8.0, um alerta também pode ser aberto na **Central de Incidentes**.

## O que é coletado

- percentual de uso total da CPU;
- percentual de uso da memória;
- percentual ocupado no disco em que o HERMES está executando;
- taxas totais de envio e recebimento da rede, em bytes por segundo;
- data e hora de cada coleta.

O monitor não captura pacotes, endereços acessados, conteúdo de rede, nomes de processos, arquivos, teclado ou tela.

## Como usar

1. Abra **Monitoramento** no menu lateral.
2. Revise o intervalo e os limites padrão.
3. Clique em **Iniciar monitoramento**.
4. Acompanhe valores atuais, médias, picos e o gráfico.
5. Use **Pausar** para interromper novas coletas sem apagar o histórico.

Quando o HERMES é fechado, a thread de coleta é encerrada. Se o usuário deixou o monitor ativo, ele retoma na próxima abertura. Clicar em **Pausar** desativa essa retomada.

## Formação dos alertas

CPU, memória e disco possuem um limite de atenção e outro crítico. O padrão exige três coletas consecutivas no mesmo nível antes de criar, escalar ou resolver um alerta. Essa confirmação reduz avisos causados por picos muito curtos.

Exemplo com intervalo de 15 segundos e confirmação de 3 coletas: a condição precisa permanecer por aproximadamente 45 segundos.

- **Atenção:** todas as leituras de confirmação atingiram o limite de atenção.
- **Crítico:** todas as leituras de confirmação atingiram o limite crítico.
- **Resolvido:** todas as leituras de confirmação voltaram para baixo do limite de atenção.

Um alerta ativo é atualizado em vez de ser recriado a cada coleta. **Marcar como visto** confirma a leitura, mas não altera a condição técnica.

## Configurações e limites

| Opção | Valores permitidos | Padrão |
| --- | --- | --- |
| Intervalo | 5, 10, 15, 30, 60, 120 ou 300 segundos | 15 segundos |
| Confirmação | 2 a 10 coletas | 3 coletas |
| Retenção | 24 a 720 horas | 168 horas (7 dias) |
| Amostras | máximo rígido | 50.000 |
| Alertas resolvidos | máximo rígido | 2.000 |

Os limites percentuais precisam ficar entre 50% e 100%, e o nível crítico deve ser maior que o nível de atenção.

## Armazenamento e privacidade

O histórico fica em `data/hermes-monitor.db`. O banco SQLite acompanha a pasta portátil e não é criptografado. **Limpar histórico** remove amostras e alertas, mas preserva intervalos e limites configurados.

**Exportar JSON** salva somente a janela de dados carregada na tela. Antes de enviar o arquivo ou compartilhar a pasta do HERMES, revise o período e apague o histórico caso ele seja sensível.

## Comportamento seguro

O monitor é somente observacional. Ele não encerra processos, não modifica o Windows, não altera a rede e não executa comandos de correção. Um alerta indica que o usuário deve investigar a causa e confirmar as evidências.
