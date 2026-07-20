from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from .config import DB_PATH

_SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  cpu REAL NOT NULL,
  memory REAL NOT NULL,
  disk REAL NOT NULL,
  net_sent INTEGER NOT NULL,
  net_recv INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_metrics_created_at ON metrics(created_at);
CREATE TABLE IF NOT EXISTS alerts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  kind TEXT NOT NULL,
  severity TEXT NOT NULL,
  value REAL NOT NULL,
  message TEXT NOT NULL,
  acknowledged INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_alerts_created_at ON alerts(created_at);
CREATE TABLE IF NOT EXISTS documents (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  path TEXT NOT NULL UNIQUE,
  collection TEXT NOT NULL,
  title TEXT NOT NULL,
  modified_at REAL NOT NULL,
  indexed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  document_id INTEGER NOT NULL,
  chunk_index INTEGER NOT NULL,
  page INTEGER,
  content TEXT NOT NULL,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id);
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
"""


class HermesDB:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=20, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _init(self) -> None:
        with self.connect() as connection:
            connection.executescript(_SCHEMA)

    def insert_metric(self, metric: dict[str, Any], history_limit: int) -> None:
        with self._lock, self.connect() as connection:
            connection.execute(
                "INSERT INTO metrics(created_at,cpu,memory,disk,net_sent,net_recv) VALUES(?,?,?,?,?,?)",
                (metric["created_at"], metric["cpu"], metric["memory"], metric["disk"], metric["net_sent"], metric["net_recv"]),
            )
            connection.execute(
                "DELETE FROM metrics WHERE id NOT IN (SELECT id FROM metrics ORDER BY id DESC LIMIT ?)",
                (history_limit,),
            )

    def metric_history(self, minutes: int = 60, limit: int = 720) -> list[dict[str, Any]]:
        since = (datetime.now() - timedelta(minutes=max(1, minutes))).isoformat(timespec="seconds")
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT created_at,cpu,memory,disk,net_sent,net_recv FROM metrics WHERE created_at >= ? ORDER BY id DESC LIMIT ?",
                (since, max(1, min(limit, 5000))),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def add_alert(self, kind: str, severity: str, value: float, message: str) -> None:
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO alerts(created_at,kind,severity,value,message) VALUES(?,?,?,?,?)",
                (datetime.now().isoformat(timespec="seconds"), kind, severity, value, message),
            )

    def recent_alerts(self, limit: int = 30) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT id,created_at,kind,severity,value,message,acknowledged FROM alerts ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [dict(row) for row in rows]

    def last_alert_time(self, kind: str) -> datetime | None:
        with self.connect() as connection:
            row = connection.execute("SELECT created_at FROM alerts WHERE kind=? ORDER BY id DESC LIMIT 1", (kind,)).fetchone()
        return datetime.fromisoformat(row["created_at"]) if row else None

    def replace_document(self, path: str, collection: str, title: str, modified_at: float, chunks: Iterable[tuple[int | None, str]]) -> int:
        with self._lock, self.connect() as connection:
            existing = connection.execute("SELECT id FROM documents WHERE path=?", (path,)).fetchone()
            if existing:
                document_id = int(existing["id"])
                connection.execute("DELETE FROM chunks WHERE document_id=?", (document_id,))
                connection.execute(
                    "UPDATE documents SET collection=?,title=?,modified_at=?,indexed_at=? WHERE id=?",
                    (collection, title, modified_at, datetime.now().isoformat(timespec="seconds"), document_id),
                )
            else:
                cursor = connection.execute(
                    "INSERT INTO documents(path,collection,title,modified_at,indexed_at) VALUES(?,?,?,?,?)",
                    (path, collection, title, modified_at, datetime.now().isoformat(timespec="seconds")),
                )
                document_id = int(cursor.lastrowid)
            connection.executemany(
                "INSERT INTO chunks(document_id,chunk_index,page,content) VALUES(?,?,?,?)",
                ((document_id, index, page, content) for index, (page, content) in enumerate(chunks)),
            )
            return document_id

    def indexed_documents(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT d.id,d.path,d.collection,d.title,d.modified_at,d.indexed_at,COUNT(c.id) chunks FROM documents d LEFT JOIN chunks c ON c.document_id=d.id GROUP BY d.id ORDER BY d.title"
            ).fetchall()
        return [dict(row) for row in rows]

    def all_chunks(self, collection: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT c.id,c.page,c.content,d.path,d.title,d.collection FROM chunks c JOIN documents d ON d.id=c.document_id"
        params: tuple[Any, ...] = ()
        if collection:
            query += " WHERE d.collection=?"
            params = (collection,)
        with self.connect() as connection:
            rows = connection.execute(query, params).fetchall()
        return [dict(row) for row in rows]

    def get_setting(self, key: str, default: Any = None) -> Any:
        with self.connect() as connection:
            row = connection.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        try:
            return json.loads(row["value"])
        except json.JSONDecodeError:
            return row["value"]

    def set_setting(self, key: str, value: Any) -> None:
        serialized = json.dumps(value, ensure_ascii=False)
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, serialized),
            )
