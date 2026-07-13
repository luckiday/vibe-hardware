#!/usr/bin/env bash
# Headless autoroute for a vibe-pcb board: replace scripted route.wire() lists in
# gen_pcb.py with freerouting, keeping every gate. See references/autorouting.md.
#
#   gen_pcb STAGE=place  ->  export_dsn.py (belly keepout + per-net widths)
#     ->  freerouting (-de/-do)  ->  import_ses.py (GND solid pour + silk fix)
#     ->  DRC + belly gate
#
# Run from the project's kicad/ dir (the one with gen_sch.py / gen_pcb.py):
#   FREEROUTING_JAR=/path/freerouting-2.2.4.jar JAVA=/path/jdk-25/bin/java \
#   BELLY_BOX="94,91,115,109" scripts/autoroute.sh <proj>
#
# Accepting the result: copy the .ses next to the generator as routing.ses and
# commit it — gen_pcb.py's full stage replays it (pcblib.route.apply_ses), so the
# routed board regenerates from committed sources on any machine.
#
# Prereqs (NOT vendored): a freerouting jar (2.1.x runs on JDK 21; 2.2.4 needs
# JDK 25) and a gen_pcb.py with STAGE=place (placement + nets, no copper).
set -eu

PROJ="${1:?usage: autoroute.sh <proj-basename>   (run in the project kicad/ dir)}"
. "$(dirname "$0")/_kicad_env.sh"
S="$_VS"
JAVA="${JAVA:-java}"
FR_JAR="${FREEROUTING_JAR:?set FREEROUTING_JAR to a freerouting jar}"
# Fanout-first knobs (references/autorouting.md): when gen_pcb pre-fans the power
# pads with LOCKED stubs+vias (pcblib.route.fanout — exported as Specctra
# "(type fix)"), set FR_INC=power so freerouting skips the whole power class and
# only ever routes signals. FR_MP caps autoroute passes (deterministic runtime).
FR_INC="${FR_INC:-}"       # net classes freerouting must IGNORE, e.g. "power"
FR_MP="${FR_MP:-}"         # max autoroute passes, e.g. 40
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
FR_OPTS=""
[ -n "$FR_INC" ] && FR_OPTS="$FR_OPTS -inc $FR_INC"
[ -n "$FR_MP" ] && FR_OPTS="$FR_OPTS -mp $FR_MP"
( cd "$WORK" && "$JAVA" -jar "$FR_JAR" -de "$PROJ.dsn" -do "$PROJ.ses" $FR_OPTS )
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
  "$PY" "$S/belly_check.py" "$ROUTED" $(echo "$BELLY_BOX" | tr ',' ' ')
fi
echo "done -> $ROUTED"
echo "accept: cp $WORK/$PROJ.ses routing.ses   (then gen_pcb.py full replays it; commit routing.ses)"
