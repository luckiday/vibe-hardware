#!/usr/bin/env bash
# Headless autoroute for a vibe-pcb board: replace scripted route.wire() lists in
# gen_pcb.py with freerouting, keeping every gate. See references/autorouting.md.
#
#   gen_pcb STAGE=place  ->  export_dsn.py (belly keepout + per-net widths)
#     ->  freerouting (-de/-do)  ->  import_ses.py (GND solid pour + silk fix)
#     ->  DRC + belly gate
#
# Run from the project's kicad/ dir (the one with gen_sch.py / gen_pcb.py):
#   FREEROUTING_JAR=/path/freerouting-2.3.0.jar JAVA=/path/jdk-25/bin/java \
#   BELLY_BOX="94,91,115,109" scripts/autoroute.sh <proj>
#
# Extra router settings go through FR_ARGS (names are snake_case -- the camelCase
# forms in freerouting's release notes are SILENTLY IGNORED; this script fails on
# that, see step 3):
#   FR_ARGS="-mp 20 --router.copper_to_edge_clearance_um=300" scripts/autoroute.sh <proj>
#
# It routes without stealing focus: no Dock icon, no window (step 3). JAVA_OPTS
# overrides the JVM flags that do that -- keep -Djava.awt.headless=true if you set it.
#
# This CLI path is the one that produces the artifact. freerouting's REST/MCP front
# ends drive the same engine (byte-identical .ses) but skip the belly keep-out, the
# per-net widths, the GND solid pour and the gates -- use them to EXPLORE settings on
# autoroute-work/<proj>.dsn, then bring the winner back here via FR_ARGS.
#
# Accepting the result: copy the .ses next to the generator as routing.ses and
# commit it -- gen_pcb.py's full stage replays it (pcblib.route.apply_ses), so the
# routed board regenerates from committed sources on any machine.
#
# Prereqs (NOT vendored): a freerouting jar (2.2.4+ needs JDK 25; 1.9.0 runs on
# JDK 11+ but only with a display session) and a gen_pcb.py with STAGE=place
# (placement + nets, no copper).
set -eu

PROJ="${1:?usage: autoroute.sh <proj-basename>   (run in the project kicad/ dir)}"
. "$(dirname "$0")/_kicad_env.sh"
S="$_VS"
JAVA="${JAVA:-java}"
FR_JAR="${FREEROUTING_JAR:?set FREEROUTING_JAR to a freerouting jar}"
WORK="$(pwd)/autoroute-work"; mkdir -p "$WORK"
[ -f gen_pcb.py ] || { echo "run me from the project kicad/ dir (no gen_pcb.py here)"; exit 1; }

echo "-> 1. placement-only board (STAGE=place)"
python3 gen_sch.py >/dev/null
STAGE=place "$PY" gen_pcb.py >/dev/null
PLACE="$PWD/$PROJ.place.kicad_pcb"

echo "-> 2. export DSN (belly keepout + per-net widths)"
"$PY" "$S/export_dsn.py" "$PLACE" "$WORK/$PROJ.dsn"

echo "-> 3. freerouting (headless)"
# --gui.enabled=false is the real headless switch (2.x only -- 1.9.0 predates the
# settings framework and needs a display session instead), so ask the jar what it is.
# On macOS that flag alone still registers a FOREGROUND app: an icon appears in the
# Dock and steals focus mid-route. Suppressing it is a JVM-side job:
#   2.x : -Djava.awt.headless=true      -> the process registers no app at all
#   1.9 : -Dapple.awt.UIElement=true    -> registers as an accessory (no Dock icon);
#         forcing headless there throws HeadlessException and writes no .ses
JVM_QUIET="-Dapple.awt.UIElement=true"
FR_VER="$("$JAVA" $JVM_QUIET -jar "$FR_JAR" -help 2>&1 | sed -n 's/.*Freerouting v\([0-9][0-9]*\)\..*/\1/p' | head -1)"
HEADLESS=""
if [ "${FR_VER:-0}" -ge 2 ] 2>/dev/null; then
  HEADLESS="--gui.enabled=false"
  JVM_QUIET="-Djava.awt.headless=true $JVM_QUIET"
else
  echo "   NOTE: freerouting v${FR_VER:-?} predates --gui.enabled; needs a logged-in desktop session"
fi
JVM_QUIET="${JAVA_OPTS:-$JVM_QUIET}"   # JAVA_OPTS overrides (e.g. to add -Xmx)
LOG="$WORK/$PROJ-freerouting.log"
# NB: freerouting logs 'session completed' ~10-15 s BEFORE it writes the .ses. Running java
# in the foreground is enough -- the process stays alive until the save finishes.
set -o pipefail   # ... so a java crash isn't masked by tee
# -mt 1: freerouting's own log calls the multi-threaded optimizer broken
# ("Multi-threaded route optimization is broken and it is known to generate
# clearance violations"), and a 27-part board came back with clearance
# violations under the default thread pool that vanished at -mt 1. It goes
# before FR_ARGS so an explicit override still wins.
( cd "$WORK" && "$JAVA" $JVM_QUIET -jar "$FR_JAR" $HEADLESS -da -mt 1 \
    ${FR_ARGS:-} -de "$PROJ.dsn" -do "$PROJ.ses" 2>&1 | tee "$LOG" )
set +o pipefail
# A misspelled or too-new --setting only WARNs and routes with the DEFAULT, which looks
# like success. Treat it as a failure so an unconstrained route can't reach the gates.
if grep -qE "Unknown settings property|Failed to apply CLI" "$LOG"; then
  echo "!! freerouting ignored a setting -- it routed with defaults:"
  grep -E "Unknown settings property|Failed to apply CLI" "$LOG" | sed 's/^/   /'
  echo "   (settings resolve by snake_case name, e.g. --router.copper_to_edge_clearance_um)"
  exit 1
fi
[ -f "$WORK/$PROJ.ses" ] || { echo "no .ses produced"; exit 1; }

echo "-> 4. import SES (+GND solid pour + silk fix)"
ROUTED="$WORK/$PROJ.routed.kicad_pcb"
"$PY" "$S/import_ses.py" "$PLACE" "$WORK/$PROJ.ses" "$ROUTED"

echo "-> 5. gates: DRC + belly"
if cli_has pcb drc; then
  "$CLI" pcb drc --refill-zones "$ROUTED" -o "$WORK/$PROJ-drc.rpt" >/dev/null
else
  "$PY" "$S/drc_report.py" "$ROUTED" "$WORK/$PROJ-drc.rpt" >/dev/null
fi
echo "   DRC errors   : $(grep -cE '; *error' "$WORK/$PROJ-drc.rpt" || true)"
echo "   DRC warnings : $(grep -cE '; *warning' "$WORK/$PROJ-drc.rpt" || true)"
grep -E "Found [0-9]+ (unconnected|Footprint)" "$WORK/$PROJ-drc.rpt" | sed 's/^/   /'
if [ -n "${BELLY_BOX:-}" ]; then
  belly_check_box "$ROUTED"
fi
echo "done -> $ROUTED"
echo "accept: cp $WORK/$PROJ.ses routing.ses   (then gen_pcb.py full replays it; commit routing.ses)"
