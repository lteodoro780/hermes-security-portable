#!/usr/bin/env python3
"""Inicializador único do HERMES e do servidor local llama.cpp."""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

try:
    from .hermes_profiles import BASE_DIR, runtime_selection
except ImportError:  # Execução direta por INICIAR-HERMES.bat.
    from hermes_profiles import BASE_DIR, runtime_selection


LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080


def port_is_open(host: str = LLAMA_HOST, port: int = LLAMA_PORT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def build_llama_command(selection: dict[str, Any]) -> list[str]:
    llama = selection["llama"]
    if not llama:
        raise RuntimeError("llama.cpp não encontrado")
    profile = selection["profile"]
    model_path = Path(profile["model_path"])
    if not model_path.is_file():
        raise RuntimeError(f"modelo não encontrado: {model_path.name}")

    command = [llama["executable"]]
    if llama["style"] == "unified":
        command.append("serve")
    command.extend(
        [
            "-m",
            str(model_path),
            "--host",
            LLAMA_HOST,
            "--port",
            str(LLAMA_PORT),
            "--ctx-size",
            str(selection["context_size"]),
            "--threads",
            str(selection["threads"]),
            "--threads-batch",
            str(selection["threads"]),
            "--n-gpu-layers",
            str(selection["gpu_layers"]),
            "--parallel",
            "1",
        ]
    )
    return command


def expose_runtime(selection: dict[str, Any]) -> None:
    profile = selection["profile"]
    os.environ["HERMES_ACTIVE_PROFILE"] = str(profile["id"])
    os.environ["HERMES_ACTIVE_MODEL"] = str(profile["model_file"])
    os.environ["HERMES_ACTIVE_THREADS"] = str(selection["threads"])
    os.environ["HERMES_ACTIVE_CONTEXT"] = str(selection["context_size"])
    os.environ["HERMES_ACTIVE_GPU_LAYERS"] = str(selection["gpu_layers"])
    os.environ.setdefault(
        "HERMES_LLAMACPP_URL",
        f"http://{LLAMA_HOST}:{LLAMA_PORT}/v1/chat/completions",
    )


def start_llama(selection: dict[str, Any]) -> subprocess.Popen[Any] | None:
    if port_is_open():
        print("[OK] Servidor de IA já está ativo em 127.0.0.1:8080.")
        return None
    if not selection["model_ready"]:
        expected = selection["profile"]["model_file"]
        print(f"[AVISO] Modelo não encontrado: models\\{expected}")
        print("        Execute CONFIGURAR-IA.bat para habilitar o assistente.")
        return None
    if not selection["llama_ready"]:
        print("[AVISO] llama.cpp não encontrado.")
        print("        Execute CONFIGURAR-IA.bat para instalar ou configurar.")
        return None

    command = build_llama_command(selection)
    profile = selection["profile"]
    print(
        f"[IA] Iniciando perfil {profile['label']} — {profile['model']} "
        f"| contexto {selection['context_size']} | threads {selection['threads']} "
        f"| GPU layers {selection['gpu_layers']}"
    )
    try:
        return subprocess.Popen(command, cwd=str(BASE_DIR), shell=False)
    except OSError as exc:
        print(f"[AVISO] Não foi possível iniciar llama.cpp: {exc}")
        return None


def stop_child(child: subprocess.Popen[Any] | None) -> None:
    if child is None or child.poll() is not None:
        return
    print("\nEncerrando servidor de IA local...")
    child.terminate()
    try:
        child.wait(timeout=8)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=3)


def show_hardware_summary(selection: dict[str, Any]) -> None:
    hardware = selection["hardware"]
    profile = selection["profile"]
    print("=" * 72)
    print("HERMES Security Portable 0.8.0 — incidentes e monitoramento local")
    print(f"CPU: {hardware['cpu_name']}")
    print(
        f"Memória: {hardware['memory_total_gb']} GB | "
        f"{hardware['physical_cores']} núcleos / {hardware['logical_cores']} threads"
    )
    print(f"Perfil resolvido: {profile['label']} — {profile['model']}")
    if profile.get("fallback"):
        print("Observação: foi usado outro perfil porque o modelo solicitado não está instalado.")
    print("=" * 72)


def main() -> None:
    parser = argparse.ArgumentParser(description="Inicializador do HERMES")
    parser.add_argument("--ai-only", action="store_true", help="inicia apenas a IA")
    parser.add_argument("--web-only", action="store_true", help="inicia apenas a interface")
    args = parser.parse_args()

    selection = runtime_selection()
    expose_runtime(selection)
    show_hardware_summary(selection)
    child: subprocess.Popen[Any] | None = None

    try:
        if not args.web_only:
            child = start_llama(selection)
        if args.ai_only:
            if child is not None:
                child.wait()
            elif port_is_open():
                print("Use CTRL+C para voltar.")
                while port_is_open():
                    time.sleep(1)
            return

        # A importação ocorre depois de definir as variáveis de runtime.
        try:
            from .hermes_web import main as web_main
        except ImportError:
            from hermes_web import main as web_main

        web_main()
    except KeyboardInterrupt:
        print("\nInicialização interrompida.")
    finally:
        stop_child(child)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    main()
