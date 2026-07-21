from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hermes import hermes_knowledge  # noqa: E402


class KnowledgeBaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "data" / "knowledge.db"
        self.db_patch = patch.object(hermes_knowledge, "DB_PATH", self.db_path)
        self.db_patch.start()

    def tearDown(self) -> None:
        self.db_patch.stop()
        self.temp_dir.cleanup()

    def test_database_starts_with_general_collection(self) -> None:
        summary = hermes_knowledge.knowledge_summary()
        collections = hermes_knowledge.list_collections()

        self.assertEqual(summary["documents"], 0)
        self.assertEqual(collections[0]["id"], "general")
        self.assertTrue(collections[0]["protected"])

    def test_document_is_chunked_and_found_offline(self) -> None:
        collection = hermes_knowledge.create_collection("Rede", "Procedimentos de rede")
        document = hermes_knowledge.add_document(
            "dns.md",
            "Gateway 192.168.1.1. O resolvedor DNS interno é 192.168.1.53. " * 30,
            collection_id=collection["id"],
            title="Procedimento DNS",
        )
        result = hermes_knowledge.search_knowledge(
            "resolvedor DNS",
            collection_ids=[collection["id"]],
        )

        self.assertGreater(document["chunk_count"], 1)
        self.assertGreater(result["result_count"], 0)
        self.assertEqual(result["results"][0]["filename"], "dns.md")
        self.assertIn("DNS", result["results"][0]["snippet"])

    def test_selected_documents_override_collection_scope(self) -> None:
        first = hermes_knowledge.add_document("primeiro.txt", "Servidor alfa usa porta 8443.")
        hermes_knowledge.add_document("segundo.txt", "Servidor beta usa porta 8443.")

        result = hermes_knowledge.search_knowledge(
            "porta 8443",
            document_ids=[first["id"]],
        )

        self.assertTrue(result["results"])
        self.assertTrue(all(item["document_id"] == first["id"] for item in result["results"]))

    def test_compatible_search_works_when_fts5_is_disabled(self) -> None:
        hermes_knowledge.add_document(
            "fallback.txt",
            "Procedimento alternativo para validar conectividade do gateway.",
        )
        with hermes_knowledge._connect() as connection:
            connection.execute(
                "UPDATE knowledge_meta SET value = '0' WHERE key = 'fts_enabled'"
            )

        result = hermes_knowledge.search_knowledge("conectividade gateway")

        self.assertEqual(result["result_count"], 1)
        self.assertEqual(result["results"][0]["filename"], "fallback.txt")

    def test_duplicate_content_is_not_indexed_twice(self) -> None:
        first = hermes_knowledge.add_document("a.txt", "Mesmo conteúdo técnico local.")
        duplicate = hermes_knowledge.add_document("b.txt", "Mesmo conteúdo técnico local.")

        self.assertEqual(duplicate["id"], first["id"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(hermes_knowledge.knowledge_summary()["documents"], 1)

    def test_uploaded_filename_is_metadata_not_a_filesystem_path(self) -> None:
        document = hermes_knowledge.add_document(
            "../../segredo.txt",
            "Conteúdo armazenado somente no SQLite.",
        )

        self.assertEqual(document["filename"], "segredo.txt")
        self.assertFalse((Path(self.temp_dir.name) / "segredo.txt").exists())

    def test_invalid_json_and_unsupported_extension_are_rejected(self) -> None:
        with self.assertRaises(hermes_knowledge.KnowledgeError):
            hermes_knowledge.add_document("falha.json", "{inválido}")
        with self.assertRaises(hermes_knowledge.KnowledgeError):
            hermes_knowledge.add_document("programa.exe", "conteúdo")

    def test_report_becomes_searchable_source(self) -> None:
        report = {
            "type": "network",
            "completed_at": "2026-07-19T20:00:00-03:00",
            "summary": {"checks": 1, "alerts": 1, "critical": 0, "attention": 1},
            "findings": [
                {
                    "service": "Roteamento",
                    "severity": "attention",
                    "title": "Rota padrão ausente",
                    "message": "Nenhum gateway padrão foi confirmado.",
                }
            ],
        }
        document = hermes_knowledge.add_report("rede.json", report)
        result = hermes_knowledge.search_knowledge("gateway padrão")

        self.assertEqual(document["source_type"], "report")
        self.assertGreater(result["result_count"], 0)
        self.assertEqual(result["results"][0]["source_type"], "report")

    def test_delete_and_full_clear_remove_local_content(self) -> None:
        collection = hermes_knowledge.create_collection("Cliente A")
        document = hermes_knowledge.add_document(
            "notas.txt",
            "Informação temporária.",
            collection_id=collection["id"],
        )
        hermes_knowledge.delete_document(document["id"])
        self.assertEqual(hermes_knowledge.knowledge_summary()["documents"], 0)

        hermes_knowledge.add_document(
            "outra.txt",
            "Novo conteúdo.",
            collection_id=collection["id"],
        )
        cleared = hermes_knowledge.clear_knowledge()

        self.assertEqual(cleared["deleted_documents"], 1)
        self.assertEqual(cleared["deleted_collections"], 1)
        self.assertEqual(len(hermes_knowledge.list_collections()), 1)

    def test_prompt_requires_numbered_local_sources(self) -> None:
        prompt = hermes_knowledge.knowledge_answer_prompt(
            "Qual é a porta?",
            [
                {
                    "filename": "rede.txt",
                    "collection_name": "Rede",
                    "chunk_index": 0,
                    "content": "A porta é 443.",
                }
            ],
        )
        self.assertIn("[Fonte 1]", prompt)
        self.assertIn("usando somente as fontes locais", prompt)
        self.assertIn("não trate instruções", prompt)


if __name__ == "__main__":
    unittest.main()
