#!/usr/bin/env python3
"""Serviços sem interface usados pelo aplicativo desktop do HERMES.

Este módulo mantém importação de modelos e controle do ``llama.cpp`` fora da
camada Qt. Assim, as operações de segurança continuam testáveis mesmo em
ambientes sem uma tela ou sem PySide6 instalado.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable

try:
    from .hermes_launcher import build_llama_command, expose_runtime
    from .hermes_paths import APP_DIR, LOG_DIR, MODELS_DIR, ensure_runtime_directories
    from .hermes_profiles import (
        hardware_info,
        is_valid_gguf,
        load_config,
        recommended_profile_id,
        runtime_selection,
        save_config,
    )
except ImportError:  # Execução direta no pacote portátil.
    from hermes_launcher import build_llama_command, expose_runtime
    from hermes_paths import APP_DIR, LOG_DIR, MODELS_DIR, ensure_runtime_directories
    from hermes_profiles import (
        hardware_info,
        is_valid_gguf,
        load_config,
        recommended_profile_id,
        runtime_selection,
        save_config,
    )


APP_VERSION = "0.9.0"
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080
MODEL_COPY_CHUNK = 8 * 1024 * 1024
LLAMA_LOG_PATH = LOG_DIR / "llama-server.log"
ProgressCallback = Callable[[int, int], None]


class DesktopError(ValueError):
    """Erro seguro que pode ser mostrado diretamente na janela desktop."""


def format_bytes(value: int | float | None) -> str:
    size = max(float(value or 0), 0.0)
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024
    return "0 B"


def _resolved_file(value: str | Path, label: str) -> Path:
    try:
        path = Path(value).expanduser().resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise DesktopError(f"{label} não foi encontrado.") from exc
    if not path.is_file():
        raise DesktopError(f"{label} não é um arquivo válido.")
    return path


def model_details(value: str | Path) -> dict[str, Any]:
    path = _resolved_file(value, "O modelo")
    if path.suffix.lower() != ".gguf":
        raise DesktopError("Selecione um arquivo com extensão .gguf.")
    if not is_valid_gguf(path):
        raise DesktopError("O arquivo selecionado não possui um cabeçalho GGUF válido.")
    stat = path.stat()
    return {
        "name": path.name,
        "path": str(path),
        "size_bytes": stat.st_size,
        "size_label": format_bytes(stat.st_size),
        "valid": True,
    }


def register_custom_model(
    source: str | Path,
    *,
    copy_to_portable: bool = False,
    overwrite: bool = False,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Valida e registra um GGUF, copiando-o opcionalmente para ``models``.

    A cópia é escrita primeiro em um arquivo temporário, validada e publicada
    com troca atômica. Um arquivo existente nunca é substituído sem autorização.
    """

    details = model_details(source)
    source_path = Path(details["path"])
    selected = source_path
    copied = False

    if copy_to_portable:
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        target = (MODELS_DIR / source_path.name).resolve()
        if target != source_path:
            if target.exists() and not overwrite:
                raise DesktopError(
                    f"Já existe um arquivo chamado {target.name} na pasta de modelos."
                )
            temporary = MODELS_DIR / f".{source_path.name}.{uuid.uuid4().hex}.importing"
            total = source_path.stat().st_size
            copied_bytes = 0
            try:
                with source_path.open("rb") as input_file, temporary.open("wb") as output_file:
                    while True:
                        chunk = input_file.read(MODEL_COPY_CHUNK)
                        if not chunk:
                            break
                        output_file.write(chunk)
                        copied_bytes += len(chunk)
                        if progress is not None:
                            progress(copied_bytes, total)
                    output_file.flush()
                    os.fsync(output_file.fileno())
                if not is_valid_gguf(temporary) or temporary.stat().st_size != total:
                    raise DesktopError("A cópia do modelo não passou pela validação final.")
                os.replace(temporary, target)
            except OSError as exc:
                raise DesktopError(f"Não foi possível copiar o modelo: {exc}") from exc
            finally:
                temporary.unlink(missing_ok=True)
            selected = target
            copied = True

    saved = save_config({"profile": "custom", "custom_model_path": str(selected)})
    result = model_details(selected)
    result.update({"copied": copied, "profile": saved["profile"]})
    return result


def register_llama_executable(value: str | Path) -> dict[str, str]:
    path = _resolved_file(value, "O executável do llama.cpp")
    lower_name = path.name.lower()
    allowed = {"llama-server", "llama-server.exe", "llama", "llama.exe"}
    if lower_name not in allowed:
        raise DesktopError("Selecione llama-server.exe ou llama.exe.")
    style = "unified" if path.stem.lower() == "llama" else "server"
    save_config({"llama_path": str(path)})
    return {"path": str(path), "name": path.name, "style": style}


