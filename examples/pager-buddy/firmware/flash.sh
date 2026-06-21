#!/usr/bin/env bash
# flash.sh — flash the firmware to a USB-connected board FROM THE HOST.
#
# Pairs with ./idf.sh (the pinned-Docker BUILD). Two reasons this is a separate host step,
# not `idf.py flash`:
#   1. Docker can't reach /dev/cu.* on macOS, so the actual write must run on the host.
#   2. A host `idf.py flash` re-runs CMake and chokes on the Docker build's baked-in
#      /project paths ("CMakeCache.txt directory is different … HINT: run idf.py fullclean")
#      — which would force a slow host re-build, defeating the reproducible Docker artifact.
# So we flash the already-built binaries in build/ directly with esptool, driven by
# build/flasher_args.json. No CMake, no reconfigure — which also means this works UNCHANGED
# from a git worktree (it never touches the cmake cache or managed_components).
#
# Standard flow (works in the main checkout or any worktree):
#   ./idf.sh build              # 1) authoritative build, pinned Docker toolchain
#   ./flash.sh [PORT]           # 2) flash from the host (auto-detects the port if omitted)
#   ./flash.sh --monitor [PORT] #    …then open the serial console
#
# Env: PAGER_BUDDY_PORT (port), PAGER_BUDDY_BAUD (default 460800).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD="$HERE/build"
BAUD="${PAGER_BUDDY_BAUD:-460800}"

MONITOR=0
PORT="${PAGER_BUDDY_PORT:-}"
for a in "$@"; do
  case "$a" in
    --monitor|-m) MONITOR=1 ;;
    -*) echo "unknown flag: $a" >&2; exit 2 ;;
    *)  PORT="$a" ;;
  esac
done

[ -f "$BUILD/flasher_args.json" ] || {
  echo "no build artifacts at $BUILD — run ./idf.sh build first" >&2; exit 1; }

# Pick a python with esptool: a host that already has it, else the host IDF's env.
PY=""
if command -v python3 >/dev/null 2>&1 && python3 -c 'import esptool' 2>/dev/null; then
  PY=python3
elif [ -n "${IDF_PATH:-}" ] && [ -f "$IDF_PATH/export.sh" ]; then
  # shellcheck disable=SC1090
  source "$IDF_PATH/export.sh" >/dev/null 2>&1 || true
  python3 -c 'import esptool' 2>/dev/null && PY=python3
fi
[ -n "$PY" ] || {
  echo "esptool not found — 'pip install esptool', or 'source \$IDF_PATH/export.sh'" >&2; exit 1; }

# Auto-detect the port if not given (first native-USB serial). Pass PORT to override.
if [ -z "$PORT" ]; then
  PORT="$(ls /dev/cu.usbmodem* /dev/ttyUSB* /dev/ttyACM* 2>/dev/null | head -1 || true)"
  [ -n "$PORT" ] || { echo "no port given and none auto-detected — pass PORT" >&2; exit 1; }
  echo "auto-detected port: $PORT  (override with ./flash.sh <PORT> or PAGER_BUDDY_PORT)"
fi

# Drive esptool from flasher_args.json so offsets/flags track the build, not a hard-coded list.
"$PY" - "$BUILD" "$PORT" "$BAUD" <<'PY'
import json, os, subprocess, sys
build, port, baud = sys.argv[1], sys.argv[2], sys.argv[3]
a = json.load(open(os.path.join(build, "flasher_args.json")))
ex = a.get("extra_esptool_args", {})
cmd = [sys.executable, "-m", "esptool",
       "--chip", ex.get("chip", "esp32s3"), "-p", port, "-b", baud,
       "--before", ex.get("before", "default_reset"),
       "--after",  ex.get("after",  "hard_reset"),
       "write_flash"]
cmd += a.get("write_flash_args", [])
for off, f in sorted(a["flash_files"].items(), key=lambda kv: int(kv[0], 16)):
    cmd += [off, os.path.join(build, f)]
print("+", " ".join(cmd))
sys.exit(subprocess.call(cmd))
PY

echo "flashed OK."
if [ "$MONITOR" = 1 ]; then
  echo "--- monitor ($PORT · Ctrl-] to quit) ---"
  # idf_monitor drives the native USB-JTAG reset correctly and needs a real TTY.
  if command -v idf.py >/dev/null 2>&1; then idf.py -p "$PORT" monitor
  else "$PY" -m esp_idf_monitor -p "$PORT"; fi
fi
