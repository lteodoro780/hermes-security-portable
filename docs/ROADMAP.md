# Roadmap HERMES

## 0.2.0

- Interface Web Cybergrid;
- abertura automática no navegador;
- backend local em Python;
- endpoint `/api/chat`;
- endpoint `/api/network`;
- script `05-iniciar-tudo.bat`.

## 0.3.0

- dashboard SOC responsivo;
- navegação real entre módulos;
- telemetria de CPU, memória, disco e rede;
- estado visual do núcleo HERMES;
- diagnósticos estruturados de sistema, rede e modo completo;
- classificação de achados por severidade;
- histórico e visualização de relatórios;
- cabeçalhos de segurança e limite de requisição;
- testes automatizados do backend e da API.

## 0.3.1

- detecção de hardware e recomendação automática;
- perfis Qwen3 Rápido, Balanceado e Qualidade;
- ajuste de contexto, threads e camadas na GPU;
- modo rápido e análise profunda;
- instalação guiada da IA local;
- inicialização unificada do dashboard e llama.cpp.

## 0.3.2

- histórico local de conversas;
- análise de relatórios com IA;
- downloads de modelos pela interface;
- benchmark local de desempenho;
- exportação HTML segura.

## 0.4.0

- comparação de evolução entre dois relatórios;
- relatório fixado como referência;
- detecção de alertas novos, resolvidos, piores e melhores;
- comparação das métricas de CPU, memória e disco;
- interpretação opcional com IA local;
- plano de correção priorizado e revisável;
- comandos de verificação somente para leitura e cópia;
- novos testes de segurança do plano e da comparação.

## 0.5.0

- Base de Conhecimento Local em SQLite;
- importação de `.txt`, `.md`, `.json` e `.log`;
- coleções e seleção de fontes;
- pesquisa offline com índice textual;
- relatórios HERMES como documentos pesquisáveis;
- perguntas à IA usando trechos recuperados;
- fontes numeradas e visualização do conteúdo;
- exclusão individual e limpeza completa da base;
- limites de capacidade e prevenção de duplicatas.

## 0.7.0

- monitoramento contínuo autorizado de CPU, memória, disco e rede agregada;
- histórico local de telemetria em SQLite;
- gráfico responsivo, médias e picos das últimas 24 horas;
- intervalo, retenção e limites configuráveis;
- confirmação sustentada para reduzir falsos positivos;
- alertas ativos, resolvidos e marcados como vistos;
- exportação JSON e limpeza do histórico;
- retomada opcional na próxima inicialização;
- nenhuma ação corretiva automática.

## 0.8.0

- Central de Incidentes vinculada aos alertas do monitor;
- registros manuais com snapshot agregado;
- estados, checklist somente de leitura e linha do tempo;
- notas e interpretação opcional pela IA local;
- exportação de incidentes em HTML e PDF;
- notificações opcionais autorizadas pelo usuário;
- backup e restauração guiados, com validação prévia;
- executável portátil único para Windows 10/11 x64;
- pacote de teste externo com hash SHA-256.

## Próximos passos

- suporte opcional a PDF na Base Local;
- perfis de prompts para suporte técnico;
- pesquisa unificada entre incidentes, relatórios e documentos;
- assinatura digital e instalador opcional, mantendo o pacote portátil.
