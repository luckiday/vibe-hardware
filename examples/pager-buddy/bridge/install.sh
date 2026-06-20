#!/usr/bin/env bash
# install.sh — one-command setup for the pager-buddy Mac bridge.
#
#   ./install.sh                 # venv + bleak, register Claude Code hooks, print next steps
#   ./install.sh --gate Bash     # scope the device approval gate (default: Bash,Edit,Write,…)
#   ./install.sh --no-hooks      # set up the relay only; don't touch ~/.claude/settings.json
#   ./install.sh --service       # also auto-start the bridge on login (LaunchAgent)
#   ./install.sh --port 8788     # hub port (default 8787)
#   ./install.sh uninstall       # reverse everything: hooks + LaunchAgent + venv
#
# Idempotent: re-running is safe. The only dependency is `bleak` (BLE), installed into a
# self-contained venv here so it survives PEP 668 / externally-managed system pythons.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$DIR/.venv"

PORT=8787
GATE=""; GATE_SET=0
HOOKS=1
SERVICE=0
ACTION=install

while [ $# -gt 0 ]; do
  case "$1" in
    uninstall)   ACTION=uninstall ;;
    --service)   SERVICE=1 ;;
    --no-hooks)  HOOKS=0 ;;
    --gate)      GATE="${2:-}"; GATE_SET=1; shift ;;
    --gate=*)    GATE="${1#*=}"; GATE_SET=1 ;;
    --port)      PORT="${2:?}"; shift ;;
    --port=*)    PORT="${1#*=}" ;;
    -h|--help)   sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1  (try --help)" >&2; exit 1 ;;
  esac
  shift
done

# Pick a base python3: PAGER_BUDDY_PY wins, else Homebrew, else system.
pick_python() {
  local c
  for c in "${PAGER_BUDDY_PY:-}" /opt/homebrew/bin/python3 /usr/bin/python3 python3; do
    [ -n "$c" ] || continue
    command -v "$c" >/dev/null 2>&1 && { command -v "$c"; return 0; }
  done
  return 1
}

if [ "$ACTION" = uninstall ]; then
  echo "uninstalling the pager-buddy bridge…"
  "$DIR/service.sh" uninstall 2>/dev/null || true
  if BASEPY="$(pick_python)"; then
    "$BASEPY" "$DIR/install_hooks.py" uninstall || true
  fi
  rm -rf "$VENV"
  echo "✓ removed the venv, Claude hooks, and LaunchAgent (if present)."
  echo "  (a backup of settings.json was written next to it by install_hooks.py)"
  exit 0
fi

BASEPY="$(pick_python)" || { echo "✗ no python3 found — install Python 3 first." >&2; exit 1; }
echo "• python: $BASEPY"

# 1. venv + bleak — robust against PEP 668 (externally-managed system/Homebrew python).
if [ ! -x "$VENV/bin/python" ]; then
  echo "• creating venv → $VENV"
  "$BASEPY" -m venv "$VENV"
fi
echo "• installing bleak (BLE)…"
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet bleak
echo "  $("$VENV/bin/python" -c 'import bleak; print("bleak", getattr(bleak,"__version__","installed"))' 2>/dev/null || echo 'bleak ready')"

# 2. Claude Code hooks (stdlib-only; install_hooks bakes an absolute hook path + URL).
if [ "$HOOKS" = 1 ]; then
  echo "• registering Claude Code hooks (~/.claude/settings.json)…"
  gate_args=()
  [ "$GATE_SET" = 1 ] && gate_args=(--gate "$GATE")
  "$BASEPY" "$DIR/install_hooks.py" install --url "http://127.0.0.1:$PORT/v1/snapshot" "${gate_args[@]}"
else
  echo "• skipping Claude hooks (--no-hooks)"
fi

# 3. optional auto-start on login (uses the venv python so the relay finds bleak).
if [ "$SERVICE" = 1 ]; then
  echo "• installing LaunchAgent (auto-start on login)…"
  PAGER_BUDDY_PORT="$PORT" PAGER_BUDDY_PY="$VENV/bin/python" "$DIR/service.sh" install
fi

echo
echo "✓ pager-buddy bridge installed."
echo "  next steps:"
echo "    1. flash + power on the device (examples/pager-buddy/firmware)"
if [ "$SERVICE" = 1 ]; then
  echo "    2. the bridge is already running (LaunchAgent) — './service.sh logs' to watch it"
else
  echo "    2. start the bridge:  $DIR/run.sh    (hub + BLE relay, Ctrl-C to stop)"
fi
[ "$HOOKS" = 1 ] && echo "    3. restart Claude Code so it loads the new hooks"
echo "    live UI → http://127.0.0.1:$PORT/"
