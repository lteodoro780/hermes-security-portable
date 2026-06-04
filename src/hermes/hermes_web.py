#!/usr/bin/env python3
from __future__ import annotations

import json, os, platform, socket, subprocess, sys, urllib.error, urllib.request, webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

APP_NAME = "HERMES Security Portable"
HOST = os.getenv("HERMES_WEB_HOST", "127.0.0.1")
PORT = int(os.getenv("HERMES_WEB_PORT", "8765"))
LLAMA_URL = os.getenv("HERMES_LLAMACPP_URL", "http://127.0.0.1:8080/completion")

BASE_DIR = Path(__file__).resolve().parents[2]
WEB_DIR = BASE_DIR / "web"
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(exist_ok=True)

def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def json_response(handler, payload: dict[str, Any], status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)

def safe_run(command: list[str], timeout: int = 25) -> dict[str, Any]:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, shell=False, encoding="utf-8", errors="replace")
        return {"command": command, "returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    except FileNotFoundError:
        return {"command": command, "returncode": 127, "stdout": "", "stderr": f"Comando não encontrado: {command[0]}"}
    except subprocess.TimeoutExpired:
        return {"command": command, "returncode": 124, "stdout": "", "stderr": f"Timeout após {timeout}s"}

def system_info() -> dict[str, Any]:
    return {
        "timestamp": now(),
        "hostname": socket.gethostname(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "python": sys.version,
    }

def network_diagnostics() -> dict[str, Any]:
    if platform.system().lower().startswith("win"):
        cmds = [["ipconfig", "/all"], ["route", "print"], ["arp", "-a"], ["ping", "127.0.0.1"]]
    else:
        cmds = [["ip", "a"], ["ip", "route"], ["arp", "-a"], ["ping", "-c", "2", "127.0.0.1"]]
    return {"timestamp": now(), "commands": [safe_run(c) for c in cmds]}

def save_report(name: str, data: dict[str, Any]) -> str:
    path = REPORT_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return str(path)

def ask_llama(prompt: str, max_tokens: int = 500) -> str:
    payload = {"prompt": prompt, "n_predict": max_tokens, "temperature": 0.3, "stop": ["</s>"]}
    req = urllib.request.Request(
        LLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            raw = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw)
            return parsed.get("content") or parsed.get("response") or raw
    except urllib.error.URLError as exc:
        return f"Não consegui conectar no llama.cpp server.\nURL: {LLAMA_URL}\nErro: {exc}\n\nInicie: scripts/windows/01-iniciar-servidor-ia.bat"
    except Exception as exc:
        return f"Erro ao consultar IA local: {exc}"

class HermesHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            json_response(self, {"ok": True, "app": APP_NAME, "web": f"http://{HOST}:{PORT}", "llama_url": LLAMA_URL, "timestamp": now()})
            return
        if parsed.path == "/api/system":
            json_response(self, system_info())
            return
        if parsed.path == "/api/network":
            data = network_diagnostics()
            json_response(self, {"report": save_report("web-network-diagnostics", data), "data": data})
            return
        return super().do_GET()

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/chat":
            json_response(self, {"error": "Endpoint não encontrado"}, status=404)
            return
        raw = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            json_response(self, {"error": "JSON inválido"}, status=400)
            return
        message = str(payload.get("message", "")).strip()
        if not message:
            json_response(self, {"error": "Campo message é obrigatório"}, status=400)
            return
        system_prompt = "Você é o HERMES, assistente local de infraestrutura de TI. Responda de forma objetiva, defensiva e segura."
        json_response(self, {"answer": ask_llama(f"{system_prompt}\n\nUsuário: {message}\n\nHERMES:"), "timestamp": now()})

def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), HermesHandler)
    url = f"http://{HOST}:{PORT}"
    print("=" * 70)
    print(APP_NAME)
    print(f"Web UI: {url}")
    print(f"llama.cpp: {LLAMA_URL}")
    print("CTRL+C para encerrar")
    print("=" * 70)
    if os.getenv("HERMES_OPEN_BROWSER", "1") == "1":
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando...")
    finally:
        server.server_close()

if __name__ == "__main__":
    main()
