#!/bin/sh
# The routing flow for this board: generate -> [freerouting] -> replay the
# .ses -> DRC. The gate is KiCad's DRC (0 error-severity, 0 unconnected), never
# freerouting's own violation count -- the two disagree, and only one of them
# ships boards.
#
# DEFAULT: replay the COMMITTED macropad.ses and gate on it. That is the
# reproducible path -- freerouting is nondeterministic (successive runs fence
# off different pour pockets and can leave different nets unrouted), so the
# accepted session is an input, not something to re-roll on every build.
#
# FRESH=1: re-run freerouting and overwrite macropad.ses. Accepting the new
# result means committing it -- and only after this script's DRC gate passes.
#
# Tools (override any of them by env):
#   KICAD_PY   KiCad's bundled python3 (the one with pcbnew)
#   KICAD_CLI  kicad-cli
#   JAVA       java >= the freerouting jar's class version (2.x needs 25)
#   FREEROUTING_JAR  path to freerouting-*.jar
set -e
cd "$(dirname "$0")"

KICAD_PY="${KICAD_PY:-/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3}"
KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
JAVA="${JAVA:-java}"
if [ -z "$FREEROUTING_JAR" ]; then
    FREEROUTING_JAR=$(ls "$HOME"/.freerouting/freerouting-*.jar 2>/dev/null | sort -V | tail -1)
fi
[ -x "$KICAD_PY" ] || { echo "no KiCad python at $KICAD_PY (set KICAD_PY)" >&2; exit 2; }
[ -z "$FRESH" ] || [ -n "$FREEROUTING_JAR" ] || { echo "FRESH=1 needs a freerouting jar (set FREEROUTING_JAR)" >&2; exit 2; }

# 1. the DSN source: placement + locked skeleton, and NO ground net on pads.
#    (A netted GND makes freerouting wire every ground pad together through
#    the connector column -- references/autorouting.md, "Freerouting at scale".)
ROUTE=none GNDLESS=1 "$KICAD_PY" gen_pcb.py
"$KICAD_PY" -c "
import pcbnew
b = pcbnew.LoadBoard('macropad.kicad_pcb')
assert pcbnew.ExportSpecctraDSN(b, 'macropad.dsn')"

# 2. route -- only when asked. -mt 1 because freerouting's own log calls the
#    multi-threaded optimizer broken ("known to generate clearance violations").
if [ -n "$FRESH" ]; then
    "$JAVA" -jar "$FREEROUTING_JAR" -de macropad.dsn -do macropad.ses -mp 30 -mt 1 -da 2>&1 \
        | grep -E "stage completed|Optimization was" | tail -3
else
    [ -f macropad.ses ] || { echo "no macropad.ses -- run with FRESH=1 to route" >&2; exit 2; }
    echo "replaying the committed macropad.ses (FRESH=1 to re-route)"
fi

# 3. replay onto the REAL board (the one that has GND on its pads and pours).
ROUTE=none "$KICAD_PY" gen_pcb.py
"$KICAD_PY" -c "
import pcbnew
b = pcbnew.LoadBoard('macropad.kicad_pcb')
assert pcbnew.ImportSpecctraSES(b, 'macropad.ses')
pcbnew.SaveBoard('macropad-fr.kicad_pcb', b)"

# 4. the gate.
"$KICAD_CLI" pcb drc --refill-zones --save-board --severity-error --exit-code-violations \
    --output drc-fr.json --format json macropad-fr.kicad_pcb 2>&1 | grep -E "violations|unconnected"
"$KICAD_PY" - << 'PYEOF'
import json
r = json.load(open("drc-fr.json"))
v, u = r.get("violations", []), r.get("unconnected_items", [])
print(f"freerouted board: {len(v)} violations, {len(u)} unconnected")
for x in v[:20]:
    pos = x.get("items", [{}])[0].get("pos", {})
    who = " | ".join(i.get("description", "?") for i in x.get("items", []))
    print(f"  [{x.get('type')}] @({pos.get('x')},{pos.get('y')})  {who}")
for x in u[:20]:
    a, b = (x.get("items", [{}, {}]) + [{}, {}])[:2]
    print(f"  unconnected: {a.get('description','?')} <-> {b.get('description','?')}")
raise SystemExit(1 if (v or u) else 0)
PYEOF

"$KICAD_CLI" pcb render --side top --output render-top.png macropad-fr.kicad_pcb > /dev/null
echo "[ ok ] DRC clean; render-top.png written"
