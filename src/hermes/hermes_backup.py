#!/usr/bin/env python3
"""Backup e restauração portáteis dos dados locais do HERMES."""

from __future__ import annotations

import io
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from .hermes_paths import CONFIG_DIR, DATA_DIR, REPORT_DIR
except ImportError:
    from hermes_paths import CONFIG_DIR, DATA_DIR, REPORT_DIR


APP_VERSION = "0.9.0"
MAX_BACKUP_BYTES = 96 * 1024 * 1024
MAX_ARCHIVE_FILES = 600
DATABASE_NAMES = {
    "hermes-monitor.db",
    "hermes-knowledge.db",
    "hermes-incidents.db",
}
DATA_JSON_NAMES = {
    "chat-history.json",
    "last-benchmark.json",
    "report-baseline.json",
}


class BackupError(ValueError):
    """Backup inválido ou maior que os limites locais."""


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _sqlite_snapshot(source_path: Path, destination_path: Path) -> None:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    source_uri = f"file:{source_path.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True, timeout=15) as source:
        with sqlite3.connect(destination_path, timeout=15) as destination:
            source.backup(destination)


def _safe_json_bytes(path: Path) -> bytes | None:
    try:
        raw = path.read_bytes()
        json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return raw


def create_backup() -> tuple[str, bytes, dict[str, Any]]:
    """Cria um ZIP em memória sem modelos, ferramentas ou executáveis."""

    created_at = now()
    included: list[str] = []
    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory(prefix="hermes-backup-") as temp_dir:
        temporary = Path(temp_dir)
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            config_path = CONFIG_DIR / "hermes.json"
            config_data = _safe_json_bytes(config_path)
            if config_data is not None:
                archive.writestr("config/hermes.json", config_data)
                included.append("config/hermes.json")

            for name in sorted(DATA_JSON_NAMES):
                data = _safe_json_bytes(DATA_DIR / name)
                if data is not None:
                    arcname = f"data/{name}"
                    archive.writestr(arcname, data)
                    included.append(arcname)

            for name in sorted(DATABASE_NAMES):
                source = DATA_DIR / name
                if not source.is_file():
                    continue
                snapshot = temporary / name
                try:
                    _sqlite_snapshot(source, snapshot)
                except sqlite3.Error as exc:
                    raise BackupError(f"Não foi possível copiar o banco {name}.") from exc
                arcname = f"data/{name}"
                archive.write(snapshot, arcname)
                included.append(arcname)

            if REPORT_DIR.is_dir():
                for report in sorted(REPORT_DIR.glob("*.json")):
                    data = _safe_json_bytes(report)
                    if data is None:
                        continue
                    arcname = f"reports/{report.name}"
                    archive.writestr(arcname, data)
                    included.append(arcname)

            manifest = {
                "schema_version": 1,
                "app": "HERMES Security Portable",
                "app_version": APP_VERSION,
                "created_at": created_at,
                "files": included,
                "excluded": ["models", "tools", "executables"],
            }
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            )
    content = buffer.getvalue()
    if len(content) > MAX_BACKUP_BYTES:
        raise BackupError("O backup excede o limite de 96 MB.")
    filename = f"HERMES-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    return filename, content, manifest


def _is_symlink(info: zipfile.ZipInfo) -> bool:
    unix_mode = (info.external_attr >> 16) & 0o170000
    return unix_mode == 0o120000


def _allowed_destination(name: str) -> Path | None:
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or "\\" in name:
        return None
    if name == "manifest.json":
        return None
    if name == "config/hermes.json":
        return CONFIG_DIR / "hermes.json"
    if len(pure.parts) == 2 and pure.parts[0] == "data":
        filename = pure.parts[1]
        if filename in DATA_JSON_NAMES | DATABASE_NAMES:
            return DATA_DIR / filename
    if (
        len(pure.parts) == 2
        and pure.parts[0] == "reports"
        and pure.parts[1].endswith(".json")
        and Path(pure.parts[1]).name == pure.parts[1]
    ):
        return REPORT_DIR / pure.parts[1]
    return None


def _validate_json(path: Path) -> None:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupError(f"JSON inválido no backup: {path.name}.") from exc
    if not isinstance(parsed, (dict, list)):
        raise BackupError(f"Estrutura JSON inválida no backup: {path.name}.")


