#!/usr/bin/env python3
"""Monitoramento contínuo, local e limitado do HERMES.

O módulo coleta somente percentuais de CPU, memória e disco, além das taxas
agregadas de rede do host. O histórico permanece em SQLite dentro da pasta
``data`` e nenhum alerta executa comandos ou altera o computador.
"""

from __future__ import annotations

import math
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

try:
    from .hermes_paths import APP_DIR as BASE_DIR, DATA_DIR
except ImportError:
    from hermes_paths import APP_DIR as BASE_DIR, DATA_DIR

try:
    import psutil
except ImportError:  # O restante do HERMES continua disponível sem telemetria.
    psutil = None


DB_PATH = DATA_DIR / "hermes-monitor.db"

ALLOWED_INTERVALS = {5, 10, 15, 30, 60, 120, 300}
MIN_RETENTION_HOURS = 24
MAX_RETENTION_HOURS = 720
MAX_SAMPLES = 50_000
MAX_ALERTS = 2_000

DEFAULT_CONFIG: dict[str, Any] = {
    "enabled": False,
    "interval_seconds": 15,
    "consecutive_samples": 3,
    "retention_hours": 168,
    "cpu_warning": 80.0,
    "cpu_critical": 92.0,
    "memory_warning": 82.0,
    "memory_critical": 92.0,
    "disk_warning": 85.0,
    "disk_critical": 95.0,
}

RESOURCE_FIELDS = {
    "cpu": ("cpu_percent", "CPU"),
    "memory": ("memory_percent", "Memória"),
    "disk": ("disk_percent", "Disco"),
}

_DB_LOCK = threading.RLock()
_INITIALISED_PATHS: set[str] = set()


class MonitorError(ValueError):
    """Erro seguro de configuração ou coleta apresentado pela API local."""


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _timestamp(value: datetime | str | None = None) -> tuple[str, float]:
    if value is None:
        instant = datetime.now().astimezone()
    elif isinstance(value, datetime):
        instant = value.astimezone() if value.tzinfo else value.astimezone()
    else:
        try:
            instant = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise MonitorError("Data de coleta inválida.") from exc
        if instant.tzinfo is None:
            instant = instant.astimezone()
    return instant.isoformat(timespec="seconds"), instant.timestamp()


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 15000")
    return connection


