#!/usr/bin/env python3
"""Generate macropad.kicad_pcb from the contracts — the vibe-pcb way.

The .kicad_pcb is an OUTPUT (gitignored, regenerated); the sources are:

  ../../cad/constraints.yaml   outline, mount holes, ports, antenna keepout
  ../parts.yaml                ref -> footprint / value / pad->net / placement
  ../pinmap.yaml               signal <-> GPIO (read by plm_check + firmware)

Nothing a contract owns is re-typed here (one number, one place).

What this generator emits is the PLACEMENT plus a LOCKED ROUTING SKELETON:
the USB fanout, the whole V3V3 tree, GND stubs and stitching vias. Everything
else is left to freerouting (../kicad/route_fr.sh). The skeleton is locked
(`SetLocked`) so it exports as Specctra `(type fix)` and the router treats it
as an obstacle instead of re-routing it — see the skill's
references/autorouting.md, "Freerouting at scale".

Two variants, selected by env:
  ROUTE=none    placement + pours + skeleton, no signal copper (the DSN source)
  GNDLESS=1     additionally strip the GND net from PADS, so freerouting sees
                no ground to route (the pours carry it on the real board)

Run with KiCad's bundled python (the one with pcbnew):
  KICAD_PY=/path/to/kicad/python3 ; $KICAD_PY gen_pcb.py
Footprint libraries are found via KICAD_FOOTPRINT_DIRS (colon-separated) or
the platform defaults.
"""
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(
    HERE, "..", "..", "..", "..", "skills", "vibe-pcb", "scripts")))
from pcblib import load_constraints, load_parts          # noqa: E402
from pcblib.layout import _find_pretty                   # noqa: E402

OUT = os.path.join(HERE, "macropad.kicad_pcb")

C = load_constraints(os.path.join(HERE, "..", "..", "cad", "constraints.yaml"))
P = load_parts(os.path.join(HERE, "..", "parts.yaml"))
RAW = P.data["parts"]                 # placement keys pcblib's PartSpec drops

BOARD_W, BOARD_H = C.outline_l, C.outline_w
CX, CY = 100.0, 80.0          # board centre in the KiCad sheet
W_SIG, W_PWR = 0.25, 0.5      # mm

# The contract's antenna keepout, converted from the board frame (origin
# bottom-left) into this file's design frame (centre origin, +y up).
_KEEPOUTS = {name: (x0 - BOARD_W / 2, y0 - BOARD_H / 2,
                    x1 - BOARD_W / 2, y1 - BOARD_H / 2)
             for name, (x0, y0, x1, y1) in C.keepout_boxes()}


def mm(v):
    return pcbnew.FromMM(v)


def K(x, y):
    """Design frame (centre origin, +y up) -> KiCad sheet position."""
    return pcbnew.VECTOR2I(mm(CX + x), mm(CY - y))


board = pcbnew.CreateEmptyBoard() if hasattr(pcbnew, "CreateEmptyBoard") else pcbnew.BOARD()

# The official WROOM land carries 0.2 mm thermal vias in its EPAD; the default
# min-through-hole constraint (0.3) would flag every one of them.
ds = board.GetDesignSettings()
ds.m_MinThroughDrill = mm(0.2)
# 0.3 mm connector pads force necked escapes; 0.15 mm is inside JLC's process
ds.m_TrackMinWidth = mm(0.15)
# The default netclass rides into the Specctra DSN export, which is how
# freerouting learns our widths -- without it, it routes at its own minimum.
try:
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetTrackWidth(mm(0.25))
    nc.SetClearance(mm(0.2))
    nc.SetViaDiameter(mm(0.6))
    nc.SetViaDrill(mm(0.3))
    pwr = pcbnew.NETCLASS("PWR")
    pwr.SetTrackWidth(mm(0.5))
    pwr.SetClearance(mm(0.2))
    pwr.SetViaDiameter(mm(0.6))
    pwr.SetViaDrill(mm(0.3))
    ds.m_NetSettings.SetNetclass("PWR", pwr)
    for pn in ("VBUS", "V3V3"):
        ds.m_NetSettings.SetNetclassPatternAssignment(pn, "PWR")
except AttributeError:
    pass

# ---- nets -------------------------------------------------------------------
net_names = sorted(P.nets())
nets = {}
for name in net_names:
    ni = pcbnew.NETINFO_ITEM(board, name)
    board.Add(ni)
    nets[name] = ni

