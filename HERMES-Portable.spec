# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-file da interface desktop para Windows 10/11 x64."""

from pathlib import Path


ROOT = Path(SPECPATH)
SOURCE = ROOT / "src" / "hermes"

hiddenimports = [
    "hermes_backup",
    "hermes_desktop",
    "hermes_desktop_core",
    "hermes_history",
    "hermes_incidents",
    "hermes_intelligence",
    "hermes_knowledge",
    "hermes_launcher",
    "hermes_models",
    "hermes_monitor",
    "hermes_paths",
    "hermes_profiles",
    "hermes_security",
    "hermes_web",
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    "psutil",
]

a = Analysis(
    [str(SOURCE / "hermes_desktop.py")],
    pathex=[str(SOURCE)],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="HERMES-Security-Portable-0.9.0",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,
)
