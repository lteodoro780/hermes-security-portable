# HERMES Security Portable 0.7.0

Esta versão consolida as atualizações construídas após a primeira Web UI CyberGrid.

## 0.3.1 — adaptação ao computador

- detecção de CPU, RAM, disco e sistema operacional;
- perfis automáticos `fast`, `balanced` e `quality`;
- ajuste de contexto, threads, batch, intervalo de monitoramento e retenção;
- perfil balanceado recomendado automaticamente para máquinas com 16 GB de RAM;
- caminhos relativos, mantendo o projeto portátil.

## 0.5.0 — base de conhecimento local

- indexação de TXT, MD, JSON e LOG;
- PDF disponível quando `pypdf` estiver instalado;
- coleções baseadas em pastas;
- busca offline sem modelo de IA;
- respostas da IA acompanhadas das fontes encontradas;
- relatórios do próprio HERMES também podem ser indexados;
- armazenamento local em SQLite.

## 0.6.x — perfis e preservação dos dados

- perfis Suporte Técnico, Segurança Defensiva, Redes e Resumo Executivo;
- referência de página para PDFs extraídos;
- backup local de `config/`, `data/` e `knowledge/`;
- OCR permanece fora do escopo da versão estável.

## 0.7.0 — monitoramento contínuo

- CPU, memória, disco e tráfego de rede;
- histórico limitado em SQLite;
- gráfico local sem CDN ou bibliotecas externas;
- intervalo controlado pelo perfil de hardware;
- alerta somente depois de três leituras consecutivas acima do limite;
- intervalo mínimo de cinco minutos entre alertas iguais;
- nenhuma correção automática ou comando arbitrário;
- modo compatibilidade quando `psutil` não estiver instalado.

## Dependências

O núcleo utiliza somente a biblioteca padrão do Python. `psutil` e `pypdf` são opcionais.