def _ensure_database() -> None:
    path_key = str(DB_PATH.resolve())
    if path_key in _INITIALISED_PATHS and DB_PATH.exists():
        return
    with _DB_LOCK:
        if path_key in _INITIALISED_PATHS and DB_PATH.exists():
            return
        with _connect() as connection:
            try:
                connection.execute("PRAGMA journal_mode = WAL")
            except sqlite3.OperationalError:
                pass
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS monitor_config (
                    id INTEGER PRIMARY KEY CHECK(id = 1),
                    enabled INTEGER NOT NULL,
                    interval_seconds INTEGER NOT NULL,
                    consecutive_samples INTEGER NOT NULL,
                    retention_hours INTEGER NOT NULL,
                    cpu_warning REAL NOT NULL,
                    cpu_critical REAL NOT NULL,
                    memory_warning REAL NOT NULL,
                    memory_critical REAL NOT NULL,
                    disk_warning REAL NOT NULL,
                    disk_critical REAL NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS monitor_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    recorded_at TEXT NOT NULL,
                    recorded_ts REAL NOT NULL,
                    cpu_percent REAL NOT NULL,
                    memory_percent REAL NOT NULL,
                    disk_percent REAL NOT NULL,
                    network_sent_bps REAL NOT NULL,
                    network_received_bps REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_monitor_samples_time
                    ON monitor_samples(recorded_ts DESC);
                CREATE TABLE IF NOT EXISTS monitor_alerts (
                    id TEXT PRIMARY KEY,
                    resource TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    first_value REAL NOT NULL,
                    last_value REAL NOT NULL,
                    peak_value REAL NOT NULL,
                    occurrences INTEGER NOT NULL DEFAULT 1,
                    detected_at TEXT NOT NULL,
                    detected_ts REAL NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    resolved_at TEXT,
                    acknowledged_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_monitor_alerts_status
                    ON monitor_alerts(status, detected_ts DESC);
                CREATE INDEX IF NOT EXISTS idx_monitor_alerts_resource
                    ON monitor_alerts(resource, status);
                CREATE TABLE IF NOT EXISTS monitor_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )
            defaults = DEFAULT_CONFIG
            connection.execute(
                """
                INSERT OR IGNORE INTO monitor_config (
                    id, enabled, interval_seconds, consecutive_samples,
                    retention_hours, cpu_warning, cpu_critical,
                    memory_warning, memory_critical, disk_warning,
                    disk_critical, updated_at
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(defaults["enabled"]),
                    defaults["interval_seconds"],
                    defaults["consecutive_samples"],
                    defaults["retention_hours"],
                    defaults["cpu_warning"],
                    defaults["cpu_critical"],
                    defaults["memory_warning"],
                    defaults["memory_critical"],
                    defaults["disk_warning"],
                    defaults["disk_critical"],
                    now(),
                ),
            )
            connection.execute(
                "INSERT OR REPLACE INTO monitor_meta(key, value) VALUES('schema_version', '1')"
            )
        _INITIALISED_PATHS.add(path_key)


def _config_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "enabled": bool(row["enabled"]),
        "interval_seconds": int(row["interval_seconds"]),
        "consecutive_samples": int(row["consecutive_samples"]),
        "retention_hours": int(row["retention_hours"]),
        "cpu_warning": float(row["cpu_warning"]),
        "cpu_critical": float(row["cpu_critical"]),
        "memory_warning": float(row["memory_warning"]),
        "memory_critical": float(row["memory_critical"]),
        "disk_warning": float(row["disk_warning"]),
        "disk_critical": float(row["disk_critical"]),
        "updated_at": row["updated_at"],
    }


def load_monitor_config() -> dict[str, Any]:
    _ensure_database()
    with _connect() as connection:
        row = connection.execute("SELECT * FROM monitor_config WHERE id = 1").fetchone()
    if row is None:  # Proteção para um banco removido durante a execução.
        raise MonitorError("Configuração do monitor não encontrada.")
    return _config_from_row(row)


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool):
        raise MonitorError(f"{label} inválido.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise MonitorError(f"{label} inválido.") from exc
    if not math.isfinite(number):
        raise MonitorError(f"{label} inválido.")
    return number


def _validated_config(candidate: dict[str, Any]) -> dict[str, Any]:
    try:
        interval = int(candidate["interval_seconds"])
        consecutive = int(candidate["consecutive_samples"])
        retention = int(candidate["retention_hours"])
    except (TypeError, ValueError) as exc:
        raise MonitorError("Intervalo, confirmação ou retenção inválidos.") from exc
    if interval not in ALLOWED_INTERVALS:
        raise MonitorError("Intervalo permitido: 5, 10, 15, 30, 60, 120 ou 300 segundos.")
    if not 2 <= consecutive <= 10:
        raise MonitorError("A confirmação deve usar entre 2 e 10 coletas consecutivas.")
    if not MIN_RETENTION_HOURS <= retention <= MAX_RETENTION_HOURS:
        raise MonitorError("A retenção deve ficar entre 24 e 720 horas.")

    validated = {
        "enabled": bool(candidate.get("enabled", False)),
        "interval_seconds": interval,
        "consecutive_samples": consecutive,
        "retention_hours": retention,
    }
    for resource in RESOURCE_FIELDS:
        warning = _number(candidate[f"{resource}_warning"], f"Limite de atenção de {resource}")
        critical = _number(candidate[f"{resource}_critical"], f"Limite crítico de {resource}")
        if not 50 <= warning <= 98:
            raise MonitorError("Limites de atenção devem ficar entre 50% e 98%.")
        if not 55 <= critical <= 100:
            raise MonitorError("Limites críticos devem ficar entre 55% e 100%.")
        if warning >= critical:
            raise MonitorError("Cada limite crítico deve ser maior que o limite de atenção.")
        validated[f"{resource}_warning"] = round(warning, 1)
        validated[f"{resource}_critical"] = round(critical, 1)
    return validated


def save_monitor_config(updates: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "interval_seconds",
        "consecutive_samples",
        "retention_hours",
        "cpu_warning",
        "cpu_critical",
        "memory_warning",
        "memory_critical",
        "disk_warning",
        "disk_critical",
    }
    safe_updates = {key: updates[key] for key in allowed if key in updates}
    if not safe_updates:
        raise MonitorError("Nenhuma configuração de monitoramento recebida.")
    current = load_monitor_config()
    candidate = {**current, **safe_updates}
    saved = _validated_config(candidate)
    timestamp = now()
    with _DB_LOCK, _connect() as connection:
        connection.execute(
            """
            UPDATE monitor_config SET
                interval_seconds = ?, consecutive_samples = ?, retention_hours = ?,
                cpu_warning = ?, cpu_critical = ?, memory_warning = ?,
                memory_critical = ?, disk_warning = ?, disk_critical = ?, updated_at = ?
            WHERE id = 1
            """,
            (
                saved["interval_seconds"],
                saved["consecutive_samples"],
                saved["retention_hours"],
                saved["cpu_warning"],
                saved["cpu_critical"],
                saved["memory_warning"],
                saved["memory_critical"],
                saved["disk_warning"],
                saved["disk_critical"],
                timestamp,
            ),
        )
    return load_monitor_config()


def set_monitor_enabled(enabled: bool) -> dict[str, Any]:
    _ensure_database()
    timestamp = now()
    with _DB_LOCK, _connect() as connection:
        connection.execute(
            "UPDATE monitor_config SET enabled = ?, updated_at = ? WHERE id = 1",
            (int(bool(enabled)), timestamp),
        )
    return load_monitor_config()


def _percentage(value: Any, label: str) -> float:
    number = _number(value, label)
    if not 0 <= number <= 100:
        raise MonitorError(f"{label} deve ficar entre 0% e 100%.")
    return round(number, 1)


def _rate(value: Any) -> float:
    number = _number(value or 0, "Taxa de rede")
    return round(max(number, 0.0), 2)


def _normalise_metrics(metrics: dict[str, Any]) -> dict[str, float]:
    if not isinstance(metrics, dict) or metrics.get("available") is False:
        reason = str(metrics.get("reason", "Telemetria indisponível.")) if isinstance(metrics, dict) else "Telemetria inválida."
        raise MonitorError(reason)
    cpu = metrics.get("cpu") if isinstance(metrics.get("cpu"), dict) else {}
    memory = metrics.get("memory") if isinstance(metrics.get("memory"), dict) else {}
    disk = metrics.get("disk") if isinstance(metrics.get("disk"), dict) else {}
    network = metrics.get("network") if isinstance(metrics.get("network"), dict) else {}
    return {
        "cpu_percent": _percentage(metrics.get("cpu_percent", cpu.get("percent")), "CPU"),
        "memory_percent": _percentage(
            metrics.get("memory_percent", memory.get("percent")), "Memória"
        ),
        "disk_percent": _percentage(metrics.get("disk_percent", disk.get("percent")), "Disco"),
        "network_sent_bps": _rate(
            metrics.get("network_sent_bps", network.get("sent_bytes_per_second", 0))
        ),
        "network_received_bps": _rate(
            metrics.get("network_received_bps", network.get("received_bytes_per_second", 0))
        ),
    }


def _sample_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "recorded_at": row["recorded_at"],
        "cpu_percent": float(row["cpu_percent"]),
        "memory_percent": float(row["memory_percent"]),
        "disk_percent": float(row["disk_percent"]),
        "network_sent_bps": float(row["network_sent_bps"]),
        "network_received_bps": float(row["network_received_bps"]),
    }


def _alert_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "resource": row["resource"],
        "severity": row["severity"],
        "status": row["status"],
        "title": row["title"],
        "message": row["message"],
        "threshold": float(row["threshold"]),
        "first_value": float(row["first_value"]),
        "last_value": float(row["last_value"]),
        "peak_value": float(row["peak_value"]),
        "occurrences": int(row["occurrences"]),
        "detected_at": row["detected_at"],
        "last_seen_at": row["last_seen_at"],
        "resolved_at": row["resolved_at"],
        "acknowledged_at": row["acknowledged_at"],
        "acknowledged": bool(row["acknowledged_at"]),
    }


def _recent_values(
    connection: sqlite3.Connection,
    field: str,
    count: int,
) -> list[float]:
    if field not in {item[0] for item in RESOURCE_FIELDS.values()}:
        raise MonitorError("Campo de monitoramento inválido.")
    rows = connection.execute(
        f"SELECT {field} AS value FROM monitor_samples ORDER BY id DESC LIMIT ?",
        (count,),
    ).fetchall()
    return [float(row["value"]) for row in rows]


def _evaluate_alerts(
    connection: sqlite3.Connection,
    config: dict[str, Any],
    recorded_at: str,
    recorded_ts: float,
) -> None:
    required = int(config["consecutive_samples"])
    severity_labels = {"attention": "Atenção", "critical": "Crítico"}
    for resource, (field, label) in RESOURCE_FIELDS.items():
        values = _recent_values(connection, field, required)
        if len(values) < required:
            continue
        warning = float(config[f"{resource}_warning"])
        critical = float(config[f"{resource}_critical"])
        desired: str | None
        threshold: float
        if all(value >= critical for value in values):
            desired, threshold = "critical", critical
        elif all(value >= warning for value in values):
            desired, threshold = "attention", warning
        elif all(value < warning for value in values):
            desired, threshold = "normal", warning
        else:
            desired = None
            threshold = warning
        if desired is None:
            continue

        active = connection.execute(
            """
            SELECT * FROM monitor_alerts
            WHERE resource = ? AND status = 'active'
            ORDER BY detected_ts DESC LIMIT 1
            """,
            (resource,),
        ).fetchone()
        last_value = values[0]
        if active is not None and active["severity"] == desired:
            connection.execute(
                """
                UPDATE monitor_alerts SET
                    last_value = ?, peak_value = MAX(peak_value, ?),
                    occurrences = occurrences + 1, last_seen_at = ?
                WHERE id = ?
                """,
                (last_value, last_value, recorded_at, active["id"]),
            )
            continue
        if active is not None:
            connection.execute(
                """
                UPDATE monitor_alerts
                SET status = 'resolved', resolved_at = ?, last_seen_at = ?, last_value = ?
                WHERE id = ?
                """,
                (recorded_at, recorded_at, last_value, active["id"]),
            )
        if desired == "normal":
            continue

        title = f"{label} em nível {severity_labels[desired].lower()}"
        message = (
            f"{label} permaneceu em ou acima de {threshold:.0f}% por "
            f"{required} coletas consecutivas. Valor atual: {last_value:.1f}%."
        )
        connection.execute(
            """
            INSERT INTO monitor_alerts (
                id, resource, severity, status, title, message, threshold,
                first_value, last_value, peak_value, occurrences, detected_at,
                detected_ts, last_seen_at, resolved_at, acknowledged_at
            ) VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, NULL, NULL)
            """,
            (
                uuid.uuid4().hex,
                resource,
                desired,
                title,
                message,
                threshold,
                last_value,
                last_value,
                last_value,
                recorded_at,
                recorded_ts,
                recorded_at,
            ),
        )


def _cleanup_history(connection: sqlite3.Connection, config: dict[str, Any], timestamp: float) -> None:
    cutoff = timestamp - int(config["retention_hours"]) * 3600
    connection.execute("DELETE FROM monitor_samples WHERE recorded_ts < ?", (cutoff,))
    connection.execute(
        "DELETE FROM monitor_alerts WHERE status = 'resolved' AND detected_ts < ?",
        (cutoff,),
    )
    connection.execute(
        """
        DELETE FROM monitor_samples WHERE id IN (
            SELECT id FROM monitor_samples ORDER BY id DESC LIMIT -1 OFFSET ?
        )
        """,
        (MAX_SAMPLES,),
    )
    connection.execute(
        """
        DELETE FROM monitor_alerts WHERE id IN (
            SELECT id FROM monitor_alerts
            WHERE status = 'resolved'
            ORDER BY detected_ts DESC LIMIT -1 OFFSET ?
        )
        """,
        (MAX_ALERTS,),
    )


def record_sample(
    metrics: dict[str, Any],
    recorded_at: datetime | str | None = None,
) -> dict[str, Any]:
    """Valida, persiste e avalia uma única coleta local."""

    _ensure_database()
    normalised = _normalise_metrics(metrics)
    timestamp_text, timestamp_value = _timestamp(recorded_at)
    config = load_monitor_config()
    with _DB_LOCK, _connect() as connection:
        cursor = connection.execute(
            """
            INSERT INTO monitor_samples (
                recorded_at, recorded_ts, cpu_percent, memory_percent,
                disk_percent, network_sent_bps, network_received_bps
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp_text,
                timestamp_value,
                normalised["cpu_percent"],
                normalised["memory_percent"],
                normalised["disk_percent"],
                normalised["network_sent_bps"],
                normalised["network_received_bps"],
            ),
        )
        sample_id = int(cursor.lastrowid)
        _evaluate_alerts(connection, config, timestamp_text, timestamp_value)
        _cleanup_history(connection, config, timestamp_value)
        row = connection.execute(
            "SELECT * FROM monitor_samples WHERE id = ?", (sample_id,)
        ).fetchone()
    if row is None:  # Só ocorre se um limite de teste for menor que uma única linha.
        raise MonitorError("A coleta não pôde ser mantida no histórico.")
    return _sample_from_row(row)


