"""Comparação determinística e planos defensivos para relatórios HERMES.

Este módulo nunca executa comandos. Ele apenas monta comparações e sugere
verificações locais de leitura que a pessoa pode revisar e copiar.
"""

from __future__ import annotations

import json
import platform
import re
import unicodedata
from typing import Any


SEVERITY_RANK = {"normal": 0, "attention": 1, "critical": 2}
SEVERITY_LABEL = {"normal": "normal", "attention": "atenção", "critical": "crítico"}


def _normalise(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"\s+", " ", text).strip().casefold()


def _severity(finding: dict[str, Any]) -> str:
    value = str(finding.get("severity", "attention")).lower()
    return value if value in SEVERITY_RANK else "attention"


def finding_key(finding: dict[str, Any]) -> str:
    """Retorna uma identidade estável para o mesmo teste entre relatórios.

    Os diagnósticos nativos geram no máximo um achado por serviço. Usar o
    serviço permite reconhecer, por exemplo, CPU normal que passou a crítica,
    embora o título do achado tenha mudado.
    """

    service = _normalise(finding.get("service"))
    if service:
        return f"service:{service}"
    title = _normalise(finding.get("title"))
    return f"title:{title or 'achado-sem-identidade'}"


def _findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    values = report.get("findings", [])
    return [item for item in values if isinstance(item, dict)] if isinstance(values, list) else []


