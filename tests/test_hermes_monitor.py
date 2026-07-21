from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hermes import hermes_monitor  # noqa: E402


def metrics(
    cpu: float = 20,
    memory: float = 30,
    disk: float = 40,
    sent: float = 100,
    received: float = 200,
) -> dict[str, float | bool]:
    return {
        "available": True,
        "cpu_percent": cpu,
        "memory_percent": memory,
        "disk_percent": disk,
        "network_sent_bps": sent,
        "network_received_bps": received,
    }


class MonitorDatabaseTests(unittest.TestCase):
    def test_database_starts_with_safe_lightweight_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_monitor, "DB_PATH", Path(temp_dir) / "monitor.db"):
                config = hermes_monitor.load_monitor_config()
                summary = hermes_monitor.monitor_statistics()

        self.assertFalse(config["enabled"])
        self.assertEqual(config["interval_seconds"], 15)
        self.assertEqual(config["consecutive_samples"], 3)
        self.assertEqual(config["retention_hours"], 168)
        self.assertEqual(summary["sample_count"], 0)

    def test_configuration_validates_intervals_and_threshold_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_monitor, "DB_PATH", Path(temp_dir) / "monitor.db"):
                saved = hermes_monitor.save_monitor_config(
                    {
                        "interval_seconds": 30,
                        "cpu_warning": 75,
                        "cpu_critical": 90,
                    }
                )
                with self.assertRaises(hermes_monitor.MonitorError):
                    hermes_monitor.save_monitor_config(
                        {"memory_warning": 95, "memory_critical": 90}
                    )
                with self.assertRaises(hermes_monitor.MonitorError):
                    hermes_monitor.save_monitor_config({"interval_seconds": 1})

        self.assertEqual(saved["interval_seconds"], 30)
        self.assertEqual(saved["cpu_warning"], 75)

    def test_alert_requires_consecutive_samples_and_resolves_after_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_monitor, "DB_PATH", Path(temp_dir) / "monitor.db"):
                hermes_monitor.record_sample(metrics(cpu=95))
                hermes_monitor.record_sample(metrics(cpu=96))
                self.assertEqual(hermes_monitor.list_alerts(), [])
                hermes_monitor.record_sample(metrics(cpu=94))
                active = hermes_monitor.list_alerts()

                hermes_monitor.record_sample(metrics(cpu=20))
                hermes_monitor.record_sample(metrics(cpu=21))
                hermes_monitor.record_sample(metrics(cpu=22))
                resolved = hermes_monitor.list_alerts()

        self.assertEqual(active[0]["resource"], "cpu")
        self.assertEqual(active[0]["severity"], "critical")
        self.assertEqual(active[0]["status"], "active")
        self.assertEqual(resolved[0]["status"], "resolved")
        self.assertIsNotNone(resolved[0]["resolved_at"])

    def test_attention_can_be_acknowledged_and_escalated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_monitor, "DB_PATH", Path(temp_dir) / "monitor.db"):
                for _ in range(3):
                    hermes_monitor.record_sample(metrics(memory=86))
                attention = hermes_monitor.list_alerts()[0]
                acknowledged = hermes_monitor.acknowledge_alerts(attention["id"])
                for _ in range(3):
                    hermes_monitor.record_sample(metrics(memory=97))
                alerts = hermes_monitor.list_alerts()

        active = next(item for item in alerts if item["status"] == "active")
        previous = next(item for item in alerts if item["status"] == "resolved")
        self.assertEqual(acknowledged["acknowledged"], 1)
        self.assertEqual(active["severity"], "critical")
        self.assertEqual(previous["severity"], "attention")
        self.assertTrue(previous["acknowledged"])

    def test_sample_history_has_a_hard_row_cap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(hermes_monitor, "DB_PATH", Path(temp_dir) / "monitor.db"),
                patch.object(hermes_monitor, "MAX_SAMPLES", 3),
            ):
                for index in range(6):
                    hermes_monitor.record_sample(metrics(cpu=20 + index))
                samples = hermes_monitor.list_samples(100)

        self.assertEqual(len(samples), 3)
        self.assertEqual(samples[-1]["cpu_percent"], 25)

    def test_invalid_or_unavailable_metrics_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_monitor, "DB_PATH", Path(temp_dir) / "monitor.db"):
                with self.assertRaises(hermes_monitor.MonitorError):
                    hermes_monitor.record_sample({"available": False, "reason": "sem psutil"})
                with self.assertRaises(hermes_monitor.MonitorError):
                    hermes_monitor.record_sample(metrics(cpu=120))

    def test_clear_history_keeps_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_monitor, "DB_PATH", Path(temp_dir) / "monitor.db"):
                for _ in range(3):
                    hermes_monitor.record_sample(metrics(disk=97))
                cleared = hermes_monitor.clear_monitor_history()
                config = hermes_monitor.load_monitor_config()
                summary = hermes_monitor.monitor_statistics()

        self.assertEqual(cleared["samples_deleted"], 3)
        self.assertEqual(cleared["alerts_deleted"], 1)
        self.assertEqual(config["interval_seconds"], 15)
        self.assertEqual(summary["sample_count"], 0)


class MonitoringEngineTests(unittest.TestCase):
    def test_engine_collects_immediately_and_stops_cleanly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_monitor, "DB_PATH", Path(temp_dir) / "monitor.db"):
                engine = hermes_monitor.MonitoringEngine(sampler=lambda: metrics(cpu=33))
                started = engine.start()
                deadline = time.monotonic() + 1.5
                while not hermes_monitor.list_samples() and time.monotonic() < deadline:
                    time.sleep(0.02)
                payload = hermes_monitor.dashboard_payload(engine)
                stopped = engine.stop()
                config = hermes_monitor.load_monitor_config()

        self.assertTrue(started["running"])
        self.assertEqual(payload["latest"]["cpu_percent"], 33)
        self.assertFalse(stopped["running"])
        self.assertFalse(config["enabled"])

    def test_previously_authorised_monitor_can_resume_on_next_start(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_monitor, "DB_PATH", Path(temp_dir) / "monitor.db"):
                hermes_monitor.set_monitor_enabled(True)
                engine = hermes_monitor.MonitoringEngine(sampler=lambda: metrics(cpu=28))
                resumed = engine.start_if_enabled()
                engine.stop(persist_enabled=False)
                config = hermes_monitor.load_monitor_config()

        self.assertTrue(resumed["running"])
        self.assertTrue(config["enabled"])


if __name__ == "__main__":
    unittest.main()
