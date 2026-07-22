from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hermes import hermes_desktop_core, hermes_profiles  # noqa: E402


class DesktopModelTests(unittest.TestCase):
    def _config_context(self, root: Path):
        config_dir = root / "config"
        return (
            patch.object(hermes_profiles, "CONFIG_DIR", config_dir),
            patch.object(hermes_profiles, "CONFIG_PATH", config_dir / "hermes.json"),
        )

    def test_format_bytes(self) -> None:
        self.assertEqual(hermes_desktop_core.format_bytes(0), "0 B")
        self.assertEqual(hermes_desktop_core.format_bytes(1024), "1.00 KB")
        self.assertEqual(hermes_desktop_core.format_bytes(3 * 1024**3), "3.00 GB")

    def test_invalid_model_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            invalid = Path(temp_dir) / "invalid.gguf"
            invalid.write_bytes(b"NOPE")
            with self.assertRaises(hermes_desktop_core.DesktopError):
                hermes_desktop_core.model_details(invalid)

    def test_registers_model_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            model = root / "local.gguf"
            model.write_bytes(b"GGUF" + b"x" * 32)
            patches = self._config_context(root)
            with patches[0], patches[1]:
                result = hermes_desktop_core.register_custom_model(model)
                config = hermes_profiles.load_config()

        self.assertFalse(result["copied"])
        self.assertEqual(config["profile"], "custom")
        self.assertEqual(config["custom_model_path"], str(model.resolve()))

    def test_copies_model_atomically_to_portable_folder(self) -> None:
        progress: list[tuple[int, int]] = []
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_dir = root / "source"
            source_dir.mkdir()
            source = source_dir / "modelo.gguf"
            payload = b"GGUF" + b"x" * 1024
            source.write_bytes(payload)
            models = root / "models"
            patches = self._config_context(root)
            with (
                patches[0],
                patches[1],
                patch.object(hermes_desktop_core, "MODELS_DIR", models),
            ):
                result = hermes_desktop_core.register_custom_model(
                    source,
                    copy_to_portable=True,
                    progress=lambda current, total: progress.append((current, total)),
                )
                copied = Path(result["path"]).read_bytes()

        self.assertTrue(result["copied"])
        self.assertEqual(copied, payload)
        self.assertEqual(progress[-1], (len(payload), len(payload)))

    def test_existing_model_is_not_overwritten_silently(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source" / "same.gguf"
            source.parent.mkdir()
            source.write_bytes(b"GGUFsource")
            models = root / "models"
            models.mkdir()
            (models / source.name).write_bytes(b"GGUFexisting")
            with patch.object(hermes_desktop_core, "MODELS_DIR", models):
                with self.assertRaises(hermes_desktop_core.DesktopError):
                    hermes_desktop_core.register_custom_model(source, copy_to_portable=True)

    def test_registers_llama_server_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            executable = root / "llama-server.exe"
            executable.write_bytes(b"test")
            patches = self._config_context(root)
            with patches[0], patches[1]:
                result = hermes_desktop_core.register_llama_executable(executable)
                config = hermes_profiles.load_config()

        self.assertEqual(result["style"], "server")
        self.assertEqual(config["llama_path"], str(executable.resolve()))

    def test_startup_payload_declares_native_desktop(self) -> None:
        with (
            patch.object(hermes_desktop_core, "ensure_runtime_directories", return_value={"data": Path("data")}),
            patch.object(hermes_desktop_core, "load_config", return_value={"setup_completed": True}),
            patch.object(
                hermes_desktop_core,
                "hardware_info",
                return_value={"memory_total_gb": 16.0},
            ),
            patch.object(
                hermes_desktop_core,
                "runtime_selection",
                return_value={
                    "profile": {"id": "balanced"},
                    "model_ready": False,
                    "llama_ready": False,
                },
            ),
        ):
            payload = hermes_desktop_core.startup_payload()

        self.assertTrue(payload["desktop"])
        self.assertFalse(payload["browser_required"])
        self.assertEqual(payload["version"], "0.9.0")


if __name__ == "__main__":
    unittest.main()
