#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import platform
import subprocess
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from . import __version__
from .backup import create_backup
from .config import HOST, LLAMA_URL, PORT, REPORT_DIR, WEB_DIR, profile_payload, resolve_profile
from .database import HermesDB
from .hardware import detect_hardware
from .knowledge import KnowledgeBase
from .monitor import MonitorService

APP_NAME = "HERMES Security Portable"
DB = HermesDB()
HARDWARE = detect_hardware()
PROFILE = resolve_profile(HARDWARE.ram_total_gb, HARDWARE.cpu_threads)
KNOWLEDGE = KnowledgeBase(DB)
MONITOR = MonitorService(DB, PROFILE.monitor_interval, PROFILE.history_limit)

ASSISTANT_PROFILES = {
    "support": "Você é o HERMES, assistente local de suporte e infraestrutura. Seja objetivo, defensivo e seguro.",
    "security": "Você é o HERMES em modo Segurança Defensiva. Priorize autorização, evidências, mitigação e não forneça ações ofensivas.",
    "network": "Você é o HERMES em modo Redes. Explique diagnóstico de conectividade, DNS, DHCP e roteamento de forma verificável.",
    "executive": "Você é o HERMES em modo Resumo Executivo. Traduza dados técnicos em impacto, prioridade e próximos passos curtos.",
}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def json_response(handler: SimpleHTTPRequestHandler, payload: Any, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def read_json(handler: SimpleHTTPRequestHandler) -> dict[str, Any]:
    raw = handler.rfile.read(int(handler.headers.get("Content-Length", "0"))).decode("utf-8", errors="replace")
    if not raw:
        return {}
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("O corpo deve ser um objeto JSON")
    return value


def safe_run(command: list[str], timeout: int = 25) -> dict[str, Any]:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, shell=False, encoding="utf-8", errors="replace")
        return {"command": command, "returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    except FileNotFoundError:
        return {"command": command, "returncode": 127, "stdout": "", "stderr": f"Comando não encontrado: {command[0]}"}
    except subprocess.TimeoutExpired:
        return {"command": command, "returncode": 124, "stdout": "", "stderr": f"Timeout após {timeout}s"}


def network_diagnostics() -> dict[str, Any]:
    if platform.system() == "Windows":
        commands = [["ipconfig", "/all"], ["route", "print"], ["arp", "-a"], ["ping", "127.0.0.1"]]
    else:
        commands = [["ip", "a"], ["ip", "route"], ["ping", "-c", "2", "127.0.0.1"]]
    data = {"timestamp": now(), "commands": [safe_run(command) for command in commands]}
    path = REPORT_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-network.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"report": str(path), "data": data}


def ask_llama(prompt: str, max_tokens: int = 650) -> str:
    payload = {
        "prompt": prompt,
        "n_predict": max_tokens,
        "temperature": 0.25,
        "n_ctx": PROFILE.context_size,
        "stop": ["</s>"],
    }
    request = urllib.request.Request(
        LLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=150) as response:
            parsed = json.loads(response.read().decode("utf-8", errors="replace"))
            return str(parsed.get("content") or parsed.get("response") or parsed)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"llama.cpp indisponível em {LLAMA_URL}: {exc}") from exc


def chat(payload: dict[str, Any]) -> dict[str, Any]:
    message = str(payload.get("message", "")).strip()
    if not message:
        raise ValueError("Campo message é obrigatório")
    profile_name = str(payload.get("profile", "support"))
    system_prompt = ASSISTANT_PROFILES.get(profile_name, ASSISTANT_PROFILES["support"])
    sources = KNOWLEDGE.search(message, collection=payload.get("collection"), limit=5)
    context = "\n\n".join(
        f"[Fonte {index}: {item['title']}{' p. '+str(item['page']) if item['page'] else ''}]\n{item['content']}"
        for index, item in enumerate(sources, start=1)
    )
    prompt = f"{system_prompt}\n\nUse somente contexto confiável quando ele existir. Cite [Fonte N].\n"
    if context:
        prompt += f"\nCONTEXTO LOCAL:\n{context}\n"
    prompt += f"\nUsuário: {message}\nHERMES:"
    try:
        answer = ask_llama(prompt)
        mode = "ia-local"
    except RuntimeError as exc:
        if sources:
            answer = "IA local indisponível. Encontrei estes trechos na base:\n\n" + "\n\n".join(
                f"• {item['title']}{' — página '+str(item['page']) if item['page'] else ''}: {item['content'][:500]}"
                for item in sources[:3]
            )
            mode = "busca-offline"
        else:
            answer = str(exc)
            mode = "sem-ia"
    return {"answer": answer, "sources": sources, "mode": mode, "timestamp": now()}


class HermesHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, format: str, *args: Any) -> None:
        if os.getenv("HERMES_QUIET", "0") != "1":
            super().log_message(format, *args)

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        try:
            if parsed.path == "/api/health":
                json_response(self, {
                    "ok": True, "app": APP_NAME, "version": __version__, "timestamp": now(),
                    "monitor": MONITOR.running, "llama_url": LLAMA_URL,
                }); return
            if parsed.path == "/api/system":
                json_response(self, {"hardware": HARDWARE.__dict__, "profile": profile_payload(PROFILE)}); return
            if parsed.path == "/api/network":
                json_response(self, network_diagnostics()); return
            if parsed.path == "/api/metrics/current":
                json_response(self, MONITOR.current()); return
            if parsed.path == "/api/metrics/history":
                minutes = int(params.get("minutes", ["60"])[0])
                json_response(self, {"items": DB.metric_history(minutes)}); return
            if parsed.path == "/api/alerts":
                json_response(self, {"items": DB.recent_alerts()}); return
            if parsed.path == "/api/knowledge/status":
                json_response(self, KNOWLEDGE.status()); return
            if parsed.path == "/api/knowledge/search":
                query = params.get("q", [""])[0]
                collection = params.get("collection", [None])[0]
                json_response(self, {"items": KNOWLEDGE.search(query, collection=collection)}); return
            return super().do_GET()
        except (ValueError, OSError) as exc:
            json_response(self, {"error": str(exc)}, status=400)
        except Exception as exc:
            json_response(self, {"error": f"Falha interna: {exc}"}, status=500)

    def do_POST(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        try:
            payload = read_json(self)
            if parsed.path == "/api/chat":
                json_response(self, chat(payload)); return
            if parsed.path == "/api/knowledge/reindex":
                json_response(self, KNOWLEDGE.index_all(bool(payload.get("include_reports", True)))); return
            if parsed.path == "/api/monitor/sample":
                json_response(self, MONITOR.sample_now()); return
            if parsed.path == "/api/monitor/start":
                MONITOR.start(); json_response(self, {"ok": True, "running": True}); return
            if parsed.path == "/api/monitor/stop":
                MONITOR.stop(); json_response(self, {"ok": True, "running": False}); return
            if parsed.path == "/api/backup/create":
                json_response(self, {"ok": True, "path": create_backup()}); return
            json_response(self, {"error": "Endpoint não encontrado"}, status=404)
        except (json.JSONDecodeError, ValueError) as exc:
            json_response(self, {"error": str(exc)}, status=400)
        except Exception as exc:
            json_response(self, {"error": f"Falha interna: {exc}"}, status=500)


def main() -> None:
    MONITOR.start()
    server = ThreadingHTTPServer((HOST, PORT), HermesHandler)
    url = f"http://{HOST}:{PORT}"
    print("=" * 72)
    print(f"{APP_NAME} v{__version__}")
    print(f"Web UI: {url}")
    print(f"Perfil: {PROFILE.name} | contexto {PROFILE.context_size} | threads {PROFILE.threads}")
    print(f"Monitor: intervalo {PROFILE.monitor_interval}s | banco {DB.path}")
    print("CTRL+C para encerrar")
    print("=" * 72)
    if os.getenv("HERMES_OPEN_BROWSER", "1") == "1":
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando HERMES...")
    finally:
        MONITOR.stop()
        server.server_close()


if __name__ == "__main__":
    main()
