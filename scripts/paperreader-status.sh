#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.run/paper-reader.pid"
LOG_FILE="$ROOT_DIR/.run/paper-reader.log"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE")"
  if [[ -n "${PID}" ]] && kill -0 "$PID" 2>/dev/null; then
    echo "paperReader is running (pid=$PID)."
    echo "log: $LOG_FILE"
    exit 0
  fi
  echo "paperReader is not running (stale pid file)."
  exit 1
fi

echo "paperReader is not running."
exit 1
