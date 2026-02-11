#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/.run/paper-reader.pid"

if [[ ! -f "$PID_FILE" ]]; then
  echo "paperReader is not running (no pid file)."
  exit 0
fi

PID="$(cat "$PID_FILE")"
if [[ -z "${PID}" ]]; then
  rm -f "$PID_FILE"
  echo "Stale pid file removed."
  exit 0
fi

if ! kill -0 "$PID" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "paperReader is not running (stale pid file removed)."
  exit 0
fi

kill "$PID"
for _ in {1..20}; do
  if kill -0 "$PID" 2>/dev/null; then
    sleep 0.2
  else
    break
  fi
done

if kill -0 "$PID" 2>/dev/null; then
  kill -9 "$PID" 2>/dev/null || true
fi

rm -f "$PID_FILE"
echo "paperReader stopped (pid=$PID)."
