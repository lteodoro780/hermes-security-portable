from pathlib import Path

from hermes.config import choose_profile
from hermes.database import HermesDB
from hermes.knowledge import KnowledgeBase, _chunks


def test_profiles():
    assert choose_profile(8, 8).name == "fast"
    assert choose_profile(16, 12).name == "balanced"
    assert choose_profile(32, 16).name == "quality"


def test_chunks_overlap():
    text = "A" * 3000
    parts = _chunks(text, size=1000, overlap=100)
    assert len(parts) >= 3
    assert all(parts)


def test_database_and_search(tmp_path: Path):
    db = HermesDB(tmp_path / "test.db")
    db.replace_document("manual.txt", "geral", "Manual", 1.0, [(None, "DNS resolve nomes e DHCP distribui endereços")])
    kb = KnowledgeBase(db)
    result = kb.search("DNS nomes")
    assert result
    assert result[0]["title"] == "Manual"
