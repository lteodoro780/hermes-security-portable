#!/usr/bin/env python3
"""Caminhos portáteis compartilhados pelo HERMES.

No código-fonte, os arquivos ficam na raiz do projeto. No executável criado pelo
PyInstaller, recursos empacotados são lidos de ``sys._MEIPASS`` e todo conteúdo
gravável permanece ao lado do ``.exe``. Assim, a pasta inteira pode ser movida
para outro computador sem depender do perfil do usuário ou de uma instalação
do Python.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


def resolve_portable_roots(
    *,
    frozen: bool | None = None,
    executable: str | Path | None = None,
    bundle_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    """Retorna ``(pasta_gravável, pasta_de_recursos)``.

    Os argumentos opcionais tornam a regra verificável sem criar um executável
    durante os testes automatizados.
    """

    source_root = Path(__file__).resolve().parents[2]
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
    if not is_frozen:
        return source_root, source_root

    executable_path = Path(executable or sys.executable).resolve()
    writable_root = executable_path.parent
    bundled = Path(
        bundle_dir or getattr(sys, "_MEIPASS", writable_root)
    ).resolve()
    return writable_root, bundled


APP_DIR, BUNDLE_DIR = resolve_portable_roots()
WEB_DIR = BUNDLE_DIR / "web"
CONFIG_DIR = APP_DIR / "config"
DATA_DIR = APP_DIR / "data"
REPORT_DIR = APP_DIR / "reports"
MODELS_DIR = APP_DIR / "models"
TOOLS_DIR = APP_DIR / "tools"


def ensure_runtime_directories() -> dict[str, Path]:
    """Cria apenas as pastas graváveis esperadas pela versão portátil."""

    directories = {
        "config": CONFIG_DIR,
        "data": DATA_DIR,
        "reports": REPORT_DIR,
        "models": MODELS_DIR,
        "tools": TOOLS_DIR,
    }
    for directory in directories.values():
        directory.mkdir(parents=True, exist_ok=True)
    return directories


def runtime_path_payload() -> dict[str, Any]:
    """Resumo seguro usado na tela de informações do executável."""

    return {
        "frozen": bool(getattr(sys, "frozen", False)),
        "app_dir": str(APP_DIR),
        "bundle_dir": str(BUNDLE_DIR),
        "data_dir": str(DATA_DIR),
        "reports_dir": str(REPORT_DIR),
        "models_dir": str(MODELS_DIR),
    }