def _finding_map(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    mapped: dict[str, dict[str, Any]] = {}
    duplicates: dict[str, int] = {}
    for finding in _findings(report):
        base_key = finding_key(finding)
        count = duplicates.get(base_key, 0)
        duplicates[base_key] = count + 1
        key = base_key if count == 0 else f"{base_key}#{count + 1}"
        mapped[key] = finding
    return mapped


def _safe_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _alert_count(report: dict[str, Any]) -> int:
    summary = report.get("summary")
    if isinstance(summary, dict):
        try:
            return max(int(summary.get("alerts", 0)), 0)
        except (TypeError, ValueError):
            pass
    return sum(1 for finding in _findings(report) if _severity(finding) != "normal")


def _report_identity(filename: str, report: dict[str, Any]) -> dict[str, Any]:
    return {
        "filename": filename,
        "type": str(report.get("type", "legacy")),
        "completed_at": report.get("completed_at"),
        "alerts": _alert_count(report),
        "checks": len(_findings(report)),
    }


def _system_metrics(report: dict[str, Any]) -> dict[str, Any]:
    data = report.get("data")
    if not isinstance(data, dict):
        return {}
    system = data.get("system")
    if not isinstance(system, dict):
        return {}
    metrics = system.get("metrics")
    return metrics if isinstance(metrics, dict) else {}


def _metric_changes(baseline: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    before_metrics = _system_metrics(baseline)
    after_metrics = _system_metrics(current)
    definitions = (
        ("CPU", "cpu", "percent"),
        ("Memória", "memory", "percent"),
        ("Disco", "disk", "percent"),
    )
    changes: list[dict[str, Any]] = []
    for label, section, field in definitions:
        before_block = before_metrics.get(section, {})
        after_block = after_metrics.get(section, {})
        before = _safe_number(before_block.get(field)) if isinstance(before_block, dict) else None
        after = _safe_number(after_block.get(field)) if isinstance(after_block, dict) else None
        if before is None or after is None:
            continue
        delta = round(after - before, 1)
        direction = "stable" if abs(delta) < 0.1 else "higher" if delta > 0 else "lower"
        changes.append(
            {
                "resource": label,
                "before": round(before, 1),
                "after": round(after, 1),
                "delta": delta,
                "unit": "%",
                "direction": direction,
            }
        )
    return changes


def compare_reports(
    baseline_filename: str,
    baseline: dict[str, Any],
    current_filename: str,
    current: dict[str, Any],
) -> dict[str, Any]:
    """Compara dois relatórios sem depender de IA ou de acesso à rede."""

    baseline_map = _finding_map(baseline)
    current_map = _finding_map(current)
    changes: dict[str, list[Any]] = {
        "new": [],
        "resolved": [],
        "worsened": [],
        "improved": [],
        "unchanged": [],
        "added_checks": [],
        "removed_checks": [],
    }

    for key in sorted(baseline_map.keys() | current_map.keys()):
        before = baseline_map.get(key)
        after = current_map.get(key)
        if before is None and after is not None:
            target = "added_checks" if _severity(after) == "normal" else "new"
            changes[target].append(after)
            continue
        if after is None and before is not None:
            target = "removed_checks" if _severity(before) == "normal" else "resolved"
            changes[target].append(before)
            continue
        if before is None or after is None:
            continue
        before_rank = SEVERITY_RANK[_severity(before)]
        after_rank = SEVERITY_RANK[_severity(after)]
        pair = {"before": before, "after": after}
        if after_rank > before_rank:
            changes["worsened"].append(pair)
        elif after_rank < before_rank:
            changes["improved"].append(pair)
        else:
            changes["unchanged"].append(pair)

    negative = len(changes["new"]) + len(changes["worsened"])
    positive = len(changes["resolved"]) + len(changes["improved"])
    if negative and positive:
        status = "mixed"
    elif negative:
        status = "worsened"
    elif positive:
        status = "improved"
    else:
        status = "stable"

    baseline_alerts = _alert_count(baseline)
    current_alerts = _alert_count(current)
    warnings: list[str] = []
    if baseline.get("type") != current.get("type"):
        warnings.append(
            "Os relatórios são de tipos diferentes; itens adicionados ou removidos podem refletir escopos distintos."
        )

    return {
        "schema_version": 1,
        "baseline": _report_identity(baseline_filename, baseline),
        "current": _report_identity(current_filename, current),
        "summary": {
            "status": status,
            "new": len(changes["new"]),
            "resolved": len(changes["resolved"]),
            "worsened": len(changes["worsened"]),
            "improved": len(changes["improved"]),
            "unchanged": len(changes["unchanged"]),
            "added_checks": len(changes["added_checks"]),
            "removed_checks": len(changes["removed_checks"]),
            "alert_delta": current_alerts - baseline_alerts,
        },
        "changes": changes,
        "metrics": _metric_changes(baseline, current),
        "warnings": warnings,
    }


READ_ONLY_COMMANDS: dict[str, dict[str, tuple[tuple[str, str], ...]]] = {
    "cpu": {
        "windows": (("Processos com maior tempo de CPU", "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name,CPU,Id"),),
        "linux": (("Processos com maior uso de CPU", "ps -eo pid,comm,%cpu --sort=-%cpu | head"),),
    },
    "memoria": {
        "windows": (("Processos com maior uso de memória", "Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 10 Name,@{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB)}}"),),
        "linux": (("Processos com maior uso de memória", "ps -eo pid,comm,%mem --sort=-%mem | head"),),
    },
    "disco": {
        "windows": (("Uso das unidades", "Get-PSDrive -PSProvider FileSystem | Select-Object Name,Used,Free"),),
        "linux": (("Uso dos sistemas de arquivos", "df -h"),),
    },
    "interfaces": {
        "windows": (("Configuração das interfaces", "Get-NetIPConfiguration"),),
        "linux": (("Configuração das interfaces", "ip address show"),),
    },
    "roteamento": {
        "windows": (("Rotas com menor métrica", "Get-NetRoute | Sort-Object RouteMetric | Select-Object -First 30"),),
        "linux": (("Tabela de rotas", "ip route show"),),
    },
    "vizinhanca arp": {
        "windows": (("Vizinhos de rede conhecidos", "Get-NetNeighbor | Select-Object -First 50"),),
        "linux": (("Vizinhos de rede conhecidos", "ip neigh show"),),
    },
    "pilha tcp/ip": {
        "windows": (("Teste local da pilha TCP/IP", "Test-NetConnection 127.0.0.1"),),
        "linux": (("Teste local da pilha TCP/IP", "ping -c 2 127.0.0.1"),),
    },
    "telemetria": {
        "windows": (("Versão instalada do psutil", 'python -c "import psutil; print(psutil.__version__)"'),),
        "linux": (("Versão instalada do psutil", 'python -c "import psutil; print(psutil.__version__)"'),),
    },
}


def _platform_name(system_name: str | None) -> str:
    detected = _normalise(system_name or platform.system())
    return "windows" if detected.startswith("win") else "linux"


def _commands_for(service: Any, system_name: str | None) -> list[dict[str, Any]]:
    platform_name = _platform_name(system_name)
    definitions = READ_ONLY_COMMANDS.get(_normalise(service), {}).get(platform_name, ())
    return [
        {
            "label": label,
            "command": command,
            "platform": "Windows PowerShell" if platform_name == "windows" else "Linux shell",
            "read_only": True,
        }
        for label, command in definitions
    ]


def build_remediation_plan(
    filename: str,
    report: dict[str, Any],
    system_name: str | None = None,
) -> dict[str, Any]:
    """Monta um plano revisável, sem executar ou autorizar alterações."""

    actionable = [finding for finding in _findings(report) if _severity(finding) != "normal"]
    actionable.sort(key=lambda item: SEVERITY_RANK[_severity(item)], reverse=True)
    tasks: list[dict[str, Any]] = []
    for index, finding in enumerate(actionable, start=1):
        severity = _severity(finding)
        service = str(finding.get("service") or "Verificação")
        commands = _commands_for(service, system_name)
        priority = "P1" if severity == "critical" else "P2"
        tasks.append(
            {
                "id": f"H-{index:02d}",
                "priority": priority,
                "severity": severity,
                "service": service,
                "title": str(finding.get("title") or f"Revisar {service}"),
                "reason": str(finding.get("message") or "O diagnóstico encontrou um item que precisa de revisão."),
                "goal": f"Confirmar a causa do alerta de {service} e registrar evidências antes de qualquer alteração.",
                "steps": [
                    "Revise o achado e confirme se a coleta representa o estado atual.",
                    "Execute, se desejar, apenas as verificações de leitura listadas abaixo.",
                    "Registre o resultado e peça aprovação antes de alterar serviços ou configurações.",
                    "Depois de uma correção autorizada, execute novamente o mesmo diagnóstico.",
                ],
                "verification": [
                    f"O novo relatório deve classificar {service} como normal ou com severidade menor.",
                    "Compare o novo relatório com a referência e confirme que não surgiram regressões.",
                ],
                "commands": commands,
            }
        )

    return {
        "schema_version": 1,
        "filename": filename,
        "status": "ready" if tasks else "no_actions",
        "generated_for": report.get("completed_at"),
        "safety_notice": (
            "O HERMES não executa correções. Os comandos exibidos são verificações de leitura; "
            "revise-os antes de copiar e não aplique mudanças sem autorização."
        ),
        "summary": {
            "tasks": len(tasks),
            "p1": sum(1 for task in tasks if task["priority"] == "P1"),
            "p2": sum(1 for task in tasks if task["priority"] == "P2"),
            "commands": sum(len(task["commands"]) for task in tasks),
        },
        "tasks": tasks,
    }


def comparison_analysis_prompt(comparison: dict[str, Any]) -> str:
    """Cria contexto reduzido para a interpretação opcional pela IA local."""

    changes = comparison.get("changes", {})
    compact: dict[str, Any] = {
        "referência": comparison.get("baseline"),
        "atual": comparison.get("current"),
        "resumo": comparison.get("summary"),
        "métricas": comparison.get("metrics"),
        "avisos": comparison.get("warnings"),
        "mudanças": {},
    }
    if isinstance(changes, dict):
        for category in ("new", "resolved", "worsened", "improved"):
            values = changes.get(category, [])
            compact["mudanças"][category] = values[:12] if isinstance(values, list) else []
    return (
        "Interprete a comparação defensiva abaixo em português simples. Explique: "
        "(1) o que melhorou, (2) o que piorou, (3) o que merece prioridade e "
        "(4) quais confirmações humanas são necessárias. Não invente evidências, "
        "não gere comandos, não diga que executou ações e não recomende mudanças automáticas.\n\n"
        + json.dumps(compact, ensure_ascii=False, indent=2)[:24_000]
    )
