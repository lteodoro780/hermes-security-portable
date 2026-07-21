#!/usr/bin/env python3
"""Servidor web local do HERMES Security Portable.

Mantém a interface e os diagnósticos restritos ao computador local por padrão.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import html
import json
import os
import platform
import re
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

try:
    from .hermes_paths import APP_DIR as BASE_DIR, DATA_DIR, REPORT_DIR, WEB_DIR
except ImportError:  # Execução direta pelo inicializador no Windows.
    from hermes_paths import APP_DIR as BASE_DIR, DATA_DIR, REPORT_DIR, WEB_DIR

try:
    from .hermes_profiles import configuration_payload, hardware_info, load_config, save_config
except ImportError:  # Execução direta pelo inicializador no Windows.
    from hermes_profiles import configuration_payload, hardware_info, load_config, save_config

try:
    from . import hermes_backup, hermes_incidents, hermes_knowledge, hermes_monitor
    from .hermes_history import append_chat_exchange, clear_chat_history, load_chat_history
    from .hermes_intelligence import (
        build_remediation_plan,
        compare_reports,
        comparison_analysis_prompt,
    )
    from .hermes_models import cancel_model_download, model_manager_payload, start_model_download
except ImportError:
    import hermes_backup
    import hermes_incidents
    import hermes_knowledge
    import hermes_monitor
    from hermes_history import append_chat_exchange, clear_chat_history, load_chat_history
    from hermes_intelligence import build_remediation_plan, compare_reports, comparison_analysis_prompt
    from hermes_models import cancel_model_download, model_manager_payload, start_model_download

try:
    import psutil
except ImportError:  # A interface continua funcional, mas sem telemetria detalhada.
    psutil = None


APP_NAME = "HERMES Security Portable"
APP_VERSION = "0.8.0"
HOST = os.getenv("HERMES_WEB_HOST", "127.0.0.1")
PORT = int(os.getenv("HERMES_WEB_PORT", "8765"))
LLAMA_URL = os.getenv(
    "HERMES_LLAMACPP_URL",
    "http://127.0.0.1:8080/v1/chat/completions",
)
MAX_REQUEST_BYTES = 64 * 1024
MAX_KNOWLEDGE_REQUEST_BYTES = 5 * 1024 * 1024
MAX_BACKUP_REQUEST_BYTES = hermes_backup.MAX_BACKUP_BYTES * 4 // 3 + 1024 * 1024

BENCHMARK_PATH = DATA_DIR / "last-benchmark.json"
BASELINE_PATH = DATA_DIR / "report-baseline.json"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

_NET_SAMPLE: tuple[float, int, int] | None = None
_NET_LOCK = threading.Lock()
_MONITOR_ENGINE: hermes_monitor.MonitoringEngine | None = None
_MONITOR_ENGINE_LOCK = threading.Lock()


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def monitor_engine() -> hermes_monitor.MonitoringEngine:
    """Retorna a única thread de monitoramento permitida pelo processo."""

    global _MONITOR_ENGINE
    if _MONITOR_ENGINE is not None:
        return _MONITOR_ENGINE
    with _MONITOR_ENGINE_LOCK:
        if _MONITOR_ENGINE is None:
            _MONITOR_ENGINE = hermes_monitor.MonitoringEngine()
    return _MONITOR_ENGINE


def json_response(handler: SimpleHTTPRequestHandler, payload: Any, status: int = 200) -> None:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def html_response(
    handler: SimpleHTTPRequestHandler,
    content: str,
    filename: str,
    status: int = 200,
) -> None:
    body = content.encode("utf-8")
    safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name) or "hermes-report.html"
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Content-Disposition", f'attachment; filename="{safe_filename}"')
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


def binary_response(
    handler: SimpleHTTPRequestHandler,
    content: bytes,
    filename: str,
    content_type: str,
    status: int = 200,
) -> None:
    safe_filename = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name) or "hermes-download.bin"
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(content)))
    handler.send_header("Content-Disposition", f'attachment; filename="{safe_filename}"')
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(content)


def safe_run(command: list[str], timeout: int = 25) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            encoding="utf-8",
            errors="replace",
        )
        return {
            "command": command,
            "returncode": proc.returncode,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except FileNotFoundError:
        return {
            "command": command,
            "returncode": 127,
            "stdout": "",
            "stderr": f"Comando não encontrado: {command[0]}",
        }
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "returncode": 124,
            "stdout": "",
            "stderr": f"Timeout após {timeout}s",
        }


def _network_rate() -> dict[str, float]:
    global _NET_SAMPLE

    if psutil is None:
        return {"sent_bytes_per_second": 0.0, "received_bytes_per_second": 0.0}

    counters = psutil.net_io_counters()
    current = (time.monotonic(), counters.bytes_sent, counters.bytes_recv)
    sent_rate = 0.0
    received_rate = 0.0

    with _NET_LOCK:
        if _NET_SAMPLE is not None:
            elapsed = max(current[0] - _NET_SAMPLE[0], 0.001)
            sent_rate = max((current[1] - _NET_SAMPLE[1]) / elapsed, 0.0)
            received_rate = max((current[2] - _NET_SAMPLE[2]) / elapsed, 0.0)
        _NET_SAMPLE = current

    return {
        "sent_bytes_per_second": round(sent_rate, 2),
        "received_bytes_per_second": round(received_rate, 2),
    }


def system_metrics() -> dict[str, Any]:
    if psutil is None:
        return {
            "available": False,
            "reason": "Instale as dependências com: pip install -r requirements.txt",
            "cpu": None,
            "memory": None,
            "disk": None,
            "network": None,
        }

    memory = psutil.virtual_memory()
    disk_root = BASE_DIR.anchor or os.sep
    disk = psutil.disk_usage(disk_root)
    network = _network_rate()

    detected_hardware = hardware_info()
    return {
        "available": True,
        "cpu": {
            "percent": round(psutil.cpu_percent(interval=0.1), 1),
            "logical_cores": psutil.cpu_count(logical=True),
            "physical_cores": detected_hardware["physical_cores"],
            "name": detected_hardware["cpu_name"],
            "frequency_mhz": round(psutil.cpu_freq().current, 0) if psutil.cpu_freq() else None,
        },
        "memory": {
            "percent": round(memory.percent, 1),
            "used_bytes": memory.used,
            "total_bytes": memory.total,
        },
        "disk": {
            "percent": round(disk.percent, 1),
            "used_bytes": disk.used,
            "total_bytes": disk.total,
            "root": disk_root,
        },
        "network": network,
    }


def system_info() -> dict[str, Any]:
    return {
        "timestamp": now(),
        "hostname": socket.gethostname(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "python": platform.python_version(),
        "hardware": hardware_info(),
        "metrics": system_metrics(),
    }


def incident_snapshot() -> dict[str, Any]:
    """Captura contexto agregado sem processos, arquivos ou pacotes de rede."""

    info = system_info()
    hardware = info.get("hardware") if isinstance(info.get("hardware"), dict) else {}
    return {
        "captured_at": now(),
        "system": {
            "hostname": info.get("hostname"),
            "system": info.get("system"),
            "release": info.get("release"),
            "machine": info.get("machine"),
        },
        "hardware": {
            "cpu_name": hardware.get("cpu_name"),
            "physical_cores": hardware.get("physical_cores"),
            "logical_cores": hardware.get("logical_cores"),
            "memory_total_gb": hardware.get("memory_total_gb"),
            "graphics_name": hardware.get("graphics_name"),
        },
        "metrics": info.get("metrics", {}),
        "monitor_sample": hermes_monitor.latest_sample(),
    }


def network_diagnostics() -> dict[str, Any]:
    if platform.system().lower().startswith("win"):
        commands = [
            ["ipconfig", "/all"],
            ["route", "print"],
            ["arp", "-a"],
            ["ping", "-n", "2", "127.0.0.1"],
        ]
    else:
        commands = [
            ["ip", "address"],
            ["ip", "route"],
            ["arp", "-a"],
            ["ping", "-c", "2", "127.0.0.1"],
        ]
    return {"timestamp": now(), "commands": [safe_run(command) for command in commands]}


def _finding(
    service: str,
    severity: str,
    title: str,
    message: str,
    evidence: str = "",
) -> dict[str, str]:
    return {
        "service": service,
        "severity": severity,
        "title": title,
        "message": message,
        "evidence": evidence[:1200],
        "detected_at": now(),
    }


def system_findings(info: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []
    metrics = info.get("metrics", {})
    if not metrics.get("available"):
        findings.append(
            _finding(
                "Telemetria",
                "attention",
                "Métricas detalhadas indisponíveis",
                str(metrics.get("reason", "Dependência psutil não encontrada.")),
            )
        )
        return findings

    checks = (
        ("CPU", metrics.get("cpu", {}).get("percent"), 90, 80),
        ("Memória", metrics.get("memory", {}).get("percent"), 92, 82),
        ("Disco", metrics.get("disk", {}).get("percent"), 95, 85),
    )
    for service, value, critical_limit, warning_limit in checks:
        if value is None:
            continue
        if value >= critical_limit:
            findings.append(
                _finding(
                    service,
                    "critical",
                    f"Uso crítico de {service.lower()}",
                    f"Utilização atual em {value:.1f}%.",
                )
            )
        elif value >= warning_limit:
            findings.append(
                _finding(
                    service,
                    "attention",
                    f"Uso elevado de {service.lower()}",
                    f"Utilização atual em {value:.1f}%.",
                )
            )
        else:
            findings.append(
                _finding(
                    service,
                    "normal",
                    f"{service} dentro do esperado",
                    f"Utilização atual em {value:.1f}%.",
                )
            )
    return findings


def network_findings(data: dict[str, Any]) -> list[dict[str, str]]:
    labels = {
        "ipconfig": "Interfaces",
        "ip": "Interfaces",
        "route": "Roteamento",
        "arp": "Vizinhança ARP",
        "ping": "Pilha TCP/IP",
    }
    findings: list[dict[str, str]] = []
    for result in data.get("commands", []):
        command = result.get("command") or ["desconhecido"]
        executable = Path(str(command[0])).name.lower()
        service = labels.get(executable, executable.upper())
        returncode = int(result.get("returncode", 1))
        evidence = result.get("stderr") or result.get("stdout") or "Sem saída."
        if returncode == 0:
            findings.append(
                _finding(
                    service,
                    "normal",
                    f"Verificação de {service.lower()} concluída",
                    "O comando local foi executado com sucesso.",
                    evidence,
                )
            )
        else:
            severity = "critical" if executable == "ping" else "attention"
            findings.append(
                _finding(
                    service,
                    severity,
                    f"Falha na verificação de {service.lower()}",
                    f"O comando terminou com código {returncode}.",
                    evidence,
                )
            )
    return findings


def _report_summary(findings: list[dict[str, str]]) -> dict[str, int]:
    alerts = [finding for finding in findings if finding.get("severity") != "normal"]
    return {
        "checks": len(findings),
        "alerts": len(alerts),
        "critical": sum(1 for finding in findings if finding.get("severity") == "critical"),
        "attention": sum(1 for finding in findings if finding.get("severity") == "attention"),
    }


def save_report(name: str, data: dict[str, Any]) -> str:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}-{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path.name


def report_metadata(path: Path, data: dict[str, Any] | None = None) -> dict[str, Any]:
    if data is None:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
    stat = path.stat()
    return {
        "filename": path.name,
        "type": data.get("type", "legacy"),
        "status": data.get("status", "completed"),
        "started_at": data.get("started_at"),
        "completed_at": data.get("completed_at")
        or datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
        "duration_seconds": data.get("duration_seconds"),
        "summary": data.get("summary", {}),
        "findings": data.get("findings", []),
        "size_bytes": stat.st_size,
    }


def list_reports(limit: int = 50) -> list[dict[str, Any]]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(REPORT_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    return [report_metadata(path) for path in files[:limit]]


def read_report(filename: str) -> dict[str, Any]:
    if not filename or Path(filename).name != filename or not filename.endswith(".json"):
        raise ValueError("Nome de relatório inválido.")
    path = (REPORT_DIR / filename).resolve()
    if path.parent != REPORT_DIR.resolve() or not path.is_file():
        raise FileNotFoundError(filename)
    return json.loads(path.read_text(encoding="utf-8"))


def read_report_baseline() -> dict[str, Any] | None:
    try:
        saved = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
        filename = str(saved.get("filename", "")) if isinstance(saved, dict) else ""
        report = read_report(filename)
        metadata = report_metadata(REPORT_DIR / filename, report)
        metadata["set_at"] = saved.get("set_at")
        return metadata
    except (OSError, ValueError, FileNotFoundError, json.JSONDecodeError):
        return None


def save_report_baseline(filename: str) -> dict[str, Any]:
    report = read_report(filename)
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    saved = {"filename": filename, "set_at": now()}
    temporary = BASELINE_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(BASELINE_PATH)
    metadata = report_metadata(REPORT_DIR / filename, report)
    metadata["set_at"] = saved["set_at"]
    return metadata


def clear_report_baseline() -> None:
    BASELINE_PATH.unlink(missing_ok=True)


def report_analysis_prompt(filename: str, report: dict[str, Any]) -> str:
    findings = []
    for finding in report.get("findings", [])[:20]:
        findings.append(
            {
                "serviço": str(finding.get("service", ""))[:120],
                "severidade": str(finding.get("severity", ""))[:40],
                "título": str(finding.get("title", ""))[:240],
                "mensagem": str(finding.get("message", ""))[:800],
                "evidência": str(finding.get("evidence", ""))[:800],
            }
        )
    context = {
        "arquivo": filename,
        "tipo": report.get("type"),
        "concluído_em": report.get("completed_at"),
        "resumo": report.get("summary", {}),
        "achados": findings,
    }
    return (
        "Analise o relatório defensivo abaixo. Entregue: (1) resumo simples, "
        "(2) itens por prioridade, (3) próximos passos seguros, "
        "(4) o que precisa de confirmação humana. Não invente evidências, "
        "não recomende exploração ofensiva e não diga que executou ações.\n\n"
        + json.dumps(context, ensure_ascii=False, indent=2)[:24_000]
    )


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def report_to_html(filename: str, report: dict[str, Any]) -> str:
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    findings = report.get("findings", []) if isinstance(report.get("findings"), list) else []
    finding_blocks: list[str] = []
    labels = {"normal": "Normal", "attention": "Atenção", "critical": "Crítico"}
    for finding in findings:
        severity = str(finding.get("severity", "attention"))
        safe_severity = severity if severity in labels else "attention"
        evidence = str(finding.get("evidence", "")).strip()
        evidence_html = (
            f"<details><summary>Evidência coletada</summary><pre>{html.escape(evidence)}</pre></details>"
            if evidence
            else ""
        )
        finding_blocks.append(
            "<article class=\"finding\">"
            f"<div><h2>{html.escape(str(finding.get('title') or finding.get('service') or 'Achado'))}</h2>"
            f"<span class=\"badge {safe_severity}\">{labels[safe_severity]}</span></div>"
            f"<p>{html.escape(str(finding.get('message') or 'Sem detalhes adicionais.'))}</p>"
            f"{evidence_html}</article>"
        )
    if not finding_blocks:
        finding_blocks.append("<p class=\"empty\">Nenhum achado estruturado neste relatório.</p>")
    raw_json = html.escape(json.dumps(report, ensure_ascii=False, indent=2))
    report_type = html.escape(str(report.get("type", "Diagnóstico")))
    completed = html.escape(str(report.get("completed_at", "—")))
    safe_filename = html.escape(filename)
    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Relatório HERMES — {report_type}</title><style>
:root{{color-scheme:dark;--bg:#07111f;--panel:#0e1e31;--line:#263c55;--text:#edf5ff;--muted:#9aabc0;--accent:#39d1ff;--ok:#2ddb88;--warn:#f5b82e;--bad:#ff5d73}}
*{{box-sizing:border-box}}body{{max-width:1000px;margin:0 auto;padding:38px 22px 70px;color:var(--text);background:var(--bg);font:15px/1.55 "Segoe UI",Arial,sans-serif}}
header{{padding-bottom:22px;border-bottom:1px solid var(--line)}}h1{{margin:4px 0;font-size:32px}}header p,.meta,.empty{{color:var(--muted)}}.eyebrow{{color:var(--accent);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.12em}}
.stats{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:22px 0}}.stat,.finding,details.raw{{padding:17px;border:1px solid var(--line);border-radius:12px;background:var(--panel)}}.stat span{{display:block;color:var(--muted);font-size:11px}}.stat strong{{font-size:24px}}
.finding{{margin:12px 0}}.finding>div{{display:flex;align-items:center;justify-content:space-between;gap:12px}}.finding h2{{margin:0;font-size:16px}}.finding p{{margin:10px 0 0;color:#c8d5e5}}.badge{{padding:4px 9px;border-radius:999px;font-size:10px;font-weight:700;text-transform:uppercase}}.badge.normal{{color:var(--ok);background:#12392c}}.badge.attention{{color:var(--warn);background:#3a3017}}.badge.critical{{color:var(--bad);background:#3b1e28}}
details{{margin-top:12px}}summary{{color:var(--accent);cursor:pointer}}pre{{max-height:420px;overflow:auto;padding:13px;border-radius:8px;background:#050b13;color:#c6d6e8;white-space:pre-wrap;word-break:break-word;font:11px/1.55 Consolas,monospace}}footer{{margin-top:28px;color:var(--muted);font-size:11px}}@media(max-width:620px){{.stats{{grid-template-columns:repeat(2,1fr)}}}}
</style></head><body>
<header><span class="eyebrow">HERMES Security Portable {APP_VERSION}</span><h1>Relatório {report_type}</h1><p>{safe_filename}</p><p class="meta">Concluído em {completed}</p></header>
<section class="stats"><div class="stat"><span>Verificações</span><strong>{_safe_int(summary.get('checks'), len(findings))}</strong></div><div class="stat"><span>Alertas</span><strong>{_safe_int(summary.get('alerts'))}</strong></div><div class="stat"><span>Críticos</span><strong>{_safe_int(summary.get('critical'))}</strong></div><div class="stat"><span>Atenção</span><strong>{_safe_int(summary.get('attention'))}</strong></div></section>
<main>{''.join(finding_blocks)}</main><details class="raw"><summary>Dados brutos do relatório</summary><pre>{raw_json}</pre></details>
<footer>Gerado localmente pelo HERMES. Revise as evidências antes de aplicar qualquer alteração.</footer></body></html>"""


