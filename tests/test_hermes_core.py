import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from hermes.config import choose_profile
from hermes.database import HermesDB
from hermes.knowledge import KnowledgeBase, _chunks


class HermesCoreCompatibilityTests(unittest.TestCase):
    def test_profiles(self) -> None:
        self.assertEqual(choose_profile(8, 8).name, "fast")
        self.assertEqual(choose_profile(16, 12).name, "balanced")
        self.assertEqual(choose_profile(32, 16).name, "quality")

    def test_chunks_overlap(self) -> None:
        text = "A" * 3000
        parts = _chunks(text, size=1000, overlap=100)
        self.assertGreaterEqual(len(parts), 3)
        self.assertTrue(all(parts))

    def test_database_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db = HermesDB(Path(temp_dir) / "test.db")
            db.replace_document(
                "manual.txt",
                "geral",
                "Manual",
                1.0,
                [(None, "DNS resolve nomes e DHCP distribui endereços")],
            )
            result = KnowledgeBase(db).search("DNS nomes")

        self.assertTrue(result)
        self.assertEqual(result[0]["title"], "Manual")


if __name__ == "__main__":
    unittest.main()