def list_samples(limit: int = 180) -> list[dict[str, Any]]:
    _ensure_database()
    safe_limit = min(max(int(limit), 1), 1_000)
    with _connect() as connection:
        rows = connection.execute(
            """
            SELECT * FROM (
                SELECT * FROM monitor_samples ORDER BY id DESC LIMIT ?
            ) ORDER BY id ASC
            """,
            (safe_limit,),
        ).fetchall()
    return [_sample_from_row(row) for row in rows]


def latest_sample() -> dict[str, Any] | None:
    _ensure_database()
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM monitor_samples ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return _sample_from_row(row) if row is not None else None


def list_alerts(limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
    _ensure_database()
    safe_limit = min(max(int(limit), 1), 500)
    if status not in {None, "active", "resolved"}:
        raise MonitorError("Estado de alerta inválido.")
    query = "SELECT * FROM monitor_alerts"
    parameters: list[Any] = []
    if status:
        query += " WHERE status = ?"
        parameters.append(status)
    query += " ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, detected_ts DESC LIMIT ?"
    parameters.append(safe_limit)
    with _connect() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [_alert_from_row(row) for row in rows]


def get_alert(alert_id: str) -> dict[str, Any]:
    """Retorna um alerta específico para vinculação segura a um incidente."""

    _ensure_database()
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM monitor_alerts WHERE id = ?", (str(alert_id),)
        ).fetchone()
    if row is None:
        raise FileNotFoundError(str(alert_id))
    return _alert_from_row(row)


