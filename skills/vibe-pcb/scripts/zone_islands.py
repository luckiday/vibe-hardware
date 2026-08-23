#!/usr/bin/env python3
"""zone_islands.py — why is a pour "unconnected"? Show its islands and what is in them.

DRC reports a fenced-off copper pour as one cryptic line:

    Zone [GND] on B.Cu, priority 0  <->  Zone [GND] on F.Cu, priority 0

…with a position that points at the board corner, not at the problem. That
single message can mean any of: a pocket the pour reached but nothing ties
down, a pocket with a via that only bridges it to ANOTHER orphan pocket (an
"enclave" — locally connected, globally isolated), or a genuinely split plane.
Chasing it by adding stitching vias at guessed coordinates does not converge.

This prints, per filled zone, every island with its bounding box and the pads
and vias of that net INSIDE it — so the fix is a coordinate you can read off:

    F.Cu GND  island  x[  6.0, 18.6] y[  2.1,  9.0]  12.6 x  6.9 mm   pads 0  vias 0   << ORPHAN
    B.Cu GND  island  x[-29.9,-25.2] y[  5.7,  9.8]   4.7 x  4.1 mm   pads 2  vias 1

An island with 0 pads and 0 vias is dead copper: either stitch it or let
island removal delete it. An island whose only via leads to another orphan is
the enclave case — the report shows both, and the bridge goes where one layer
is inside the enclave and the other is main pour.

Usage:
    zone_islands.py <board.kicad_pcb> [--net GND] [--max-mm 70] [--strict]

  --net      only this net (default: every zone with a net)
  --max-mm   only report islands smaller than this across (default: all)
  --strict   exit 1 if any island has no pad and no via of its net

Run with KiCad's BUNDLED python (the one with pcbnew).

Two pcbnew traps this script exists to avoid, both measured on KiCad 10:
  - ZONE.GetLayerName() returns "F.Cu" for a B.Cu zone. Read the layer from
    GetLayerSet().Seq() (GetLayer() is also correct; only the NAME lies).
  - GetFilledPolysList() takes the layer -- pass the zone's true layer or you
    are looking at the wrong fill (or none).
"""
import sys

import pcbnew


def _args(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        sys.exit(__doc__)
    opts = {"board": argv[1], "net": None, "max_mm": None, "strict": False}
    i = 2
    while i < len(argv):
        a = argv[i]
        if a == "--net":
            i += 1
            opts["net"] = argv[i]
        elif a == "--max-mm":
            i += 1
            opts["max_mm"] = float(argv[i])
        elif a == "--strict":
            opts["strict"] = True
        else:
            sys.exit(f"unknown argument {a!r}\n\n{__doc__}")
        i += 1
    return opts


def _mm(v):
    return v / 1e6


def _inside(poly, pt):
    """Ray-cast point-in-polygon; poly is [(x, y)…] in mm, pt is (x, y)."""
    x, y = pt
    n = len(poly)
    hit = False
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def islands(board_path, net_filter=None, max_mm=None):
    """[(layer_name, net, [(x0,y0,x1,y1)], pads, vias)] for every filled island."""
    board = pcbnew.LoadBoard(board_path)
    layer_name = pcbnew.BOARD.GetStandardLayerName

    # pads and vias, per net, in mm — the things that can tie an island down
    anchors = {}
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            n = pad.GetNetname()
            if n:
                p = pad.GetPosition()
                anchors.setdefault(n, {"pads": [], "vias": []})["pads"].append(
                    (_mm(p.x), _mm(p.y)))
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA" and t.GetNetname():
            p = t.GetPosition()
            anchors.setdefault(t.GetNetname(), {"pads": [], "vias": []})["vias"].append(
                (_mm(p.x), _mm(p.y)))

    out = []
    for z in board.Zones():
        if z.GetIsRuleArea():
            continue
        net = z.GetNetname()
        if not net or (net_filter and net != net_filter):
            continue
        # the layer NAME accessor lies for B.Cu zones; use the layer set
        for layer in z.GetLayerSet().Seq():
            fill = z.GetFilledPolysList(layer)
            for i in range(fill.OutlineCount()):
                o = fill.Outline(i)
                poly = [(_mm(o.CPoint(j).x), _mm(o.CPoint(j).y))
                        for j in range(o.PointCount())]
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                if max_mm and (max(xs) - min(xs)) > max_mm:
                    continue
                a = anchors.get(net, {"pads": [], "vias": []})
                out.append({
                    "layer": layer_name(layer), "net": net,
                    "box": (min(xs), min(ys), max(xs), max(ys)),
                    "pads": sum(1 for p in a["pads"] if _inside(poly, p)),
                    "vias": sum(1 for v in a["vias"] if _inside(poly, v)),
                })
    return out


def main(argv):
    o = _args(argv)
    rows = islands(o["board"], o["net"], o["max_mm"])
    if not rows:
        print("no filled zones matched (did the board get refilled? "
              "kicad-cli pcb drc --refill-zones --save-board)")
        return 0
    orphans = 0
    for r in rows:
        x0, y0, x1, y1 = r["box"]
        flag = ""
        if r["pads"] == 0 and r["vias"] == 0:
            flag = "   << ORPHAN (no pad, no via of this net inside)"
            orphans += 1
        print(f'{r["layer"]:5} {r["net"]:8} island  '
              f'x[{x0:7.1f},{x1:7.1f}] y[{y0:7.1f},{y1:7.1f}]  '
              f'{x1 - x0:5.1f} x {y1 - y0:5.1f} mm   '
              f'pads {r["pads"]:2}  vias {r["vias"]:2}{flag}')
    print(f"\n{len(rows)} island(s), {orphans} orphan(s)")
    if orphans and o["strict"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