def run_diagnostic(diagnostic_type: str) -> dict[str, Any]:
    allowed = {"system", "network", "full"}
    if diagnostic_type not in allowed:
        raise ValueError("Tipo de diagnóstico inválido.")

    started_clock = time.monotonic()
    started_at = now()
    data: dict[str, Any] = {}
    findings: list[dict[str, str]] = []

    if diagnostic_type in {"system", "full"}:
        info = system_info()
        data["system"] = info
        findings.extend(system_findings(info))
    if diagnostic_type in {"network", "full"}:
        network = network_diagnostics()
        data["network"] = network
        findings.extend(network_findings(network))

    diagnostic = {
        "schema_version": 1,
        "type": diagnostic_type,
        "status": "completed",
        "started_at": started_at,
        "completed_at": now(),
        "duration_seconds": round(time.monotonic() - started_clock, 2),
        "summary": _report_summary(findings),
        "findings": findings,
        "data": data,
    }
    filename = save_report(f"{diagnostic_type}-diagnostic", diagnostic)
    return {"diagnostic": diagnostic, "report": report_metadata(REPORT_DIR / filename, diagnostic)}


def service_reachable(url: str, timeout: float = 0.4) -> bool:
    parsed = urlparse(url)
    if not parsed.hostname:
        return False
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        with socket.create_connection((parsed.hostname, port), timeout=timeout):
            return True
    except OSError:
        return False


