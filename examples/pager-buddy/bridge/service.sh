#!/usr/bin/env bash
# service.sh — DEPRECATED compatibility shim. The bridge now has one entry point:
#
#     pager boot on      (was: ./service.sh install)     auto-start at login
#     pager boot off     (stop auto-start; ./service.sh uninstall still removes it)
#     pager status       (was: ./service.sh status)
#     pager logs -f      (was: ./service.sh logs)
#
# Kept so older docs / muscle memory / install.sh keep working. Prefer `pager`.
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LABEL="com.pagerbuddy.bridge"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

case "${1:-}" in
  install)   exec "$DIR/pager" boot on ;;
  status)    exec "$DIR/pager" status ;;
  logs)      exec "$DIR/pager" logs -f ;;
  uninstall)
    # Full removal (what install.sh uninstall relies on): unload + delete the plist.
    launchctl bootout "gui/$(id -u)/$LABEL" 2>/dev/null \
      || launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo "✓ removed LaunchAgent $LABEL  (next time, use: pager boot off / pager uninstall)"
    ;;
  *)
    echo "usage: $0 {install|uninstall|status|logs}   — deprecated; use 'pager' instead" >&2
    exit 1 ;;
esac