# ---- outline ----------------------------------------------------------------
x0, y0 = mm(CX - BOARD_W / 2), mm(CY - BOARD_H / 2)
x1, y1 = mm(CX + BOARD_W / 2), mm(CY + BOARD_H / 2)
corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
for i in range(4):
    seg = pcbnew.PCB_SHAPE(board)
    seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
    seg.SetStart(pcbnew.VECTOR2I(*corners[i]))
    seg.SetEnd(pcbnew.VECTOR2I(*corners[(i + 1) % 4]))
    seg.SetLayer(pcbnew.Edge_Cuts)
    seg.SetWidth(mm(0.1))
    board.Add(seg)

# ---- footprints -------------------------------------------------------------
fps = {}
for ref, p in RAW.items():
    lib, name = p["footprint"].split(":")
    fp = pcbnew.FootprintLoad(_find_pretty(lib), name)
    if fp is None:
        sys.exit(f"footprint not found: {p['footprint']}")
    fp.SetReference(ref)
    fp.SetValue(str(p.get("value", "")))
    tx, ty = p["at"]
    pos = K(tx, ty)
    if "center" in p:  # footprint origin is not the part centre we placed
        cx_off, cy_off = p["center"]
        pos = pcbnew.VECTOR2I(pos.x - mm(cx_off), pos.y - mm(cy_off))
    fp.SetPosition(pos)
    if p.get("rot"):
        fp.SetOrientationDegrees(p["rot"])
    for pad in fp.Pads():
        net = P.netmap(ref).get(pad.GetNumber())
        # GNDLESS=1: the freerouting variant. The DSN has no plane concept, so
        # a netted GND makes the router wire 28 pads together straight through
        # the connector column. Netless GND pads are obstacles instead; the
        # pours pick them up when the .ses replays onto the real board.
        if net == "GND" and os.environ.get("GNDLESS"):
            continue
        if net:
            pad.SetNet(nets[net])
    board.Add(fp)
    fps[ref] = fp


def pad_pos(ref, num):
    for pad in fps[ref].Pads():
        if pad.GetNumber() == str(num):
            return pad.GetPosition()
    sys.exit(f"no pad {num} on {ref}")


# ---- antenna keepout (rule area, both layers, no copper of any kind) --------
ka = pcbnew.ZONE(board)
ka.SetIsRuleArea(True)
ka.SetDoNotAllowZoneFills(True)
ka.SetDoNotAllowTracks(True)
ka.SetDoNotAllowVias(True)
ka.SetDoNotAllowPads(False)
lset = pcbnew.LSET()
lset.AddLayer(pcbnew.F_Cu)
lset.AddLayer(pcbnew.B_Cu)
ka.SetLayerSet(lset)
outline = ka.Outline()
outline.NewOutline()
ant_x0, ant_y0, ant_x1, ant_y1 = _KEEPOUTS["antenna"]
for tx, ty in [(ant_x0, ant_y0), (ant_x1, ant_y0),
               (ant_x1, ant_y1), (ant_x0, ant_y1)]:
    v = K(tx, ty)
    outline.Append(v.x, v.y)
board.Add(ka)

# ---- GND pours on both layers ----------------------------------------------
for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(board)
    zl = pcbnew.LSET()
    zl.AddLayer(layer)
    z.SetLayerSet(zl)
    z.SetNet(nets["GND"])
    z.SetLocalClearance(mm(0.25))
    z.SetMinThickness(mm(0.2))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    # orphan pockets fenced off by routing are deleted at fill time, the
    # standard island-removal setting a GUI zone gets by default
    z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    o = z.Outline()
    o.NewOutline()
    for tx, ty in [(-BOARD_W / 2, -BOARD_H / 2), (BOARD_W / 2, -BOARD_H / 2),
                   (BOARD_W / 2, BOARD_H / 2), (-BOARD_W / 2, BOARD_H / 2)]:
        v = K(tx, ty)
        o.Append(v.x, v.y)
    board.Add(z)


# ---- wiring helpers ---------------------------------------------------------
def wire(net, pts, width=W_SIG, layer=pcbnew.F_Cu):
    """A chain of track segments. pts are VECTOR2I or (ref, pad) tuples or
    (x, y) design-frame waypoints."""
    # GND wires stay in every variant: locked (fix) wiring is an obstacle
    # freerouting must respect. Only GND PADS are stripped in GNDLESS --
    # a pad-less net gives the router nothing to route.
    resolved = []
    for pt in pts:
        if isinstance(pt, tuple) and isinstance(pt[0], str):
            resolved.append(pad_pos(*pt))
        elif isinstance(pt, tuple):
            resolved.append(K(*pt))
        else:
            resolved.append(pt)
    for a, b in zip(resolved, resolved[1:]):
        if a == b:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(a)
        t.SetEnd(b)
        t.SetWidth(mm(width))
        t.SetLayer(layer)
        t.SetNet(nets[net])
        t.SetLocked(True)   # pre-placed = fixed; exported as `fix` in the DSN
        board.Add(t)


