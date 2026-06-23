#!/usr/bin/env bash
# Headless autoroute for a vibe-pcb board: replace the hand-coded trk()/via() lists in
# gen_pcb.py P5 with freerouting, keeping every gate. See references/autorouting.md.
#
#   gen_pcb STAGE=place  ->  export_dsn.py (belly keepout + per-net widths)
#     ->  freerouting 2.2.x (-de/-do)  ->  import_ses.py (GND solid pour + silk fix)
#     ->  pcb_check.sh (ERC/DRC + belly)
#
# Run from the project's kicad/ dir (the one with gen_sch.py / gen_pcb.py):
#   FREEROUTING_JAR=/path/freerouting-2.2.4.jar JAVA=/path/jdk-25/bin/java \
#   BELLY_BOX="94,91,115,109" scripts/autoroute.sh <proj>
#
# Prereqs (NOT vendored): a freerouting 2.2.x jar (needs JDK 21+; 2.2.4 needs JDK 25) and
# a gen_pcb.py that supports STAGE=place (placement + nets + outline, no copper).
set -eu

PROJ="${1:?usage: autoroute.sh <proj-basename>   (run in the project kicad/ dir)}"
S="$(cd "$(dirname "$0")" && pwd)"
KC="/Applications/KiCad/KiCad.app/Contents"
PY="${KICAD_PY:-$KC/Frameworks/Python.framework/Versions/3.9/bin/python3}"
CLI="${KICAD_CLI:-$KC/MacOS/kicad-cli}"
JAVA="${JAVA:-java}"
FR_JAR="${FREEROUTING_JAR:?set FREEROUTING_JAR to a freerouting 2.2.x jar}"
WORK="$(pwd)/autoroute-work"; mkdir -p "$WORK"
[ -f gen_pcb.py ] || { echo "run me from the project kicad/ dir (no gen_pcb.py here)"; exit 1; }

echo "-> 1. placement-only board (STAGE=place)"
python3 gen_sch.py >/dev/null
STAGE=place "$PY" gen_pcb.py >/dev/null
PLACE="$PWD/$PROJ.place.kicad_pcb"

echo "-> 2. export DSN (belly keepout + per-net widths)"
"$PY" "$S/export_dsn.py" "$PLACE" "$WORK/$PROJ.dsn"

echo "-> 3. freerouting (headless)"
# NB: freerouting logs 'session completed' ~10-15 s BEFORE it writes the .ses. Running java
# in the foreground is enough -- the process stays alive until the save finishes.
( cd "$WORK" && "$JAVA" -jar "$FR_JAR" -de "$PROJ.dsn" -do "$PROJ.ses" )
[ -f "$WORK/$PROJ.ses" ] || { echo "no .ses produced"; exit 1; }

echo "-> 4. import SES (+GND solid pour + silk fix)"
ROUTED="$WORK/$PROJ.routed.kicad_pcb"
"$PY" "$S/import_ses.py" "$PLACE" "$WORK/$PROJ.ses" "$ROUTED"

echo "-> 5. gates: DRC + belly"
"$CLI" pcb drc --refill-zones "$ROUTED" -o "$WORK/$PROJ-drc.rpt" >/dev/null
echo "   DRC errors   : $(grep -cE '; *error' "$WORK/$PROJ-drc.rpt" || true)"
echo "   DRC warnings : $(grep -cE '; *warning' "$WORK/$PROJ-drc.rpt" || true)"
grep -E "Found [0-9]+ (unconnected|Footprint)" "$WORK/$PROJ-drc.rpt" | sed 's/^/   /'
if [ -n "${BELLY_BOX:-}" ]; then
  "$PY" "$S/belly_check.py" "$ROUTED" $(echo "$BELLY_BOX" | tr ',' ' ')
fi
echo "done -> $ROUTED   (review, then fold the routing into gen_pcb.py / accept this board)"
