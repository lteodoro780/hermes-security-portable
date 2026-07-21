from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hermes import hermes_incidents  # noqa: E402


def monitor_alert(alert_id: str = "alert-1") -> dict[str, object]:
    return {
        "id": alert_id,
        "resource": "cpu",
        "severity": "critical",
        "status": "active",
        "title": "CPU em nível crítico",
        "message": "CPU permaneceu acima do limite.",
        "threshold": 92.0,
        "peak_value": 98.0,
    }


class IncidentTests(unittest.TestCase):
    def test_manual_incident_has_timeline_and_safe_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_incidents, "DB_PATH", Path(temp_dir) / "incidents.db"):
                incident = hermes_incidents.create_incident(
                    "Revisar comportamento",
                    "attention",
                    "Observação local",
                )

        self.assertEqual(incident["status"], "open")
        self.assertEqual(incident["timeline"][0]["type"], "created")
        self.assertGreaterEqual(len(incident["checklist"]), 4)
        self.assertTrue(all("excluir" not in item["label"].lower() for item in incident["checklist"]))

    def test_monitor_alert_creates_only_one_active_incident(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_incidents, "DB_PATH", Path(temp_dir) / "incidents.db"):
                first = hermes_incidents.create_from_alert(
                    monitor_alert(), {"metrics": {"cpu_percent": 98}}
                )
                duplicate = hermes_incidents.create_from_alert(
                    monitor_alert(), {"metrics": {"cpu_percent": 99}}
                )

        self.assertFalse(first["duplicate"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(first["id"], duplicate["id"])

    def test_status_notes_and_checklist_are_recorded_in_timeline(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_incidents, "DB_PATH", Path(temp_dir) / "incidents.db"):
                incident = hermes_incidents.create_incident("Teste")
                incident = hermes_incidents.update_status(incident["id"], "investigating")
                incident = hermes_incidents.add_note(incident["id"], "Evidência revisada.")
                incident = hermes_incidents.set_checklist_item(
                    incident["id"], incident["checklist"][0]["id"], True
                )
                incident = hermes_incidents.update_status(incident["id"], "resolved")

        event_types = [event["type"] for event in incident["timeline"]]
        self.assertIn("status", event_types)
        self.assertIn("note", event_types)
        self.assertIn("checklist", event_types)
        self.assertEqual(incident["status"], "resolved")
        self.assertIsNotNone(incident["resolved_at"])

    def test_resolved_alert_can_open_a_new_incident(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_incidents, "DB_PATH", Path(temp_dir) / "incidents.db"):
                first = hermes_incidents.create_from_alert(monitor_alert(), {})
                hermes_incidents.update_status(first["id"], "resolved")
                second = hermes_incidents.create_from_alert(monitor_alert(), {})

        self.assertNotEqual(first["id"], second["id"])

    def test_html_and_pdf_exports_escape_or_encode_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_incidents, "DB_PATH", Path(temp_dir) / "incidents.db"):
                incident = hermes_incidents.create_incident(
                    "<script>alert(1)</script>", description="Teste (acentuação)"
                )
                html_report = hermes_incidents.incident_html(incident)
                pdf_report = hermes_incidents.incident_pdf(incident)

        self.assertNotIn("<script>alert(1)</script>", html_report)
        self.assertIn("&lt;script&gt;", html_report)
        self.assertTrue(pdf_report.startswith(b"%PDF-1.4"))
        self.assertIn(b"xref", pdf_report)
        self.assertTrue(pdf_report.rstrip().endswith(b"%%EOF"))

    def test_invalid_state_and_missing_incident_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_incidents, "DB_PATH", Path(temp_dir) / "incidents.db"):
                incident = hermes_incidents.create_incident("Teste")
                with self.assertRaises(hermes_incidents.IncidentError):
                    hermes_incidents.update_status(incident["id"], "deleted")
                with self.assertRaises(FileNotFoundError):
                    hermes_incidents.get_incident("missing")


if __name__ == "__main__":
    unittest.main()
