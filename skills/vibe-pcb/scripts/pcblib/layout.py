"""Relational placement on a pcbnew board — relations in, coordinates out.

The LLM authoring a gen_pcb.py reasons in RELATIONS ("the cap sits against the
codec's supply pads", "USB-C exits the +X wall at the contract's port position").
This module keeps those relations as code, so the geometry recomputes when
anything moves:

  Board       outline / mount holes / keepouts drawn FROM cad/constraints.yaml
  place()     the only footprint-dropping primitive (nets from parts.yaml)
  beside/align_pads/row/at_edge   relations that compute positions from real
              footprint courtyards and pad geometry
  Cluster     a functional group: MACRO origin + members; move the origin and
              the whole group follows; bbox derives from member courtyards

Board frame: origin at the board's BOTTOM-LEFT corner, +x right, +y UP, viewed
from the front — the same frame constraints.yaml and placement.json use. KiCad's
sheet frame is y-DOWN; the flip lives in Board.xy()/Board.from_kicad() and
NOWHERE else.

Needs pcbnew (run under KiCad's python). Layout-only; gates live in gates.py,
copper in route.py.
"""

from __future__ import annotations

import os

import pcbnew
from pcbnew import VECTOR2I, FromMM as MM, ToMM

__all__ = [
    "Board", "Part", "Cluster", "place", "beside", "align_pads", "row",
    "at_edge", "apply_move_env", "footprint_dirs",
]


# ------------------------------------------------------------------ lib resolution

def footprint_dirs() -> list:
    """Where to look for <Lib>.pretty. Env KICAD_FOOTPRINT_DIRS (colon-separated)
    is prepended; the project dir (cwd) is always searched for local .pretty."""
    dirs = []
    env = os.environ.get("KICAD_FOOTPRINT_DIRS", "")
    dirs += [d for d in env.split(":") if d]
    dirs.append(os.getcwd())
    dirs += [
        "/usr/share/kicad/footprints",                                    # linux
        "/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints",  # mac
    ]
    return [d for d in dirs if os.path.isdir(d)]


def _find_pretty(lib: str) -> str:
    if lib.endswith(".pretty"):                       # explicit path form
        if os.path.isdir(lib):
            return lib
    for d in footprint_dirs():
        p = os.path.join(d, lib + ".pretty")
        if os.path.isdir(p):
            return p
        p = os.path.join(d, lib)                      # already-suffixed dir name
        if lib.endswith(".pretty") and os.path.isdir(p):
            return p
    raise FileNotFoundError(
        f"footprint lib {lib!r} not found (searched {footprint_dirs()}; "
        "set KICAD_FOOTPRINT_DIRS or add a local .pretty)")


# --------------------------------------------------------------------------- board