def acknowledge_alerts(alert_id: str | None = None) -> dict[str, Any]:
    _ensure_database()
    acknowledged_at = now()
    with _DB_LOCK, _connect() as connection:
        if alert_id:
            cursor = connection.execute(
                """
                UPDATE monitor_alerts SET acknowledged_at = ?
                WHERE id = ? AND acknowledged_at IS NULL
                """,
                (acknowledged_at, str(alert_id)),
            )
            exists = connection.execute(
                "SELECT 1 FROM monitor_alerts WHERE id = ?", (str(alert_id),)
            ).fetchone()
            if exists is None:
                raise FileNotFoundError(str(alert_id))
        else:
            cursor = connection.execute(
                "UPDATE monitor_alerts SET acknowledged_at = ? WHERE acknowledged_at IS NULL",
                (acknowledged_at,),
            )
        count = max(int(cursor.rowcount), 0)
    return {"acknowledged": count, "acknowledged_at": acknowledged_at}


def clear_monitor_history() -> dict[str, int]:
    _ensure_database()
    with _DB_LOCK, _connect() as connection:
        sample_count = int(connection.execute("SELECT COUNT(*) FROM monitor_samples").fetchone()[0])
        alert_count = int(connection.execute("SELECT COUNT(*) FROM monitor_alerts").fetchone()[0])
        connection.execute("DELETE FROM monitor_samples")
        connection.execute("DELETE FROM monitor_alerts")
    return {"samples_deleted": sample_count, "alerts_deleted": alert_count}


