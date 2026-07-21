from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from hermes.hermes_intelligence import (  # noqa: E402
    build_remediation_plan,
    compare_reports,
    comparison_analysis_prompt,
    finding_key,
)


def finding(service: str, severity: str, title: str | None = None) -> dict[str, str]:
    return {
        "service": service,
        "severity": severity,
        "title": title or f"Estado de {service}",
        "message": f"Resultado para {service}",
    }


def report(findings: list[dict[str, str]], metrics: dict | None = None) -> dict:
    return {
        "type": "full",
        "completed_at": "2026-07-19T10:00:00-03:00",
        "summary": {
            "checks": len(findings),
            "alerts": sum(1 for item in findings if item["severity"] != "normal"),
        },
        "findings": findings,
        "data": {"system": {"metrics": metrics or {}}},
    }


class ComparisonTests(unittest.TestCase):
    def test_finding_identity_survives_title_and_accent_changes(self) -> None:
        before = finding("Memória", "normal", "Memória dentro do esperado")
        after = finding("MEMORIA", "critical", "Uso crítico de memória")
        self.assertEqual(finding_key(before), finding_key(after))

    def test_comparison_classifies_new_resolved_worse_and_better(self) -> None:
        baseline = report(
            [
                finding("CPU", "normal"),
                finding("Memória", "critical"),
                finding("Disco", "attention"),
                finding("Roteamento", "attention"),
            ]
        )
        current = report(
            [
                finding("CPU", "critical"),
                finding("Memória", "attention"),
                finding("Disco", "attention"),
                finding("Interfaces", "critical"),
            ]
        )

        result = compare_reports("antes.json", baseline, "agora.json", current)

        self.assertEqual(result["summary"]["status"], "mixed")
        self.assertEqual(result["summary"]["new"], 1)
        self.assertEqual(result["summary"]["resolved"], 1)
        self.assertEqual(result["summary"]["worsened"], 1)
        self.assertEqual(result["summary"]["improved"], 1)
        self.assertEqual(result["summary"]["unchanged"], 1)

    def test_comparison_calculates_resource_deltas(self) -> None:
        baseline = report(
            [finding("CPU", "normal")],
            {
                "cpu": {"percent": 20},
                "memory": {"percent": 60},
                "disk": {"percent": 70},
            },
        )
        current = report(
            [finding("CPU", "normal")],
            {
                "cpu": {"percent": 35.5},
                "memory": {"percent": 55},
                "disk": {"percent": 70},
            },
        )

        result = compare_reports("antes.json", baseline, "agora.json", current)
        metrics = {item["resource"]: item for item in result["metrics"]}

        self.assertEqual(metrics["CPU"]["delta"], 15.5)
        self.assertEqual(metrics["CPU"]["direction"], "higher")
        self.assertEqual(metrics["Memória"]["direction"], "lower")
        self.assertEqual(metrics["Disco"]["direction"], "stable")

    def test_prompt_prohibits_commands_and_unsupported_claims(self) -> None:
        result = compare_reports("antes.json", report([]), "agora.json", report([]))
        prompt = comparison_analysis_prompt(result)
        self.assertIn("não gere comandos", prompt.lower())
        self.assertIn("não invente evidências", prompt.lower())


class RemediationPlanTests(unittest.TestCase):
    def test_plan_prioritises_alerts_and_marks_every_command_read_only(self) -> None:
        source = report(
            [
                finding("Memória", "attention"),
                finding("CPU", "critical"),
                finding("Disco", "normal"),
            ]
        )

        plan = build_remediation_plan("relatorio.json", source, system_name="Windows")

        self.assertEqual(plan["summary"]["tasks"], 2)
        self.assertEqual(plan["tasks"][0]["priority"], "P1")
        self.assertEqual(plan["tasks"][1]["priority"], "P2")
        commands = [command for task in plan["tasks"] for command in task["commands"]]
        self.assertTrue(commands)
        self.assertTrue(all(command["read_only"] is True for command in commands))
        self.assertTrue(all(command["platform"] == "Windows PowerShell" for command in commands))

    def test_unknown_service_never_receives_an_arbitrary_command(self) -> None:
        source = report([finding("Serviço desconhecido", "critical")])
        plan = build_remediation_plan("relatorio.json", source, system_name="Windows")
        self.assertEqual(plan["tasks"][0]["commands"], [])

    def test_normal_report_requires_no_remediation(self) -> None:
        source = report([finding("CPU", "normal")])
        plan = build_remediation_plan("relatorio.json", source, system_name="Windows")
        self.assertEqual(plan["status"], "no_actions")
        self.assertEqual(plan["tasks"], [])


if __name__ == "__main__":
    unittest.main()