def health_payload() -> dict[str, Any]:
    configuration = configuration_payload()
    monitoring = monitor_engine().status()
    return {
        "ok": True,
        "app": APP_NAME,
        "version": APP_VERSION,
        "web": f"http://{HOST}:{PORT}",
        "host": HOST,
        "port": PORT,
        "llama_url": LLAMA_URL,
        "llama_online": service_reachable(LLAMA_URL),
        "metrics_available": psutil is not None,
        "monitor_available": monitoring["available"],
        "monitor_running": monitoring["running"],
        "profile": configuration["runtime"]["active_profile"],
        "model": configuration["runtime"]["active_model"],
        "response_mode": configuration["config"]["default_mode"],
        "timestamp": now(),
    }


def _clean_model_answer(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    if "</think>" in text.lower():
        text = re.split(r"</think>", text, flags=re.IGNORECASE)[-1].strip()
    return text


def _llama_request_payload(prompt: str, mode: str, token_limit: int) -> dict[str, Any]:
    safe_mode = mode if mode in {"quick", "deep"} else "quick"
    mode_switch = "/think" if safe_mode == "deep" else "/no_think"
    system_prompt = (
        "Você é o HERMES, assistente local de infraestrutura de TI e segurança defensiva. "
        "Responda em português do Brasil, de forma objetiva, segura e acionável. "
        "Não invente resultados de diagnóstico e destaque quando uma verificação humana for necessária."
    )
    legacy_endpoint = urlparse(LLAMA_URL).path.rstrip("/").endswith("completion")
    if legacy_endpoint:
        return {
            "prompt": f"{system_prompt}\n\nUsuário: {prompt}\n{mode_switch}\n\nHERMES:",
            "n_predict": token_limit,
            "temperature": 0.4 if safe_mode == "quick" else 0.6,
            "stop": ["</s>"],
        }
    return {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{prompt}\n\n{mode_switch}"},
        ],
        "max_tokens": token_limit,
        "temperature": 0.4 if safe_mode == "quick" else 0.6,
        "stream": False,
    }


