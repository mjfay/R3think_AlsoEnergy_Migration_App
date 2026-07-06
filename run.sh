#!/usr/bin/env bash
# Asset Owner Export Tool — browser launcher
# Double-click this file (or run it in a terminal) to start the app.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"
PORT=8000
URL="http://127.0.0.1:$PORT"

# ── 1. Create virtual environment if it doesn't exist ────────────────────────
if [ ! -d "$VENV_DIR" ]; then
  echo "Setting up environment (first run only — this takes about a minute)..."
  python3 -m venv "$VENV_DIR"
fi

PYTHON="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

# ── 2. Install / upgrade dependencies silently ───────────────────────────────
"$PIP" install --quiet --upgrade pip
"$PIP" install --quiet "$BACKEND_DIR"

# ── 3. Start server in background ────────────────────────────────────────────
cd "$BACKEND_DIR"
"$PYTHON" -m uvicorn app.main:app --host 127.0.0.1 --port $PORT &
SERVER_PID=$!

# ── 4. Wait until server is accepting connections, then open browser ──────────
for i in $(seq 1 30); do
  if curl -sf "$URL/api/health" > /dev/null 2>&1; then
    break
  fi
  sleep 0.5
done

if command -v open &>/dev/null; then
  open "$URL"        # macOS
elif command -v xdg-open &>/dev/null; then
  xdg-open "$URL"   # Linux
fi

echo "App running at $URL  —  press Ctrl+C to stop."

# ── 5. Keep script alive; kill server on exit ─────────────────────────────────
trap "kill $SERVER_PID 2>/dev/null" EXIT INT TERM
wait $SERVER_PID