def monitor_statistics() -> dict[str, Any]:
    _ensure_database()
    cutoff = time.time() - 24 * 3600
    with _connect() as connection:
        total = int(connection.execute("SELECT COUNT(*) FROM monitor_samples").fetchone()[0])
        row = connection.execute(
            """
            SELECT COUNT(*) AS count,
                   AVG(cpu_percent) AS cpu_average, MAX(cpu_percent) AS cpu_peak,
                   AVG(memory_percent) AS memory_average, MAX(memory_percent) AS memory_peak,
                   AVG(disk_percent) AS disk_average, MAX(disk_percent) AS disk_peak,
                   MIN(recorded_at) AS first_recorded_at, MAX(recorded_at) AS last_recorded_at
            FROM monitor_samples WHERE recorded_ts >= ?
            """,
            (cutoff,),
        ).fetchone()
        active = int(
            connection.execute(
                "SELECT COUNT(*) FROM monitor_alerts WHERE status = 'active'"
            ).fetchone()[0]
        )
        unacknowledged = int(
            connection.execute(
                "SELECT COUNT(*) FROM monitor_alerts WHERE acknowledged_at IS NULL"
            ).fetchone()[0]
        )

    def optional_round(value: Any) -> float | None:
        return round(float(value), 1) if value is not None else None

    return {
        "sample_count": total,
        "window_hours": 24,
        "window_sample_count": int(row["count"]),
        "first_recorded_at": row["first_recorded_at"],
        "last_recorded_at": row["last_recorded_at"],
        "cpu_average": optional_round(row["cpu_average"]),
        "cpu_peak": optional_round(row["cpu_peak"]),
        "memory_average": optional_round(row["memory_average"]),
        "memory_peak": optional_round(row["memory_peak"]),
        "disk_average": optional_round(row["disk_average"]),
        "disk_peak": optional_round(row["disk_peak"]),
        "active_alerts": active,
        "unacknowledged_alerts": unacknowledged,
    }


