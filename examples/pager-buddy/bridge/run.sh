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
. "$DIR/lib.sh"
PORT="${PAGER_BUDDY_PORT:-8787}"
BLE="${PAGER_BUDDY_BLE:-1}"
# Runtime python (prefers the install.sh venv that has bleak — see lib.sh).
PY="$(pb_runtime_python)"

# free the port if a previous bridge is lingering
if lsof -ti ":$PORT" >/dev/null 2>&1; then
  echo "port $PORT busy — stopping the previous bridge…"
  pb_free_port "$PORT"
fi

pids=()
stopping=0
on_stop() { stopping=1; }                                  # Ctrl-C / launchctl SIGTERM
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }       # always reap children
trap on_stop INT TERM
trap cleanup EXIT

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

# Keep the hub in the foreground. A deliberate stop (Ctrl-C / launchctl SIGTERM) exits 0
# so a KeepAlive LaunchAgent won't treat it as a crash; an unexpected hub exit propagates
# its code so launchd restarts it (plist KeepAlive = SuccessfulExit:false).
rc=0
wait "$hub_pid" || rc=$?
if [ "$stopping" = 1 ]; then echo; echo "stopping…"; exit 0; fi
exit "$rc"
