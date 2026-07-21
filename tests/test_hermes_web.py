from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hermes import hermes_incidents, hermes_knowledge, hermes_monitor, hermes_web  # noqa: E402


class FindingTests(unittest.TestCase):
    def test_system_findings_report_missing_metrics(self) -> None:
        findings = hermes_web.system_findings(
            {"metrics": {"available": False, "reason": "psutil ausente"}}
        )

        self.assertEqual(findings[0]["service"], "Telemetria")
        self.assertEqual(findings[0]["severity"], "attention")

    def test_system_findings_apply_resource_thresholds(self) -> None:
        findings = hermes_web.system_findings(
            {
                "metrics": {
                    "available": True,
                    "cpu": {"percent": 34},
                    "memory": {"percent": 86},
                    "disk": {"percent": 97},
                }
            }
        )

        by_service = {finding["service"]: finding for finding in findings}
        self.assertEqual(by_service["CPU"]["severity"], "normal")
        self.assertEqual(by_service["Memória"]["severity"], "attention")
        self.assertEqual(by_service["Disco"]["severity"], "critical")

    def test_network_findings_distinguish_success_and_failure(self) -> None:
        findings = hermes_web.network_findings(
            {
                "commands": [
                    {
                        "command": ["ipconfig", "/all"],
                        "returncode": 0,
                        "stdout": "Ethernet",
                        "stderr": "",
                    },
                    {
                        "command": ["ping", "127.0.0.1"],
                        "returncode": 1,
                        "stdout": "",
                        "stderr": "falha",
                    },
                ]
            }
        )

        self.assertEqual(findings[0]["severity"], "normal")
        self.assertEqual(findings[1]["severity"], "critical")


class AssistantTests(unittest.TestCase):
    def test_clean_model_answer_hides_thinking_block(self) -> None:
        answer = hermes_web._clean_model_answer(
            "<think>raciocínio interno</think>\nRecomendação objetiva."
        )
        self.assertEqual(answer, "Recomendação objetiva.")

    def test_deep_mode_uses_chat_endpoint_payload(self) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"choices": [{"message": {"content": "Resposta segura"}}]}
        ).encode("utf-8")
        with patch.object(hermes_web.urllib.request, "urlopen", return_value=response) as call:
            answer = hermes_web.ask_llama("Analise o DNS", mode="deep")

        request = call.call_args.args[0]
        payload = json.loads(request.data)
        self.assertEqual(answer, "Resposta segura")
        self.assertTrue(payload["messages"][-1]["content"].endswith("/think"))
        self.assertEqual(payload["max_tokens"], 900)

    def test_offline_benchmark_is_saved_as_hardware_estimate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_dir = Path(temp_dir)
            benchmark_path = data_dir / "benchmark.json"
            with (
                patch.object(hermes_web, "DATA_DIR", data_dir),
                patch.object(hermes_web, "BENCHMARK_PATH", benchmark_path),
                patch.object(hermes_web, "service_reachable", return_value=False),
            ):
                result = hermes_web.run_performance_benchmark()
                loaded = hermes_web.read_last_benchmark()
        self.assertEqual(result["kind"], "hardware")
        self.assertFalse(result["model_online"])
        self.assertEqual(loaded["timestamp"], result["timestamp"])


class ReportTests(unittest.TestCase):
    def test_report_round_trip_and_metadata(self) -> None:
        report = {
            "type": "system",
            "status": "completed",
            "completed_at": "2026-07-19T10:00:00-03:00",
            "summary": {"checks": 3, "alerts": 1},
            "findings": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_web, "REPORT_DIR", Path(temp_dir)):
                filename = hermes_web.save_report("system-diagnostic", report)
                loaded = hermes_web.read_report(filename)
                reports = hermes_web.list_reports()

        self.assertEqual(loaded, report)
        self.assertEqual(reports[0]["filename"], filename)
        self.assertEqual(reports[0]["type"], "system")
        self.assertEqual(reports[0]["summary"]["alerts"], 1)

    def test_report_reader_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.object(hermes_web, "REPORT_DIR", Path(temp_dir)):
                with self.assertRaises(ValueError):
                    hermes_web.read_report("../segredo.json")

    def test_full_diagnostic_creates_structured_report(self) -> None:
        info = {
            "metrics": {
                "available": True,
                "cpu": {"percent": 20},
                "memory": {"percent": 30},
                "disk": {"percent": 40},
            }
        }
        network = {
            "commands": [
                {"command": ["ping", "127.0.0.1"], "returncode": 0, "stdout": "ok", "stderr": ""}
            ]
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(hermes_web, "REPORT_DIR", Path(temp_dir)),
                patch.object(hermes_web, "system_info", return_value=info),
                patch.object(hermes_web, "network_diagnostics", return_value=network),
            ):
                result = hermes_web.run_diagnostic("full")

        self.assertEqual(result["diagnostic"]["type"], "full")
        self.assertEqual(result["diagnostic"]["summary"]["checks"], 4)
        self.assertTrue(result["report"]["filename"].endswith("full-diagnostic.json"))


