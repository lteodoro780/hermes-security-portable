#!/usr/bin/env python3
from __future__ import annotations

import json, os, platform, shutil, socket, subprocess, sys
import urllib.error, urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .hermes_paths import APP_DIR as BASE_DIR, REPORT_DIR
except ImportError:
    from hermes_paths import APP_DIR as BASE_DIR, REPORT_DIR

APP_NAME = "HERMES Security Portable"
LLAMA_SERVER_URL = os.getenv(
    "HERMES_LLAMACPP_URL",
    "http://127.0.0.1:8080/v1/chat/completions",
)
REPORT_DIR.mkdir(parents=True, exist_ok=True)

def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def safe_run(command: list[str], timeout: int = 25) -> dict[str, Any]:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout, shell=False, encoding="utf-8", errors="replace")
        return {"command": command, "returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    except FileNotFoundError:
        return {"command": command, "returncode": 127, "stdout": "", "stderr": f"Comando não encontrado: {command[0]}"}
    except subprocess.TimeoutExpired:
        return {"command": command, "returncode": 124, "stdout": "", "stderr": f"Timeout após {timeout}s"}

def ask_llama(prompt: str, max_tokens: int = 450, mode: str = "quick") -> str:
    mode_switch = "/think" if mode == "deep" else "/no_think"
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "Você é o HERMES, assistente local de infraestrutura e segurança defensiva. Responda em português do Brasil.",
            },
            {"role": "user", "content": f"{prompt}\n\n{mode_switch}"},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.4 if mode == "quick" else 0.6,
        "stream": False,
    }
    req = urllib.request.Request(
        LLAMA_SERVER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = response.read().decode("utf-8", errors="replace")
            parsed = json.loads(raw)
            choices = parsed.get("choices") or []
            if choices:
                message = choices[0].get("message") or {}
                return message.get("content") or choices[0].get("text") or raw
            return parsed.get("content") or parsed.get("response") or raw
    except urllib.error.URLError as exc:
        return f"Não consegui conectar no llama.cpp server. Inicie scripts\\\\windows\\\\01-iniciar-servidor-ia.bat\\nErro: {exc}"
    except Exception as exc:
        return f"Erro ao consultar IA local: {exc}"

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

def nmap_basic_scan(target: str) -> dict[str, Any]:
    if not shutil.which("nmap"):
        return {"target": target, "available": False, "message": "Nmap não encontrado no PATH."}
    return {"target": target, "available": True, "result": safe_run(["nmap", "-sV", "--top-ports", "20", target], timeout=120)}

def save_report(name: str, data: dict[str, Any]) -> Path:
    path = REPORT_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path

def help_text() -> str:
    return """
Comandos:
  ajuda
  info
  diagnostico rede
  scan <alvo>
  perguntar <texto>
  relatorio
  sair
"""

def main() -> None:
    print("=" * 60)
    print(APP_NAME)
    print("IA local portátil para diagnóstico defensivo")
    print("=" * 60)
    print("Digite 'ajuda'.\\n")

    while True:
        try:
            cmd = input("hermes> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\\nSaindo...")
            break

        if not cmd:
            continue
        if cmd in {"sair", "exit", "quit"}:
            break
        if cmd == "ajuda":
            print(help_text())
        elif cmd == "info":
            data = system_info()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("Salvo em:", save_report("system-info", data))
        elif cmd == "diagnostico rede":
            data = network_diagnostics()
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("Salvo em:", save_report("network-diagnostics", data))
        elif cmd.startswith("scan "):
            target = cmd.replace("scan ", "", 1).strip()
            data = nmap_basic_scan(target)
            print(json.dumps(data, indent=2, ensure_ascii=False))
            print("Salvo em:", save_report("nmap-basic", data))
        elif cmd.startswith("perguntar "):
            print(ask_llama(cmd.replace("perguntar ", "", 1).strip()))
        elif cmd == "relatorio":
            data = {"system": system_info(), "network": network_diagnostics()}
            print("Salvo em:", save_report("full-diagnostic", data))
            prompt = "Analise este diagnóstico e gere próximos passos defensivos:\\n" + json.dumps(data, ensure_ascii=False)[:7000]
            print(ask_llama(prompt, max_tokens=900, mode="deep"))
        else:
            print("Comando desconhecido. Digite 'ajuda'.")

if __name__ == "__main__":
    main()
