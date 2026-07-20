from __future__ import annotations

import zipfile
from datetime import datetime

from .config import BASE_DIR, CONFIG_DIR, DATA_DIR, KNOWLEDGE_DIR


def create_backup() -> str:
    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    destination = backup_dir / f"hermes-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.zip"
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for directory in (CONFIG_DIR, DATA_DIR, KNOWLEDGE_DIR):
            for path in directory.rglob("*"):
                if path.is_file():
                    archive.write(path, path.relative_to(BASE_DIR))
    return str(destination)
