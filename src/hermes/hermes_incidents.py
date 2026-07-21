#!/usr/bin/env python3
"""Central local de incidentes do HERMES.

O módulo registra contexto, linha do tempo e checklist defensivo. Ele não coleta
processos, não captura pacotes e não executa ações corretivas no computador.
"""

from __future__ import annotations

import html
import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from .hermes_paths import DATA_DIR
except ImportError:
    from hermes_paths import DATA_DIR


DB_PATH = DATA_DIR / "hermes-incidents.db"
MAX_INCIDENTS = 500
MAX_TITLE_CHARS = 180
MAX_DESCRIPTION_CHARS = 8_000
MAX_EVENT_CHARS = 12_000
MAX_SNAPSHOT_BYTES = 96 * 1024
VALID_SEVERITIES = {"normal", "attention", "critical"}
VALID_STATUSES = {"open", "investigating", "resolved"}

_DB_LOCK = threading.RLock()
_INITIALISED_PATHS: set[str] = set()


class IncidentError(ValueError):
    """Erro de validação seguro para apresentação na interface local."""


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
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
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    source_type TEXT NOT NULL,
                    monitor_alert_id TEXT,
                    snapshot_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    created_ts REAL NOT NULL,
                    updated_at TEXT NOT NULL,
                    resolved_at TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_incidents_status
                    ON incidents(status, created_ts DESC);
                CREATE INDEX IF NOT EXISTS idx_incidents_severity
                    ON incidents(severity, status);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_incidents_active_alert
                    ON incidents(monitor_alert_id)
                    WHERE monitor_alert_id IS NOT NULL AND status != 'resolved';
                CREATE TABLE IF NOT EXISTS incident_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
                    event_type TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metadata_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    created_ts REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_incident_events_time
                    ON incident_events(incident_id, id);
                CREATE TABLE IF NOT EXISTS incident_checklist (
                    id TEXT PRIMARY KEY,
                    incident_id TEXT NOT NULL REFERENCES incidents(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    label TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    completed_at TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_incident_checklist_position
                    ON incident_checklist(incident_id, position);
                """
            )
        _INITIALISED_PATHS.add(path_key)


def _clean_text(value: Any, label: str, maximum: int, *, required: bool = False) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise IncidentError(f"{label} é obrigatório.")
    if len(text) > maximum:
        raise IncidentError(f"{label} excede o limite de {maximum} caracteres.")
    return text


def _clean_severity(value: Any) -> str:
    severity = str(value or "attention").strip().lower()
    if severity not in VALID_SEVERITIES:
        raise IncidentError("Severidade inválida.")
    return severity


def _clean_status(value: Any) -> str:
    status = str(value or "").strip().lower()
    if status not in VALID_STATUSES:
        raise IncidentError("Estado de incidente inválido.")
    return status


def _snapshot_json(snapshot: Any) -> str:
    if snapshot is None:
        snapshot = {}
    if not isinstance(snapshot, dict):
        raise IncidentError("O snapshot do incidente deve ser um objeto.")
    try:
        encoded = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise IncidentError("O snapshot contém dados inválidos.") from exc
    if len(encoded.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise IncidentError("O snapshot excede o limite local permitido.")
    return encoded


def _load_json(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _incident_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "severity": row["severity"],
        "status": row["status"],
        "description": row["description"],
        "source_type": row["source_type"],
        "monitor_alert_id": row["monitor_alert_id"],
        "snapshot": _load_json(row["snapshot_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "resolved_at": row["resolved_at"],
    }


def _event_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "type": row["event_type"],
        "message": row["message"],
        "metadata": _load_json(row["metadata_json"]),
        "created_at": row["created_at"],
    }


def _checklist_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "position": int(row["position"]),
        "label": row["label"],
        "completed": bool(row["completed"]),
        "completed_at": row["completed_at"],
        "updated_at": row["updated_at"],
    }


def _resource_from_snapshot(snapshot: dict[str, Any]) -> str:
    alert = snapshot.get("alert")
    if isinstance(alert, dict):
        resource = str(alert.get("resource", "")).lower()
        if resource in {"cpu", "memory", "disk"}:
            return resource
    return "generic"


def checklist_labels(resource: str) -> list[str]:
    """Retorna passos de verificação somente leitura para o tipo de alerta."""

    common = [
        "Confirmar o horário, a duração e a severidade do alerta.",
        "Comparar o snapshot com as coletas anteriores do monitor.",
    ]
    specific = {
        "cpu": [
            "Confirmar se o uso de CPU voltou abaixo do limite configurado.",
            "Registrar qual atividade legítima estava em execução no período.",
        ],
        "memory": [
            "Confirmar se o uso de memória voltou abaixo do limite configurado.",
            "Registrar aplicações abertas e mudanças recentes conhecidas.",
        ],
        "disk": [
            "Confirmar o espaço livre atual e a tendência observada no histórico.",
            "Identificar, sem excluir arquivos, qual área exige revisão manual.",
        ],
        "generic": [
            "Registrar evidências locais relevantes sem incluir dados sensíveis.",
            "Validar se o comportamento continua ocorrendo antes de agir.",
        ],
    }
    return common + specific.get(resource, specific["generic"]) + [
        "Documentar a conclusão e resolver o incidente quando a verificação terminar."
    ]


def _add_event(
    connection: sqlite3.Connection,
    incident_id: str,
    event_type: str,
    message: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    timestamp = now()
    safe_message = _clean_text(message, "Evento", MAX_EVENT_CHARS, required=True)
    metadata_json = _snapshot_json(metadata or {})
    connection.execute(
        """
        INSERT INTO incident_events
            (incident_id, event_type, message, metadata_json, created_at, created_ts)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (incident_id, event_type[:40], safe_message, metadata_json, timestamp, time.time()),
    )


def _prune_resolved(connection: sqlite3.Connection, *, reserve: int = 0) -> None:
    count = int(connection.execute("SELECT COUNT(*) FROM incidents").fetchone()[0])
    excess = max(count - MAX_INCIDENTS + max(int(reserve), 0), 0)
    if excess:
        connection.execute(
            """
            DELETE FROM incidents WHERE id IN (
                SELECT id FROM incidents WHERE status = 'resolved'
                ORDER BY created_ts ASC LIMIT ?
            )
            """,
            (excess,),
        )


def create_incident(
    title: Any,
    severity: Any = "attention",
    description: Any = "",
    *,
    source_type: str = "manual",
    monitor_alert_id: str | None = None,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Cria um incidente ou devolve o incidente ativo do mesmo alerta."""

    _ensure_database()
    safe_title = _clean_text(title, "Título", MAX_TITLE_CHARS, required=True)
    safe_description = _clean_text(description, "Descrição", MAX_DESCRIPTION_CHARS)
    safe_severity = _clean_severity(severity)
    safe_source = "monitor" if source_type == "monitor" else "manual"
    safe_alert_id = str(monitor_alert_id).strip()[:80] if monitor_alert_id else None
    safe_snapshot = snapshot or {}
    encoded_snapshot = _snapshot_json(safe_snapshot)
    timestamp = now()
    incident_id = uuid.uuid4().hex

    with _DB_LOCK, _connect() as connection:
        if safe_alert_id:
            existing = connection.execute(
                """
                SELECT * FROM incidents
                WHERE monitor_alert_id = ? AND status != 'resolved'
                ORDER BY created_ts DESC LIMIT 1
                """,
                (safe_alert_id,),
            ).fetchone()
            if existing is not None:
                result = get_incident(existing["id"])
                result["duplicate"] = True
                return result
        _prune_resolved(connection, reserve=1)
        count = int(connection.execute("SELECT COUNT(*) FROM incidents").fetchone()[0])
        if count >= MAX_INCIDENTS:
            raise IncidentError(
                "O limite de incidentes ativos foi atingido. Resolva ou remova um incidente."
            )
        connection.execute(
            """
            INSERT INTO incidents (
                id, title, severity, status, description, source_type,
                monitor_alert_id, snapshot_json, created_at, created_ts,
                updated_at, resolved_at
            ) VALUES (?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                incident_id,
                safe_title,
                safe_severity,
                safe_description,
                safe_source,
                safe_alert_id,
                encoded_snapshot,
                timestamp,
                time.time(),
                timestamp,
            ),
        )
        _add_event(
            connection,
            incident_id,
            "created",
            "Incidente criado a partir do monitor." if safe_source == "monitor" else "Incidente criado manualmente.",
            {"severity": safe_severity, "source_type": safe_source},
        )
        for position, label in enumerate(
            checklist_labels(_resource_from_snapshot(safe_snapshot)), start=1
        ):
            connection.execute(
                """
                INSERT INTO incident_checklist
                    (id, incident_id, position, label, completed, completed_at, updated_at)
                VALUES (?, ?, ?, ?, 0, NULL, ?)
                """,
                (uuid.uuid4().hex, incident_id, position, label, timestamp),
            )
    result = get_incident(incident_id)
    result["duplicate"] = False
    return result


def create_from_alert(alert: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    alert_id = str(alert.get("id", "")).strip()
    if not alert_id:
        raise IncidentError("Alerta de origem inválido.")
    combined = dict(snapshot)
    combined["alert"] = dict(alert)
    return create_incident(
        alert.get("title") or "Alerta do monitor",
        alert.get("severity") or "attention",
        alert.get("message") or "",
        source_type="monitor",
        monitor_alert_id=alert_id,
        snapshot=combined,
    )


def list_incidents(limit: int = 100, status: str | None = None) -> list[dict[str, Any]]:
    _ensure_database()
    safe_limit = min(max(int(limit), 1), MAX_INCIDENTS)
    if status is not None:
        status = _clean_status(status)
    query = "SELECT * FROM incidents"
    parameters: list[Any] = []
    if status:
        query += " WHERE status = ?"
        parameters.append(status)
    query += (
        " ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'investigating' THEN 1 ELSE 2 END,"
        " updated_at DESC LIMIT ?"
    )
    parameters.append(safe_limit)
    with _connect() as connection:
        rows = connection.execute(query, parameters).fetchall()
    return [_incident_from_row(row) for row in rows]


def get_incident(incident_id: str) -> dict[str, Any]:
    _ensure_database()
    with _connect() as connection:
        row = connection.execute(
            "SELECT * FROM incidents WHERE id = ?", (str(incident_id),)
        ).fetchone()
        if row is None:
            raise FileNotFoundError(str(incident_id))
        events = connection.execute(
            "SELECT * FROM incident_events WHERE incident_id = ? ORDER BY id ASC",
            (str(incident_id),),
        ).fetchall()
        checklist = connection.execute(
            "SELECT * FROM incident_checklist WHERE incident_id = ? ORDER BY position ASC",
            (str(incident_id),),
        ).fetchall()
    incident = _incident_from_row(row)
    incident["timeline"] = [_event_from_row(event) for event in events]
    incident["checklist"] = [_checklist_from_row(item) for item in checklist]
    return incident


def find_active_by_alert(monitor_alert_id: str) -> dict[str, Any] | None:
    _ensure_database()
    with _connect() as connection:
        row = connection.execute(
            """
            SELECT * FROM incidents
            WHERE monitor_alert_id = ? AND status != 'resolved'
            ORDER BY created_ts DESC LIMIT 1
            """,
            (str(monitor_alert_id),),
        ).fetchone()
    return _incident_from_row(row) if row is not None else None


def update_status(incident_id: str, status: Any) -> dict[str, Any]:
    _ensure_database()
    safe_status = _clean_status(status)
    timestamp = now()
    with _DB_LOCK, _connect() as connection:
        row = connection.execute(
            "SELECT status FROM incidents WHERE id = ?", (str(incident_id),)
        ).fetchone()
        if row is None:
            raise FileNotFoundError(str(incident_id))
        previous = row["status"]
        if previous == safe_status:
            return get_incident(incident_id)
        try:
            connection.execute(
                """
                UPDATE incidents SET status = ?, updated_at = ?, resolved_at = ?
                WHERE id = ?
                """,
                (
                    safe_status,
                    timestamp,
                    timestamp if safe_status == "resolved" else None,
                    str(incident_id),
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise IncidentError("Já existe outro incidente ativo para este alerta.") from exc
        labels = {
            "open": "Incidente reaberto.",
            "investigating": "Investigação iniciada.",
            "resolved": "Incidente marcado como resolvido.",
        }
        _add_event(
            connection,
            str(incident_id),
            "status",
            labels[safe_status],
            {"from": previous, "to": safe_status},
        )
    return get_incident(incident_id)


def add_note(incident_id: str, message: Any) -> dict[str, Any]:
    _ensure_database()
    safe_message = _clean_text(message, "Nota", MAX_EVENT_CHARS, required=True)
    timestamp = now()
    with _DB_LOCK, _connect() as connection:
        exists = connection.execute(
            "SELECT 1 FROM incidents WHERE id = ?", (str(incident_id),)
        ).fetchone()
        if exists is None:
            raise FileNotFoundError(str(incident_id))
        _add_event(connection, str(incident_id), "note", safe_message)
        connection.execute(
            "UPDATE incidents SET updated_at = ? WHERE id = ?",
            (timestamp, str(incident_id)),
        )
    return get_incident(incident_id)


def add_analysis(
    incident_id: str,
    analysis: Any,
    *,
    duration_seconds: float | None = None,
) -> dict[str, Any]:
    _ensure_database()
    safe_analysis = _clean_text(analysis, "Análise", MAX_EVENT_CHARS, required=True)
    timestamp = now()
    metadata = {"duration_seconds": round(float(duration_seconds or 0), 2)}
    with _DB_LOCK, _connect() as connection:
        exists = connection.execute(
            "SELECT 1 FROM incidents WHERE id = ?", (str(incident_id),)
        ).fetchone()
        if exists is None:
            raise FileNotFoundError(str(incident_id))
        _add_event(connection, str(incident_id), "analysis", safe_analysis, metadata)
        connection.execute(
            "UPDATE incidents SET updated_at = ? WHERE id = ?",
            (timestamp, str(incident_id)),
        )
    return get_incident(incident_id)


def set_checklist_item(incident_id: str, item_id: str, completed: Any) -> dict[str, Any]:
    _ensure_database()
    is_completed = completed is True
    timestamp = now()
    with _DB_LOCK, _connect() as connection:
        row = connection.execute(
            """
            SELECT label, completed FROM incident_checklist
            WHERE id = ? AND incident_id = ?
            """,
            (str(item_id), str(incident_id)),
        ).fetchone()
        if row is None:
            raise FileNotFoundError(str(item_id))
        connection.execute(
            """
            UPDATE incident_checklist
            SET completed = ?, completed_at = ?, updated_at = ?
            WHERE id = ? AND incident_id = ?
            """,
            (
                int(is_completed),
                timestamp if is_completed else None,
                timestamp,
                str(item_id),
                str(incident_id),
            ),
        )
        connection.execute(
            "UPDATE incidents SET updated_at = ? WHERE id = ?",
            (timestamp, str(incident_id)),
        )
        if bool(row["completed"]) != is_completed:
            _add_event(
                connection,
                str(incident_id),
                "checklist",
                ("Etapa concluída: " if is_completed else "Etapa reaberta: ") + row["label"],
                {"item_id": str(item_id), "completed": is_completed},
            )
    return get_incident(incident_id)


def delete_incident(incident_id: str) -> dict[str, str]:
    _ensure_database()
    with _DB_LOCK, _connect() as connection:
        row = connection.execute(
            "SELECT title FROM incidents WHERE id = ?", (str(incident_id),)
        ).fetchone()
        if row is None:
            raise FileNotFoundError(str(incident_id))
        connection.execute("DELETE FROM incidents WHERE id = ?", (str(incident_id),))
    return {"id": str(incident_id), "title": row["title"]}


def incident_summary() -> dict[str, int]:
    _ensure_database()
    with _connect() as connection:
        rows = connection.execute(
            "SELECT status, COUNT(*) AS total FROM incidents GROUP BY status"
        ).fetchall()
        critical = int(
            connection.execute(
                "SELECT COUNT(*) FROM incidents WHERE severity = 'critical' AND status != 'resolved'"
            ).fetchone()[0]
        )
        total = int(connection.execute("SELECT COUNT(*) FROM incidents").fetchone()[0])
    counts = {row["status"]: int(row["total"]) for row in rows}
    return {
        "total": total,
        "open": counts.get("open", 0),
        "investigating": counts.get("investigating", 0),
        "resolved": counts.get("resolved", 0),
        "active": counts.get("open", 0) + counts.get("investigating", 0),
        "critical_active": critical,
    }


def dashboard_payload(limit: int = 100) -> dict[str, Any]:
    return {
        "summary": incident_summary(),
        "incidents": list_incidents(limit),
        "timestamp": now(),
    }


def analysis_prompt(incident: dict[str, Any]) -> str:
    snapshot = json.dumps(incident.get("snapshot", {}), ensure_ascii=False, indent=2)
    checklist = "\n".join(f"- {item['label']}" for item in incident.get("checklist", []))
    return (
        "Analise este incidente local de forma defensiva. Explique o que os dados realmente "
        "mostram, indique hipóteses sem tratá-las como fatos e proponha próximos passos somente "
        "de leitura. Não invente evidências, não recomende apagar arquivos e não execute comandos.\n\n"
        f"Título: {incident['title']}\nSeveridade: {incident['severity']}\n"
        f"Descrição: {incident['description']}\n\nSnapshot:\n{snapshot[:12_000]}\n\n"
        f"Checklist previsto:\n{checklist}"
    )


def incident_html(incident: dict[str, Any]) -> str:
    esc = lambda value: html.escape(str(value), quote=True)
    checklist = "".join(
        f"<li>{'✓' if item['completed'] else '○'} {esc(item['label'])}</li>"
        for item in incident.get("checklist", [])
    )
    timeline = "".join(
        f"<li><strong>{esc(event['created_at'])}</strong> — {esc(event['message'])}</li>"
        for event in incident.get("timeline", [])
    )
    snapshot = esc(json.dumps(incident.get("snapshot", {}), ensure_ascii=False, indent=2))
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>Incidente {esc(incident['id'])}</title>
<style>body{{font:15px Arial,sans-serif;color:#172033;max-width:920px;margin:40px auto;padding:0 24px}}
h1,h2{{color:#0d2a48}}.meta{{background:#eef5fb;padding:16px;border-radius:10px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#f5f7fa;padding:14px;border-radius:8px}}
li{{margin:8px 0}}small{{color:#5d6b7b}}</style></head><body>
<small>HERMES Security Portable — relatório local</small><h1>{esc(incident['title'])}</h1>
<div class="meta"><strong>Severidade:</strong> {esc(incident['severity'])}<br>
<strong>Estado:</strong> {esc(incident['status'])}<br><strong>Criado:</strong> {esc(incident['created_at'])}<br>
<strong>Atualizado:</strong> {esc(incident['updated_at'])}</div>
<h2>Descrição</h2><p>{esc(incident['description']) or 'Sem descrição.'}</p>
<h2>Checklist</h2><ul>{checklist}</ul><h2>Linha do tempo</h2><ol>{timeline}</ol>
<h2>Snapshot local</h2><pre>{snapshot}</pre></body></html>"""


def _pdf_escape(value: str) -> bytes:
    encoded = value.encode("cp1252", errors="replace")
    return encoded.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def _wrap_text(value: Any, width: int = 86) -> list[str]:
    words = str(value or "").replace("\r", "").split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        if len(current) + len(word) + 1 <= width:
            current += " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def incident_pdf(incident: dict[str, Any]) -> bytes:
    """Gera um PDF simples com biblioteca padrão, adequado ao pacote portátil."""

    lines = [
        "HERMES Security Portable - Relatorio de incidente",
        "",
        f"Titulo: {incident['title']}",
        f"Severidade: {incident['severity']} | Estado: {incident['status']}",
        f"Criado: {incident['created_at']} | Atualizado: {incident['updated_at']}",
        "",
        "Descricao:",
        *_wrap_text(incident.get("description") or "Sem descricao."),
        "",
        "Checklist:",
    ]
    for item in incident.get("checklist", []):
        prefix = "[x] " if item["completed"] else "[ ] "
        lines.extend(_wrap_text(prefix + item["label"]))
    lines.extend(["", "Linha do tempo:"])
    for event in incident.get("timeline", []):
        lines.extend(_wrap_text(f"{event['created_at']} - {event['message']}"))
    lines.extend(["", "Snapshot local:"])
    snapshot = json.dumps(incident.get("snapshot", {}), ensure_ascii=False, sort_keys=True)
    lines.extend(_wrap_text(snapshot, 86))

    page_lines = [lines[index : index + 48] for index in range(0, len(lines), 48)] or [[""]]
    object_count = 2 + len(page_lines) * 2 + 1
    font_id = object_count
    page_ids = [3 + index * 2 for index in range(len(page_lines))]
    objects: dict[int, bytes] = {}
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = b" ".join(f"{page_id} 0 R".encode("ascii") for page_id in page_ids)
    objects[2] = b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(page_ids)).encode("ascii") + b" >>"
    for index, page in enumerate(page_lines):
        page_id = page_ids[index]
        content_id = page_id + 1
        content = [b"BT", b"/F1 10 Tf", b"46 790 Td", b"14 TL"]
        for line in page:
            content.append(b"(" + _pdf_escape(line) + b") Tj")
            content.append(b"T*")
        content.append(b"ET")
        stream = b"\n".join(content) + b"\n"
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")
        objects[content_id] = (
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream"
        )
    objects[font_id] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"

    result = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, object_count + 1):
        offsets.append(len(result))
        result.extend(f"{object_id} 0 obj\n".encode("ascii"))
        result.extend(objects[object_id])
        result.extend(b"\nendobj\n")
    xref_offset = len(result)
    result.extend(f"xref\n0 {object_count + 1}\n".encode("ascii"))
    result.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    result.extend(
        f"trailer\n<< /Size {object_count + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode(
            "ascii"
        )
    )
    return bytes(result)
