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
#   - <proj>-<stage>-top.png   top render: where the parts actually sit
# The generator also prints the numeric gates (pcblib scorecard: courtyard/cluster
# overlaps, keepouts, HPWL). Nudge cluster origins without editing code:
#   MOVE="AUDIO:-3,2;UI:0,4" pcb_skeleton.sh <proj> floorplan
# Loop: floorplan -> read -> fix placement -> place -> read -> route (full) -> read.
set -eu

PROJ="${1:?usage: pcb_skeleton.sh <proj> <floorplan|place>   (run in the project kicad/ dir)}"
STAGE="${2:?usage: pcb_skeleton.sh <proj> <floorplan|place>}"
case "$STAGE" in floorplan|place) ;; *) echo "stage must be floorplan|place"; exit 1;; esac

. "$(dirname "$0")/_kicad_env.sh"
[ -f gen_pcb.py ] || { echo "run me from the project kicad/ dir (no gen_pcb.py here)"; exit 1; }

echo "-> generate skeleton (STAGE=$STAGE)"
STAGE="$STAGE" "$PY" gen_pcb.py
BRD="$PROJ.$STAGE.kicad_pcb"
[ -f "$BRD" ] || { echo "stage file $BRD not written — does gen_pcb.py honor STAGE?"; exit 1; }

echo "-> 2D placement plot (PDF): outline + fab + courtyards + cluster boxes"
"$CLI" pcb export pdf "$BRD" -o "$PROJ-$STAGE.pdf" \
   --layers "Edge.Cuts,Dwgs.User,F.Fab,B.Fab,F.Courtyard,B.Courtyard,F.Silkscreen" \
   --black-and-white >/dev/null

echo "-> top render (PNG): where the parts sit"
render_top "$BRD" "$PROJ-$STAGE-top.png"

echo
echo "skeleton ready — READ then iterate:"
echo "   2D : $PROJ-$STAGE.pdf"
echo "   top: $PROJ-$STAGE-top.png"
echo "Fix placement in gen_pcb.py (move a cluster origin / a relation), re-run. Route only"
echo "once the floorplan + place views read right (then: STAGE unset -> full -> pcb_check.sh)."
