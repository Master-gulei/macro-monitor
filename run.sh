#!/usr/bin/env bash
# 宏观监测看板 - Linux/macOS 入口（与 run.bat 等价）
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m macro_monitor.cli --project "$ROOT" "$@"
