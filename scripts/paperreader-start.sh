#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_DIR="$ROOT_DIR/.run"
PID_FILE="$RUN_DIR/paper-reader.pid"
LOG_FILE="$RUN_DIR/paper-reader.log"
ENV_FILE="$ROOT_DIR/.env"
VENV_PY="$ROOT_DIR/.venv/bin/python"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"

mkdir -p "$RUN_DIR"

if [[ -f "$PID_FILE" ]]; then
  OLD_PID="$(cat "$PID_FILE")"
  if [[ -n "${OLD_PID}" ]] && kill -0 "$OLD_PID" 2>/dev/null; then
    echo "paperReader is already running (pid=$OLD_PID)"
    echo "log: $LOG_FILE"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

if [[ ! -x "$VENV_PY" ]]; then
  echo "Missing virtualenv python: $VENV_PY"
  echo "Run: python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt"
  exit 1
fi

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ENV_FILE"
  set +a
fi

if [[ -z "${OPENAI_API_KEY:-}" || "${OPENAI_API_KEY}" == "..." ]]; then
  echo "Missing OPENAI_API_KEY. Refusing to start."
  echo "Create $ENV_FILE with:"
  echo "  OPENAI_API_KEY=<your_real_key>"
  echo "  OPENAI_SUMMARY_MODEL=gpt-5.2-pro"
  echo "  OPENAI_CHAT_MODEL=gpt-5.2-pro"
  exit 1
fi

cd "$ROOT_DIR"
nohup "$VENV_PY" -m uvicorn backend.app.main:app --host "$HOST" --port "$PORT" >"$LOG_FILE" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"

sleep 1
if kill -0 "$PID" 2>/dev/null; then
  echo "paperReader started"
  echo "pid: $PID"
  echo "url: http://$HOST:$PORT"
  echo "log: $LOG_FILE"
else
  echo "Failed to start paperReader. Check log: $LOG_FILE"
  rm -f "$PID_FILE"
  exit 1
fi