class Board:
    """The board frame + everything drawn from the cad<->pcb contract."""

    def __init__(self, pcb: "pcbnew.BOARD", constraints, origin=(100.0, 100.0),
                 copper_layers: int = 2, min_track: float = 0.2,
                 min_clearance: float = 0.2, min_hole: float = 0.3):
        self.pcb = pcb
        self.c = constraints
        self.ox, self.oy = origin           # KiCad-sheet mm of the board's TOP-left
        self.L = constraints.outline_l      # x extent, mm
        self.W = constraints.outline_w      # y extent, mm
        self.parts: dict = {}
        self._nets: dict = {}
        self.copper_layers = copper_layers
        self._set_stackup(copper_layers)
        self._set_design_rules(min_track, min_clearance, min_hole)
        self._draw_outline()
        self._draw_mount_holes()
        self._draw_keepouts()

    def _set_design_rules(self, min_track: float, min_clearance: float,
                          min_hole: float = 0.3):
        """Board-wide min track width + clearance + through-hole drill (mm).
        Fine-pitch parts (0.4mm QFN) need ~0.15mm track/clearance to fan out their
        pads; modules with a stitched thermal pad (ESP32-S3-WROOM-1) ship 0.2mm
        belly vias, so min_hole must reach 0.2mm or DRC flags the stock footprint.
        Kept within JLCPCB standard capability."""
        ds = self.pcb.GetDesignSettings()
        ds.m_TrackMinWidth = MM(min_track)
        ds.m_MinClearance = MM(min_clearance)
        ds.m_MinThroughDrill = MM(min_hole)
        # DRC enforces the (default) netclass clearance/width, not just m_MinClearance
        # — set it too, or narrow routes flag against the stock 0.2mm netclass.
        nc = ds.m_NetSettings.GetDefaultNetclass()
        nc.SetClearance(MM(min_clearance))
        nc.SetTrackWidth(MM(min_track))

    def _set_stackup(self, n: int):
        """Enable an n-layer copper stack (2 or 4). For 4-layer boards the two
        inner layers (In1.Cu / In2.Cu) become power/GND planes — pour them with
        route.plane_pours(). Antenna/belly keepouts (see _draw_keepouts) then
        pull every copper layer back, inner planes included."""
        if n <= 2:
            return
        if n not in (4,):
            raise ValueError(f"copper_layers={n}: only 2 or 4 supported")
        self.pcb.SetCopperLayerCount(n)
        enabled = self.pcb.GetEnabledLayers()
        for lyr in self._inner_copper():
            enabled.AddLayer(lyr)
        self.pcb.SetEnabledLayers(enabled)

    def _inner_copper(self) -> list:
        """The inner copper layer ids for the current stack (empty on 2-layer)."""
        return [pcbnew.In1_Cu, pcbnew.In2_Cu][: max(0, self.copper_layers - 2)]

    def _copper_layers(self) -> list:
        """Every enabled copper layer id (F, inner…, B)."""
        return [pcbnew.F_Cu, *self._inner_copper(), pcbnew.B_Cu]

    # --- frame mapping: the ONE place the y-flip lives ---
    def xy(self, x: float, y: float) -> VECTOR2I:
        """Board frame (mm, +y up, origin bottom-left) -> KiCad sheet point."""
        return VECTOR2I(MM(self.ox + x), MM(self.oy + (self.W - y)))

    def from_kicad(self, p: VECTOR2I):
        """KiCad sheet point -> board frame (mm)."""
        return (ToMM(p.x) - self.ox, self.W - (ToMM(p.y) - self.oy))

    def edge(self, name: str) -> float:
        """Coordinate of a board edge in board frame: '-X'->0, '+X'->L, etc."""
        return {"-X": 0.0, "+X": self.L, "-Y": 0.0, "+Y": self.W}[name]

    def port(self, name: str) -> dict:
        """The contract's ports.<name> spec (edge, center_y/center_x, w, h)."""
        return self.c.port(name)

    # --- nets ---
    def net(self, name: str) -> int:
        """Net code for name, creating the net on first use."""
        if name not in self._nets:
            item = pcbnew.NETINFO_ITEM(self.pcb, name)
            self.pcb.Add(item)
            self._nets[name] = item.GetNetCode()
        return self._nets[name]

    # --- contract-driven geometry ---
    def _seg(self, a, b, layer=pcbnew.Edge_Cuts, w=0.12):
        s = pcbnew.PCB_SHAPE(self.pcb)
        s.SetShape(pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(a); s.SetEnd(b)
        s.SetLayer(layer); s.SetWidth(MM(w))
        self.pcb.Add(s)

    def _arc(self, start, mid, end, layer=pcbnew.Edge_Cuts, w=0.12):
        s = pcbnew.PCB_SHAPE(self.pcb)
        s.SetShape(pcbnew.SHAPE_T_ARC)
        s.SetArcGeometry(start, mid, end)
        s.SetLayer(layer); s.SetWidth(MM(w))
        self.pcb.Add(s)

    def _draw_outline(self):
        """Rounded rect on Edge.Cuts from the contract's outline numbers."""
        L, W, r = self.L, self.W, self.c.corner_r
        xy = self.xy
        if r <= 0:
            for a, b in [((0, 0), (L, 0)), ((L, 0), (L, W)),
                         ((L, W), (0, W)), ((0, W), (0, 0))]:
                self._seg(xy(*a), xy(*b))
            return
        k = r * (1 - 0.7071067811865476)  # r - r/sqrt(2): 45-degree arc midpoint inset
        self._seg(xy(r, 0), xy(L - r, 0))          # bottom
        self._seg(xy(L, r), xy(L, W - r))          # right
        self._seg(xy(L - r, W), xy(r, W))          # top
        self._seg(xy(0, W - r), xy(0, r))          # left
        self._arc(xy(L - r, 0), xy(L - k, k), xy(L, r))          # bottom-right
        self._arc(xy(L, W - r), xy(L - k, W - k), xy(L - r, W))  # top-right
        self._arc(xy(r, W), xy(k, W - k), xy(0, W - r))          # top-left
        self._arc(xy(0, r), xy(k, k), xy(r, 0))                  # bottom-left

    def _draw_mount_holes(self):
        """NPTH mount holes at the contract's positions (standard MountingHole lib)."""
        if not self.c.hole_positions:
            return
        dia = self.c.hole_dia
        name = _mount_hole_name(dia)
        for i, (x, y) in enumerate(self.c.hole_positions, 1):
            p = place(self, "MountingHole", name, f"H{i}", value="", nets={},
                      at=(x, y))
            p.fp.SetAttributes(pcbnew.FP_EXCLUDE_FROM_BOM
                               | pcbnew.FP_EXCLUDE_FROM_POS_FILES)

    def _draw_keepouts(self):
        """Structured contract keepouts -> copper rule areas on EVERY copper layer
        (no tracks, vias, or fills). On a 4-layer board this is what pulls the
        inner GND/power planes back under the antenna. DRC enforces them;
        gates.keepout_violations re-checks."""
        from .route import _kicad_rule_area
        layers = tuple(self._copper_layers())
        for name, (x0, y0, x1, y1) in self.c.keepout_boxes():
            a, b = self.xy(x0, y0), self.xy(x1, y1)
            box = (min(ToMM(a.x), ToMM(b.x)), min(ToMM(a.y), ToMM(b.y)),
                   max(ToMM(a.x), ToMM(b.x)), max(ToMM(a.y), ToMM(b.y)))
            _kicad_rule_area(self.pcb, box, layers=layers, name=name)

    def save(self, path: str):
        self.pcb.BuildConnectivity()
        pcbnew.SaveBoard(path, self.pcb)


def _mount_hole_name(dia: float) -> str:
    """Map a hole dia to a stock MountingHole footprint name."""
    table = {2.2: "MountingHole_2.2mm_M2", 2.7: "MountingHole_2.7mm_M2.5",
             3.2: "MountingHole_3.2mm_M3", 2.5: "MountingHole_2.5mm_M2.2",
             4.3: "MountingHole_4.3mm_M4"}
    if dia in table:
        return table[dia]
    return f"MountingHole_{dia}mm"


def _merged(a, b):
    m = pcbnew.BOX2I(a.GetPosition(), a.GetSize())
    m.Merge(b)
    return m


# ---------------------------------------------------------------------------- part

class Part:
    """A placed footprint. All coordinates in board frame (mm, +y up)."""

    def __init__(self, board: Board, fp: "pcbnew.FOOTPRINT"):
        self.board = board
        self.fp = fp

    @property
    def ref(self) -> str:
        return self.fp.GetReference()

    @property
    def pos(self):
        return self.board.from_kicad(self.fp.GetPosition())

    def set(self, x: float, y: float, rot=None):
        self.fp.SetPosition(self.board.xy(x, y))
        if rot is not None:
            self.fp.SetOrientationDegrees(rot)
        return self

    def move(self, dx: float, dy: float):
        x, y = self.pos
        return self.set(x + dx, y + dy)

    def pad(self, name) -> tuple:
        """Center of pad <name> in board frame. First match if several."""
        name = str(name)
        for p in self.fp.Pads():
            if p.GetPadName() == name:
                return self.board.from_kicad(p.GetPosition())
        raise KeyError(f"{self.ref}: no pad {name!r}")

    def pads(self, name) -> list:
        name = str(name)
        return [self.board.from_kicad(p.GetPosition())
                for p in self.fp.Pads() if p.GetPadName() == name]

    def courtyard(self, side=None) -> tuple:
        """(x0, y0, x1, y1) BODY box (pads ∪ Fab shapes + 0.25 mm) in board
        frame — the box the overlap/keepout gates use.

        Deliberately NOT the F.CrtYd polygon: antenna modules draw their
        recommended far-field clear zone on the courtyard layer (the WROOM's
        spans ±24 mm), which would make any compact board "overlap"
        everything; the antenna rule is the contract keepout instead. Real
        courtyard-vs-courtyard checking still happens in DRC. (KiCad 7 note:
        GetCourtyard() is empty off-board and BuildCourtyardCaches() segfaults
        on an unattached footprint — another reason to derive from geometry.)"""
        bb = None
        for p in self.fp.Pads():
            b = p.GetBoundingBox()
            bb = b if bb is None else _merged(bb, b)
        fab = pcbnew.B_Fab if (side or self.side()) == "B" else pcbnew.F_Fab
        for g in self.fp.GraphicalItems():
            if g.GetClass() in ("MGRAPHIC", "FP_SHAPE", "PCB_SHAPE") \
                    and g.GetLayer() in (fab, pcbnew.F_Fab, pcbnew.B_Fab):
                b = g.GetBoundingBox()
                bb = b if bb is None else _merged(bb, b)
        if bb is None:
            bb = self.fp.GetBoundingBox(False, False)
        pad = 0.25
        x0, y0 = self.board.from_kicad(VECTOR2I(bb.GetLeft(), bb.GetBottom()))
        x1, y1 = self.board.from_kicad(VECTOR2I(bb.GetRight(), bb.GetTop()))
        return (min(x0, x1) - pad, min(y0, y1) - pad,
                max(x0, x1) + pad, max(y0, y1) + pad)

    def side(self) -> str:
        return "B" if self.fp.IsFlipped() else "F"

    @property
    def width(self) -> float:
        c = self.courtyard()
        return c[2] - c[0]

    @property
    def height(self) -> float:
        c = self.courtyard()
        return c[3] - c[1]


def place(board: Board, lib: str, name: str, ref: str, value: str = "",
          nets: dict = None, at=(0.0, 0.0), rot: float = 0, flip: bool = False,
          cluster: "Cluster" = None) -> Part:
    """THE footprint primitive. `nets` is {pad_name: net_name} — normally
    parts.netmap(ref), never hand-typed. `at` is board frame mm."""
    fp = pcbnew.FootprintLoad(_find_pretty(lib), name)
    if fp is None:
        raise FileNotFoundError(f"footprint {name!r} not in {lib!r}")
    fp.SetReference(ref)
    fp.SetValue(value)
    board.pcb.Add(fp)
    fp.SetPosition(board.xy(*at))
    if flip:
        fp.Flip(fp.GetPosition(), True)
    fp.SetOrientationDegrees(rot)
    unmatched = dict(nets or {})
    for p in fp.Pads():
        n = unmatched.get(p.GetPadName())
        if n is not None:
            p.SetNetCode(board.net(n))
    matched = {p.GetPadName() for p in fp.Pads()}
    missing = [k for k in unmatched if k not in matched]
    if missing:
        raise KeyError(f"{ref}: parts.yaml names pads {missing} that footprint "
                       f"{lib}:{name} does not have")
    part = Part(board, fp)
    board.parts[ref] = part
    if cluster is not None:
        cluster.add(part)
    return part


# ------------------------------------------------------------------------ relations

def beside(a: Part, b: Part, side: str = "right", gap: float = 0.5,
           align: str = "center") -> Part:
    """Abut b's courtyard against a's with `gap` mm between them.
    side: right|left|above|below (in board frame). align: center|top|bottom
    (for horizontal sides) or center|left|right (for vertical sides)."""
    ca, cb = a.courtyard(), b.courtyard()
    bx, by = b.pos
    if side in ("right", "left"):
        dx = (ca[2] + gap - cb[0]) if side == "right" else (ca[0] - gap - cb[2])
        dy = {"center": ((ca[1] + ca[3]) - (cb[1] + cb[3])) / 2,
              "top": ca[3] - cb[3], "bottom": ca[1] - cb[1]}[align]
    elif side in ("above", "below"):
        dy = (ca[3] + gap - cb[1]) if side == "above" else (ca[1] - gap - cb[3])
        dx = {"center": ((ca[0] + ca[2]) - (cb[0] + cb[2])) / 2,
              "left": ca[0] - cb[0], "right": ca[2] - cb[2]}[align]
    else:
        raise ValueError(f"side={side!r}")
    return b.set(bx + dx, by + dy)


def align_pads(a: Part, pa, b: Part, pb, axis: str = "both",
               offset=(0.0, 0.0)) -> Part:
    """Move b so its pad pb lands on a's pad pa (plus offset), on the given
    axis — the decoupling-cap relation: the cap's pad sits ON the IC's supply
    pad column, the trace becomes a stub."""
    ax, ay = a.pad(pa)
    bx, by = b.pad(pb)
    px, py = b.pos
    dx = (ax + offset[0]) - bx if axis in ("x", "both") else 0.0
    dy = (ay + offset[1]) - by if axis in ("y", "both") else 0.0
    return b.set(px + dx, py + dy)


def row(parts: list, axis: str = "x", gap: float = 0.4,
        align: str = "center") -> list:
    """Chain parts[1:] beside parts[0] into a row/column (banks of caps, buttons)."""
    side = "right" if axis == "x" else "above"
    for prev, nxt in zip(parts, parts[1:]):
        beside(prev, nxt, side=side, gap=gap, align=align)
    return parts


def at_edge(board: Board, part: Part, port: str, overhang: float = 0.0) -> Part:
    """Put a connector at a contract port: cross-axis center from the contract,
    courtyard flush with the wall edge (+overhang mm past it). The port's x/y
    NEVER appears in gen_pcb.py — it lives in constraints.yaml only."""
    spec = board.port(port)
    edge = spec["edge"]
    x, y = part.pos
    c = part.courtyard()
    if edge in ("+X", "-X"):
        ty = float(spec["center_y"])
        part.set(x, y + (ty - (c[1] + c[3]) / 2))
        c = part.courtyard()
        dx = (board.edge(edge) + overhang - c[2]) if edge == "+X" \
            else (board.edge(edge) - overhang - c[0])
        part.move(dx, 0)
    else:
        tx = float(spec["center_x"])
        part.set(x + (tx - (c[0] + c[2]) / 2), y)
        c = part.courtyard()
        dy = (board.edge(edge) + overhang - c[3]) if edge == "+Y" \
            else (board.edge(edge) - overhang - c[1])
        part.move(0, dy)
    return part


# ------------------------------------------------------------------------- clusters

class Cluster:
    """A functional group with a movable MACRO origin. Slots are relative;
    move the origin (code or MOVE env) and every member follows.

    pinned=True marks a group whose members sit at CONTRACT positions
    (buttons on their panel windows, connectors on ports). Pinned groups are
    excluded from the cluster-overlap gate — they are not free-floating
    floorplan blocks, and their real collisions are still caught by the
    courtyard gate."""

    all: dict = {}

    def __init__(self, board: Board, name: str, origin, pinned: bool = False):
        self.board = board
        self.name = name
        self.ox, self.oy = float(origin[0]), float(origin[1])
        self.pinned = pinned
        self.members: list = []
        Cluster.all[name] = self

    def at(self, dx: float, dy: float):
        return (self.ox + dx, self.oy + dy)

    def add(self, part: Part) -> Part:
        if part not in self.members:
            self.members.append(part)
        return part

    def place(self, lib, name, ref, value="", nets=None, at=(0, 0), rot=0,
              flip=False) -> Part:
        return place(self.board, lib, name, ref, value=value, nets=nets,
                     at=self.at(*at), rot=rot, flip=flip, cluster=self)

    def move(self, dx: float, dy: float):
        self.ox += dx; self.oy += dy
        for m in self.members:
            m.move(dx, dy)
        return self

    def bbox(self, pad: float = 0.3) -> tuple:
        """Union of member courtyards + pad — the REAL group extent."""
        if not self.members:
            return (self.ox, self.oy, self.ox, self.oy)
        cs = [m.courtyard() for m in self.members]
        return (min(c[0] for c in cs) - pad, min(c[1] for c in cs) - pad,
                max(c[2] for c in cs) + pad, max(c[3] for c in cs) + pad)


def apply_move_env():
    """A/B floorplan knob without editing code:
    MOVE="AUDIO:-3,2;UI:0,4" gen_pcb.py ...  nudges cluster origins."""
    spec = os.environ.get("MOVE", "")
    for item in spec.split(";"):
        if ":" not in item:
            continue
        name, _, d = item.partition(":")
        dx, dy = (float(v) for v in d.split(","))
        Cluster.all[name.strip()].move(dx, dy)
        print(f"MOVE {name.strip()}: ({dx:+g},{dy:+g})")
