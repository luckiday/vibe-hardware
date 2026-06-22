#!/usr/bin/env bash
# Build the simulator and render every UI state to sim/shots/*.png.
# The renderer is the device's real components/ui/ui.c (-DUI_SIM). One command, then
# read the PNGs — the agent-in-the-loop way to tune the UI without flashing hardware.
#
#   ./shoot.sh                 # render all states at 3x into shots/
#   ./shoot.sh idle            # render a single state to shots/idle.png
#   TICK_MS=1400 ./shoot.sh    # advance the animation clock further before the snapshot
#   SCALE=1 ./shoot.sh         # 1x = real 135x240 pixels
set -euo pipefail
cd "$(dirname "$0")"

TICK_MS="${TICK_MS:-600}"
SCALE="${SCALE:-3}"
BUILD=build
SHOTS=shots

cmake -S . -B "$BUILD" -DCMAKE_BUILD_TYPE=Release >/dev/null
cmake --build "$BUILD" -j >/dev/null
mkdir -p "$SHOTS"

if [ $# -ge 1 ]; then
  "./$BUILD/pager_sim" "$1" "$SHOTS/$1.png" "$TICK_MS" "$SCALE"
else
  "./$BUILD/pager_sim" all "$SHOTS" "$TICK_MS" "$SCALE"
fi
echo "shots in $(pwd)/$SHOTS/"
