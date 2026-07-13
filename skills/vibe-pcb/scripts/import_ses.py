#!/usr/bin/env python3
"""Import a freerouting .ses onto the placed board and re-add the pour + silk that the
autoroute detour skipped. Part of the vibe-pcb autoroute flow (references/autorouting.md).

kicad-cli has NO Specctra import (`pcb import` only takes Eagle etc.). The bundled pcbnew
Python is the only headless way back in -> pcbnew.ImportSpecctraSES(board, file) (KiCad 10).

Key fix encoded here: freerouting routes GND as copper, so a GND pour with the default
THERMAL relief on top of that trips DRC [starved_thermal]. We pour GND with SOLID pad
connection (ZONE_CONNECTION_FULL) so the pour merges with the routed copper. The pour
outline is the board's Edge.Cuts bounding box (fill is auto-clipped to the real edge).

Run with KiCad's BUNDLED python:
  import_ses.py <place.kicad_pcb> <in.ses> <out.kicad_pcb>

Env (all optional):
  BELLY_BOX="x0,y0,x1,y1"  re-add the no-fill belly rule area (keeps the F.Cu pour out)
  GND_NET="GND"            net to pour on F.Cu + B.Cu (empty = skip pours)
  SILK_FIX_REF="A1"        move this footprint's F.SilkS graphics to F.Fab (edge-overhang)
"""
import os, sys, pcbnew
from pcbnew import VECTOR2I, FromMM as MM

if len(sys.argv) != 4:
    sys.exit(__doc__)
PLACE, SES, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
BELLY   = os.environ.get("BELLY_BOX")
GND_NET = os.environ.get("GND_NET", "GND")
SILK_FIX_REF = os.environ.get("SILK_FIX_REF")

board = pcbnew.LoadBoard(PLACE)
if not pcbnew.ImportSpecctraSES(board, SES):
    sys.exit("ImportSpecctraSES failed")
board.BuildConnectivity()
ntrk = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_TRACK")
nvia = sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA")
print(f"imported: tracks={ntrk} vias={nvia}")

def edge_bbox():
    xs, ys = [], []
    for d in board.GetDrawings():
        if d.GetClass() == "PCB_SHAPE" and d.GetLayer() == pcbnew.Edge_Cuts:
            for p in (d.GetStart(), d.GetEnd()):
                xs.append(pcbnew.ToMM(p.x)); ys.append(pcbnew.ToMM(p.y))
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None

# the zone construction lives ONCE, in pcblib.route (PYTHONPATH is set by
# autoroute.sh; both helpers take sheet-frame mm boxes)
from pcblib.route import _kicad_rule_area, _kicad_pour

if BELLY:
    box = tuple(float(v) for v in BELLY.split(","))
    z = _kicad_rule_area(board, box, layers=(pcbnew.F_Cu,), name="belly")
    # after routing only the POUR must stay out (copper was router-checked);
    # keep tracks/vias allowed so DRC doesn't re-flag the imported route
    z.SetDoNotAllowTracks(False)
    z.SetDoNotAllowVias(False)

if GND_NET:
    bb = edge_bbox()
    if not bb:
        sys.exit("no Edge.Cuts found -- cannot place GND pour")
    gc = board.GetNetInfo().GetNetItem(GND_NET).GetNetCode()
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        _kicad_pour(board, layer, gc, bb)

if SILK_FIX_REF:
    for fp in board.GetFootprints():
        if fp.GetReference() == SILK_FIX_REF:
            for it in fp.GraphicalItems():
                if it.GetLayer() == pcbnew.F_SilkS:
                    it.SetLayer(pcbnew.F_Fab)

board.BuildConnectivity()
board.Save(OUT)
print("wrote", OUT)
