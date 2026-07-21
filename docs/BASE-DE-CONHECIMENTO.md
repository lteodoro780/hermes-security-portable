# Base de Conhecimento Local

A versão 0.5.0 guarda documentos e trechos pesquisáveis em `data/hermes-knowledge.db`. O banco acompanha a pasta portátil e não depende de nuvem.

## Como usar

1. Abra **Base Local**.
2. Crie uma coleção ou mantenha **Geral**.
3. Arraste arquivos TXT, MD, JSON ou LOG para a área de importação.
4. Se desejar, adicione um relatório HERMES pelo seletor da mesma tela.
5. Marque documentos específicos ou selecione uma coleção.
6. Use **Buscar sem IA** para localizar trechos ou **Perguntar à IA** para gerar uma resposta fundamentada.

Cada resposta apresenta as fontes numeradas. Abra um cartão de fonte para revisar o documento original armazenado localmente.

## Limites

- 2 MB por documento;
- 500 documentos;
- 64 MB de conteúdo indexado;
- 40 coleções;
- até 20 arquivos selecionados por importação.

O HERMES evita duplicatas dentro da mesma coleção usando o hash do conteúdo. A pesquisa usa SQLite FTS5 quando disponível e ativa automaticamente um modo compatível quando necessário.

## Privacidade

O banco SQLite não é criptografado. Qualquer pessoa com acesso à pasta pode inspecionar seu conteúdo. Use **Limpar toda a base** antes de compartilhar ou descartar a pasta portátil.

Documentos são tratados como fontes não confiáveis: textos que tentem dar ordens à IA não substituem as regras do HERMES. Mesmo assim, revise respostas e fontes antes de tomar decisões técnicas.