def monitor_storage_bytes() -> int:
    total = 0
    for suffix in ("", "-wal", "-shm"):
        path = Path(f"{DB_PATH}{suffix}")
        try:
            total += path.stat().st_size
        except OSError:
            pass
    return total


class SystemSampler:
    """Coletor psutil com cálculo isolado das taxas agregadas de rede."""

    def __init__(self) -> None:
        self._network_sample: tuple[float, int, int] | None = None
        self._lock = threading.Lock()

    def __call__(self) -> dict[str, Any]:
        if psutil is None:
            return {
                "available": False,
                "reason": "Instale as dependências com INSTALAR-HERMES.bat.",
            }
        try:
            cpu_percent = psutil.cpu_percent(interval=0.08)
            memory_percent = psutil.virtual_memory().percent
            disk_percent = psutil.disk_usage(BASE_DIR.anchor or os.sep).percent
            counters = psutil.net_io_counters()
            current = (time.monotonic(), counters.bytes_sent, counters.bytes_recv)
            sent_rate = received_rate = 0.0
            with self._lock:
                if self._network_sample is not None:
                    elapsed = max(current[0] - self._network_sample[0], 0.001)
                    sent_rate = max((current[1] - self._network_sample[1]) / elapsed, 0.0)
                    received_rate = max((current[2] - self._network_sample[2]) / elapsed, 0.0)
                self._network_sample = current
            return {
                "available": True,
                "cpu_percent": cpu_percent,
                "memory_percent": memory_percent,
                "disk_percent": disk_percent,
                "network_sent_bps": sent_rate,
                "network_received_bps": received_rate,
            }
        except (OSError, RuntimeError, AttributeError) as exc:
            return {"available": False, "reason": f"Falha na coleta local: {exc}"}


