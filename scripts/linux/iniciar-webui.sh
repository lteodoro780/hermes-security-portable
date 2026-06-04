#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
export HERMES_WEB_HOST="${HERMES_WEB_HOST:-127.0.0.1}"
export HERMES_WEB_PORT="${HERMES_WEB_PORT:-8765}"
export HERMES_OPEN_BROWSER="${HERMES_OPEN_BROWSER:-1}"
export HERMES_LLAMACPP_URL="${HERMES_LLAMACPP_URL:-http://127.0.0.1:8080/completion}"
python3 src/hermes/hermes_web.py
