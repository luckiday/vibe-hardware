#!/usr/bin/env python3
"""Belly keep-out verifier — the #1 module-carrier gotcha, made checkable.

A module that solder-mounts FLUSH (e.g. a XIAO on castellations) has exposed pads on
its underside (Thermal/JTAG/BAT/USB). Those will SHORT to any *front* copper or via
barrel under its body. Rule: under the module footprint, no F.Cu and no vias — route
those nets on B.Cu (the module is on F, so back copper never touches it); put vias and
any front jumpers in the board margins / off-body.

This proves the rule held after a regen. DRC will NOT catch it (it's a mechanical,
not electrical, constraint), so run it as a separate gate.

Run with KiCad's BUNDLED python (it has pcbnew):
  KC=/Applications/KiCad/KiCad.app/Contents
  "$KC/Frameworks/Python.framework/Versions/3.9/bin/python3" belly_check.py \
       <proj>.kicad_pcb  x0 y0 x1 y1

x0..y1 = the module body box in board mm (a small margin past the pad rows is fine;
the exposed pads sit between the rows). Find it from the footprint centre ± body size.
Exit 0 = clean, 2 = copper/vias found under the belly.
"""
import sys, pcbnew

if len(sys.argv) != 6:
    sys.exit(__doc__)
pcb = sys.argv[1]
x0, y0, x1, y1 = map(float, sys.argv[2:6])
b = pcbnew.LoadBoard(pcb)
mm = lambda v: v / 1e6
inbox = lambda x, y: x0 <= x <= x1 and y0 <= y <= y1

bad = []
for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        p = t.GetPosition()
        if inbox(mm(p.x), mm(p.y)):
            bad.append(f"VIA  {t.GetNetname():6} @({mm(p.x):.2f},{mm(p.y):.2f})")
    elif t.GetLayer() == pcbnew.F_Cu:
        s, e = t.GetStart(), t.GetEnd()
        sx, sy, ex, ey = mm(s.x), mm(s.y), mm(e.x), mm(e.y)
        # flag if either endpoint or the midpoint lands in the box
        if inbox(sx, sy) or inbox(ex, ey) or inbox((sx + ex) / 2, (sy + ey) / 2):
            bad.append(f"F.Cu {t.GetNetname():6} ({sx:.2f},{sy:.2f})->({ex:.2f},{ey:.2f})")

box = f"[{x0},{y0}]-[{x1},{y1}]"
if bad:
    print(f"FAIL belly keep-out {box}: front copper / vias under the module:")
    for x in bad:
        print("  -", x)
    sys.exit(2)
print(f"PASS belly keep-out {box}: no F.Cu, no vias under the module body.")