def _validate_database(path: Path) -> None:
    try:
        uri = f"file:{path.resolve().as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=10) as connection:
            result = connection.execute("PRAGMA quick_check").fetchone()
    except sqlite3.Error as exc:
        raise BackupError(f"Banco SQLite inválido no backup: {path.name}.") from exc
    if not result or result[0] != "ok":
        raise BackupError(f"Falha de integridade no banco {path.name}.")


def inspect_backup(content: bytes) -> dict[str, Any]:
    """Valida o arquivo inteiro antes de qualquer alteração local."""

    if not content or len(content) > MAX_BACKUP_BYTES:
        raise BackupError("Arquivo de backup vazio ou maior que 96 MB.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(content), "r")
    except (zipfile.BadZipFile, OSError) as exc:
        raise BackupError("O arquivo selecionado não é um ZIP válido.") from exc
    with archive:
        infos = archive.infolist()
        if not infos or len(infos) > MAX_ARCHIVE_FILES:
            raise BackupError("Quantidade de arquivos inválida no backup.")
        if sum(info.file_size for info in infos) > MAX_BACKUP_BYTES:
            raise BackupError("O conteúdo descompactado excede 96 MB.")
        names = {info.filename for info in infos if not info.is_dir()}
        if "manifest.json" not in names:
            raise BackupError("Manifesto do HERMES não encontrado.")
        for info in infos:
            if info.is_dir():
                continue
            if info.flag_bits & 0x1:
                raise BackupError("Backups criptografados não são aceitos.")
            if _is_symlink(info):
                raise BackupError("Links simbólicos não são aceitos no backup.")
            if info.filename != "manifest.json" and _allowed_destination(info.filename) is None:
                raise BackupError(f"Caminho não permitido no backup: {info.filename}.")
        try:
            manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        except (KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackupError("Manifesto do backup inválido.") from exc
        if not isinstance(manifest, dict) or manifest.get("app") != "HERMES Security Portable":
            raise BackupError("Este arquivo não é um backup reconhecido do HERMES.")
    return {
        "manifest": manifest,
        "file_count": len(names) - 1,
        "compressed_bytes": len(content),
        "uncompressed_bytes": sum(info.file_size for info in infos),
    }


def restore_backup(content: bytes) -> dict[str, Any]:
    """Restaura somente caminhos permitidos, com validação e rollback local."""

    inspection = inspect_backup(content)
    restored: list[str] = []
    with tempfile.TemporaryDirectory(prefix="hermes-restore-") as temp_dir:
        root = Path(temp_dir)
        staged_root = root / "staged"
        rollback_root = root / "rollback"
        staged: list[tuple[str, Path, Path]] = []
        with zipfile.ZipFile(io.BytesIO(content), "r") as archive:
            for info in archive.infolist():
                destination = _allowed_destination(info.filename)
                if destination is None or info.is_dir():
                    continue
                staged_path = staged_root / PurePosixPath(info.filename)
                staged_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, staged_path.open("wb") as target:
                    shutil.copyfileobj(source, target, length=1024 * 1024)
                if staged_path.suffix == ".json":
                    _validate_json(staged_path)
                elif staged_path.name in DATABASE_NAMES:
                    _validate_database(staged_path)
                staged.append((info.filename, staged_path, destination))

        changed: list[tuple[Path, Path | None]] = []
        try:
            for arcname, staged_path, destination in staged:
                destination.parent.mkdir(parents=True, exist_ok=True)
                rollback_path: Path | None = None
                if destination.exists():
                    rollback_path = rollback_root / PurePosixPath(arcname)
                    rollback_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(destination, rollback_path)
                temporary = destination.with_name(destination.name + ".restore-tmp")
                shutil.copy2(staged_path, temporary)
                os.replace(temporary, destination)
                if destination.name in DATABASE_NAMES:
                    for suffix in ("-wal", "-shm"):
                        sidecar = Path(str(destination) + suffix)
                        try:
                            sidecar.unlink()
                        except FileNotFoundError:
                            pass
                changed.append((destination, rollback_path))
                restored.append(arcname)
        except OSError as exc:
            for destination, rollback_path in reversed(changed):
                try:
                    if rollback_path is not None:
                        os.replace(rollback_path, destination)
                    else:
                        destination.unlink(missing_ok=True)
                except OSError:
                    pass
            raise BackupError("A restauração falhou e as alterações foram revertidas.") from exc

    return {
        "restored": restored,
        "restored_count": len(restored),
        "manifest": inspection["manifest"],
        "timestamp": now(),
    }
