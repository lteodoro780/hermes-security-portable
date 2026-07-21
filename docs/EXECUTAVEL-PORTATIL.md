# Executável portátil do Windows

O artefato `HERMES-Security-Portable-0.8.0.exe` é compilado em um runner Windows x64 com PyInstaller. Ele inclui Python 3.11, `psutil`, o backend e a interface web. A máquina externa não precisa ter Python instalado.

## O que vem no pacote

- executável único para Windows 10/11 x64;
- `COMECE-AQUI.txt` com o teste rápido;
- pastas vazias `config`, `data`, `models`, `reports` e `tools`;
- `SHA256SUMS.txt` para conferir a integridade.

Modelos GGUF e `llama.cpp` não são incorporados. Eles são opcionais, têm vários gigabytes e continuam nas pastas portáteis ao lado do executável.

## Teste em outra máquina

1. Copie o ZIP para a máquina de teste.
2. Confira o SHA-256 do `.exe`:

   ```powershell
   Get-FileHash .\HERMES-Security-Portable-0.8.0.exe -Algorithm SHA256
   ```

3. Compare o resultado com `SHA256SUMS.txt`.
4. Extraia todos os arquivos para uma pasta gravável, como `Documentos\HERMES`.
5. Execute o `.exe` e aguarde a abertura de `http://127.0.0.1:8765`.
6. Teste **Visão Geral**, **Monitoramento**, **Incidentes**, exportação PDF e backup.
7. Encerre com `CTRL+C` na janela do HERMES ou feche a janela.

Evite executar diretamente dentro do ZIP, de `Arquivos de Programas` ou de uma pasta sem permissão de gravação.

## SmartScreen e assinatura

Esta compilação de teste não possui certificado comercial. Por isso o SmartScreen pode exibir um aviso mesmo quando o hash está correto. Só prossiga se o arquivo veio do pacote esperado e o SHA-256 foi conferido. Uma futura distribuição pública deve ser assinada digitalmente.

## Regra de caminhos

Em execução congelada, os arquivos da interface são extraídos internamente pelo PyInstaller. Todo conteúdo do usuário é gravado ao lado do `.exe`:

| Pasta | Conteúdo |
| --- | --- |
| `config` | Preferências da aplicação |
| `data` | Conversas, monitor, Base Local e incidentes |
| `models` | Modelos GGUF opcionais |
| `reports` | Diagnósticos JSON |
| `tools` | `llama.cpp` opcional |

Mover a pasta completa preserva os dados. Mover somente o `.exe` inicia uma pasta portátil nova no destino.

## Compilação reproduzível

No Windows com Python instalado:

```bat
scripts\windows\03-gerar-executavel.bat
```

O arquivo `HERMES-Portable.spec` define recursos, módulos e nome do executável. O workflow `Windows Portable EXE` executa testes Python e JavaScript, inicia o `.exe` com `--web-only`, consulta `/api/health` e só então publica o pacote.
