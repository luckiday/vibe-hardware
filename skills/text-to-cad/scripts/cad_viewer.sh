#!/usr/bin/env bash
# Start (or restart) the latest CAD Viewer on a model directory, working around the
# three launch gotchas (see references/cad-viewer.md): fixed port + lingering server,
# the agent:start->start launcher rename, and locating the vendored skill.
#
#   tools/skills/text-to-cad/scripts/cad_viewer.sh <abs-models-dir> [port]
#
# Runs in the FOREGROUND (the server must stay up) — launch it in the background:
#   ... cad_viewer.sh /abs/models &     (or via the agent's run_in_background)
# Then open  http://127.0.0.1:<port>/?file=<name>.step   (file= relative to the dir)
set -eu

DIR="${1:?usage: cad_viewer.sh <abs-models-dir> [port]}"
PORT="${2:-4178}"
[ -d "$DIR" ] || { echo "model dir not found: $DIR"; exit 1; }
case "$DIR" in /*) ;; *) echo "use an ABSOLUTE --dir (got: $DIR)"; exit 1;; esac

# 1) locate the vendored cad-viewer skill (npx skills install earthtojake/text-to-cad).
#    Resolve the repo root from THIS script's path so it works from ANY caller CWD;
#    try both layouts — skills/<name>/scripts and tools/skills/<name>/scripts — plus a
#    git fallback + CWD-relative + $HOME.
R3="$(cd "$(dirname "$0")/../../.." 2>/dev/null && pwd || true)"      # skills/<name>/scripts
R4="$(cd "$(dirname "$0")/../../../.." 2>/dev/null && pwd || true)"   # tools/skills/<name>/scripts
GROOT="$(git -C "$(dirname "$0")" rev-parse --show-toplevel 2>/dev/null || true)"
SKILL=""
for c in "$R3/.agents/skills/cad-viewer" "$R3/.claude/skills/cad-viewer" \
         "$R4/.agents/skills/cad-viewer" "$R4/.claude/skills/cad-viewer" \
         "$GROOT/.agents/skills/cad-viewer" "$GROOT/.claude/skills/cad-viewer" \
         .agents/skills/cad-viewer .claude/skills/cad-viewer \
         "$HOME/.agents/skills/cad-viewer" "$HOME/.claude/skills/cad-viewer"; do
  [ -n "$c" ] && [ -d "$c" ] && { SKILL="$c"; break; }
done
[ -n "$SKILL" ] || { echo "cad-viewer not installed — run: npx skills install earthtojake/text-to-cad"; exit 1; }
[ -f "$SKILL/scripts/viewer/package.json" ] || { echo "unexpected skill layout at $SKILL"; exit 1; }

# 2) free the port: a prior --shutdown-after server often still squats on it, and the
#    server binds a FIXED port (no auto-increment) so it would die with EADDRINUSE.
old=$(lsof -nP -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)
if [ -n "$old" ]; then echo "freeing port $PORT (stale viewer pid: $old)"; kill $old 2>/dev/null || true; sleep 1; fi

# 3) pick the npm script — newer bundles renamed agent:start -> start
script=start
grep -q '"agent:start"' "$SKILL/scripts/viewer/package.json" && script=agent:start

echo "CAD Viewer -> http://127.0.0.1:$PORT/?file=<name>.step   (dir: $DIR)"
cd "$SKILL"
exec npm --prefix scripts/viewer run "$script" -- \
     --host 127.0.0.1 --dir "$DIR" --port "$PORT" --shutdown-after 12h
