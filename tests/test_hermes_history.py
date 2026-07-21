from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hermes import hermes_history  # noqa: E402


class ChatHistoryTests(unittest.TestCase):
    def test_history_round_trip_and_clear(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            history_path = directory / "chat-history.json"
            with (
                patch.object(hermes_history, "DATA_DIR", directory),
                patch.object(hermes_history, "CHAT_HISTORY_PATH", history_path),
            ):
                exchange = hermes_history.append_chat_exchange(
                    "Como verifico DNS?",
                    "Confira a configuração local.",
                    "deep",
                )
                loaded = hermes_history.load_chat_history()
                hermes_history.clear_chat_history()
                cleared = hermes_history.load_chat_history()

        self.assertEqual(len(exchange), 2)
        self.assertEqual(loaded[0]["role"], "user")
        self.assertEqual(loaded[1]["mode"], "deep")
        self.assertEqual(cleared, [])

    def test_history_discards_invalid_entries(self) -> None:
        cleaned = hermes_history._clean_message({"role": "system", "content": "segredo"})
        self.assertIsNone(cleaned)


if __name__ == "__main__":
    unittest.main()
