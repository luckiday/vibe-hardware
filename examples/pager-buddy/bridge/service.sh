#!/usr/bin/env bash
# service.sh — run the pager-buddy bridge as a macOS LaunchAgent: auto-start on
# login, restart on crash, logs to a file. Reversible (uninstall removes it).
#
#   ./service.sh install     write + load the agent (starts now, and on every login)
#   ./service.sh uninstall   unload + remove the agent
#   ./service.sh status      is it loaded / running?
#   ./service.sh logs        tail the bridge log
#
# Env: PAGER_BUDDY_PORT (default 8787) · PAGER_BUDDY_PY (python to use)
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.pagerbuddy.bridge"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
LOG="$HOME/Library/Logs/$LABEL.log"
PORT="${PAGER_BUDDY_PORT:-8787}"
# Pick a python that can import bleak (the BLE relay needs it); PAGER_BUDDY_PY wins,
# else the install.sh venv. Resolve to an ABSOLUTE path — launchd runs a minimal PATH.
PY="${PAGER_BUDDY_PY:-}"
if [ -z "$PY" ]; then
  if [ -x "$DIR/.venv/bin/python" ]; then
    PY="$DIR/.venv/bin/python"
  else
    for c in python3 /opt/homebrew/bin/python3 /usr/bin/python3; do
      command -v "$c" >/dev/null 2>&1 || continue
      PY="$c"; "$c" -c 'import bleak' 2>/dev/null && break
    done
  fi
fi
PY="$(command -v "$PY" 2>/dev/null || echo "$PY")"

write_plist() {
  mkdir -p "$HOME/Library/LaunchAgents" "$HOME/Library/Logs"
  cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>$DIR/run.sh</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PAGER_BUDDY_PORT</key><string>$PORT</string>
    <key>PAGER_BUDDY_PY</key><string>$PY</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$LOG</string>
  <key>StandardErrorPath</key><string>$LOG</string>
</dict>
</plist>
EOF
}

case "${1:-}" in
  install)
    pkill -f 'pager_stub.py|ble_push.py' 2>/dev/null || true
    lsof -ti ":$PORT" 2>/dev/null | xargs -r kill -9 2>/dev/null || true
    write_plist
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST"
    echo "✓ installed + started LaunchAgent $LABEL (hub + BLE relay, via run.sh)"
    echo "  python: $PY    UI → http://127.0.0.1:$PORT/    logs: $LOG"
    echo "  auto-starts on login · run './service.sh uninstall' to remove."
    echo "  note: a background LaunchAgent doing BLE may need Bluetooth permission —"
    echo "        if the relay never connects, prefer the 'pager' shell command (your"
    echo "        terminal already has Bluetooth access)."
    ;;
  uninstall)
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "✓ removed LaunchAgent $LABEL"
    ;;
  status)
    if launchctl list 2>/dev/null | grep -q "$LABEL"; then
      launchctl list | awk 'NR==1 || /'"$LABEL"'/'
      echo "health: $(curl -s -m 2 http://127.0.0.1:$PORT/healthz || echo 'not responding')"
    else
      echo "not loaded (run './service.sh install')"
    fi
    ;;
  logs)
    touch "$LOG"; tail -n 40 -f "$LOG"
    ;;
  *)
    echo "usage: $0 {install|uninstall|status|logs}"; exit 1 ;;
esac
