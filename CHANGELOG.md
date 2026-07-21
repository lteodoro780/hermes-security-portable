# Changelog

## 0.8.0

- nova Central de Incidentes local em `data/hermes-incidents.db`;
- criação manual ou a partir de um alerta sustentado do monitor;
- prevenção de incidentes ativos duplicados para o mesmo alerta;
- estados em aberto, investigando e resolvido com linha do tempo completa;
- snapshot agregado de sistema e métricas, sem nomes de processos ou leitura de arquivos;
- checklist específico para CPU, memória, disco ou observações gerais;
- notas, etapas marcáveis e análise opcional usando somente a IA local;
- exportação autocontida em HTML e PDF gerado pela biblioteca padrão;
- notificações opcionais do navegador/Windows para novos alertas confirmados;
- backup ZIP de configurações, bancos SQLite, histórico e relatórios;
- restauração com lista de caminhos permitidos, bloqueio de travessia, validação JSON/SQLite e rollback;
- caminhos portáteis compatíveis com execução congelada pelo PyInstaller;
- executável único para Windows 10/11 x64, sem exigir Python na máquina de teste;
- workflow Windows com testes, smoke test da API, ZIP externo e SHA-256;
- novos testes de incidentes, PDF, backup, restauração, caminhos congelados e API.

## 0.7.0

- novo módulo de monitoramento contínuo, ativado e pausado pelo usuário;
- coleta leve de CPU, memória, disco e taxas agregadas de rede via `psutil`;
- intervalo configurável entre 5 segundos e 5 minutos, com padrão de 15 segundos;
- histórico local em `data/hermes-monitor.db`, usando SQLite e retenção limitada;
- gráfico responsivo de CPU, memória e disco sem bibliotecas externas de frontend;
- médias e picos das últimas 24 horas, última coleta e uso do banco;
- limites de atenção e crítico configuráveis para CPU, memória e disco;
- confirmação por 2 a 10 coletas consecutivas antes da abertura ou resolução de alertas;
- escalonamento entre atenção e crítico sem criar alertas repetidos a cada coleta;
- linha do tempo com eventos ativos, resolvidos e confirmação de leitura;
- limite rígido de 50.000 amostras e 2.000 alertas resolvidos;
- limpeza do histórico preservando as regras e exportação JSON da janela exibida;
- retomada opcional na próxima abertura quando o usuário deixou o monitor ativo;
- nenhuma captura de pacotes, leitura de arquivos, encerramento de processos ou correção automática;
- novas APIs locais e testes automatizados do banco, motor, ciclo de vida e alertas.

## 0.5.0

- Base de Conhecimento Local em SQLite, sem novas dependências;
- importação segura de `.txt`, `.md`, `.json` e `.log`;
- limite de 2 MB por documento, 64 MB por base e 500 documentos;
- coleções personalizadas e seleção de fontes específicas;
- divisão automática em trechos com sobreposição controlada;
- pesquisa offline com SQLite FTS5 e fallback compatível;
- relatórios HERMES transformados em fontes pesquisáveis;
- respostas da IA restritas ao contexto local recuperado;
- referências numeradas, trechos de origem e visualização das fontes;
- prevenção de duplicatas por hash de conteúdo;
- exclusão individual, por coleção ou limpeza completa;
- documentos tratados como conteúdo não confiável no prompt da IA;
- novos endpoints e testes automatizados da base local.

## 0.4.0

- comparação determinística entre dois relatórios, disponível mesmo sem IA;
- classificação de alertas novos, resolvidos, piores, melhores e inalterados;
- cálculo das variações de CPU, memória e disco entre coletas compatíveis;
- relatório de referência persistente para acompanhamento de evolução;
- interpretação opcional da comparação usando somente a IA local;
- plano de correção estruturado por prioridade, objetivo, passos e validação;
- comandos restritos a uma lista fechada de verificações somente de leitura;
- nenhum comando ou correção é executado automaticamente;
- novos endpoints locais para referência, comparação e plano;
- novos testes automatizados do motor de diagnóstico inteligente e da API.

## 0.3.2

- histórico local e limitado de conversas, com opção de limpeza;
- botão para analisar relatórios existentes com a IA local;
- gerenciador de modelos na interface com progresso, pausa e retomada;
- downloads restritos aos modelos oficiais configurados e finalização por arquivo `.part`;
- teste de desempenho real do modelo em tokens por segundo;
- estimativa de CPU e memória quando a IA está offline;
- exportação de relatórios em HTML autocontido e seguro;
- cópia rápida das respostas e análises;
- novos endpoints locais para histórico, modelos, benchmark e exportação;
- testes automatizados dos novos fluxos sem baixar modelos reais.

## 0.3.1

- detecção automática de CPU, núcleos físicos, threads, memória e vídeo;
- recomendação de perfil baseada na memória disponível;
- perfis Rápido, Balanceado e Qualidade para modelos Qwen3 oficiais;
- inicializador Python unificado para o dashboard e o `llama.cpp`;
- contexto de 4.096 tokens, threads físicas e zero camadas de GPU como padrão seguro;
- modos de resposta Rápido (`/no_think`) e Análise profunda (`/think`);
- endpoint OpenAI-compatible `/v1/chat/completions` com fallback legado;
- painel de configuração persistente e aviso de reinicialização;
- instalador guiado opcional `CONFIGURAR-IA.bat`;
- novos testes de perfis, validação e API.

## 0.3.0

- nova interface SOC responsiva e totalmente local;
- dashboard com telemetria do host via `psutil`;
- áreas de Visão Geral, Diagnósticos, Assistente IA, Relatórios e Configurações;
- diagnósticos estruturados de sistema, rede e modo completo;
- classificação de achados por severidade;
- histórico e visualização segura dos relatórios JSON;
- estados visuais do núcleo HERMES;
- limites de requisição e cabeçalhos de segurança no servidor web;
- testes automatizados do backend e da API.

## 0.2.0

- interface Web Cybergrid inicial;
- backend HTTP local e integração com `llama.cpp`.

## 0.1.0

- Pacote portátil inicial.