def _perform_llama_request(
    prompt: str,
    mode: str = "quick",
    max_tokens: int | None = None,
) -> tuple[str, dict[str, Any], float]:
    safe_mode = mode if mode in {"quick", "deep"} else "quick"
    token_limit = max_tokens or (900 if safe_mode == "deep" else 500)
    payload = _llama_request_payload(prompt, safe_mode, token_limit)
    request = urllib.request.Request(
        LLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=300 if safe_mode == "deep" else 180) as response:
        raw = response.read().decode("utf-8", errors="replace")
    elapsed = time.monotonic() - started
    parsed = json.loads(raw)
    choices = parsed.get("choices") or []
    if choices and isinstance(choices[0], dict):
        message = choices[0].get("message") or {}
        content = message.get("content") if isinstance(message, dict) else None
        answer = content or choices[0].get("text")
    else:
        answer = parsed.get("content") or parsed.get("response") or raw
    cleaned = _clean_model_answer(answer) or "A IA concluiu a análise sem retornar texto."
    return cleaned, parsed, elapsed


def ask_llama(prompt: str, mode: str = "quick", max_tokens: int | None = None) -> str:
    try:
        answer, _parsed, _elapsed = _perform_llama_request(prompt, mode, max_tokens)
        return answer
    except urllib.error.URLError as exc:
        return (
            "Não consegui conectar no llama.cpp server.\n"
            f"URL: {LLAMA_URL}\nErro: {exc}\n\n"
            "Inicie: scripts/windows/01-iniciar-servidor-ia.bat"
        )
    except Exception as exc:
        return f"Erro ao consultar IA local: {exc}"


