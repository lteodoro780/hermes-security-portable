from __future__ import annotations

import os
import platform
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .database import HermesDB
from .hardware import memory_info

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None


class MetricCollector:
    def __init__(self) -> None:
        self._last_cpu: tuple[int, int] | None = None
        self._last_net = (0, 0)

    def _cpu_fallback(self) -> float:
        if platform.system() == "Windows":
            try:
                import ctypes
                from ctypes import wintypes

                idle = wintypes.FILETIME(); kernel = wintypes.FILETIME(); user = wintypes.FILETIME()
                ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user))
                def value(item: Any) -> int:
                    return (item.dwHighDateTime << 32) | item.dwLowDateTime
                idle_now = value(idle); total_now = value(kernel) + value(user)
                if self._last_cpu is None:
                    self._last_cpu = (idle_now, total_now)
                    return 0.0
                idle_delta = idle_now - self._last_cpu[0]; total_delta = total_now - self._last_cpu[1]
                self._last_cpu = (idle_now, total_now)
                return 0.0 if total_delta <= 0 else max(0.0, min(100.0, (1 - idle_delta / total_delta) * 100))
            except Exception:
                return 0.0
        try:
            load = os.getloadavg()[0]
            return max(0.0, min(100.0, load / max(1, os.cpu_count() or 1) * 100))
        except (OSError, AttributeError):
            return 0.0

    def collect(self) -> dict[str, Any]:
        root = Path(os.environ.get("SystemDrive", "C:")) if platform.system() == "Windows" else Path("/")
        if psutil is not None:
            cpu = float(psutil.cpu_percent(interval=0.25))
            memory = float(psutil.virtual_memory().percent)
            disk = float(psutil.disk_usage(str(root)).percent)
            net = psutil.net_io_counters()
            if net is None:
                sent, recv = self._last_net
            else:
                sent, recv = int(net.bytes_sent), int(net.bytes_recv)
        else:
            cpu = self._cpu_fallback()
            _, _, memory = memory_info()
            usage = shutil.disk_usage(root)
            disk = 0.0 if usage.total <= 0 else (usage.used / usage.total) * 100
            sent, recv = self._last_net
        self._last_net = (sent, recv)
        return {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "cpu": round(cpu, 1),
            "memory": round(memory, 1),
            "disk": round(disk, 1),
            "net_sent": sent,
            "net_recv": recv,
            "mode": "psutil" if psutil is not None else "compatibilidade",
        }


class MonitorService:
    thresholds = {"cpu": 90.0, "memory": 90.0, "disk": 90.0}

    def __init__(self, db: HermesDB, interval: int, history_limit: int) -> None:
        self.db = db
        self.interval = max(5, interval)
        self.history_limit = max(100, history_limit)
        self.collector = MetricCollector()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._current: dict[str, Any] = self.collector.collect()
        self._streaks = {key: 0 for key in self.thresholds}
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="hermes-monitor", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)

    def current(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._current, running=self.running, interval=self.interval)

    def sample_now(self) -> dict[str, Any]:
        metric = self.collector.collect()
        with self._lock:
            self._current = metric
        self.db.insert_metric(metric, self.history_limit)
        self._evaluate(metric)
        return metric

    def _evaluate(self, metric: dict[str, Any]) -> None:
        labels = {"cpu": "CPU", "memory": "Memória", "disk": "Disco"}
        for key, threshold in self.thresholds.items():
            value = float(metric[key])
            self._streaks[key] = self._streaks[key] + 1 if value >= threshold else 0
            if self._streaks[key] < 3:
                continue
            last = self.db.last_alert_time(key)
            if last and datetime.now() - last < timedelta(minutes=5):
                continue
            severity = "critical" if value >= 97 else "warning"
            self.db.add_alert(key, severity, value, f"{labels[key]} permaneceu em {value:.1f}% por três leituras consecutivas.")
            self._streaks[key] = 0

    def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                self.sample_now()
            except Exception as exc:
                self.db.add_alert("monitor", "warning", 0, f"Falha de coleta: {exc}")
            self._stop.wait(self.interval)
