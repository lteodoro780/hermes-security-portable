#!/usr/bin/env python3
"""Histórico local e limitado de conversas do HERMES."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .hermes_paths import APP_DIR as BASE_DIR, DATA_DIR
except ImportError:
    from hermes_paths import APP_DIR as BASE_DIR, DATA_DIR

CHAT_HISTORY_PATH = DATA_DIR / "chat-history.json"
MAX_HISTORY_MESSAGES = 200
MAX_MESSAGE_CHARS = 12_000
_HISTORY_LOCK = threading.RLock()


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _clean_message(entry: Any) -> dict[str, str] | None:
    if not isinstance(entry, dict):
        return None
    role = str(entry.get("role", "")).lower()
    if role not in {"user", "assistant"}:
        return None
    content = str(entry.get("content", "")).strip()[:MAX_MESSAGE_CHARS]
    if not content:
        return None
    mode = str(entry.get("mode", "quick")).lower()
    if mode not in {"quick", "deep"}:
        mode = "quick"
    return {
        "id": str(entry.get("id") or uuid.uuid4().hex),
        "role": role,
        "content": content,
        "mode": mode,
        "created_at": str(entry.get("created_at") or now()),
    }


def _read_unlocked() -> list[dict[str, str]]:
    try:
        payload = json.loads(CHAT_HISTORY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw_messages = payload.get("messages", []) if isinstance(payload, dict) else []
    messages = [clean for item in raw_messages if (clean := _clean_message(item))]
    return messages[-MAX_HISTORY_MESSAGES:]


def _write_unlocked(messages: list[dict[str, str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "updated_at": now(),
        "messages": messages[-MAX_HISTORY_MESSAGES:],
    }
    temporary = CHAT_HISTORY_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(CHAT_HISTORY_PATH)


def load_chat_history(limit: int = MAX_HISTORY_MESSAGES) -> list[dict[str, str]]:
    safe_limit = min(max(int(limit), 1), MAX_HISTORY_MESSAGES)
    with _HISTORY_LOCK:
        return _read_unlocked()[-safe_limit:]


def append_chat_exchange(user_text: str, assistant_text: str, mode: str) -> list[dict[str, str]]:
    safe_mode = mode if mode in {"quick", "deep"} else "quick"
    created_at = now()
    exchange = [
        {
            "id": uuid.uuid4().hex,
            "role": "user",
            "content": user_text.strip()[:MAX_MESSAGE_CHARS],
            "mode": safe_mode,
            "created_at": created_at,
        },
        {
            "id": uuid.uuid4().hex,
            "role": "assistant",
            "content": assistant_text.strip()[:MAX_MESSAGE_CHARS],
            "mode": safe_mode,
            "created_at": now(),
        },
    ]
    with _HISTORY_LOCK:
        messages = _read_unlocked()
        messages.extend(exchange)
        messages = [clean for item in messages if (clean := _clean_message(item))]
        _write_unlocked(messages)
    return exchange


def clear_chat_history() -> None:
    with _HISTORY_LOCK:
        _write_unlocked([])
