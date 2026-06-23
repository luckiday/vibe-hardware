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

if BELLY:
    x0, y0, x1, y1 = (float(v) for v in BELLY.split(","))
    z = pcbnew.ZONE(board); z.SetLayer(pcbnew.F_Cu); z.SetIsRuleArea(True)
    z.SetDoNotAllowZoneFills(True)
    for c in (z.SetDoNotAllowPads, z.SetDoNotAllowVias, z.SetDoNotAllowTracks,
              z.SetDoNotAllowFootprints):
        c(False)
    o = z.Outline(); o.NewOutline()
    for x, y in [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]:
        o.Append(VECTOR2I(MM(x), MM(y)))
    board.Add(z)

if GND_NET:
    bb = edge_bbox()
    if not bb:
        sys.exit("no Edge.Cuts found -- cannot place GND pour")
    gx0, gy0, gx1, gy1 = bb
    gc = board.GetNetInfo().GetNetItem(GND_NET).GetNetCode()
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        z = pcbnew.ZONE(board); z.SetLayer(layer); z.SetNetCode(gc); z.SetAssignedPriority(0)
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)   # solid -- GND already trace-routed
        o = z.Outline(); o.NewOutline()
        for x, y in [(gx0,gy0),(gx1,gy0),(gx1,gy1),(gx0,gy1)]:
            o.Append(VECTOR2I(MM(x), MM(y)))
        board.Add(z)

if SILK_FIX_REF:
    for fp in board.GetFootprints():
        if fp.GetReference() == SILK_FIX_REF:
            for it in fp.GraphicalItems():
                if it.GetLayer() == pcbnew.F_SilkS:
                    it.SetLayer(pcbnew.F_Fab)

board.BuildConnectivity()
board.Save(OUT)
print("wrote", OUT)
