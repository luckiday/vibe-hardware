#!/usr/bin/env bash
# Staged SKELETON render for the layered-layout visual-feedback loop.
# (See SKILL.md -> "Layered layout + the visual feedback loop" and
#  references/design-rules.md -> "Layered layout & the feedback loop".)
#
#   pcb_skeleton.sh <proj> <floorplan|place>     # run from the project kicad/ dir
#
# Regenerates ONLY the skeleton stage (STAGE=... gen_pcb.py writes a separate
# <proj>.<stage>.kicad_pcb — never the canonical board) and renders it two ways for
# you (the model) to READ before committing copper:
#   - <proj>-<stage>.pdf       2D top-down: Edge.Cuts + fab outlines + courtyards
#                              + Dwgs.User cluster boxes (floorplan stage)  -> read this
#   - <proj>-<stage>-top.png   3D top render: where the parts actually sit
# The generator also prints the cheap numeric gates (placement HPWL + pad overlaps).
# Loop: floorplan -> read -> fix placement -> place -> read -> route (full) -> read.
set -eu

PROJ="${1:?usage: pcb_skeleton.sh <proj> <floorplan|place>   (run in the project kicad/ dir)}"
STAGE="${2:?usage: pcb_skeleton.sh <proj> <floorplan|place>}"
case "$STAGE" in floorplan|place) ;; *) echo "stage must be floorplan|place"; exit 1;; esac

KC="/Applications/KiCad/KiCad.app/Contents"
CLI="${KICAD_CLI:-$KC/MacOS/kicad-cli}"
PY="${KICAD_PY:-$KC/Frameworks/Python.framework/Versions/Current/bin/python3}"  # has pcbnew
[ -x "$CLI" ] || { echo "kicad-cli not found at: $CLI   (set KICAD_CLI)"; exit 1; }
[ -x "$PY" ]  || { echo "bundled python not found at: $PY   (set KICAD_PY)"; exit 1; }
[ -f gen_pcb.py ] || { echo "run me from the project kicad/ dir (no gen_pcb.py here)"; exit 1; }

echo "-> generate skeleton (STAGE=$STAGE)"
STAGE="$STAGE" "$PY" gen_pcb.py
BRD="$PROJ.$STAGE.kicad_pcb"
[ -f "$BRD" ] || { echo "stage file $BRD not written — does gen_pcb.py honor STAGE?"; exit 1; }

echo "-> 2D placement plot (PDF): outline + fab + courtyards + cluster boxes"
"$CLI" pcb export pdf "$BRD" -o "$PROJ-$STAGE.pdf" --mode-single \
   --layers "Edge.Cuts,Dwgs.User,F.Fab,B.Fab,F.Courtyard,B.Courtyard,F.Silkscreen" \
   --black-and-white >/dev/null

echo "-> 3D top render (PNG): where the parts sit"
"$CLI" pcb render "$BRD" -o "$PROJ-$STAGE-top.png" \
   --side top --background opaque -w 950 --height 600 >/dev/null

echo
echo "skeleton ready — READ then iterate:"
echo "   2D : $PROJ-$STAGE.pdf"
echo "   3D : $PROJ-$STAGE-top.png"
echo "Fix placement in gen_pcb.py (move a cluster anchor / a slot), re-run. Route only"
echo "once the floorplan + place views read right (then: STAGE unset -> full -> pcb_check.sh)."
