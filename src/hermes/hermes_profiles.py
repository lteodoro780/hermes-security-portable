#!/usr/bin/env python3
"""Perfis locais de IA e detecção de hardware do HERMES."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from .hermes_paths import APP_DIR as BASE_DIR, CONFIG_DIR, MODELS_DIR, TOOLS_DIR
except ImportError:  # Execução direta pelo inicializador no Windows.
    from hermes_paths import APP_DIR as BASE_DIR, CONFIG_DIR, MODELS_DIR, TOOLS_DIR

try:
    import psutil
except ImportError:  # O instalador adiciona psutil, mas há fallback sem ele.
    psutil = None


CONFIG_PATH = CONFIG_DIR / "hermes.json"

ALLOWED_CONTEXT_SIZES = (2048, 4096, 8192)
PROFILE_ORDER = ("fast", "balanced", "quality")

PROFILE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "fast": {
        "label": "Rápido",
        "model": "Qwen3 1.7B Q8_0",
        "model_file": "Qwen3-1.7B-Q8_0.gguf",
        "description": "Menor consumo e respostas mais ágeis.",
        "best_for": "Perguntas simples e suporte rápido",
        "approx_size": "1,83 GB",
        "source_url": "https://huggingface.co/Qwen/Qwen3-1.7B-GGUF",
        "download_url": "https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/main/Qwen3-1.7B-Q8_0.gguf?download=true",
    },
    "balanced": {
        "label": "Balanceado",
        "model": "Qwen3 4B Q4_K_M",
        "model_file": "Qwen3-4B-Q4_K_M.gguf",
        "description": "Equilíbrio entre qualidade, memória e velocidade.",
        "best_for": "Uso diário e diagnóstico técnico",
        "approx_size": "2,50 GB",
        "source_url": "https://huggingface.co/Qwen/Qwen3-4B-GGUF",
        "download_url": "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf?download=true",
    },
    "quality": {
        "label": "Qualidade",
        "model": "Qwen3 8B Q4_K_M",
        "model_file": "Qwen3-8B-Q4_K_M.gguf",
        "description": "Respostas mais elaboradas, com maior uso de recursos.",
        "best_for": "Análises complexas quando houver tempo",
        "approx_size": "5,03 GB",
        "source_url": "https://huggingface.co/Qwen/Qwen3-8B-GGUF",
        "download_url": "https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf?download=true",
    },
}

DEFAULT_CONFIG: dict[str, Any] = {
    "profile": "auto",
    "default_mode": "quick",
    "context_size": 4096,
    "threads": 0,
    "gpu_layers": 0,
}


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def normalize_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    data = {**DEFAULT_CONFIG, **(raw or {})}
    profile = str(data.get("profile", "auto")).lower()
    if profile not in {"auto", *PROFILE_ORDER}:
        profile = "auto"
    mode = str(data.get("default_mode", "quick")).lower()
    if mode not in {"quick", "deep"}:
        mode = "quick"
    context_size = _bounded_int(data.get("context_size"), 4096, 2048, 8192)
    if context_size not in ALLOWED_CONTEXT_SIZES:
        context_size = min(ALLOWED_CONTEXT_SIZES, key=lambda size: abs(size - context_size))
    return {
        "profile": profile,
        "default_mode": mode,
        "context_size": context_size,
        "threads": _bounded_int(data.get("threads"), 0, 0, 128),
        "gpu_layers": _bounded_int(data.get("gpu_layers"), 0, 0, 999),
    }


def load_config() -> dict[str, Any]:
    try:
        raw = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        return normalize_config(raw if isinstance(raw, dict) else {})
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)


def save_config(updates: dict[str, Any]) -> dict[str, Any]:
    current = load_config()
    current.update(updates)
    normalized = normalize_config(current)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    temporary = CONFIG_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(CONFIG_PATH)
    return normalized


def _run_quiet(command: list[str], timeout: int = 5) -> str:
    kwargs: dict[str, Any] = {}
    if platform.system() == "Windows":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            encoding="utf-8",
            errors="replace",
            **kwargs,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


@lru_cache(maxsize=1)
def _cpu_name() -> str:
    if platform.system() == "Windows":
        value = _run_quiet(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)",
            ]
        )
        if value:
            return value.splitlines()[0].strip()
    if platform.system() == "Linux":
        try:
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines():
                if line.lower().startswith("model name") and ":" in line:
                    return line.split(":", 1)[1].strip()
        except OSError:
            pass
    return platform.processor() or platform.machine() or "Processador não identificado"


@lru_cache(maxsize=1)
def _graphics_name() -> str:
    if platform.system() != "Windows":
        return "Detecção detalhada disponível no Windows"
    value = _run_quiet(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
        ]
    )
    names = [line.strip() for line in value.splitlines() if line.strip()]
    return " • ".join(names) if names else "Vídeo não identificado"


def _total_memory_bytes() -> int:
    if psutil is not None:
        return int(psutil.virtual_memory().total)
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, TypeError, ValueError):
        return 0


@lru_cache(maxsize=1)
def hardware_info() -> dict[str, Any]:
    logical = (psutil.cpu_count(logical=True) if psutil else os.cpu_count()) or 1
    physical = psutil.cpu_count(logical=False) if psutil else None
    if not physical:
        physical = max(1, logical // 2)
    total_bytes = _total_memory_bytes()
    total_gb = round(total_bytes / (1024**3), 1) if total_bytes else 0.0
    return {
        "cpu_name": _cpu_name(),
        "physical_cores": int(physical),
        "logical_cores": int(logical),
        "recommended_threads": max(1, min(int(physical), 16)),
        "memory_total_bytes": total_bytes,
        "memory_total_gb": total_gb,
        "graphics_name": _graphics_name(),
        "system": platform.system(),
        "architecture": platform.machine(),
    }


def recommended_profile_id(hardware: dict[str, Any] | None = None) -> str:
    total_gb = float((hardware or hardware_info()).get("memory_total_gb") or 0)
    if total_gb and total_gb < 11.5:
        return "fast"
    if total_gb and total_gb >= 23.5:
        return "quality"
    return "balanced"


def recommendation_reason(profile_id: str, hardware: dict[str, Any]) -> str:
    memory = hardware.get("memory_total_gb") or "—"
    if profile_id == "fast":
        return f"Perfil leve selecionado para preservar a memória disponível ({memory} GB)."
    if profile_id == "quality":
        return f"A memória detectada ({memory} GB) permite priorizar qualidade."
    return f"Melhor equilíbrio para os {memory} GB de memória detectados."


def is_valid_gguf(path: Path) -> bool:
    try:
        if not path.is_file() or path.stat().st_size < 4:
            return False
        with path.open("rb") as handle:
            return handle.read(4) == b"GGUF"
    except OSError:
        return False


def profile_catalog() -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for profile_id in PROFILE_ORDER:
        definition = PROFILE_DEFINITIONS[profile_id]
        model_path = MODELS_DIR / definition["model_file"]
        catalog.append(
            {
                "id": profile_id,
                **definition,
                "installed": is_valid_gguf(model_path),
                "model_path": str(model_path),
            }
        )
    return catalog


def _profile_with_state(profile_id: str) -> dict[str, Any]:
    definition = PROFILE_DEFINITIONS[profile_id]
    model_path = MODELS_DIR / definition["model_file"]
    return {
        "id": profile_id,
        **definition,
        "installed": is_valid_gguf(model_path),
        "model_path": str(model_path),
    }


def resolve_profile(
    config: dict[str, Any] | None = None,
    hardware: dict[str, Any] | None = None,
) -> dict[str, Any]:
    settings = normalize_config(config or load_config())
    detected = hardware or hardware_info()
    recommended = recommended_profile_id(detected)
    wanted = recommended if settings["profile"] == "auto" else settings["profile"]

    candidates = [wanted, "balanced", "fast", "quality"]
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        profile = _profile_with_state(candidate)
        if profile["installed"]:
            profile["fallback"] = candidate != wanted
            profile["requested_profile"] = settings["profile"]
            return profile

    legacy_model = MODELS_DIR / "model.gguf"
    if is_valid_gguf(legacy_model):
        return {
            "id": "custom",
            "label": "Personalizado",
            "model": "Modelo GGUF legado",
            "model_file": legacy_model.name,
            "model_path": str(legacy_model),
            "description": "Modelo personalizado encontrado na pasta portátil.",
            "best_for": "Compatibilidade com versões anteriores",
            "approx_size": "—",
            "source_url": "",
            "download_url": "",
            "installed": True,
            "fallback": True,
            "requested_profile": settings["profile"],
        }

    profile = _profile_with_state(wanted)
    profile["fallback"] = False
    profile["requested_profile"] = settings["profile"]
    return profile


def find_llama_command() -> dict[str, str] | None:
    portable_candidates = (
        TOOLS_DIR / "llama.cpp" / "llama-server.exe",
        TOOLS_DIR / "llama.cpp" / "llama-server",
    )
    for candidate in portable_candidates:
        if candidate.is_file():
            return {"executable": str(candidate), "style": "server", "source": "portable"}

    server = shutil.which("llama-server") or shutil.which("llama-server.exe")
    if server:
        return {"executable": server, "style": "server", "source": "PATH"}
    unified = shutil.which("llama") or shutil.which("llama.exe")
    if unified:
        return {"executable": unified, "style": "unified", "source": "PATH"}
    return None


def runtime_selection() -> dict[str, Any]:
    settings = load_config()
    hardware = hardware_info()
    recommended = recommended_profile_id(hardware)
    profile = resolve_profile(settings, hardware)
    llama = find_llama_command()
    threads = settings["threads"] or hardware["recommended_threads"]
    return {
        "config": settings,
        "hardware": hardware,
        "recommended_profile": recommended,
        "recommendation_reason": recommendation_reason(recommended, hardware),
        "profile": profile,
        "threads": threads,
        "context_size": settings["context_size"],
        "gpu_layers": settings["gpu_layers"],
        "llama": llama,
        "model_ready": bool(profile.get("installed")),
        "llama_ready": llama is not None,
    }


def configuration_payload() -> dict[str, Any]:
    runtime = runtime_selection()
    active_profile = os.getenv("HERMES_ACTIVE_PROFILE") or runtime["profile"]["id"]
    active_model = os.getenv("HERMES_ACTIVE_MODEL") or runtime["profile"]["model_file"]
    active_threads = _bounded_int(
        os.getenv("HERMES_ACTIVE_THREADS"), runtime["threads"], 1, 128
    )
    active_context = _bounded_int(
        os.getenv("HERMES_ACTIVE_CONTEXT"), runtime["context_size"], 2048, 8192
    )
    active_gpu_layers = _bounded_int(
        os.getenv("HERMES_ACTIVE_GPU_LAYERS"), runtime["gpu_layers"], 0, 999
    )
    return {
        "config": runtime["config"],
        "hardware": runtime["hardware"],
        "profiles": profile_catalog(),
        "recommended_profile": runtime["recommended_profile"],
        "recommendation_reason": runtime["recommendation_reason"],
        "effective_profile": runtime["profile"]["id"],
        "runtime": {
            "active_profile": active_profile,
            "active_model": active_model,
            "threads": active_threads,
            "context_size": active_context,
            "gpu_layers": active_gpu_layers,
            "model_ready": runtime["model_ready"],
            "llama_ready": runtime["llama_ready"],
            "llama_source": runtime["llama"]["source"] if runtime["llama"] else None,
        },
    }


def _print_summary() -> None:
    data = configuration_payload()
    hardware = data["hardware"]
    profile_id = data["recommended_profile"]
    profile = PROFILE_DEFINITIONS[profile_id]
    print("HERMES - análise do hardware")
    print(f"CPU: {hardware['cpu_name']}")
    print(
        f"Núcleos: {hardware['physical_cores']} físicos / "
        f"{hardware['logical_cores']} threads"
    )
    print(f"Memória: {hardware['memory_total_gb']} GB")
    print(f"Recomendação: {profile['label']} ({profile['model']})")
    print(data["recommendation_reason"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Perfis de IA do HERMES")
    parser.add_argument("--summary", action="store_true", help="mostra a recomendação")
    parser.add_argument("--json", action="store_true", help="mostra a configuração em JSON")
    parser.add_argument("--set-profile", choices=("auto", *PROFILE_ORDER))
    args = parser.parse_args()
    if args.set_profile:
        saved = save_config({"profile": args.set_profile})
        print(f"Perfil salvo: {saved['profile']}")
        return
    if args.json:
        print(json.dumps(configuration_payload(), ensure_ascii=False, indent=2))
        return
    _print_summary()


if __name__ == "__main__":
    main()