def via(net, tx, ty, drill=0.3, size=0.6):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(K(tx, ty))
    v.SetDrill(mm(drill))
    v.SetWidth(mm(size))
    # GND vias keep their net even in the GNDLESS variant: netless vias are
    # dropped from the DSN entirely (measured -- freerouting routed straight
    # through them), while a GND net that is vias-only has nothing to route
    # and still blocks the router.
    v.SetNet(nets[net])
    v.SetLocked(True)
    board.Add(v)


# ---- routes -----------------------------------------------------------------
# ROUTE=manual (default): the hand-scripted routing.py.
# ROUTE=none: bare placement+pours, the input the freerouting flow exports.
ROUTES_FILE = os.path.join(HERE, "routing.py")
if os.environ.get("ROUTE", "manual") != "none" and os.path.exists(ROUTES_FILE):
    exec(compile(open(ROUTES_FILE).read(), ROUTES_FILE, "exec"))

# ---- USB fanout: deterministic, pre-placed in every ROUTE mode --------------
# The rot-270 column interleaves everything at 0.5 mm pitch and freerouting
# cannot escape it cleanly, so the whole quadrant is pre-routed:
#   - DP bridges on the LEFT of the column, DM on the RIGHT (opposite sides
#     = planar, no layer hop); DP descends to D1 right of the part.
#   - CC1/CC2 dive to B.Cu and run UNDER the column -- the pads are F-only,
#     so the bottom layer there is empty by construction.
#   - VBUS pairs are coincident pads; one B.Cu hop carries them to the LDO
#     side of D1.
#   - Every J1 GND pad gets its stub+via; without them the pour cannot reach
#     into the column and freerouting draws garbage GND wires across it.
wire("USB_DP", [("J1", "A6"), (-33.3, 8.25)], 0.2)
wire("USB_DP", [("J1", "B6"), (-33.3, 7.25)], 0.2)
wire("USB_DP", [(-33.3, 7.25), (-33.3, 13.3), (-24.9, 13.3), (-24.9, 8.95),
                ("D1", 6), ("D1", 1)], 0.2)
wire("USB_DM", [("J1", "B7"), (-29.6, 8.75)], 0.2)
wire("USB_DM", [("J1", "A7"), (-29.6, 7.75)], 0.2)
wire("USB_DM", [(-29.6, 8.75), (-29.6, 7.05), ("D1", 3)], 0.2)
wire("USB_DM", [("D1", 3), ("D1", 4)], 0.2)
wire("VBUS", [("J1", "A4"), (-29.4, 10.2)], 0.25)
via("VBUS", -29.4, 10.2)
wire("VBUS", [("J1", "A9"), (-29.8, 5.55), (-29.5, 5.2)], 0.25)
via("VBUS", -29.5, 5.2)
wire("VBUS", [(-29.4, 10.2), (-24.2, 8.3)], 0.25, pcbnew.B_Cu)
wire("VBUS", [(-29.5, 5.2), (-24.2, 8.3)], 0.25, pcbnew.B_Cu)
via("VBUS", -24.2, 8.3)
wire("VBUS", [(-24.2, 8.3), (-24.2, 8), ("D1", 5)], 0.25)
wire("CC1", [("J1", "A5"), (-32.3, 9.25)], 0.2)
via("CC1", -32.3, 9.25)
wire("CC1", [(-32.3, 9.25), (-33.9, 11.5), (-34.6, 15.8)], 0.2, pcbnew.B_Cu)
via("CC1", -34.6, 15.8)
wire("CC1", [(-34.6, 15.8), (-34.6, 17), ("R9", 1)], 0.2)
wire("CC2", [("J1", "B5"), (-29.9, 6.25)], 0.2)
via("CC2", -29.9, 6.25)
wire("CC2", [(-29.9, 6.25), (-30.6, 13.6)], 0.2, pcbnew.B_Cu)
via("CC2", -30.6, 14.0)
wire("CC2", [(-30.6, 13.6), (-30.6, 14.0)], 0.2, pcbnew.B_Cu)
wire("CC2", [(-30.6, 14.0), ("R10", 1)], 0.2)
# DP's last leg to the module, pre-routed through the y=6.9 corridor
wire("USB_DP", [(-24.9, 8.95), (-23.4, 8.95), (-23.4, 2.5), (-10.3, 2.5),
                (-10.3, 5.25), ("U1", 14)], 0.2)