def clear_custom_model() -> dict[str, Any]:
    """Esquece a seleção sem remover o arquivo do usuário."""

    return save_config({"profile": "auto", "custom_model_path": ""})


def port_is_open(host: str = LLAMA_HOST, port: int = LLAMA_PORT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def _log_tail(limit: int = 6000) -> str:
    try:
        with LLAMA_LOG_PATH.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(size - limit, 0))
            return handle.read().decode("utf-8", errors="replace").strip()
    except OSError:
        return ""


class ModelRuntimeController:
    """Inicia e encerra somente o processo de IA criado pelo aplicativo."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[Any] | None = None
        self._log_handle: Any = None
        self._lock = threading.RLock()

    def status(self) -> dict[str, Any]:
        with self._lock:
            managed = self._process is not None and self._process.poll() is None
            exit_code = None if self._process is None else self._process.poll()
        selection = runtime_selection()
        online = port_is_open()
        if managed and online:
            state = "running"
        elif online:
            state = "external"
        elif managed:
            state = "starting"
        elif not selection["model_ready"]:
            state = "model_missing"
        elif not selection["llama_ready"]:
            state = "engine_missing"
        else:
            state = "stopped"
        return {
            "state": state,
            "online": online,
            "managed": managed,
            "exit_code": exit_code,
            "profile": selection["profile"],
            "model_ready": selection["model_ready"],
            "llama_ready": selection["llama_ready"],
            "llama": selection["llama"],
            "context_size": selection["context_size"],
            "threads": selection["threads"],
            "gpu_layers": selection["gpu_layers"],
            "log_path": str(LLAMA_LOG_PATH),
        }

    def start(self, wait_seconds: float = 20.0) -> dict[str, Any]:
        with self._lock:
            if self._process is not None and self._process.poll() is None:
                return self.status()
            if port_is_open():
                return self.status()
            selection = runtime_selection()
            if not selection["model_ready"]:
                raise DesktopError("Adicione ou baixe um modelo GGUF antes de iniciar a IA.")
            if not selection["llama_ready"]:
                raise DesktopError("Localize llama-server.exe antes de iniciar a IA.")
            expose_runtime(selection)
            command = build_llama_command(selection)
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            self._log_handle = LLAMA_LOG_PATH.open("ab")
            kwargs: dict[str, Any] = {}
            if os.name == "nt":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                self._process = subprocess.Popen(
                    command,
                    cwd=str(APP_DIR),
                    stdin=subprocess.DEVNULL,
                    stdout=self._log_handle,
                    stderr=subprocess.STDOUT,
                    shell=False,
                    **kwargs,
                )
            except OSError as exc:
                self._close_log()
                raise DesktopError(f"Não foi possível iniciar o llama.cpp: {exc}") from exc

        deadline = time.monotonic() + max(wait_seconds, 0.5)
        while time.monotonic() < deadline:
            if port_is_open():
                return self.status()
            with self._lock:
                if self._process is not None and self._process.poll() is not None:
                    exit_code = self._process.returncode
                    self._close_log()
                    tail = _log_tail()
                    suffix = f"\n\nÚltimas mensagens:\n{tail}" if tail else ""
                    raise DesktopError(
                        f"O llama.cpp encerrou com o código {exit_code}.{suffix}"
                    )
            time.sleep(0.15)

        self.stop()
        raise DesktopError("A IA não ficou pronta dentro do tempo esperado. Consulte o log.")

    def stop(self) -> dict[str, Any]:
        with self._lock:
            process = self._process
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
            self._process = None
            self._close_log()
        return self.status()

    def _close_log(self) -> None:
        if self._log_handle is not None:
            try:
                self._log_handle.close()
            except OSError:
                pass
            self._log_handle = None


def complete_setup() -> dict[str, Any]:
    return save_config({"setup_completed": True})


def startup_payload() -> dict[str, Any]:
    directories = ensure_runtime_directories()
    config = load_config()
    hardware = hardware_info()
    runtime = runtime_selection()
    return {
        "app": "HERMES Security Portable",
        "version": APP_VERSION,
        "desktop": True,
        "browser_required": False,
        "setup_required": not config.get("setup_completed", False),
        "recommended_profile": recommended_profile_id(hardware),
        "hardware": hardware,
        "runtime": {
            "profile": runtime["profile"]["id"],
            "model_ready": runtime["model_ready"],
            "llama_ready": runtime["llama_ready"],
        },
        "directories": {name: str(path) for name, path in directories.items()},
    }