def _save_benchmark(result: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = BENCHMARK_PATH.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(BENCHMARK_PATH)


def read_last_benchmark() -> dict[str, Any] | None:
    try:
        payload = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _performance_grade(tokens_per_second: float) -> tuple[str, str]:
    if tokens_per_second >= 12:
        return "excellent", "Excelente para uso local"
    if tokens_per_second >= 7:
        return "good", "Boa velocidade para uso diário"
    if tokens_per_second >= 3:
        return "usable", "Utilizável; respostas profundas podem demorar"
    return "slow", "Lento; considere o perfil Rápido"


def _hardware_benchmark() -> dict[str, Any]:
    block = (b"HERMES-local-benchmark-" * 45_591)[: 1024 * 1024]
    rounds = 96
    digest = b""
    started = time.monotonic()
    for index in range(rounds):
        digest = hashlib.sha256(block + digest + index.to_bytes(2, "little")).digest()
    elapsed = max(time.monotonic() - started, 0.001)
    throughput = round((len(block) * rounds / (1024**2)) / elapsed, 1)
    configuration = configuration_payload()
    hardware = configuration["hardware"]
    result = {
        "timestamp": now(),
        "kind": "hardware",
        "model_online": False,
        "duration_seconds": round(elapsed, 3),
        "cpu_throughput_mb_s": throughput,
        "tokens_per_second": None,
        "grade": "estimated",
        "grade_label": "Estimativa de hardware concluída",
        "recommended_profile": configuration["recommended_profile"],
        "recommended_threads": hardware["recommended_threads"],
        "message": (
            "A IA está offline; o HERMES avaliou CPU e memória. "
            "Execute novamente com o modelo online para medir tokens por segundo."
        ),
    }
    _save_benchmark(result)
    return result


def run_performance_benchmark() -> dict[str, Any]:
    if not service_reachable(LLAMA_URL):
        return _hardware_benchmark()
    prompt = (
        "Escreva um checklist técnico defensivo com exatamente cinco itens curtos "
        "para verificar conectividade local."
    )
    answer, parsed, elapsed = _perform_llama_request(prompt, mode="quick", max_tokens=96)
    usage = parsed.get("usage") if isinstance(parsed.get("usage"), dict) else {}
    timings = parsed.get("timings") if isinstance(parsed.get("timings"), dict) else {}
    completion_tokens = int(
        usage.get("completion_tokens")
        or timings.get("predicted_n")
        or max(len(answer.split()), 1)
    )
    measured = timings.get("predicted_per_second")
    tokens_per_second = round(
        float(measured) if measured else completion_tokens / max(elapsed, 0.001),
        2,
    )
    grade, grade_label = _performance_grade(tokens_per_second)
    configuration = configuration_payload()
    result = {
        "timestamp": now(),
        "kind": "model",
        "model_online": True,
        "model": configuration["runtime"]["active_model"],
        "profile": configuration["runtime"]["active_profile"],
        "duration_seconds": round(elapsed, 2),
        "completion_tokens": completion_tokens,
        "tokens_per_second": tokens_per_second,
        "grade": grade,
        "grade_label": grade_label,
        "recommended_profile": configuration["recommended_profile"],
        "recommended_threads": configuration["hardware"]["recommended_threads"],
        "message": "Medição realizada diretamente no modelo local ativo.",
    }
    _save_benchmark(result)
    return result


class HermesHandler(SimpleHTTPRequestHandler):
    server_version = f"HERMES/{APP_VERSION}"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; frame-ancestors 'none'",
        )
        super().end_headers()

    def _read_json_body(self, max_bytes: int = MAX_REQUEST_BYTES) -> dict[str, Any]:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Content-Length inválido.") from exc
        if content_length < 0:
            raise ValueError("Content-Length inválido.")
        if content_length > max_bytes:
            limit_mb = max_bytes / (1024 * 1024)
            label = f"{limit_mb:g} MB" if limit_mb >= 1 else f"{max_bytes // 1024} KB"
            raise OverflowError(f"Requisição excede o limite de {label}.")
        raw = self.rfile.read(content_length).decode("utf-8", errors="replace")
        try:
            return json.loads(raw) if raw else {}
        except json.JSONDecodeError as exc:
            raise ValueError("JSON inválido.") from exc

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            json_response(self, health_payload())
            return
        if path == "/api/system":
            json_response(self, system_info())
            return
        if path == "/api/config":
            json_response(self, configuration_payload())
            return
        if path == "/api/chat/history":
            json_response(self, {"messages": load_chat_history(), "timestamp": now()})
            return
        if path == "/api/models":
            json_response(self, model_manager_payload())
            return
        if path == "/api/benchmark":
            json_response(self, {"benchmark": read_last_benchmark(), "timestamp": now()})
            return
        if path == "/api/monitor":
            query = parse_qs(parsed.query)
            sample_limit = _safe_int((query.get("sample_limit") or [180])[0], 180)
            alert_limit = _safe_int((query.get("alert_limit") or [100])[0], 100)
            json_response(
                self,
                hermes_monitor.dashboard_payload(
                    monitor_engine(),
                    sample_limit=sample_limit,
                    alert_limit=alert_limit,
                ),
            )
            return
        if path == "/api/monitor/samples":
            query = parse_qs(parsed.query)
            limit = _safe_int((query.get("limit") or [180])[0], 180)
            json_response(
                self,
                {"samples": hermes_monitor.list_samples(limit), "timestamp": now()},
            )
            return
        if path == "/api/monitor/alerts":
            query = parse_qs(parsed.query)
            limit = _safe_int((query.get("limit") or [100])[0], 100)
            status = str((query.get("status") or [""])[0]).strip() or None
            try:
                alerts = hermes_monitor.list_alerts(limit, status=status)
            except hermes_monitor.MonitorError as exc:
                json_response(self, {"error": str(exc)}, status=400)
                return
            json_response(self, {"alerts": alerts, "timestamp": now()})
            return
        if path == "/api/incidents":
            query = parse_qs(parsed.query)
            limit = _safe_int((query.get("limit") or [100])[0], 100)
            status = str((query.get("status") or [""])[0]).strip() or None
            try:
                incidents = hermes_incidents.list_incidents(limit, status=status)
                summary = hermes_incidents.incident_summary()
            except hermes_incidents.IncidentError as exc:
                json_response(self, {"error": str(exc)}, status=400)
                return
            json_response(
                self,
                {"incidents": incidents, "summary": summary, "timestamp": now()},
            )
            return
        if path.startswith("/api/incidents/"):
            suffix = path.removeprefix("/api/incidents/")
            parts = [unquote(part) for part in suffix.split("/") if part]
            if not parts:
                json_response(self, {"error": "Incidente não informado."}, status=400)
                return
            try:
                incident = hermes_incidents.get_incident(parts[0])
                if len(parts) == 1:
                    json_response(self, {"incident": incident, "timestamp": now()})
                elif len(parts) == 2 and parts[1] == "html":
                    html_response(
                        self,
                        hermes_incidents.incident_html(incident),
                        f"HERMES-incidente-{incident['id'][:12]}.html",
                    )
                elif len(parts) == 2 and parts[1] == "pdf":
                    binary_response(
                        self,
                        hermes_incidents.incident_pdf(incident),
                        f"HERMES-incidente-{incident['id'][:12]}.pdf",
                        "application/pdf",
                    )
                else:
                    json_response(self, {"error": "Endpoint de incidente inválido."}, status=404)
            except FileNotFoundError as exc:
                json_response(self, {"error": f"Incidente não encontrado: {exc}"}, status=404)
            return
        if path == "/api/backup":
            try:
                filename, content, _manifest = hermes_backup.create_backup()
                binary_response(self, content, filename, "application/zip")
            except hermes_backup.BackupError as exc:
                json_response(self, {"error": str(exc)}, status=500)
            return
        if path == "/api/knowledge":
            json_response(
                self,
                {
                    "summary": hermes_knowledge.knowledge_summary(),
                    "collections": hermes_knowledge.list_collections(),
                    "documents": hermes_knowledge.list_documents(),
                    "timestamp": now(),
                },
            )
            return
        if path == "/api/knowledge/collections":
            json_response(
                self,
                {"collections": hermes_knowledge.list_collections(), "timestamp": now()},
            )
            return
        if path == "/api/knowledge/documents":
            query = parse_qs(parsed.query)
            collection_id = str((query.get("collection_id") or [""])[0]).strip() or None
            json_response(
                self,
                {
                    "documents": hermes_knowledge.list_documents(collection_id=collection_id),
                    "timestamp": now(),
                },
            )
            return
        if path.startswith("/api/knowledge/documents/"):
            document_id = unquote(path.removeprefix("/api/knowledge/documents/"))
            try:
                document = hermes_knowledge.get_document(document_id)
            except FileNotFoundError as exc:
                json_response(self, {"error": f"Documento não encontrado: {exc}"}, status=404)
                return
            json_response(self, {"document": document, "timestamp": now()})
            return
        if path == "/api/reports/baseline":
            json_response(self, {"baseline": read_report_baseline(), "timestamp": now()})
            return
        if path == "/api/reports":
            json_response(
                self,
                {
                    "reports": list_reports(),
                    "baseline": read_report_baseline(),
                    "timestamp": now(),
                },
            )
            return
        if path.startswith("/api/reports/") and path.endswith("/html"):
            filename = unquote(path.removeprefix("/api/reports/").removesuffix("/html"))
            try:
                report = read_report(filename)
                export_name = f"{Path(filename).stem}.html"
                html_response(self, report_to_html(filename, report), export_name)
            except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
                json_response(self, {"error": str(exc)}, status=404)
            return
        if path.startswith("/api/reports/"):
            filename = unquote(path.removeprefix("/api/reports/"))
            try:
                json_response(self, {"report": read_report(filename)})
            except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
                json_response(self, {"error": str(exc)}, status=404)
            return
        if path == "/api/network":  # Compatibilidade com a Web UI 0.2.
            result = run_diagnostic("network")
            json_response(
                self,
                {
                    "report": result["report"]["filename"],
                    "data": result["diagnostic"]["data"]["network"],
                    "findings": result["diagnostic"]["findings"],
                },
            )
            return
        return super().do_GET()

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            request_limit = (
                MAX_KNOWLEDGE_REQUEST_BYTES
                if path == "/api/knowledge/documents"
                else MAX_BACKUP_REQUEST_BYTES
                if path == "/api/backup/restore"
                else MAX_REQUEST_BYTES
            )
            payload = self._read_json_body(request_limit)
        except OverflowError as exc:
            json_response(self, {"error": str(exc)}, status=413)
            return
        except ValueError as exc:
            json_response(self, {"error": str(exc)}, status=400)
            return

        if path == "/api/monitor/start":
            try:
                monitor_engine().start()
                result = hermes_monitor.dashboard_payload(monitor_engine())
            except hermes_monitor.MonitorError as exc:
                json_response(self, {"error": str(exc)}, status=409)
                return
            json_response(self, result)
            return

        if path == "/api/monitor/stop":
            monitor_engine().stop()
            json_response(self, hermes_monitor.dashboard_payload(monitor_engine()))
            return

        if path == "/api/monitor/config":
            try:
                hermes_monitor.save_monitor_config(payload)
                result = hermes_monitor.dashboard_payload(monitor_engine())
            except hermes_monitor.MonitorError as exc:
                json_response(self, {"error": str(exc)}, status=400)
                return
            json_response(self, result)
            return

        if path == "/api/monitor/alerts/acknowledge":
            alert_id = str(payload.get("alert_id", "")).strip() or None
            try:
                acknowledged = hermes_monitor.acknowledge_alerts(alert_id)
            except FileNotFoundError as exc:
                json_response(self, {"error": f"Alerta não encontrado: {exc}"}, status=404)
                return
            json_response(
                self,
                {
                    "ok": True,
                    **acknowledged,
                    "alerts": hermes_monitor.list_alerts(),
                    "timestamp": now(),
                },
            )
            return

        if path == "/api/incidents":
            try:
                incident = hermes_incidents.create_incident(
                    payload.get("title"),
                    payload.get("severity", "attention"),
                    payload.get("description", ""),
                    snapshot=incident_snapshot(),
                )
            except (hermes_incidents.IncidentError, OSError) as exc:
                json_response(self, {"error": str(exc)}, status=400)
                return
            json_response(self, {"incident": incident, "timestamp": now()}, status=201)
            return

        if path == "/api/incidents/from-alert":
            alert_id = str(payload.get("alert_id", "")).strip()
            try:
                alert = hermes_monitor.get_alert(alert_id)
                incident = hermes_incidents.create_from_alert(alert, incident_snapshot())
            except FileNotFoundError as exc:
                json_response(self, {"error": f"Alerta não encontrado: {exc}"}, status=404)
                return
            except (hermes_incidents.IncidentError, OSError) as exc:
                json_response(self, {"error": str(exc)}, status=400)
                return
            response_status = 200 if incident.get("duplicate") else 201
            json_response(self, {"incident": incident, "timestamp": now()}, status=response_status)
            return

        if path.startswith("/api/incidents/"):
            suffix = path.removeprefix("/api/incidents/")
            parts = [unquote(part) for part in suffix.split("/") if part]
            if len(parts) < 2:
                json_response(self, {"error": "Ação de incidente inválida."}, status=404)
                return
            incident_id, action = parts[0], parts[1]
            try:
                if len(parts) == 2 and action == "status":
                    incident = hermes_incidents.update_status(incident_id, payload.get("status"))
                elif len(parts) == 2 and action == "note":
                    incident = hermes_incidents.add_note(incident_id, payload.get("message"))
                elif len(parts) == 3 and action == "checklist":
                    incident = hermes_incidents.set_checklist_item(
                        incident_id, parts[2], payload.get("completed")
                    )
                elif len(parts) == 2 and action == "analyze":
                    source = hermes_incidents.get_incident(incident_id)
                    if not service_reachable(LLAMA_URL):
                        json_response(
                            self,
                            {"error": "A IA local precisa estar online para analisar o incidente."},
                            status=503,
                        )
                        return
                    answer, _parsed, elapsed = _perform_llama_request(
                        hermes_incidents.analysis_prompt(source),
                        mode="deep",
                        max_tokens=1000,
                    )
                    incident = hermes_incidents.add_analysis(
                        incident_id, answer, duration_seconds=elapsed
                    )
                else:
                    json_response(self, {"error": "Ação de incidente inválida."}, status=404)
                    return
            except FileNotFoundError as exc:
                json_response(self, {"error": f"Incidente não encontrado: {exc}"}, status=404)
                return
            except hermes_incidents.IncidentError as exc:
                json_response(self, {"error": str(exc)}, status=400)
                return
            except urllib.error.URLError as exc:
                json_response(self, {"error": f"Falha ao consultar a IA local: {exc}"}, status=503)
                return
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                json_response(self, {"error": f"Análise não concluída: {exc}"}, status=502)
                return
            json_response(self, {"incident": incident, "timestamp": now()})
            return

        if path == "/api/backup/restore":
            encoded = str(payload.get("archive_base64", "")).strip()
            try:
                content = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error):
                json_response(self, {"error": "Conteúdo do backup inválido."}, status=400)
                return
            engine = monitor_engine()
            was_running = bool(engine.status().get("running"))
            engine.stop(persist_enabled=False)
            try:
                restored = hermes_backup.restore_backup(content)
            except hermes_backup.BackupError as exc:
                if was_running:
                    try:
                        engine.start(persist_enabled=False)
                    except hermes_monitor.MonitorError:
                        pass
                json_response(self, {"error": str(exc)}, status=400)
                return
            try:
                engine.start_if_enabled()
            except hermes_monitor.MonitorError:
                pass
            json_response(self, {"ok": True, **restored})
            return

        if path == "/api/knowledge/collections":
            try:
                collection = hermes_knowledge.create_collection(
                    payload.get("name"),
                    payload.get("description", ""),
                )
            except hermes_knowledge.KnowledgeError as exc:
                json_response(self, {"error": str(exc)}, status=400)
                return
            json_response(self, {"collection": collection, "timestamp": now()}, status=201)
            return

        if path == "/api/knowledge/documents":
            try:
                document = hermes_knowledge.add_document(
                    filename=payload.get("filename"),
                    content=payload.get("content"),
                    collection_id=str(
                        payload.get("collection_id") or hermes_knowledge.DEFAULT_COLLECTION_ID
                    ),
                    title=payload.get("title", ""),
                )
            except hermes_knowledge.KnowledgeError as exc:
                json_response(self, {"error": str(exc)}, status=400)
                return
            status = 200 if document.get("duplicate") else 201
            json_response(self, {"document": document, "timestamp": now()}, status=status)
            return

        if path == "/api/knowledge/reports":
            filename = str(payload.get("filename", "")).strip()
            try:
                report = read_report(filename)
                document = hermes_knowledge.add_report(
                    filename,
                    report,
                    collection_id=str(
                        payload.get("collection_id") or hermes_knowledge.DEFAULT_COLLECTION_ID
                    ),
                )
            except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
                json_response(self, {"error": str(exc)}, status=404)
                return
            except hermes_knowledge.KnowledgeError as exc:
                json_response(self, {"error": str(exc)}, status=400)
                return
            status = 200 if document.get("duplicate") else 201
            json_response(self, {"document": document, "timestamp": now()}, status=status)
            return

        if path in {"/api/knowledge/search", "/api/knowledge/ask"}:
            question = str(payload.get("query") or payload.get("question") or "").strip()
            try:
                search = hermes_knowledge.search_knowledge(
                    question,
                    collection_ids=payload.get("collection_ids"),
                    document_ids=payload.get("document_ids"),
                    limit=8 if path.endswith("/ask") else payload.get("limit", 10),
                )
            except (hermes_knowledge.KnowledgeError, TypeError, ValueError) as exc:
                json_response(self, {"error": str(exc)}, status=400)
                return
            if path.endswith("/search"):
                json_response(self, {"search": search, "timestamp": now()})
                return
            if not search["results"]:
                json_response(
                    self,
                    {"error": "Nenhuma fonte local relevante foi encontrada para a pergunta."},
                    status=404,
                )
                return
            if not service_reachable(LLAMA_URL):
                json_response(
                    self,
                    {"error": "A busca local funciona, mas a IA precisa estar online para responder."},
                    status=503,
                )
                return
            mode = str(payload.get("mode", "deep")).lower()
            if mode not in {"quick", "deep"}:
                json_response(self, {"error": "Modo de resposta inválido."}, status=400)
                return
            try:
                answer, _parsed, elapsed = _perform_llama_request(
                    hermes_knowledge.knowledge_answer_prompt(question, search["results"]),
                    mode=mode,
                    max_tokens=950 if mode == "deep" else 600,
                )
            except urllib.error.URLError as exc:
                json_response(self, {"error": f"Falha ao consultar a IA local: {exc}"}, status=503)
                return
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                json_response(self, {"error": f"Resposta inválida da IA local: {exc}"}, status=502)
                return
            sources = [
                {
                    "source_number": result["source_number"],
                    "document_id": result["document_id"],
                    "title": result["title"],
                    "filename": result["filename"],
                    "collection_name": result["collection_name"],
                    "source_type": result["source_type"],
                    "chunk_index": result["chunk_index"],
                    "snippet": result["snippet"],
                }
                for result in search["results"]
            ]
            json_response(
                self,
                {
                    "answer": answer,
                    "question": question,
                    "sources": sources,
                    "mode": mode,
                    "duration_seconds": round(elapsed, 2),
                    "timestamp": now(),
                },
            )
            return

        if path == "/api/chat":
            message = str(payload.get("message", "")).strip()
            if not message:
                json_response(self, {"error": "Campo message é obrigatório"}, status=400)
                return
            requested_mode = str(payload.get("mode") or load_config()["default_mode"]).lower()
            if requested_mode not in {"quick", "deep"}:
                json_response(self, {"error": "Modo de resposta inválido"}, status=400)
                return
            if not service_reachable(LLAMA_URL):
                json_response(
                    self,
                    {"error": "A IA local está offline. Inicie ou instale o modelo primeiro."},
                    status=503,
                )
                return
            try:
                answer, _parsed, _elapsed = _perform_llama_request(
                    message,
                    mode=requested_mode,
                )
                exchange = append_chat_exchange(message, answer, requested_mode)
            except urllib.error.URLError as exc:
                json_response(self, {"error": f"Falha ao consultar a IA local: {exc}"}, status=503)
                return
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                json_response(self, {"error": f"Resposta inválida da IA local: {exc}"}, status=502)
                return
            json_response(
                self,
                {
                    "answer": answer,
                    "mode": requested_mode,
                    "messages": exchange,
                    "timestamp": now(),
                },
            )
            return

        if path == "/api/reports/baseline":
            filename = str(payload.get("filename", "")).strip()
            try:
                baseline = save_report_baseline(filename)
            except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
                json_response(self, {"error": str(exc)}, status=404)
                return
            json_response(self, {"baseline": baseline, "timestamp": now()})
            return

        if path == "/api/reports/compare":
            baseline_filename = str(payload.get("baseline", "")).strip()
            current_filename = str(payload.get("current", "")).strip()
            if baseline_filename == current_filename:
                json_response(self, {"error": "Escolha dois relatórios diferentes."}, status=400)
                return
            try:
                baseline_report = read_report(baseline_filename)
                current_report = read_report(current_filename)
            except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
                json_response(self, {"error": str(exc)}, status=404)
                return
            comparison = compare_reports(
                baseline_filename,
                baseline_report,
                current_filename,
                current_report,
            )
            ai_analysis = None
            if payload.get("use_ai") is True:
                if not service_reachable(LLAMA_URL):
                    json_response(
                        self,
                        {"error": "A IA local precisa estar online para interpretar a comparação."},
                        status=503,
                    )
                    return
                try:
                    answer, _parsed, elapsed = _perform_llama_request(
                        comparison_analysis_prompt(comparison),
                        mode="deep",
                        max_tokens=900,
                    )
                    ai_analysis = {
                        "analysis": answer,
                        "mode": "deep",
                        "duration_seconds": round(elapsed, 2),
                    }
                except urllib.error.URLError as exc:
                    json_response(self, {"error": f"Falha ao consultar a IA local: {exc}"}, status=503)
                    return
                except (OSError, ValueError, json.JSONDecodeError) as exc:
                    json_response(self, {"error": f"Resposta inválida da IA local: {exc}"}, status=502)
                    return
            json_response(
                self,
                {
                    "comparison": comparison,
                    "ai_analysis": ai_analysis,
                    "timestamp": now(),
                },
            )
            return

        if path == "/api/reports/plan":
            filename = str(payload.get("filename", "")).strip()
            try:
                report = read_report(filename)
            except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
                json_response(self, {"error": str(exc)}, status=404)
                return
            json_response(
                self,
                {
                    "plan": build_remediation_plan(filename, report),
                    "timestamp": now(),
                },
            )
            return

        if path == "/api/reports/analyze":
            filename = str(payload.get("filename", "")).strip()
            mode = str(payload.get("mode", "deep")).lower()
            if mode not in {"quick", "deep"}:
                json_response(self, {"error": "Modo de análise inválido"}, status=400)
                return
            if not service_reachable(LLAMA_URL):
                json_response(self, {"error": "A IA local precisa estar online para analisar."}, status=503)
                return
            try:
                report = read_report(filename)
            except (ValueError, FileNotFoundError, json.JSONDecodeError) as exc:
                json_response(self, {"error": str(exc)}, status=404)
                return
            try:
                answer, _parsed, elapsed = _perform_llama_request(
                    report_analysis_prompt(filename, report),
                    mode=mode,
                    max_tokens=1000 if mode == "deep" else 600,
                )
                json_response(
                    self,
                    {
                        "filename": filename,
                        "analysis": answer,
                        "mode": mode,
                        "duration_seconds": round(elapsed, 2),
                        "timestamp": now(),
                    },
                )
            except urllib.error.URLError as exc:
                json_response(self, {"error": f"Falha ao consultar a IA local: {exc}"}, status=503)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                json_response(self, {"error": f"Resposta inválida da IA local: {exc}"}, status=502)
            return

        if path == "/api/models/download":
            profile = str(payload.get("profile", "")).lower()
            try:
                json_response(self, {"download": start_model_download(profile)}, status=202)
            except ValueError as exc:
                json_response(self, {"error": str(exc)}, status=400)
            except RuntimeError as exc:
                json_response(self, {"error": str(exc)}, status=409)
            return

        if path == "/api/models/cancel":
            try:
                json_response(self, {"download": cancel_model_download()})
            except RuntimeError as exc:
                json_response(self, {"error": str(exc)}, status=409)
            return

        if path == "/api/benchmark":
            try:
                json_response(self, {"benchmark": run_performance_benchmark()})
            except urllib.error.URLError as exc:
                json_response(self, {"error": f"Falha no teste do modelo: {exc}"}, status=503)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                json_response(self, {"error": f"Teste não concluído: {exc}"}, status=500)
            return

        if path == "/api/config":
            allowed_keys = {"profile", "default_mode", "context_size", "threads", "gpu_layers"}
            updates = {key: payload[key] for key in allowed_keys if key in payload}
            if not updates:
                json_response(self, {"error": "Nenhuma configuração recebida"}, status=400)
                return
            before = load_config()
            saved = save_config(updates)
            restart_keys = {"profile", "context_size", "threads", "gpu_layers"}
            restart_required = any(
                before.get(key) != saved.get(key) for key in restart_keys
            )
            response = configuration_payload()
            response["restart_required"] = restart_required
            json_response(self, response)
            return

        if path == "/api/diagnostics":
            diagnostic_type = str(payload.get("type", "network")).strip().lower()
            try:
                json_response(self, run_diagnostic(diagnostic_type))
            except ValueError as exc:
                json_response(self, {"error": str(exc)}, status=400)
            return

        json_response(self, {"error": "Endpoint não encontrado"}, status=404)

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/monitor/history":
            cleared = hermes_monitor.clear_monitor_history()
            json_response(self, {"ok": True, **cleared, "timestamp": now()})
            return
        if path == "/api/knowledge":
            cleared = hermes_knowledge.clear_knowledge()
            json_response(self, {"ok": True, **cleared, "timestamp": now()})
            return
        if path.startswith("/api/incidents/"):
            incident_id = unquote(path.removeprefix("/api/incidents/"))
            if not incident_id or "/" in incident_id:
                json_response(self, {"error": "Incidente inválido."}, status=400)
                return
            try:
                deleted = hermes_incidents.delete_incident(incident_id)
            except FileNotFoundError as exc:
                json_response(self, {"error": f"Incidente não encontrado: {exc}"}, status=404)
                return
            json_response(self, {"ok": True, "deleted": deleted, "timestamp": now()})
            return
        if path.startswith("/api/knowledge/documents/"):
            document_id = unquote(path.removeprefix("/api/knowledge/documents/"))
            try:
                deleted = hermes_knowledge.delete_document(document_id)
            except FileNotFoundError as exc:
                json_response(self, {"error": f"Documento não encontrado: {exc}"}, status=404)
                return
            json_response(self, {"ok": True, "deleted": deleted, "timestamp": now()})
            return
        if path.startswith("/api/knowledge/collections/"):
            collection_id = unquote(path.removeprefix("/api/knowledge/collections/"))
            try:
                deleted = hermes_knowledge.delete_collection(collection_id)
            except FileNotFoundError as exc:
                json_response(self, {"error": f"Coleção não encontrada: {exc}"}, status=404)
                return
            except hermes_knowledge.KnowledgeError as exc:
                json_response(self, {"error": str(exc)}, status=400)
                return
            json_response(self, {"ok": True, **deleted, "timestamp": now()})
            return
        if path == "/api/chat/history":
            clear_chat_history()
            json_response(self, {"ok": True, "messages": [], "timestamp": now()})
            return
        if path == "/api/reports/baseline":
            clear_report_baseline()
            json_response(self, {"ok": True, "baseline": None, "timestamp": now()})
            return
        json_response(self, {"error": "Endpoint não encontrado"}, status=404)


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), HermesHandler)
    engine = monitor_engine()
    try:
        engine.start_if_enabled()
    except hermes_monitor.MonitorError as exc:
        print(f"[AVISO] Monitoramento contínuo não iniciado: {exc}")
    url = f"http://{HOST}:{PORT}"
    print("=" * 70)
    print(f"{APP_NAME} {APP_VERSION}")
    print(f"Web UI: {url}")
    print(f"llama.cpp: {LLAMA_URL}")
    print("CTRL+C para encerrar")
    print("=" * 70)
    if os.getenv("HERMES_OPEN_BROWSER", "1") == "1":
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nEncerrando...")
    finally:
        engine.stop(persist_enabled=False)
        server.server_close()


if __name__ == "__main__":
    main()
