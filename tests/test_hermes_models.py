from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hermes import hermes_models  # noqa: E402


class FakeResponse:
    def __init__(self, payload: bytes, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.stream = io.BytesIO(payload)
        self.headers = headers or {"Content-Length": str(len(payload))}
        self.status = status

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self.stream.read(size)

    def getcode(self) -> int:
        return self.status


class ModelDownloadTests(unittest.TestCase):
    def setUp(self) -> None:
        hermes_models._CANCEL_EVENT.clear()
        hermes_models._update_job(
            status="idle",
            profile=None,
            filename=None,
            downloaded_bytes=0,
            total_bytes=0,
            message="idle",
            started_at=None,
            completed_at=None,
        )

    def test_simulated_download_creates_valid_model(self) -> None:
        payload = b"GGUF" + (b"local-test" * 64)
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            with (
                patch.object(hermes_models, "MODELS_DIR", models_dir),
                patch.object(
                    hermes_models.urllib.request,
                    "urlopen",
                    return_value=FakeResponse(payload),
                ),
                patch.object(hermes_models, "save_config") as save,
            ):
                hermes_models._download_worker("fast")
                target = models_dir / hermes_models.PROFILE_DEFINITIONS["fast"]["model_file"]
                valid = hermes_models.valid_gguf(target)

        self.assertTrue(valid)
        self.assertEqual(hermes_models.download_snapshot()["status"], "completed")
        save.assert_called_once_with({"profile": "fast"})

    def test_invalid_profile_is_rejected_before_thread_starts(self) -> None:
        with self.assertRaises(ValueError):
            hermes_models.start_model_download("unknown")

    def test_partial_download_is_resumed(self) -> None:
        complete = b"GGUF" + (b"R" * 300)
        first_part = complete[:80]
        remaining = complete[80:]
        with tempfile.TemporaryDirectory() as temp_dir:
            models_dir = Path(temp_dir)
            filename = hermes_models.PROFILE_DEFINITIONS["balanced"]["model_file"]
            partial = models_dir / f"{filename}.part"
            partial.write_bytes(first_part)

            def fake_open(request: object, timeout: int) -> FakeResponse:
                self.assertEqual(request.get_header("Range"), f"bytes={len(first_part)}-")
                self.assertEqual(timeout, 60)
                return FakeResponse(
                    remaining,
                    status=206,
                    headers={
                        "Content-Length": str(len(remaining)),
                        "Content-Range": f"bytes {len(first_part)}-{len(complete)-1}/{len(complete)}",
                    },
                )

            with (
                patch.object(hermes_models, "MODELS_DIR", models_dir),
                patch.object(hermes_models.urllib.request, "urlopen", side_effect=fake_open),
                patch.object(hermes_models, "save_config"),
            ):
                hermes_models._download_worker("balanced")
                final = models_dir / filename
                content = final.read_bytes()

        self.assertEqual(content, complete)
        self.assertEqual(hermes_models.download_snapshot()["percent"], 100.0)


if __name__ == "__main__":
    unittest.main()