# ---- V3V3: the whole power tree, pre-routed --------------------------------
# North side: LDO -> spine -> module decoupling and the module pin.
wire("V3V3", [("U3", 5), (-18.86, 14.3), (-15.3, 14.3), (-15.3, 21.75),
              (-10.1, 21.75), (-10.1, 20.49), ("U1", 2)], W_PWR)
wire("V3V3", [(-11.55, 21.75), ("C10", 1)], W_PWR)
wire("V3V3", [(-16.48, 14.3), ("C4", 1)], W_PWR)
wire("V3V3", [(-15.3, 17.5), ("C11", 1)], W_SIG)
wire("V3V3", [(-15.3, 15.5), ("R1", 1)], W_SIG)
# South corridor: dives to B.Cu past the DP lane and the module's pad rows,
# then runs along y=1.6 (the clear band above the keys) to the right side.
via("V3V3", -16.48, 11.0)
wire("V3V3", [("C4", 1), (-16.48, 11.0)], W_PWR)
wire("V3V3", [(-16.48, 11.0), (-16.48, 1.6)], W_PWR, pcbnew.B_Cu)
via("V3V3", -16.48, 1.6)
wire("V3V3", [(-16.48, 1.6), (32.7, 1.6)], W_PWR)
wire("V3V3", [("R2", 1), (18.99, 1.6)], W_SIG)
wire("V3V3", [(28, 1.6), (28, -20.86), ("U4", 5)], W_SIG)
wire("V3V3", [(28, -15), ("C9", 1)], W_SIG)
wire("V3V3", [(32.7, 1.6), (32.7, 15), ("TP1", 1)], W_SIG)

# The LDO's VIN (1) and EN (3) are both VBUS, but GND (2) sits BETWEEN them
# on the same pad column -- the recurring 3-pin-side trap. Left to the router,
# it wraps the FAR side of the part in eight segments, threading the gap
# between the GND pad and the output pins at close to minimum clearance and
# running VBUS alongside V3V3 at the regulator's own pins.
#
# Instead: surface VBUS on the input side at pad 3's own height, and the feed
# is one straight run along the bottom with the input cap and VIN teed off it.
# The via is placed HERE rather than left to the router -- anchoring a locked
# trace to a via the router chose would move it on the next re-route.
wire("VBUS", [(-24.2, 8.3), (-24.2, 11.05)], W_PWR, pcbnew.B_Cu)
via("VBUS", -24.2, 11.05)
wire("VBUS", [(-24.2, 11.05), ("U3", 3)], W_PWR)          # the bottom run
wire("VBUS", [(-23.98, 11.05), ("C3", 1)], W_PWR)         # T up to the input cap
wire("VBUS", [("C3", 1), (-23.98, 12.95), ("U3", 1)], W_PWR)

wire("GND", [("J1", "A1"), (-29.5, 11.9)])
via("GND", -29.5, 11.9)
wire("GND", [("J1", "A12"), (-29.9, 3.6)])
via("GND", -29.9, 3.6)
wire("GND", [("D1", 2), (-27.4, 8)])
via("GND", -27.4, 8)

# ---- GND stubs: pads the pour cannot reach, in every ROUTE mode -------------
# (the mic's boxed-in pads and the C10/C11 pocket; freerouting sees GND as a
# plane and will not route these either)
wire("GND", [("C10", 2), (-14.5, 20.5)])
via("GND", -14.5, 20.5)
wire("GND", [("C11", 2), (-10.6, 17.5)])
via("GND", -10.6, 17.5)
wire("GND", [("U4", 2), (32.8, -20.04)])
via("GND", 32.8, -20.04)
wire("GND", [("U4", 3), (29.84, -17.6)])
via("GND", 29.84, -17.6)
# stitching, plus two rescues for pockets the USB-area routing fences off
for _gx, _gy in [(-22, 0.2), (12, -25), (29, 16), (0, -27), (-28, -12), (8, -10),
                 (-12.9, -24.6), (-15.8, -17.5), (-17, -16), (20, -20),
                 (-30, 18), (33, 0), (-18.5, -19.5), (-12.2, -16.9), (-34.5, 8), (-34.5, 13.5), (-15, 9), (17, -2), (-28, 11), (-26.3, 5), (12, 2.9), (0, 0.3), (24, 12), (-20, -20), (5, 12), (34, 12.7), (-28.85, 8)]:
    via("GND", _gx, _gy)

# ---- save (zone fill happens in check.sh: ZONE_FILLER segfaults in headless
# ---- python here, but `kicad-cli pcb drc --refill-zones --save-board` fills)
pcbnew.SaveBoard(OUT, board)
print(f"wrote {OUT}: {len(RAW)} parts, {len(net_names)} nets")
