#!/usr/bin/env bash
# Regenerate a script-built KiCad project, then run the gates: ERC + DRC + render.
# Run from the project's kicad/ dir (the one with gen_sch.py / gen_pcb.py).
#
#   tools/skills/vibe-pcb/scripts/pcb_check.sh <proj-basename>
#
# <proj-basename> is the .kicad_pcb name without extension (e.g. xiao-carrier).
# Needs KiCad 10's bundled tools — kicad-cli + the BUNDLED python (it has pcbnew).
# Override on non-mac / other versions:  KICAD_CLI=... KICAD_PY=... pcb_check.sh ...
set -eu

PROJ="${1:?usage: pcb_check.sh <proj-basename>   (run in the project kicad/ dir)}"

KC="/Applications/KiCad/KiCad.app/Contents"
CLI="${KICAD_CLI:-$KC/MacOS/kicad-cli}"
PY="${KICAD_PY:-$KC/Frameworks/Python.framework/Versions/3.9/bin/python3}"  # has pcbnew

[ -x "$CLI" ] || { echo "kicad-cli not found at: $CLI   (set KICAD_CLI)"; exit 1; }
[ -x "$PY" ]  || { echo "bundled python not found at: $PY   (set KICAD_PY)"; exit 1; }
[ -f gen_pcb.py ] || { echo "run me from the project kicad/ dir (no gen_pcb.py here)"; exit 1; }

echo "-> generate (gen_sch.py + gen_pcb.py)"
python3 gen_sch.py            # schematic writer — plain python
"$PY"   gen_pcb.py            # pcb builder — needs the bundled python's pcbnew

echo "-> ERC";    "$CLI" sch erc "$PROJ.kicad_sch" -o "$PROJ-erc.rpt" >/dev/null
echo "-> DRC";    "$CLI" pcb drc "$PROJ.kicad_pcb" -o "$PROJ-drc.rpt" >/dev/null
echo "-> render"; "$CLI" pcb render "$PROJ.kicad_pcb" -o "$PROJ-pcb-top.png" \
                     --side top --background opaque -w 950 --height 600 >/dev/null

# --- parse gate counts. CRUCIAL: a DRC "violation" can be error- OR warning-severity.
# "Found N violations" is the TOTAL — counting it as the fail metric flags benign silk
# warnings (text height, edge clip) as failures. Gate on ERROR severity + unconnected;
# report warnings separately. (This false-fail bit us: 10 silk warnings != a fail.) ---
num() { grep -oE "$1" "$2" 2>/dev/null | grep -oE '[0-9]+' | head -1; }
erc_err=$(grep -oE 'Errors[[:space:]]+[0-9]+' "$PROJ-erc.rpt" 2>/dev/null | awk '{s+=$2} END{print s+0}')
drc_err=$(grep -cE '; *error'   "$PROJ-drc.rpt" 2>/dev/null || true)   # error-severity items
drc_warn=$(grep -cE '; *warning' "$PROJ-drc.rpt" 2>/dev/null || true)  # warning-severity items
drc_u=$(num 'Found [0-9]+ unconnected pads'    "$PROJ-drc.rpt"); drc_u=${drc_u:-?}
drc_f=$(num 'Found [0-9]+ Footprint errors'    "$PROJ-drc.rpt"); drc_f=${drc_f:-?}

echo
echo "==== gate ===="
printf '  ERC errors            : %s\n' "$erc_err"
printf '  DRC errors            : %s\n' "$drc_err"
printf '  DRC unconnected pads   : %s\n' "$drc_u"
printf '  DRC footprint errors   : %s\n' "$drc_f"
printf '  DRC warnings (cosmetic): %s   (silk/edge — see references/design-rules.md)\n' "$drc_warn"

# Optional belly keep-out gate: BELLY_BOX="x0,y0,x1,y1" runs belly_check.py (no F.Cu /
# vias under a flush-mounted module). DRC can't see this — it's mechanical, not net.
belly_ok=skip
if [ -n "${BELLY_BOX:-}" ]; then
  echo; echo "-> belly keep-out ($BELLY_BOX)"
  if "$PY" "$(dirname "$0")/belly_check.py" "$PROJ.kicad_pcb" $(echo "$BELLY_BOX" | tr ',' ' '); then
    belly_ok=pass; else belly_ok=FAIL; fi
fi
echo

if [ "$erc_err" = 0 ] && [ "$drc_err" = 0 ] && [ "$drc_u" = 0 ] && [ "$drc_f" = 0 ] && [ "$belly_ok" != FAIL ]; then
  echo "PASS  (0 errors / 0 unconnected).  $drc_warn cosmetic warning(s) left — clean if you like."
  echo "Then: run kicad-happy for the cross/EMC pass; package with scripts/fab_export.sh."
else
  echo "FAIL.  Open $PROJ-erc.rpt / $PROJ-drc.rpt — a DRC *error* is usually a real short, not noise."
  exit 2
fi
