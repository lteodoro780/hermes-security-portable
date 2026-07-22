#!/usr/bin/env python3
"""Gerenciador seguro de downloads dos modelos oficiais configurados."""

from __future__ import annotations

import copy
import re
import threading
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .hermes_profiles import (
        MODELS_DIR,
        PROFILE_DEFINITIONS,
        PROFILE_ORDER,
        is_valid_gguf,
        profile_catalog,
        save_config,
    )
except ImportError:
    from hermes_profiles import (
        MODELS_DIR,
        PROFILE_DEFINITIONS,
        PROFILE_ORDER,
        is_valid_gguf,
        profile_catalog,
        save_config,
    )


CHUNK_SIZE = 1024 * 1024
_JOB_LOCK = threading.RLock()
_CANCEL_EVENT = threading.Event()
_JOB: dict[str, Any] = {
    "status": "idle",
    "profile": None,
    "filename": None,
    "downloaded_bytes": 0,
    "total_bytes": 0,
    "percent": None,
    "message": "Nenhum download em andamento.",
    "started_at": None,
    "completed_at": None,
}


class DownloadCancelled(Exception):
    pass


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def valid_gguf(path: Path) -> bool:
    return is_valid_gguf(path)


def _update_job(**updates: Any) -> None:
    with _JOB_LOCK:
        _JOB.update(updates)
        total = int(_JOB.get("total_bytes") or 0)
        downloaded = int(_JOB.get("downloaded_bytes") or 0)
        _JOB["percent"] = round(min(downloaded / total * 100, 100), 1) if total else None


def download_snapshot() -> dict[str, Any]:
    with _JOB_LOCK:
        return copy.deepcopy(_JOB)


def model_manager_payload() -> dict[str, Any]:
    profiles = profile_catalog()
    for profile in profiles:
        profile["installed"] = valid_gguf(Path(profile["model_path"]))
        part_path = Path(profile["model_path"] + ".part")
        profile["partial_bytes"] = part_path.stat().st_size if part_path.is_file() else 0
    return {"profiles": profiles, "download": download_snapshot()}


def _total_from_headers(response: Any, existing: int) -> int:
    content_range = response.headers.get("Content-Range", "")
    match = re.search(r"/(\d+)$", content_range)
    if match:
        return int(match.group(1))
    length = int(response.headers.get("Content-Length", "0") or 0)
    status = getattr(response, "status", None)
    if status is None:
        status = response.getcode()
    return existing + length if status == 206 else length


def _finalize_partial(partial: Path, target: Path, profile_id: str) -> None:
    if not valid_gguf(partial):
        raise ValueError("O arquivo recebido não possui um cabeçalho GGUF válido.")
    partial.replace(target)
    save_config({"profile": profile_id})


def _download_worker(profile_id: str) -> None:
    definition = PROFILE_DEFINITIONS[profile_id]
    target = MODELS_DIR / definition["model_file"]
    partial = Path(str(target) + ".part")
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    existing = partial.stat().st_size if partial.is_file() else 0
    headers = {"User-Agent": "HERMES-Security-Portable/0.9.0"}
    if existing:
        headers["Range"] = f"bytes={existing}-"
    request = urllib.request.Request(definition["download_url"], headers=headers)

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status = getattr(response, "status", None)
            if status is None:
                status = response.getcode()
            if existing and status != 206:
                existing = 0
            total = _total_from_headers(response, existing)
            mode = "ab" if existing and status == 206 else "wb"
            downloaded = existing
            _update_job(
                status="downloading",
                downloaded_bytes=downloaded,
                total_bytes=total,
                message=f"Baixando {definition['model']}…",
            )
            with partial.open(mode) as output:
                while True:
                    if _CANCEL_EVENT.is_set():
                        raise DownloadCancelled()
                    chunk = response.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    output.write(chunk)
                    downloaded += len(chunk)
                    _update_job(downloaded_bytes=downloaded)
            if total and downloaded < total:
                raise OSError(
                    f"Transferência incompleta: {downloaded} de {total} bytes recebidos."
                )
        _finalize_partial(partial, target, profile_id)
        final_size = target.stat().st_size
        _update_job(
            status="completed",
            downloaded_bytes=final_size,
            total_bytes=final_size,
            message=f"{definition['model']} instalado. Reinicie o HERMES para ativá-lo.",
            completed_at=now(),
        )
    except DownloadCancelled:
        _update_job(
            status="cancelled",
            message="Download pausado. O progresso foi mantido para continuar depois.",
            completed_at=now(),
        )
    except urllib.error.HTTPError as exc:
        if exc.code == 416 and partial.is_file() and valid_gguf(partial):
            try:
                _finalize_partial(partial, target, profile_id)
                final_size = target.stat().st_size
                _update_job(
                    status="completed",
                    downloaded_bytes=final_size,
                    total_bytes=final_size,
                    message=f"{definition['model']} instalado. Reinicie o HERMES para ativá-lo.",
                    completed_at=now(),
                )
                return
            except (OSError, ValueError) as finalize_error:
                exc = finalize_error  # type: ignore[assignment]
        _update_job(status="error", message=f"Falha no download: {exc}", completed_at=now())
    except (OSError, ValueError, urllib.error.URLError) as exc:
        _update_job(status="error", message=f"Falha no download: {exc}", completed_at=now())
    except Exception as exc:  # Mantém o gerenciador recuperável após falhas de transporte.
        _update_job(status="error", message=f"Falha inesperada no download: {exc}", completed_at=now())


def start_model_download(profile_id: str) -> dict[str, Any]:
    if profile_id not in PROFILE_ORDER:
        raise ValueError("Perfil de modelo inválido.")
    with _JOB_LOCK:
        if _JOB.get("status") in {"starting", "downloading", "cancelling"}:
            raise RuntimeError("Já existe um download de modelo em andamento.")
        definition = PROFILE_DEFINITIONS[profile_id]
        target = MODELS_DIR / definition["model_file"]
        if valid_gguf(target):
            save_config({"profile": profile_id})
            _JOB.update(
                {
                    "status": "completed",
                    "profile": profile_id,
                    "filename": target.name,
                    "downloaded_bytes": target.stat().st_size,
                    "total_bytes": target.stat().st_size,
                    "percent": 100.0,
                    "message": "O modelo já está instalado e foi selecionado.",
                    "started_at": now(),
                    "completed_at": now(),
                }
            )
            return copy.deepcopy(_JOB)
        if target.exists():
            raise ValueError(
                f"O arquivo {target.name} existe, mas não parece ser GGUF. "
                "Mova-o para outro local antes de baixar novamente."
            )
        _CANCEL_EVENT.clear()
        _JOB.update(
            {
                "status": "starting",
                "profile": profile_id,
                "filename": target.name,
                "downloaded_bytes": 0,
                "total_bytes": 0,
                "percent": None,
                "message": "Preparando download seguro…",
                "started_at": now(),
                "completed_at": None,
            }
        )
    thread = threading.Thread(
        target=_download_worker,
        args=(profile_id,),
        daemon=True,
        name=f"hermes-model-{profile_id}",
    )
    thread.start()
    return download_snapshot()


def cancel_model_download() -> dict[str, Any]:
    with _JOB_LOCK:
        if _JOB.get("status") not in {"starting", "downloading"}:
            raise RuntimeError("Não há download ativo para pausar.")
        _CANCEL_EVENT.set()
        _JOB["status"] = "cancelling"
        _JOB["message"] = "Pausando o download…"
    return download_snapshot()
