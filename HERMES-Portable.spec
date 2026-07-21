# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller one-file para Windows 10/11 x64."""

from pathlib import Path


ROOT = Path(SPECPATH)
SOURCE = ROOT / "src" / "hermes"

hiddenimports = [
    "hermes_backup",
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
    "psutil",
]

a = Analysis(
    [str(SOURCE / "hermes_launcher.py")],
    pathex=[str(SOURCE)],
    binaries=[],
    datas=[(str(ROOT / "web"), "web")],
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
    name="HERMES-Security-Portable-0.8.0",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    uac_admin=False,
)
