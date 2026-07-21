# HERMES Security Portable

Assistente portátil de IA local para diagnóstico defensivo de infraestrutura, suporte técnico e uso offline.

## Novidades da versão 0.8.0

- transforma alertas do monitor em incidentes vinculados, sem duplicar registros ativos;
- cria incidentes manuais com snapshot agregado do computador;
- organiza estados **Em aberto**, **Investigando** e **Resolvido**;
- oferece checklist defensivo somente de leitura e linha do tempo auditável;
- registra notas e análises opcionais da IA local no histórico do incidente;
- exporta cada incidente em HTML e PDF, sem dependência adicional;
- envia notificações nativas do navegador/Windows somente após permissão do usuário;
- exporta e restaura um backup ZIP validado de configurações, históricos e relatórios;
- inclui compilação reproduzível para um `.exe` único do Windows 10/11 x64;
- mantém dados graváveis ao lado do executável, preservando a portabilidade.

Consulte [`docs/CENTRAL-DE-INCIDENTES.md`](docs/CENTRAL-DE-INCIDENTES.md) e [`docs/EXECUTAVEL-PORTATIL.md`](docs/EXECUTAVEL-PORTATIL.md).

## Monitoramento da versão 0.7.0

- monitora CPU, memória, disco e taxas agregadas de rede enquanto o HERMES está aberto;
- registra um histórico local com intervalos de 5 segundos a 5 minutos;
- cria alertas somente depois de várias leituras consecutivas acima do limite;
- permite configurar níveis de atenção e crítico para cada recurso;
- mostra gráfico em tempo real, médias e picos das últimas 24 horas;
- acompanha alertas ativos e resolvidos, com confirmação de leitura;
- exporta em JSON a janela de dados exibida na interface;
- limita automaticamente retenção, quantidade de amostras e alertas;
- retoma o monitor na próxima abertura somente depois de ele ter sido ativado pelo usuário;
- não encerra processos, captura pacotes ou aplica correções automaticamente.

Consulte [`docs/MONITORAMENTO-CONTINUO.md`](docs/MONITORAMENTO-CONTINUO.md) para entender os limites, alertas e cuidados de privacidade.
O registro técnico da versão anterior permanece em [`docs/VERSAO-0.7.0.md`](docs/VERSAO-0.7.0.md).

## Base de Conhecimento da versão 0.5.0

- importa documentos `.txt`, `.md`, `.json` e `.log` de até 2 MB;
- organiza fontes em coleções locais;
- indexa o conteúdo com SQLite, sem serviços externos;
- pesquisa documentos mesmo com a IA desligada;
- responde perguntas usando somente as fontes recuperadas;
- apresenta referências numeradas e trechos usados na resposta;
- transforma relatórios HERMES em fontes pesquisáveis;
- permite selecionar documentos, visualizar conteúdo e excluir dados localmente.

Consulte [`docs/BASE-DE-CONHECIMENTO.md`](docs/BASE-DE-CONHECIMENTO.md) para o fluxo completo, limites e cuidados de privacidade.

## Diagnóstico inteligente da versão 0.4.0

- compara dois relatórios sem depender da IA;
- separa alertas novos, resolvidos, piores, melhores e inalterados;
- mostra a variação de CPU, memória e disco entre as coletas;
- permite fixar um relatório como referência;
- interpreta a evolução com a IA local, quando disponível;
- gera um plano priorizado com passos e validação;
- oferece somente comandos conhecidos de leitura para copiar, sem executá-los.

## Recursos da versão 0.3.2

- analisa qualquer relatório com a IA local;
- mantém histórico das conversas dentro da pasta portátil;
- baixa, pausa e continua modelos pela interface;
- mede a velocidade real do modelo em tokens por segundo;
- exporta relatórios autocontidos em HTML;
- permite copiar respostas e limpar o histórico.

## Otimizações da versão 0.3.1

- detecta CPU, núcleos, memória e vídeo do computador;
- recomenda automaticamente o perfil de IA adequado;
- inicia o `llama.cpp` com contexto, threads e GPU layers controlados;
- alterna entre respostas rápidas e análise profunda;
- permite salvar os ajustes pela interface;
- inclui `CONFIGURAR-IA.bat` para instalar o servidor e baixar o modelo escolhido.

## O que faz

- conversa com um modelo local via `llama.cpp`;
- coleta diagnóstico básico da máquina;
- gera relatórios JSON;
- auxilia troubleshooting;
- oferece dashboard SOC local com métricas, alertas e histórico;
- pode ser empacotado em `.exe` com PyInstaller.

## Primeiro uso no Windows com o executável

1. Extraia o pacote `HERMES-Security-Portable-0.8.0-Windows-x64.zip`.
2. Execute `HERMES-Security-Portable-0.8.0.exe`.
3. Aguarde o painel abrir em `http://127.0.0.1:8765`.

O `.exe` já inclui Python, `psutil` e a interface. O modelo GGUF continua opcional e não é incluído por ocupar vários gigabytes.

## Primeiro uso pelo código-fonte

1. Extraia todo o ZIP.
2. Execute `INSTALAR-HERMES.bat`.
3. Execute `CONFIGURAR-IA.bat` e escolha o perfil Balanceado.
4. Execute `INICIAR-HERMES.bat`.

O dashboard abre em `http://127.0.0.1:8765`. Os diagnósticos funcionam mesmo antes de instalar o modelo.

## Perfis disponíveis

| Perfil | Modelo oficial | Indicação |
| --- | --- | --- |
| Rápido | Qwen3 1.7B Q8_0 | Menor consumo e respostas simples |
| Balanceado | Qwen3 4B Q4_K_M | Recomendado para 16 GB de RAM |
| Qualidade | Qwen3 8B Q4_K_M | Análises mais elaboradas e lentas |

Os modelos são baixados da [organização oficial Qwen](https://huggingface.co/Qwen) e não estão incluídos no ZIP.

## Interface Web 0.8.0

- visão geral com CPU, memória, disco e atividade de rede;
- monitoramento contínuo autorizado, gráfico histórico e estado da coleta;
- limites configuráveis e alertas locais ativos ou resolvidos;
- confirmação de leitura, limpeza e exportação da janela de telemetria;
- estado do servidor `llama.cpp`;
- diagnósticos de sistema, rede ou completos;
- achados classificados como normal, atenção ou crítico;
- histórico e visualização dos relatórios locais;
- assistente de IA em área separada;
- perfis Automático, Rápido, Balanceado e Qualidade;
- controles de contexto, threads, camadas na GPU e profundidade da resposta;
- histórico local, gerenciador de modelos e benchmark;
- análise assistida e exportação HTML de relatórios;
- comparação de evolução com referência persistente;
- plano de correção seguro, revisável e sem execução automática;
- Base Local com coleções, importação e pesquisa offline;
- perguntas à IA com fontes numeradas e escopo selecionável;
- Central de Incidentes com snapshot, checklist, notas e linha do tempo;
- exportação HTML/PDF de incidentes e notificações autorizadas;
- backup e restauração guiados dos dados portáteis;
- layout responsivo e sem dependências externas de frontend.

## Segurança

Use apenas em laboratório ou ambiente autorizado. Não publique senhas, tokens, IPs reais, logs reais, documentos internos, modelos ou executáveis de terceiros. A Base Local, os incidentes e o histórico do monitor não são criptografados: proteja a pasta portátil. Revise qualquer comando antes de copiá-lo; o HERMES não executa correções automaticamente. A compilação de teste não possui assinatura digital comercial.
