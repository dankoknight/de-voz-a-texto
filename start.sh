#!/usr/bin/env bash
set -euo pipefail
export PATH="${HOME}/.local/bin:${PATH}"
cd "$(dirname "$0")"
exec python3 -m uvicorn app:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8787}"
