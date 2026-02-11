#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STOP_SCRIPT="$ROOT_DIR/scripts/paperreader-stop.sh"
START_SCRIPT="$ROOT_DIR/scripts/paperreader-start.sh"
STATUS_SCRIPT="$ROOT_DIR/scripts/paperreader-status.sh"

if [[ ! -x "$STOP_SCRIPT" || ! -x "$START_SCRIPT" ]]; then
  echo "Missing control scripts in $ROOT_DIR/scripts"
  exit 1
fi

echo "[paperReader] stopping..."
"$STOP_SCRIPT" || true

echo "[paperReader] starting..."
"$START_SCRIPT"

echo "[paperReader] status:"
if [[ -x "$STATUS_SCRIPT" ]]; then
  "$STATUS_SCRIPT" || true
fi
