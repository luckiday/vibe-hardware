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
    "path", "wire", "via", "fanout_decoupling", "fanout", "bridge_pads",
    "gnd_pours", "plane_pours", "apply_ses",
]

_LAYERS = {"F.Cu": pcbnew.F_Cu, "In1.Cu": pcbnew.In1_Cu,
           "In2.Cu": pcbnew.In2_Cu, "B.Cu": pcbnew.B_Cu}


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
         bend: str = None, lock: bool = False):
    """Lay track segments through pts (board frame mm). With bend='x'/'y' and
    exactly two points, insert the L-corner (go x-first / y-first). lock=True
    marks the tracks Locked — KiCad's DSN export then emits them (type fix),
    so freerouting treats them as untouchable pre-routes (fanout-first flow)."""
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
        t.SetLocked(lock)
        board.pcb.Add(t)
    return pts[-1]


def via(board, net: str, at, size: float = 0.6, drill: float = 0.3,
        lock: bool = False):
    """Through via at a point (normally a pad or a wire() return)."""
    v = pcbnew.PCB_VIA(board.pcb)
    v.SetPosition(board.xy(*at))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetWidth(MM(size))
    v.SetDrill(MM(drill))
    v.SetNetCode(board.net(net))
    v.SetLocked(lock)
    board.pcb.Add(v)
    return tuple(at)


def fanout_decoupling(board, cap, cap_pad, ic, ic_pad, net: str,
                      layer: str = "F.Cu", w: float = 0.3):
    """The decoupling stub, computed: cap pad -> IC supply pad. Place the cap
    with align_pads() first so this is a short straight/L run."""
    a, b = cap.pad(cap_pad), ic.pad(ic_pad)
    bend = "x" if abs(a[1] - b[1]) < abs(a[0] - b[0]) else "y"
    wire(board, net, [a, b], layer=layer, w=w, bend=bend)


def _fanout_obstacles(board):
    """Cached collision map for fanout(): every pad's (x, y, keepaway-radius,
    netcode). Radius = half the pad diagonal (or the drill for holes)."""
    if getattr(board, "_fanout_obs", None) is None:
        obs = []
        for f in board.pcb.GetFootprints():
            for p in f.Pads():
                x, y = board.from_kicad(p.GetPosition())
                bb = p.GetBoundingBox()
                r = (pcbnew.ToMM(bb.GetWidth()) ** 2 +
                     pcbnew.ToMM(bb.GetHeight()) ** 2) ** 0.5 / 2
                drill = pcbnew.ToMM(max(p.GetDrillSize().x, p.GetDrillSize().y))
                obs.append((x, y, max(r, drill / 2 + 0.3), p.GetNetCode()))
        board._fanout_obs = obs
        board._fanout_vias = []
    return board._fanout_obs


def _via_fits(board, at, net_code, via_size, clearance):
    """True if a via at `at` clears every foreign pad/hole and every fanout via."""
    vr = via_size / 2
    for x, y, r, nc in _fanout_obstacles(board):
        if nc == net_code and r < 1.0:
            continue                      # its own (small) pad — the stub target
        if (at[0] - x) ** 2 + (at[1] - y) ** 2 < (r + vr + clearance) ** 2:
            return False
    for x, y in board._fanout_vias:
        if (at[0] - x) ** 2 + (at[1] - y) ** 2 < (via_size + clearance) ** 2:
            return False
    return True


