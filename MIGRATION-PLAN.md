# Plano de evolução a partir da versão 0.7.0

## Regra principal

A versão 0.7.0 que funciona no computador é a única base confiável. A 0.8.0-r2 não deve ser mesclada diretamente na `main`.

## O que preservar da 0.7.0

- interface e organização visual atuais;
- inicializador e caminhos portáteis já validados;
- chat local com llama.cpp;
- detecção de hardware e perfis de desempenho;
- base de conhecimento local;
- monitoramento de CPU, memória, disco e rede;
- gráficos, alertas e histórico SQLite.

## Melhorias candidatas da experiência 0.8

Portar separadamente, uma por commit:

1. diagnóstico rápido e completo;
2. severidades Normal, Atenção, Crítico e Não verificado;
3. comparação com diagnóstico anterior;
4. exportação HTML, JSON e TXT;
5. explicação dos dados pela IA local;
6. ações seguras por lista permitida;
7. fallback quando `psutil` não estiver instalado.

## Ordem de implementação no modo Work

1. Copiar para uma branch a pasta real da 0.7.0 que está funcionando.
2. Executar e registrar o estado inicial antes de alterar qualquer arquivo.
3. Adicionar somente o fallback de dependências e testar.
4. Adicionar o diagnóstico estruturado sem trocar a interface.
5. Adicionar um único componente visual por vez.
6. Testar inicialização limpa em outra pasta.
7. Somente depois atualizar número de versão e documentação.

## Critérios de aprovação

- abre por `Iniciar-HERMES.bat` sem instalação manual obrigatória;
- mantém o mesmo layout da 0.7.0 até aprovação explícita;
- funciona sem modelo GGUF para monitoramento e diagnóstico básico;
- falha de dependência não encerra o programa sem explicação;
- caminhos permanecem relativos e portáteis;
- não executa comandos arbitrários gerados pela IA;
- cada melhoria pode ser revertida por commit.
