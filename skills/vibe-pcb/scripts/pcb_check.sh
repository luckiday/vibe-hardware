#!/usr/bin/env bash
# Regenerate a script-built KiCad project, then run the gates: ERC + DRC + render.
# Run from the project's kicad/ dir (the one with gen_sch.py / gen_pcb.py).
#
#   tools/skills/vibe-pcb/scripts/pcb_check.sh <proj-basename>
#
# <proj-basename> is the .kicad_pcb name without extension (e.g. xiao-carrier).
# Tooling is auto-resolved (env KICAD_CLI/KICAD_PY override -> mac bundle ->
# PATH; see _kicad_env.sh). Works on KiCad 10 (full gates) and degrades
# honestly on KiCad 7/8-era CLIs: no `sch erc` -> ERC is SKIPPED with a loud
# note (run this again on a >=8 host before fab); no `pcb drc` -> DRC runs
# through pcbnew (drc_report.py) with identical report format.
set -eu

PROJ="${1:?usage: pcb_check.sh <proj-basename>   (run in the project kicad/ dir)}"

. "$(dirname "$0")/_kicad_env.sh"
S="$_VS"
[ -f gen_pcb.py ] || { echo "run me from the project kicad/ dir (no gen_pcb.py here)"; exit 1; }

echo "-> generate (gen_sch.py + gen_pcb.py)"
python3 gen_sch.py            # schematic writer — plain python (pcblib.sch is stdlib)
"$PY"   gen_pcb.py            # pcb builder — needs a python with pcbnew

erc_ran=yes
if cli_has sch erc; then
  echo "-> ERC";  "$CLI" sch erc "$PROJ.kicad_sch" -o "$PROJ-erc.rpt" >/dev/null
else
  erc_ran=no
  echo "-> ERC: SKIPPED (this kicad-cli predates 'sch erc' — run pcb_check.sh on a KiCad >=8 host before fab)"
fi

if cli_has pcb drc; then
  echo "-> DRC";  "$CLI" pcb drc --refill-zones "$PROJ.kicad_pcb" -o "$PROJ-drc.rpt" >/dev/null
else
  echo "-> DRC (pcbnew fallback)"; "$PY" "$S/drc_report.py" "$PROJ.kicad_pcb" "$PROJ-drc.rpt" >/dev/null
fi

echo "-> render"; render_top "$PROJ.kicad_pcb" "$PROJ-pcb-top.png"

# --- parse gate counts. CRUCIAL: a DRC "violation" can be error- OR warning-severity.
# "Found N violations" is the TOTAL — counting it as the fail metric flags benign silk
# warnings (text height, edge clip) as failures. Gate on ERROR severity + unconnected;
# report warnings separately. (This false-fail bit us: 10 silk warnings != a fail.) ---
num() { grep -oE "$1" "$2" 2>/dev/null | grep -oE '[0-9]+' | head -1; }
if [ "$erc_ran" = yes ]; then
  erc_err=$(grep -oE 'Errors[[:space:]]+[0-9]+' "$PROJ-erc.rpt" 2>/dev/null | awk '{s+=$2} END{print s+0}')
else
  erc_err=SKIP
fi
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
  if "$PY" "$S/belly_check.py" "$PROJ.kicad_pcb" $(echo "$BELLY_BOX" | tr ',' ' '); then
    belly_ok=pass; else belly_ok=FAIL; fi
fi
echo

if { [ "$erc_err" = 0 ] || [ "$erc_err" = SKIP ]; } && [ "$drc_err" = 0 ] \
    && [ "$drc_u" = 0 ] && [ "$drc_f" = 0 ] && [ "$belly_ok" != FAIL ]; then
  if [ "$erc_err" = SKIP ]; then
    echo "PASS* (DRC 0 errors / 0 unconnected; ERC NOT RUN on this host).  $drc_warn cosmetic warning(s)."
    echo "Re-run on a KiCad >=8 host for the ERC gate before fab."
  else
    echo "PASS  (0 errors / 0 unconnected).  $drc_warn cosmetic warning(s) left — clean if you like."
    echo "Then: run kicad-happy for the cross/EMC pass; package with scripts/fab_export.sh."
  fi
else
  echo "FAIL.  Open $PROJ-erc.rpt / $PROJ-drc.rpt — a DRC *error* is usually a real short, not noise."
  exit 2
fi
