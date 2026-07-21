from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hermes import hermes_profiles  # noqa: E402


class ProfileConfigurationTests(unittest.TestCase):
    def test_normalize_config_rejects_unsafe_values(self) -> None:
        config = hermes_profiles.normalize_config(
            {
                "profile": "gigantic",
                "default_mode": "unlimited",
                "context_size": 999999,
                "threads": -10,
                "gpu_layers": -4,
            }
        )

        self.assertEqual(config["profile"], "auto")
        self.assertEqual(config["default_mode"], "quick")
        self.assertEqual(config["context_size"], 8192)
        self.assertEqual(config["threads"], 0)
        self.assertEqual(config["gpu_layers"], 0)

    def test_16_gb_recommends_balanced_profile(self) -> None:
        recommended = hermes_profiles.recommended_profile_id({"memory_total_gb": 16.0})
        self.assertEqual(recommended, "balanced")

    def test_resolve_profile_uses_installed_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            models = Path(temp_dir)
            fast_model = models / hermes_profiles.PROFILE_DEFINITIONS["fast"]["model_file"]
            fast_model.write_bytes(b"GGUF")
            with patch.object(hermes_profiles, "MODELS_DIR", models):
                selected = hermes_profiles.resolve_profile(
                    {"profile": "balanced"},
                    {"memory_total_gb": 16.0},
                )

        self.assertEqual(selected["id"], "fast")
        self.assertTrue(selected["installed"])
        self.assertTrue(selected["fallback"])

    def test_save_config_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            config_path = directory / "hermes.json"
            with (
                patch.object(hermes_profiles, "CONFIG_DIR", directory),
                patch.object(hermes_profiles, "CONFIG_PATH", config_path),
            ):
                saved = hermes_profiles.save_config(
                    {"profile": "quality", "context_size": 4096, "threads": 6}
                )
                loaded = hermes_profiles.load_config()
                raw = json.loads(config_path.read_text(encoding="utf-8"))

        self.assertEqual(saved, loaded)
        self.assertEqual(raw["profile"], "quality")
        self.assertEqual(raw["threads"], 6)


if __name__ == "__main__":
    unittest.main()
