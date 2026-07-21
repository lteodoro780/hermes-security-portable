from __future__ import annotations

import io
import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hermes import hermes_backup  # noqa: E402


class BackupTests(unittest.TestCase):
    def _directories(self, root: Path) -> tuple[Path, Path, Path]:
        config = root / "config"
        data = root / "data"
        reports = root / "reports"
        config.mkdir()
        data.mkdir()
        reports.mkdir()
        return config, data, reports

    def test_backup_excludes_models_and_preserves_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config, data, reports = self._directories(Path(temp_dir))
            (config / "hermes.json").write_text('{"profile":"balanced"}', encoding="utf-8")
            (reports / "sample.json").write_text('{"status":"completed"}', encoding="utf-8")
            with sqlite3.connect(data / "hermes-incidents.db") as connection:
                connection.execute("CREATE TABLE sample (id INTEGER)")
                connection.execute("INSERT INTO sample VALUES (1)")
            with (
                patch.object(hermes_backup, "CONFIG_DIR", config),
                patch.object(hermes_backup, "DATA_DIR", data),
                patch.object(hermes_backup, "REPORT_DIR", reports),
            ):
                filename, content, manifest = hermes_backup.create_backup()

            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                names = archive.namelist()
                database = archive.read("data/hermes-incidents.db")

        self.assertTrue(filename.endswith(".zip"))
        self.assertIn("config/hermes.json", names)
        self.assertIn("reports/sample.json", names)
        self.assertNotIn("models", " ".join(names))
        self.assertEqual(manifest["app_version"], "0.8.0")
        self.assertTrue(database.startswith(b"SQLite format 3"))

    def test_restore_validates_then_replaces_allowed_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config, data, reports = self._directories(Path(temp_dir))
            (config / "hermes.json").write_text('{"profile":"fast"}', encoding="utf-8")
            with (
                patch.object(hermes_backup, "CONFIG_DIR", config),
                patch.object(hermes_backup, "DATA_DIR", data),
                patch.object(hermes_backup, "REPORT_DIR", reports),
            ):
                _filename, content, _manifest = hermes_backup.create_backup()
                (config / "hermes.json").write_text('{"profile":"quality"}', encoding="utf-8")
                result = hermes_backup.restore_backup(content)
                restored = json.loads((config / "hermes.json").read_text(encoding="utf-8"))

        self.assertEqual(restored["profile"], "fast")
        self.assertEqual(result["restored_count"], 1)

    def test_restore_rejects_traversal_and_unknown_paths(self) -> None:
        for unsafe_name in ("../secret.json", "models/model.gguf"):
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr(
                    "manifest.json",
                    json.dumps({"app": "HERMES Security Portable", "schema_version": 1}),
                )
                archive.writestr(unsafe_name, "x")
            with self.assertRaises(hermes_backup.BackupError):
                hermes_backup.inspect_backup(buffer.getvalue())

    def test_invalid_json_is_rejected_before_existing_data_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config, data, reports = self._directories(Path(temp_dir))
            original = '{"profile":"balanced"}'
            (config / "hermes.json").write_text(original, encoding="utf-8")
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr(
                    "manifest.json",
                    json.dumps({"app": "HERMES Security Portable", "schema_version": 1}),
                )
                archive.writestr("config/hermes.json", "not-json")
            with (
                patch.object(hermes_backup, "CONFIG_DIR", config),
                patch.object(hermes_backup, "DATA_DIR", data),
                patch.object(hermes_backup, "REPORT_DIR", reports),
            ):
                with self.assertRaises(hermes_backup.BackupError):
                    hermes_backup.restore_backup(buffer.getvalue())
                current = (config / "hermes.json").read_text(encoding="utf-8")

        self.assertEqual(current, original)


if __name__ == "__main__":
    unittest.main()
