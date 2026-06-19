#!/usr/bin/env bash
# run.sh — start the pager-buddy bridge in the FOREGROUND (Ctrl-C to stop). Brings up:
#   • the hub (pager_stub.py): serves the design UI + snapshot endpoint at
#     http://127.0.0.1:<port>/  — Claude hooks POST here, the web mock reads here.
#   • the BLE relay (ble_push.py): connects to the pager (pg-XXXX) and writes snapshots
#     over BLE. Best-effort: skipped (with a note) if `bleak` isn't installed, or if
#     PAGER_BUDDY_BLE=0. Needs `pip install bleak` and a flashed, advertising device.
# Day-to-day: run this in a terminal tab and leave it; open the URL, click Connect.
#
# Env: PAGER_BUDDY_PORT (default 8787) · PAGER_BUDDY_PY (python) · PAGER_BUDDY_BLE (1/0)
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PAGER_BUDDY_PORT:-8787}"
BLE="${PAGER_BUDDY_BLE:-1}"
# Pick python: an explicit PAGER_BUDDY_PY wins; else prefer one that can import bleak
# (the BLE relay needs it), falling back to any python3 (hub still runs, relay skips).
PY="${PAGER_BUDDY_PY:-}"
if [ -z "$PY" ]; then
  for c in python3 /opt/homebrew/bin/python3 /usr/bin/python3; do
    command -v "$c" >/dev/null 2>&1 || continue
    PY="$c"; "$c" -c 'import bleak' 2>/dev/null && break
  done
fi

# free the port if a previous bridge is lingering
if lsof -ti ":$PORT" >/dev/null 2>&1; then
  echo "port $PORT busy — stopping the previous bridge…"
  pkill -f pager_stub.py 2>/dev/null || true
  pkill -f ble_push.py   2>/dev/null || true
  lsof -ti ":$PORT" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
fi

pids=()
cleanup() { trap - INT TERM EXIT; echo; echo "stopping…"; kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup INT TERM EXIT

# the hub (authoritative — keep this in the foreground via wait)
echo "pager-buddy hub → http://127.0.0.1:$PORT/   (Ctrl-C to stop)"
"$PY" "$DIR/pager_stub.py" --ui --port "$PORT" &
hub_pid=$!
pids+=("$hub_pid")

# the BLE relay (best-effort; a relay death must not take the hub down)
if [ "$BLE" != "0" ]; then
  if "$PY" -c "import bleak" >/dev/null 2>&1; then
    echo "BLE relay → scanning for the pager (pg-XXXX)…"
    PYTHONUNBUFFERED=1 "$PY" "$DIR/ble_push.py" --hub "http://127.0.0.1:$PORT/v1/snapshot" &
    pids+=("$!")
  else
    echo "BLE relay skipped — 'bleak' not installed (pip install bleak). Hub only."
  fi
fi

wait "$hub_pid"