class MonitoringEngine:
    """Executa coletas periódicas em uma única thread de baixo impacto."""

    def __init__(self, sampler: Callable[[], dict[str, Any]] | None = None) -> None:
        self._sampler = sampler or SystemSampler()
        self._available = sampler is not None or psutil is not None
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._started_at: str | None = None
        self._last_sample_at: str | None = None
        self._last_error: str | None = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            running = bool(self._thread and self._thread.is_alive())
            return {
                "available": self._available,
                "running": running,
                "started_at": self._started_at,
                "last_sample_at": self._last_sample_at,
                "last_error": self._last_error,
            }

    def collect_once(self) -> dict[str, Any]:
        if not self._available:
            raise MonitorError("Telemetria indisponível. Execute INSTALAR-HERMES.bat.")
        metrics = self._sampler()
        try:
            sample = record_sample(metrics)
        except (MonitorError, OSError, sqlite3.Error) as exc:
            with self._lock:
                self._last_error = str(exc)
            raise
        with self._lock:
            self._last_sample_at = sample["recorded_at"]
            self._last_error = None
        return sample

    def start(self, persist_enabled: bool = True) -> dict[str, Any]:
        if not self._available:
            raise MonitorError("Telemetria indisponível. Execute INSTALAR-HERMES.bat.")
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self.status()
            if persist_enabled:
                set_monitor_enabled(True)
            self._stop_event.clear()
            self._started_at = now()
            self._last_error = None
            self._thread = threading.Thread(
                target=self._run,
                name="hermes-monitor",
                daemon=True,
            )
            self._thread.start()
        return self.status()

    def start_if_enabled(self) -> dict[str, Any]:
        config = load_monitor_config()
        if config["enabled"]:
            return self.start(persist_enabled=False)
        return self.status()

    def stop(self, persist_enabled: bool = True) -> dict[str, Any]:
        with self._lock:
            thread = self._thread
            self._stop_event.set()
        if thread and thread is not threading.current_thread():
            thread.join(timeout=2.5)
        with self._lock:
            if self._thread is thread:
                self._thread = None
            self._started_at = None
        if persist_enabled:
            set_monitor_enabled(False)
        return self.status()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            started = time.monotonic()
            try:
                self.collect_once()
            except (MonitorError, OSError, sqlite3.Error):
                pass
            try:
                interval = int(load_monitor_config()["interval_seconds"])
            except (MonitorError, OSError, sqlite3.Error):
                interval = int(DEFAULT_CONFIG["interval_seconds"])
            remaining = max(interval - (time.monotonic() - started), 1.0)
            self._stop_event.wait(remaining)


def dashboard_payload(
    engine: MonitoringEngine,
    sample_limit: int = 180,
    alert_limit: int = 100,
) -> dict[str, Any]:
    return {
        "runtime": engine.status(),
        "config": load_monitor_config(),
        "latest": latest_sample(),
        "summary": monitor_statistics(),
        "samples": list_samples(sample_limit),
        "alerts": list_alerts(alert_limit),
        "storage_bytes": monitor_storage_bytes(),
        "limits": {
            "max_samples": MAX_SAMPLES,
            "max_alerts": MAX_ALERTS,
            "allowed_intervals": sorted(ALLOWED_INTERVALS),
            "max_retention_hours": MAX_RETENTION_HOURS,
        },
        "timestamp": now(),
    }
