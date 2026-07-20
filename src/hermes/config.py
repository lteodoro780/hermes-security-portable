from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
CONFIG_DIR = BASE_DIR / "config"
WEB_DIR = BASE_DIR / "web"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "hermes.db"
RUNTIME_CONFIG = CONFIG_DIR / "runtime.json"

for directory in (DATA_DIR, REPORT_DIR, KNOWLEDGE_DIR, CONFIG_DIR, LOG_DIR):
    directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class PerformanceProfile:
    name: str
    context_size: int
    threads: int
    batch_size: int
    gpu_layers: int
    monitor_interval: int
    history_limit: int


def choose_profile(total_ram_gb: float, cpu_threads: int) -> PerformanceProfile:
    usable_threads = max(2, min(12, max(1, cpu_threads - 2)))
    if total_ram_gb < 12:
        return PerformanceProfile("fast", 3072, min(usable_threads, 6), 128, 0, 20, 2880)
    if total_ram_gb < 24:
        return PerformanceProfile("balanced", 6144, min(usable_threads, 10), 256, 0, 15, 5760)
    return PerformanceProfile("quality", 8192, usable_threads, 384, 0, 10, 8640)


def load_runtime_config() -> dict[str, Any]:
    if not RUNTIME_CONFIG.exists():
        return {}
    try:
        return json.loads(RUNTIME_CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_runtime_config(data: dict[str, Any]) -> None:
    RUNTIME_CONFIG.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def resolve_profile(total_ram_gb: float, cpu_threads: int) -> PerformanceProfile:
    automatic = choose_profile(total_ram_gb, cpu_threads)
    config = load_runtime_config()
    selected = str(config.get("profile", "auto")).lower()
    if selected == "auto" or selected == automatic.name:
        return automatic

    presets = {
        "fast": PerformanceProfile("fast", 3072, min(max(2, cpu_threads - 2), 6), 128, 0, 20, 2880),
        "balanced": PerformanceProfile("balanced", 6144, min(max(2, cpu_threads - 2), 10), 256, 0, 15, 5760),
        "quality": PerformanceProfile("quality", 8192, min(max(2, cpu_threads - 2), 12), 384, 0, 10, 8640),
    }
    return presets.get(selected, automatic)


def profile_payload(profile: PerformanceProfile) -> dict[str, Any]:
    return asdict(profile)


HOST = os.getenv("HERMES_WEB_HOST", "127.0.0.1")
PORT = int(os.getenv("HERMES_WEB_PORT", "8765"))
LLAMA_URL = os.getenv("HERMES_LLAMACPP_URL", "http://127.0.0.1:8080/completion")
