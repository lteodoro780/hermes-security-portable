from __future__ import annotations

import ctypes
import os
import platform
import shutil
import socket
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import psutil  # type: ignore
except ImportError:
    psutil = None


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


@dataclass(frozen=True)
class HardwareInfo:
    hostname: str
    system: str
    release: str
    machine: str
    processor: str
    cpu_threads: int
    ram_total_gb: float
    disk_total_gb: float
    disk_free_gb: float
    optional_psutil: bool


def _windows_memory() -> tuple[float, float]:
    status = MEMORYSTATUSEX()
    status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return status.ullTotalPhys / (1024**3), status.ullAvailPhys / (1024**3)
    return 0.0, 0.0


def memory_info() -> tuple[float, float, float]:
    if psutil is not None:
        vm = psutil.virtual_memory()
        return vm.total / (1024**3), vm.available / (1024**3), float(vm.percent)
    if platform.system() == "Windows":
        total, available = _windows_memory()
        percent = 0.0 if total <= 0 else (1 - available / total) * 100
        return total, available, percent
    try:
        values: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, raw = line.split(":", 1)
            values[key] = int(raw.strip().split()[0])
        total = values.get("MemTotal", 0) * 1024
        available = values.get("MemAvailable", values.get("MemFree", 0)) * 1024
        total_gb = total / (1024**3)
        available_gb = available / (1024**3)
        percent = 0.0 if total <= 0 else (1 - available / total) * 100
        return total_gb, available_gb, percent
    except (OSError, ValueError):
        return 0.0, 0.0, 0.0


def detect_hardware() -> HardwareInfo:
    total_ram, _, _ = memory_info()
    root = Path(os.environ.get("SystemDrive", "C:")) if platform.system() == "Windows" else Path("/")
    try:
        usage = shutil.disk_usage(root)
        disk_total = usage.total / (1024**3)
        disk_free = usage.free / (1024**3)
    except OSError:
        disk_total = disk_free = 0.0
    return HardwareInfo(
        hostname=socket.gethostname(),
        system=platform.system(),
        release=platform.release(),
        machine=platform.machine(),
        processor=platform.processor() or "não informado",
        cpu_threads=os.cpu_count() or 1,
        ram_total_gb=round(total_ram, 2),
        disk_total_gb=round(disk_total, 2),
        disk_free_gb=round(disk_free, 2),
        optional_psutil=psutil is not None,
    )


def payload() -> dict[str, Any]:
    return asdict(detect_hardware())
