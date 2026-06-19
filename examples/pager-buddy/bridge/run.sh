#!/usr/bin/env bash
# run.sh — start the pager-buddy bridge in the FOREGROUND (Ctrl-C to stop).
# Serves the design UI + the snapshot endpoint at http://127.0.0.1:<port>/.
# Day-to-day: run this in a terminal tab and leave it; open the URL, click Connect.
#
# Env: PAGER_BUDDY_PORT (default 8787) · PAGER_BUDDY_PY (python to use)
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PAGER_BUDDY_PORT:-8787}"
PY="${PAGER_BUDDY_PY:-/usr/bin/python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python3

# free the port if a previous bridge is lingering
if lsof -ti ":$PORT" >/dev/null 2>&1; then
  echo "port $PORT busy — stopping the previous bridge…"
  pkill -f pager_stub.py 2>/dev/null || true
  lsof -ti ":$PORT" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
fi

echo "pager-buddy bridge → http://127.0.0.1:$PORT/   (Ctrl-C to stop)"
exec "$PY" "$DIR/pager_stub.py" --ui --port "$PORT"