def fanout(board, part, nets, stub: float = 0.8, stagger: float = 0.6,
           w: float = 0.2, via_size: float = 0.4, via_drill: float = 0.2,
           direction: str = "out", ep_pitch: float = 1.1):
    """Fanout-first escape for the pads freerouting can't/won't do itself.

    For every SMD pad of `part` whose net is in `nets` (normally the plane
    nets — PTH pads reach an inner plane natively and are skipped):
      - perimeter pad -> a LOCKED stub straight out of the pad ring + a LOCKED
        through-via `stub` mm from the pad center. Same-facing pads alternate
        between two via rows (`stagger`), and every via is collision-checked
        against all pads/holes and previously placed fanout vias, sliding
        outward in `stagger` steps until it fits (skipped loudly if it never
        does). The via reaches the inner plane on a 4-layer board.
      - large pad (EP, both dims >= 1.5mm) -> a LOCKED thermal via grid on the
        pad itself (`ep_pitch`), no stub.

    via_size 0.4 is the geometric limit at 0.45mm QFN pitch with 0.15mm rules:
    via edge to the neighbour pad's stub = pitch - via/2 - w/2 = exactly the
    clearance. Locked copper exports to Specctra as (type fix): freerouting
    never rips it. Run freerouting with `-inc power` (the DSN power class) and
    the router only ever sees signals — the standard fanout-first flow (the
    2.2.x routers deleted their own fanout pass; references/autorouting.md).

    direction: 'out' = away from the part center (QFN/module escape);
               'in'  = toward the board center (edge connectors, where 'out'
               would walk off the board).
    """
    clearance = 0.15
    _fanout_obstacles(board)                     # prime the cache
    fc = board.from_kicad(part.fp.GetPosition())
    bc = (board.L / 2.0, board.W / 2.0)
    groups = {}                                  # (dx,dy) -> [(perp, pad, pos)]
    n_vias = 0
    for p in part.fp.Pads():
        net = p.GetNetname()
        if net not in nets or p.GetAttribute() != pcbnew.PAD_ATTRIB_SMD:
            continue
        pos = board.from_kicad(p.GetPosition())
        bb = p.GetBoundingBox()
        pw, ph = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
        if min(pw, ph) >= 1.5:                   # EP -> thermal via grid
            nx = max(1, int((pw - 0.6) / ep_pitch) + 1)
            ny = max(1, int((ph - 0.6) / ep_pitch) + 1)
            for i in range(nx):
                for j in range(ny):
                    at = (pos[0] - (nx - 1) * ep_pitch / 2 + i * ep_pitch,
                          pos[1] - (ny - 1) * ep_pitch / 2 + j * ep_pitch)
                    via(board, net, at, size=via_size + 0.15,
                        drill=via_drill + 0.1, lock=True)
                    board._fanout_vias.append(at)
                    n_vias += 1
            continue
        ref = fc if direction == "out" else pos
        tgt = pos if direction == "out" else bc
        vx, vy = tgt[0] - ref[0], tgt[1] - ref[1]
        d = ((1 if vx > 0 else -1), 0) if abs(vx) >= abs(vy) \
            else (0, (1 if vy > 0 else -1))
        perp = pos[1] if d[0] else pos[0]
        groups.setdefault(d, []).append((perp, p, pos))
    layer = "B.Cu" if part.side() == "B" else "F.Cu"
    for d, pads in groups.items():
        pads.sort(key=lambda t: t[0])
        for i, (_, p, pos) in enumerate(pads):
            dist = stub + (i % 2) * stagger
            for _try in range(6):                # slide outward until clear
                at = (pos[0] + d[0] * dist, pos[1] + d[1] * dist)
                if _via_fits(board, at, p.GetNetCode(), via_size, clearance):
                    break
                dist += stagger
            else:
                print(f"fanout: NO ROOM for {part.ref}.{p.GetPadName()} "
                      f"[{p.GetNetname()}] via — pad left to the pour")
                continue
            wire(board, p.GetNetname(), [pos, at], layer=layer, w=w, lock=True)
            via(board, p.GetNetname(), at, size=via_size, drill=via_drill,
                lock=True)
            board._fanout_vias.append(at)
            n_vias += 1
    return n_vias


def bridge_pads(board, part, net: str, w: float = 0.3):
    """LOCKED jumpers chaining every same-net SMD pad of one footprint — the
    USB-C 16P A/B mirror-pad pattern (A6<->B6 etc.), which autorouters at a
    board edge reliably fail. Nearest-neighbour chain, straight segments."""
    todo = [(board.from_kicad(p.GetPosition()), p) for p in part.fp.Pads()
            if p.GetNetname() == net
            and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    if len(todo) < 2:
        return 0
    layer = "B.Cu" if part.side() == "B" else "F.Cu"
    chain = [todo.pop(0)]
    n = 0
    while todo:
        cx, cy = chain[-1][0]
        todo.sort(key=lambda t: (t[0][0] - cx) ** 2 + (t[0][1] - cy) ** 2)
        nxt = todo.pop(0)
        wire(board, net, [chain[-1][0], nxt[0]], layer=layer, w=w, lock=True)
        chain.append(nxt)
        n += 1
    return n


def gnd_pours(board, net: str = "GND"):
    """GND pour on F+B, SOLID pad connection (see import_ses.py header for why)."""
    bb = board.pcb.GetBoardEdgesBoundingBox()
    box = (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
           pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
        _kicad_pour(board.pcb, layer, board.net(net), box)


def plane_pours(board, mapping: dict):
    """Solid inner-layer planes on a 4-layer board: mapping {layer: net}, e.g.
    {"In1.Cu": "GND", "In2.Cu": "+3V3"}. Add these on the PLACED board (before the
    STAGE=place save) so ExportSpecctraDSN emits them as Specctra planes — then
    freerouting drops GND/power pads straight to the plane with a via instead of
    routing them as tracks on the outer layers, which is what makes a dense board
    routable. The pour is clipped to the board edge and honours the antenna/belly
    keepouts already drawn on every copper layer (see Board._draw_keepouts)."""
    bb = board.pcb.GetBoardEdgesBoundingBox()
    box = (pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
           pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom()))
    for layer, net in mapping.items():
        _kicad_pour(board.pcb, _LAYERS[layer], board.net(net), box)


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
