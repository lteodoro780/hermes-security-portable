# HERMES Web UI Cybergrid

Interface web local para o HERMES.

## Como iniciar

Terminal 1:

```bat
scripts\windows\01-iniciar-servidor-ia.bat
```

Terminal 2:

```bat
scripts\windows\04-iniciar-webui.bat
```

Ou tudo de uma vez:

```bat
scripts\windows\05-iniciar-tudo.bat
```

Acesse:

```text
http://127.0.0.1:8765
```

## Endpoints

```text
GET  /api/health
GET  /api/system
GET  /api/network
POST /api/chat
```

Por padrão a interface usa `127.0.0.1`, ficando disponível somente na própria máquina.
