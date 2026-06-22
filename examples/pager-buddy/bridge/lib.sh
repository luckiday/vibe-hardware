#!/usr/bin/env bash
# lib.sh — shared helpers for the pager-buddy bridge scripts (install/run/service).
#
# Source it, don't run it: it only defines functions (no side effects), so the
# python-picking + port-freeing logic lives in ONE place instead of drifting across
# three scripts. Callers set DIR (the bridge dir) before sourcing, e.g.
#   DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
#   . "$DIR/lib.sh"
#
# Env honored: PAGER_BUDDY_PY (force a specific python).

# A base python3 to *create the venv* with — bleak NOT required yet. PAGER_BUDDY_PY
# wins, else Homebrew, else system. Prints the resolved path; returns 1 if none found.
pb_base_python() {
  local c
  for c in "${PAGER_BUDDY_PY:-}" /opt/homebrew/bin/python3 /usr/bin/python3 python3; do
    [ -n "$c" ] || continue
    command -v "$c" >/dev/null 2>&1 && { command -v "$c"; return 0; }
  done
  return 1
}

# The python to *run the relay* with — it needs bleak, so prefer the install.sh venv.
# PAGER_BUDDY_PY wins; else the venv; else the first python3 that can import bleak
# (falling back to plain python3 so the hub still runs and the relay self-skips).
# Always prints an ABSOLUTE path — launchd runs a minimal PATH. Needs DIR set.
pb_runtime_python() {
  local py="${PAGER_BUDDY_PY:-}" c
  if [ -z "$py" ]; then
    if [ -x "$DIR/.venv/bin/python" ]; then
      py="$DIR/.venv/bin/python"
    else
      for c in python3 /opt/homebrew/bin/python3 /usr/bin/python3; do
        command -v "$c" >/dev/null 2>&1 || continue
        py="$c"; "$c" -c 'import bleak' 2>/dev/null && break
      done
    fi
  fi
  command -v "$py" 2>/dev/null || echo "$py"
}

# Stop any previous bridge so the hub port is free: kill our two processes, then
# anything still bound to $1 (the port). Quiet + idempotent.
pb_free_port() {
  local port="$1"
  pkill -f 'pager_stub.py|ble_push.py' 2>/dev/null || true
  lsof -ti ":$port" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
}