class QuietHandler(hermes_web.HermesHandler):
    def log_message(self, format: str, *args: object) -> None:
        return


class HttpApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), QuietHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_health_endpoint_and_security_headers(self) -> None:
        with patch.object(hermes_web, "service_reachable", return_value=False):
            with urllib.request.urlopen(f"{self.base_url}/api/health", timeout=3) as response:
                data = json.loads(response.read())
                csp = response.headers["Content-Security-Policy"]

        self.assertTrue(data["ok"])
        self.assertEqual(data["version"], "0.8.0")
        self.assertFalse(data["llama_online"])
        self.assertIn("frame-ancestors 'none'", csp)

    def test_invalid_diagnostic_type_returns_400(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/diagnostics",
            data=json.dumps({"type": "arbitrary-shell"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request, timeout=3)

        self.assertEqual(raised.exception.code, 400)

    def test_invalid_chat_mode_returns_400(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps({"message": "Olá", "mode": "ilimitado"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request, timeout=3)

        self.assertEqual(raised.exception.code, 400)

    def test_successful_chat_is_persisted(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps({"message": "Verifique DNS", "mode": "quick"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        exchange = [
            {"role": "user", "content": "Verifique DNS"},
            {"role": "assistant", "content": "Resposta local"},
        ]
        with (
            patch.object(hermes_web, "service_reachable", return_value=True),
            patch.object(
                hermes_web,
                "_perform_llama_request",
                return_value=("Resposta local", {}, 0.2),
            ),
            patch.object(hermes_web, "append_chat_exchange", return_value=exchange) as append,
        ):
            with urllib.request.urlopen(request, timeout=3) as response:
                data = json.loads(response.read())
        self.assertEqual(data["answer"], "Resposta local")
        self.assertEqual(len(data["messages"]), 2)
        append.assert_called_once_with("Verifique DNS", "Resposta local", "quick")

    def test_configuration_endpoint_returns_profiles(self) -> None:
        mocked = {
            "config": {"profile": "auto", "default_mode": "quick"},
            "hardware": {"memory_total_gb": 16.0},
            "profiles": [{"id": "balanced", "installed": False}],
            "recommended_profile": "balanced",
            "runtime": {"active_profile": "balanced"},
        }
        with patch.object(hermes_web, "configuration_payload", return_value=mocked):
            with urllib.request.urlopen(f"{self.base_url}/api/config", timeout=3) as response:
                data = json.loads(response.read())

        self.assertEqual(data["recommended_profile"], "balanced")
        self.assertEqual(data["runtime"]["active_profile"], "balanced")

    def test_model_download_rejects_unknown_profile(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/models/download",
            data=json.dumps({"profile": "enorme"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(request, timeout=3)
        self.assertEqual(raised.exception.code, 400)

    def test_chat_history_can_be_cleared(self) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/api/chat/history",
            method="DELETE",
        )
        with patch.object(hermes_web, "clear_chat_history") as clear:
            with urllib.request.urlopen(request, timeout=3) as response:
                data = json.loads(response.read())
        self.assertTrue(data["ok"])
        clear.assert_called_once_with()

    def test_static_interface_is_served(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/", timeout=3) as response:
            body = response.read().decode("utf-8")

        self.assertIn("Central de diagnóstico defensivo", body)
        self.assertIn("Visão Geral", body)
        self.assertIn("Comparar evolução", body)
        self.assertIn("Plano seguro", body)
        self.assertIn("Base de Conhecimento Local", body)
        self.assertIn("Buscar sem IA", body)
        self.assertIn("Monitoramento Contínuo", body)
        self.assertIn("Iniciar monitoramento", body)
        self.assertIn("Central de Incidentes", body)
        self.assertIn("Backup e restauração", body)

    def test_incident_workflow_and_pdf_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "incidents.db"
            create_request = urllib.request.Request(
                f"{self.base_url}/api/incidents",
                data=json.dumps(
                    {
                        "title": "Revisar memória",
                        "severity": "attention",
                        "description": "Uso elevado observado.",
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with (
                patch.object(hermes_incidents, "DB_PATH", db_path),
                patch.object(
                    hermes_web,
                    "incident_snapshot",
                    return_value={"captured_at": "2026-07-21T10:00:00-03:00"},
                ),
            ):
                with urllib.request.urlopen(create_request, timeout=3) as response:
                    created = json.loads(response.read())
                incident_id = created["incident"]["id"]
                status_request = urllib.request.Request(
                    f"{self.base_url}/api/incidents/{incident_id}/status",
                    data=b'{"status":"investigating"}',
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(status_request, timeout=3) as response:
                    updated = json.loads(response.read())
                with urllib.request.urlopen(
                    f"{self.base_url}/api/incidents/{incident_id}/pdf", timeout=3
                ) as response:
                    pdf = response.read()
                    content_type = response.headers["Content-Type"]

        self.assertEqual(updated["incident"]["status"], "investigating")
        self.assertTrue(pdf.startswith(b"%PDF-1.4"))
        self.assertEqual(content_type, "application/pdf")

    def test_monitor_can_be_configured_started_and_stopped(self) -> None:
        sample = {
            "available": True,
            "cpu_percent": 35,
            "memory_percent": 45,
            "disk_percent": 55,
            "network_sent_bps": 120,
            "network_received_bps": 240,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "monitor.db"
            engine = hermes_monitor.MonitoringEngine(sampler=lambda: sample)
            config_request = urllib.request.Request(
                f"{self.base_url}/api/monitor/config",
                data=json.dumps({"interval_seconds": 30}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            start_request = urllib.request.Request(
                f"{self.base_url}/api/monitor/start",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            stop_request = urllib.request.Request(
                f"{self.base_url}/api/monitor/stop",
                data=b"{}",
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with (
                patch.object(hermes_monitor, "DB_PATH", db_path),
                patch.object(hermes_web, "_MONITOR_ENGINE", engine),
            ):
                with urllib.request.urlopen(config_request, timeout=3) as response:
                    configured = json.loads(response.read())
                with urllib.request.urlopen(start_request, timeout=3) as response:
                    started = json.loads(response.read())
                with urllib.request.urlopen(stop_request, timeout=3) as response:
                    stopped = json.loads(response.read())

        self.assertEqual(configured["config"]["interval_seconds"], 30)
        self.assertTrue(started["runtime"]["running"])
        self.assertFalse(stopped["runtime"]["running"])
        self.assertFalse(stopped["config"]["enabled"])

    def test_monitor_alerts_can_be_acknowledged_and_history_cleared(self) -> None:
        sample = {
            "available": True,
            "cpu_percent": 97,
            "memory_percent": 30,
            "disk_percent": 40,
            "network_sent_bps": 0,
            "network_received_bps": 0,
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "monitor.db"
            with patch.object(hermes_monitor, "DB_PATH", db_path):
                for _ in range(3):
                    hermes_monitor.record_sample(sample)
                acknowledge_request = urllib.request.Request(
                    f"{self.base_url}/api/monitor/alerts/acknowledge",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                clear_request = urllib.request.Request(
                    f"{self.base_url}/api/monitor/history",
                    method="DELETE",
                )
                with urllib.request.urlopen(acknowledge_request, timeout=3) as response:
                    acknowledged = json.loads(response.read())
                with urllib.request.urlopen(clear_request, timeout=3) as response:
                    cleared = json.loads(response.read())

        self.assertEqual(acknowledged["acknowledged"], 1)
        self.assertEqual(cleared["samples_deleted"], 3)
        self.assertEqual(cleared["alerts_deleted"], 1)

    def test_report_html_endpoint_returns_download(self) -> None:
        report = {
            "type": "system",
            "completed_at": "2026-07-19T10:00:00-03:00",
            "summary": {"checks": 1, "alerts": 0},
            "findings": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)
            filename = "safe-report.json"
            (report_dir / filename).write_text(json.dumps(report), encoding="utf-8")
            with patch.object(hermes_web, "REPORT_DIR", report_dir):
                with urllib.request.urlopen(
                    f"{self.base_url}/api/reports/{filename}/html", timeout=3
                ) as response:
                    body = response.read().decode("utf-8")
                    disposition = response.headers["Content-Disposition"]
        self.assertIn("Relatório system", body)
        self.assertIn("safe-report.html", disposition)

    def test_report_comparison_endpoint_works_without_ai(self) -> None:
        baseline = {
            "type": "system",
            "summary": {"checks": 1, "alerts": 0},
            "findings": [{"service": "CPU", "severity": "normal", "title": "CPU normal"}],
        }
        current = {
            "type": "system",
            "summary": {"checks": 1, "alerts": 1},
            "findings": [{"service": "CPU", "severity": "critical", "title": "CPU crítica"}],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)
            (report_dir / "antes.json").write_text(json.dumps(baseline), encoding="utf-8")
            (report_dir / "agora.json").write_text(json.dumps(current), encoding="utf-8")
            request = urllib.request.Request(
                f"{self.base_url}/api/reports/compare",
                data=json.dumps(
                    {"baseline": "antes.json", "current": "agora.json", "use_ai": False}
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with patch.object(hermes_web, "REPORT_DIR", report_dir):
                with urllib.request.urlopen(request, timeout=3) as response:
                    data = json.loads(response.read())

        self.assertEqual(data["comparison"]["summary"]["worsened"], 1)
        self.assertIsNone(data["ai_analysis"])

    def test_report_plan_endpoint_returns_only_read_only_commands(self) -> None:
        report = {
            "type": "system",
            "summary": {"checks": 1, "alerts": 1},
            "findings": [
                {
                    "service": "Memória",
                    "severity": "attention",
                    "title": "Uso elevado de memória",
                    "message": "Utilização atual em 86%.",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            report_dir = Path(temp_dir)
            (report_dir / "alerta.json").write_text(json.dumps(report), encoding="utf-8")
            request = urllib.request.Request(
                f"{self.base_url}/api/reports/plan",
                data=json.dumps({"filename": "alerta.json"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with patch.object(hermes_web, "REPORT_DIR", report_dir):
                with urllib.request.urlopen(request, timeout=3) as response:
                    data = json.loads(response.read())

        commands = data["plan"]["tasks"][0]["commands"]
        self.assertTrue(commands)
        self.assertTrue(all(command["read_only"] for command in commands))

    def test_report_baseline_can_be_saved_and_cleared(self) -> None:
        report = {"type": "system", "summary": {"alerts": 0}, "findings": []}
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_dir = root / "reports"
            report_dir.mkdir()
            baseline_path = root / "data" / "report-baseline.json"
            (report_dir / "referencia.json").write_text(json.dumps(report), encoding="utf-8")
            save_request = urllib.request.Request(
                f"{self.base_url}/api/reports/baseline",
                data=json.dumps({"filename": "referencia.json"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            delete_request = urllib.request.Request(
                f"{self.base_url}/api/reports/baseline",
                method="DELETE",
            )
            with (
                patch.object(hermes_web, "REPORT_DIR", report_dir),
                patch.object(hermes_web, "BASELINE_PATH", baseline_path),
            ):
                with urllib.request.urlopen(save_request, timeout=3) as response:
                    saved = json.loads(response.read())
                with urllib.request.urlopen(
                    f"{self.base_url}/api/reports/baseline", timeout=3
                ) as response:
                    loaded = json.loads(response.read())
                with urllib.request.urlopen(delete_request, timeout=3) as response:
                    cleared = json.loads(response.read())

        self.assertEqual(saved["baseline"]["filename"], "referencia.json")
        self.assertEqual(loaded["baseline"]["filename"], "referencia.json")
        self.assertTrue(cleared["ok"])
        self.assertFalse(baseline_path.exists())

    def test_knowledge_document_can_be_imported_searched_and_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "knowledge.db"
            import_request = urllib.request.Request(
                f"{self.base_url}/api/knowledge/documents",
                data=json.dumps(
                    {
                        "filename": "procedimento.md",
                        "content": "O servidor DNS interno responde no endereço 10.0.0.53.",
                        "collection_id": "general",
                    }
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            search_request = urllib.request.Request(
                f"{self.base_url}/api/knowledge/search",
                data=json.dumps({"query": "servidor DNS"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with patch.object(hermes_knowledge, "DB_PATH", db_path):
                with urllib.request.urlopen(import_request, timeout=3) as response:
                    imported = json.loads(response.read())
                with urllib.request.urlopen(search_request, timeout=3) as response:
                    searched = json.loads(response.read())
                document_id = imported["document"]["id"]
                delete_request = urllib.request.Request(
                    f"{self.base_url}/api/knowledge/documents/{document_id}",
                    method="DELETE",
                )
                with urllib.request.urlopen(delete_request, timeout=3) as response:
                    deleted = json.loads(response.read())

        self.assertEqual(imported["document"]["source_type"], "file")
        self.assertGreater(searched["search"]["result_count"], 0)
        self.assertEqual(searched["search"]["results"][0]["filename"], "procedimento.md")
        self.assertTrue(deleted["ok"])

    def test_knowledge_answer_returns_numbered_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "knowledge.db"
            with patch.object(hermes_knowledge, "DB_PATH", db_path):
                hermes_knowledge.add_document(
                    "portas.txt",
                    "O painel administrativo usa a porta TCP 8443.",
                )
                request = urllib.request.Request(
                    f"{self.base_url}/api/knowledge/ask",
                    data=json.dumps(
                        {"question": "Qual porta o painel utiliza?", "mode": "quick"}
                    ).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with (
                    patch.object(hermes_web, "service_reachable", return_value=True),
                    patch.object(
                        hermes_web,
                        "_perform_llama_request",
                        return_value=("A porta é 8443 [Fonte 1].", {}, 0.3),
                    ),
                ):
                    with urllib.request.urlopen(request, timeout=3) as response:
                        data = json.loads(response.read())

        self.assertIn("[Fonte 1]", data["answer"])
        self.assertEqual(data["sources"][0]["source_number"], 1)
        self.assertEqual(data["sources"][0]["filename"], "portas.txt")

    def test_report_can_be_added_to_knowledge_base(self) -> None:
        report = {
            "type": "network",
            "completed_at": "2026-07-19T10:00:00-03:00",
            "summary": {"checks": 1, "alerts": 1},
            "findings": [
                {
                    "service": "DNS",
                    "severity": "attention",
                    "title": "Resolvedor indisponível",
                    "message": "A consulta local falhou.",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_dir = root / "reports"
            report_dir.mkdir()
            db_path = root / "knowledge.db"
            (report_dir / "rede.json").write_text(json.dumps(report), encoding="utf-8")
            request = urllib.request.Request(
                f"{self.base_url}/api/knowledge/reports",
                data=json.dumps(
                    {"filename": "rede.json", "collection_id": "general"}
                ).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with (
                patch.object(hermes_web, "REPORT_DIR", report_dir),
                patch.object(hermes_knowledge, "DB_PATH", db_path),
            ):
                with urllib.request.urlopen(request, timeout=3) as response:
                    data = json.loads(response.read())

        self.assertEqual(data["document"]["source_type"], "report")
        self.assertEqual(data["document"]["metadata"]["report_filename"], "rede.json")


class HtmlExportTests(unittest.TestCase):
    def test_report_html_escapes_untrusted_content(self) -> None:
        report = {
            "type": "<script>alert(1)</script>",
            "summary": {"checks": "inválido"},
            "findings": [
                {
                    "title": "<img src=x onerror=alert(1)>",
                    "message": "texto & evidência",
                    "severity": "critical",
                }
            ],
        }
        exported = hermes_web.report_to_html("report.json", report)
        self.assertNotIn("<script>alert(1)</script>", exported)
        self.assertNotIn("<img src=x", exported)
        self.assertIn("&lt;script&gt;", exported)
        self.assertIn("texto &amp; evidência", exported)


if __name__ == "__main__":
    unittest.main()
