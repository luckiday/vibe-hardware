"""Computed copper. Routing preference order (references/autorouting.md):

  1. freerouting via autoroute.sh, replayed with apply_ses() — the primary path
  2. scripted routes with THIS vocabulary — endpoints come from Part.pad(),
     waypoints are relative steps; no absolute mm literal ever names a trace

Also home to the pour/rule-area helpers shared with import_ses.py (one
implementation — import_ses.py imports these).

All generator-facing functions take the layout.Board wrapper and board-frame
mm; the _kicad_* helpers at the bottom take a raw pcbnew.BOARD in sheet mm.
"""

from __future__ import annotations

import pcbnew
from pcbnew import VECTOR2I, FromMM as MM

__all__ = [
    "path", "wire", "via", "fanout_decoupling", "gnd_pours", "apply_ses",
]

_LAYERS = {"F.Cu": pcbnew.F_Cu, "B.Cu": pcbnew.B_Cu}


# ------------------------------------------------------------------- waypoint DSL

def path(start, *steps):
    """Resolve a waypoint chain into board-frame points.

    start: (x, y) — normally a Part.pad(n), NOT a literal.
    each step: "dx+3.5" / "dy-2"  relative move
               "x=12" / "y=40"    set one coordinate (other kept)
               (x, y)             a point — normally the far pad, not a literal
    Returns [pt, pt, ...] including start.
    """
    pts = [tuple(start)]
    for s in steps:
        x, y = pts[-1]
        if isinstance(s, str):
            if s.startswith("dx"):
                pts.append((x + float(s[2:]), y))
            elif s.startswith("dy"):
                pts.append((x, y + float(s[2:])))
            elif s.startswith("x="):
                pts.append((float(s[2:]), y))
            elif s.startswith("y="):
                pts.append((x, float(s[2:])))
            else:
                raise ValueError(f"bad step {s!r}")
        else:
            pts.append((float(s[0]), float(s[1])))
    return pts


def wire(board, net: str, pts, layer: str = "F.Cu", w: float = 0.3,
         bend: str = None):
    """Lay track segments through pts (board frame mm). With bend='x'/'y' and
    exactly two points, insert the L-corner (go x-first / y-first)."""
    pts = [tuple(p) for p in pts]
    if bend and len(pts) == 2:
        (x0, y0), (x1, y1) = pts
        corner = (x1, y0) if bend == "x" else (x0, y1)
        if corner not in (pts[0], pts[1]):
            pts = [pts[0], corner, pts[1]]
    code = board.net(net)
    for a, b in zip(pts, pts[1:]):
        if a == b:
            continue
        t = pcbnew.PCB_TRACK(board.pcb)
        t.SetStart(board.xy(*a))
        t.SetEnd(board.xy(*b))
        t.SetLayer(_LAYERS[layer])
        t.SetWidth(MM(w))
        t.SetNetCode(code)
        board.pcb.Add(t)
    return pts[-1]


def via(board, net: str, at, size: float = 0.6, drill: float = 0.3):
    """Through via at a point (normally a pad or a wire() return)."""
    v = pcbnew.PCB_VIA(board.pcb)
    v.SetPosition(board.xy(*at))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetWidth(MM(size))
    v.SetDrill(MM(drill))
    v.SetNetCode(board.net(net))
    board.pcb.Add(v)
    return tuple(at)


def fanout_decoupling(board, cap, cap_pad, ic, ic_pad, net: str,
                      layer: str = "F.Cu", w: float = 0.3):
    """The decoupling stub, computed: cap pad -> IC supply pad. Place the cap
    with align_pads() first so this is a short straight/L run."""
    a, b = cap.pad(cap_pad), ic.pad(ic_pad)
    bend = "x" if abs(a[1] - b[1]) < abs(a[0] - b[0]) else "y"
    wire(board, net, [a, b], layer=layer, w=w, bend=bend)


def gnd_pours(board, net: str = "GND"):
    """GND pour on F+B, SOLID pad connection (see import_ses.py header for why)."""
    bb = board.pcb.GetBoardEdgesBoundingBox()
    box = (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
           pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        _kicad_pour(board.pcb, layer, board.net(net), box)


def apply_ses(board, ses_path: str):
    """Replay an accepted freerouting session (committed pcb/routing.ses) onto
    the placed board — the regenerable-routing path."""
    if not pcbnew.ImportSpecctraSES(board.pcb, ses_path):
        raise RuntimeError(f"ImportSpecctraSES failed on {ses_path}")
    board.pcb.BuildConnectivity()


# ------------------------------------------- raw-pcbnew helpers (shared with
# import_ses.py; sheet-frame mm, no layout.Board needed)

def _kicad_pour(pcb, layer, netcode: int, box):
    """SOLID-connection copper pour over box=(x0,y0,x1,y1) sheet mm."""
    x0, y0, x1, y1 = box
    z = pcbnew.ZONE(pcb)
    z.SetLayer(layer)
    z.SetNetCode(netcode)
    z.SetAssignedPriority(0)
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    o = z.Outline(); o.NewOutline()
    for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
        o.Append(VECTOR2I(MM(x), MM(y)))
    pcb.Add(z)
    return z


def _kicad_rule_area(pcb, box, layers=(pcbnew.F_Cu,), name: str = ""):
    """No-fill/track/via rule area over box=(x0,y0,x1,y1) sheet mm."""
    x0, y0, x1, y1 = box
    z = pcbnew.ZONE(pcb)
    z.SetIsRuleArea(True)
    # KiCad 7 calls it CopperPour; 8+ renamed to ZoneFills — support both
    no_fill = getattr(z, "SetDoNotAllowZoneFills",
                      getattr(z, "SetDoNotAllowCopperPour", None))
    no_fill(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    ls = pcbnew.LSET()
    for l in layers:
        ls.AddLayer(l)
    z.SetLayerSet(ls)
    if name:
        z.SetZoneName(name)
    o = z.Outline(); o.NewOutline()
    for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
        o.Append(VECTOR2I(MM(x), MM(y)))
    pcb.Add(z)
    return z
