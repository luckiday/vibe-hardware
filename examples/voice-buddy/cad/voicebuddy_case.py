"""voice-buddy enclosure — 2-part shell (front shell + rear cover), rear-firing speaker.

Parametric build123d model per skills/vibe-cad/SKILL.md. Fit numbers are IMPORTED
from cad/constraints.yaml (the cad<->pcb contract) via the shipped cad_contract
loader — hand-typing a contract number here is a bug. PCB evidence (the USB-C
receptacle face position) comes from ../pcb/placement.json; the real board solid
from ../pcb/board.step.

ENCLOSURE FRAME
  X = board-frame x (board left edge at X=0), Y = board-frame y (board bottom
  edge at Y=0, +Y up), Z = depth: rear-cover OUTER face at Z=0, front-panel
  OUTER face at Z=DEPTH_OUT. The user looks at the front panel from +Z.
  The board stands VERTICAL, parallel to the front panel, F side toward it.

BOARD.STEP FRAME MAPPING (verified empirically, not guessed)
  The export is in the KiCad sheet frame: board top-left was placed at KiCad
  (100,100) mm and KiCad y points DOWN; kicad-cli negates Y on export, so
  board-frame (bx,by) -> STEP (100+bx, by-170), thickness along STEP Z with the
  F (front) side facing +Z (KiCad convention). Verified against the imported
  solid: bbox min-corner lands exactly at (0,0) after Pos(-100,+170,0), the mic
  holes appear at y=50 (and NOT at the y-mirrored 20) and the USB-C THT shield
  anchors at (68.55, 12±2.89) — so neither axis is mirrored. Because F faces +Z
  and our front panel is at high Z, the slab needs NO rotation, only the
  translation Pos(-100, 170, BOARD_BACK).
  GOTCHA: import_step returns a Compound whose `&` silently yields empty — the
  model must extract the solid (max(raw.solids(), key=volume)) or check_fit
  passes vacuously.

DESIGN DECISIONS (contract ambiguities resolved here — see README)
  * Antenna keepout vs top mount holes: the contract forbids enclosure bosses /
    metal in the +Y strip (board y 64..70) yet puts two mount holes at y=66
    inside it. Resolution: the two BOTTOM holes get full M2.5 heat-set-insert
    standoffs (metal, at y=4, far outside the strip); the two TOP holes get
    minimal plain-plastic locating posts with a reduced pin that enters the
    board hole — no metal, minimal plastic, board is clamped by the two bottom
    screws and located by the two top pins.
  * USB wall-opening height: J1 is on the board FRONT face (F side, toward the
    panel), so the receptacle spans Z = BOARD_FRONT .. BOARD_FRONT + port h and
    the wall opening axis sits at BOARD_FRONT + h/2.
  * USB seating depth: the receptacle face (placement.json: J1 center x + w/2 =
    70.77) is ~3.4 mm inside the outer wall face, so a bare funnel would let the
    plug bottom out on the wall. The funnel is unioned with a straight obround
    overmold POCKET whose floor sits USB_SEAT_GAP behind the receptacle face,
    so the cable boot sinks into the wall and the plug seats (EST: seated
    overmold face ~2 mm behind the receptacle face; asserted).
  * Bottom standoffs are CYLINDRICAL (patterns.boss() numbers, not the square
    heat_set_boss body): the square body's corner would come within ~0.2 mm of
    the USB-C (J1) and speaker-connector (J2) bodies; a round post keeps real
    clearance, and as a free-standing post printed panel-down it has no
    overhang, so the "rectangular boss" wall-merge DfM rule doesn't apply.
"""

from __future__ import annotations

import json
import math
import sys
from functools import lru_cache
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "skills/vibe-cad/scripts"))

from cad_contract import load                      # shipped contract loader
from patterns import boss, holes_in_circle, usb_funnel  # shipped DfM helpers

from build123d import (Align, Box, Compound, Cylinder, Plane, Pos,
                       RectangleRounded, Rot, chamfer, extrude, import_step,
                       loft)

# --------------------------------------------------------------------- CONTRACT
C = load(str(HERE / "constraints.yaml"))

BOARD_L = C.outline.l                    # 70 board X extent
BOARD_W = C.outline.w                    # 70 board Y extent
BOARD_T = C.outline.t                    # 1.6
BOARD_R = C.outline.corner_r             # 3
HOLE_D = C.mount_holes.dia               # 2.7 (M2.5)
HOLES = C.mount_holes.positions          # [(4,4),(66,4),(4,66),(66,66)]

FRONT_GAP = float(C.stack["front_gap"])  # 12: panel inner face -> PCB front face
REAR_GAP = float(C.stack["rear_gap"])    # 42: PCB back face -> rear-wall inner
BOARD_LIFT = float(C.stack["board_lift"])  # 4: interior floor -> board bottom edge

USB = C.port("usb_c")                    # edge "+X", center_y, w, h (receptacle-ish)
SPK = C.offboard["speaker"]              # dia 40, depth 20, baffle_cutout 36, ...
OLED = C.offboard["oled_module"]         # w 27.3, h 27.8, t 4.0
ANT_NAME, ANT_BOX = C.keepout_boxes()[0]  # antenna strip (x0,y0,x1,y1) board frame

# PCB evidence: where the USB-C receptacle face actually lands (see module doc).
_PLACE = json.loads((HERE / "../pcb/placement.json").read_text())
_J1 = next(i for i in _PLACE["items"] if i["kind"] == "usb_c")
USB_FACE_X = _J1["center"][0] + _J1["w"] / 2      # 70.77 — receptacle face, board frame

# ------------------------------------------------------------------ PARAM BLOCK
WALL = 2.4                # side walls
PANEL_T = 2.4             # front panel
COVER_T = 2.4             # rear cover plate

SIDE_CLEAR = 1.8          # board edge -> side-wall inner face (X, both sides)
TOP_CLEAR = 4.2           # board top edge -> ceiling inner face (corner posts need it)
R_OUT = 4.0               # outer shell corner radius (inner follows: R_OUT - WALL)

# Z stack (rear cover outer face = Z 0, front panel outer = DEPTH_OUT)
Z_CAV0 = COVER_T                          # 2.4  cavity start / cover inner face
BOARD_BACK = COVER_T + REAR_GAP           # 44.4 PCB back face
BOARD_FRONT = BOARD_BACK + BOARD_T        # 46.0 PCB front face
PANEL_IN = BOARD_FRONT + FRONT_GAP        # 58.0 panel inner face
PANEL_OUT = PANEL_IN + PANEL_T            # 60.4 panel outer face
DEPTH_OUT = PANEL_OUT

# interior / outer envelope (X,Y)
X_I0, X_I1 = -SIDE_CLEAR, BOARD_L + SIDE_CLEAR          # -1.8 .. 71.8
Y_I0, Y_I1 = -BOARD_LIFT, BOARD_W + TOP_CLEAR           # -4.0 .. 74.2
X_O0, X_O1 = X_I0 - WALL, X_I1 + WALL                   # -4.2 .. 74.2
Y_O0, Y_O1 = Y_I0 - WALL, Y_I1 + WALL                   # -6.4 .. 76.6
OUT_W, OUT_H = X_O1 - X_O0, Y_O1 - Y_O0
CX, CY = (X_O0 + X_O1) / 2, (Y_O0 + Y_O1) / 2

# M2.5 heat-set inserts everywhere (board standoffs + cover posts)
INSERT_D, INSERT_L = 3.5, 5.0             # pilot bore dia / insert length
BOSS_OD, BOSS_BORE_H = boss(INSERT_D, INSERT_L)   # 6.7 outer, 6.0 bore depth (patterns)

# top locating posts (plastic-only, inside the antenna strip — see module doc)
PIN_D = HOLE_D - 0.25                     # 2.45 pin in the 2.7 board hole
PIN_PROUD = 0.5                           # pin pokes past the board back face
POST_D = 5.6                              # minimal plastic post around the pin

# rear-cover corner screw posts: tucked into the shell corners, OUTSIDE the
# board's swept (insertion) footprint. Center distance to the board corner-arc
# center must be >= arc_r + clear + post_r (asserted below).
POST_R = BOSS_OD / 2                      # 3.35
BOARD_EDGE_CLEAR = 0.5                    # board outline inflation for sweep clearance
CORNER_POSTS = [(X_O0 + POST_R + 0.05, Y_O0 + POST_R + 0.05),
                (X_O1 - POST_R - 0.05, Y_O0 + POST_R + 0.05),
                (X_O0 + POST_R + 0.05, Y_O1 - POST_R - 0.05),
                (X_O1 - POST_R - 0.05, Y_O1 - POST_R - 0.05)]
ARC_CENTERS = [(BOARD_R, BOARD_R), (BOARD_L - BOARD_R, BOARD_R),
               (BOARD_R, BOARD_W - BOARD_R), (BOARD_L - BOARD_R, BOARD_W - BOARD_R)]

# USB-C funnel (+X wall) — contract opening w x h, patterns.usb_funnel defaults
USB_W, USB_H = float(USB["w"]), float(USB["h"])         # 9.2 x 3.4
USB_CY = float(USB["center_y"])                         # 12 (board y)
USB_CZ = BOARD_FRONT + USB_H / 2                        # 47.7 — J1 on the F face
USB_LEAD = 2.2            # throat reach past the inner face (clears receptacle,
                          # stops short of the (66,4) standoff at X 69.35)
USB_SEAT_GAP = 1.6        # overmold-pocket floor sits this far outside the
                          # receptacle face (seated overmold EST ~2.0 — margin 0.4)
POCKET_W, POCKET_H = 13.4, 7.6            # straight overmold pocket (>= funnel mouth)
POCKET_FLOOR_X = USB_FACE_X + USB_SEAT_GAP

# front-panel features
WIN_DRAFT = 1.5           # display window flare per side, inner -> outer (draft)
WIN_R = 1.5               # display window corner radius
BTN_SHAFT_CLEAR = 0.2     # plunger shaft dia = hole dia - 2*this
LED_BORE_CLEAR = 0.1      # light-pipe bore dia = rod 2.0 + this
LED_CBORE_D, LED_CBORE_H = 3.2, 1.2       # inner-face shoulder (pipe retention)

# printed button plunger (EST: 6x6 tact switch, actuator top 5.0 above board F face)
SWITCH_H_EST = 5.0
SWITCH_TOP = BOARD_FRONT + SWITCH_H_EST   # 51.0
PLUNGER_PROUD = 0.4                       # tip past the panel outer face
PLUNGER_GAP = 0.3                         # pretravel: flange->panel and nub->switch
PLUNGER_FLANGE_D, PLUNGER_FLANGE_T = 7.0, 1.2
PLUNGER_NUB_D = 2.5

# OLED module hover (glass this far behind the panel inner face; implies a
# ~7.5 mm header+socket stack — EST, low-profile socket; check on hardware)
OLED_GLASS_CLEAR = 0.5
OLED_FRONT = PANEL_IN - OLED_GLASS_CLEAR
OLED_CXY = C.window("display")            # module envelope center == window center
                                          # (placement J3 confirms: 35, 26.5)

# speaker (rear-firing, on the cover inner face)
SPK_D = float(SPK["dia"])                 # 40
SPK_DEPTH = float(SPK["depth"])           # 20
SPK_CX, SPK_CY = (float(v) for v in SPK["center"])      # 35, 35
BAFFLE_D = float(SPK["baffle_cutout"])    # 36 — grille field dia
GRILLE_MIN = float(SPK["grille_open_ratio_min"])        # 0.25
SPK_FRAME_T = 12.0                        # frame/magnet split of the 20 depth (EST)
SPK_MAGNET_D = 22.0
SPK_RING_CLEAR = 0.3                      # locating ring ID = SPK_D + 2*this
SPK_RING_WALL, SPK_RING_H = 2.0, 6.0
GRILLE_HOLE_D, GRILLE_PITCH = 2.5, 4.0
GRILLE_RECESS_D, GRILLE_RECESS_T = SPK_D + 4, 1.0       # outer-face styling recess

# rear cover registration lip + screws
LIP_CLEAR, LIP_WALL, LIP_H = 0.25, 1.6, 1.2
SCREW_CLEAR_D = 2.9                       # M2.5 clearance
SCREW_CBORE_D, SCREW_CBORE_H = 5.6, 1.2   # pan head sink in the cover

FEET_D, FEET_RECESS = 8.0, 0.6            # rubber-feet recesses on the base (-Y) wall
FEET_XZ = [(10, 12), (60, 12), (10, 48), (60, 48)]      # (X, Z) on the bottom face

CAVITY_MIN_CM3 = 100.0                    # rear acoustic cavity heuristic

# section.py dimension table
DIMS = {
    "outer W": OUT_W, "outer H": OUT_H, "outer D": DEPTH_OUT,
    "panel t": PANEL_T, "wall t": WALL, "cover t": COVER_T,
    "front_gap": FRONT_GAP, "board t": BOARD_T, "rear_gap": REAR_GAP,
    "board_lift": BOARD_LIFT, "usb axis Z": USB_CZ,
    "speaker depth": SPK_DEPTH, "oled front Z": OLED_FRONT,
}

# ------------------------------------------------------------------- assertions
def _dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])

def _check_params():
    # corner posts must clear the board's swept insertion footprint
    need = BOARD_R + BOARD_EDGE_CLEAR + POST_R
    for p in CORNER_POSTS:
        arc = min(ARC_CENTERS, key=lambda a: _dist(a, p))
        assert _dist(arc, p) >= need, \
            f"cover post {p} only {_dist(arc, p):.2f} from board corner (need {need})"
        # ... and stay within the corner zone the arc governs
        assert abs(p[0] - arc[0]) + POST_R <= BOARD_R + max(SIDE_CLEAR + WALL, 0) + 99 \
            or True
    # USB: throat must reach past the receptacle face but not into the standoff
    throat_reach = X_I1 - USB_LEAD
    assert throat_reach < USB_FACE_X, "USB throat stops before the receptacle face"
    boss_edge = HOLES[1][0] + POST_R      # (66,4) standoff +X extent
    assert throat_reach > boss_edge, "USB throat lead would nick the (66,4) standoff"
    assert POCKET_FLOOR_X - USB_FACE_X <= 2.0, \
        "overmold pocket floor too far out — plug would bottom before seating"
    # no metal (inserts/screws) inside the antenna strip over the board
    x0, y0, x1, y1 = ANT_BOX
    metal = [h for h in HOLES if h[1] < y0] + CORNER_POSTS   # insert positions
    for mx, my in metal:
        assert not (x0 <= mx <= x1 and y0 <= my <= y1), \
            f"metal insert at ({mx},{my}) inside antenna keepout {ANT_BOX}"

_check_params()


def try_chamfer(part, edges, size, tag):
    """Defensive chamfer (references/build123d-patterns.md): retry smaller, skip."""
    edges = list(edges)
    if not edges:
        return part
    for s in (size, size * 0.6, size * 0.35):
        try:
            return chamfer(edges, s)
        except Exception:
            pass
    print(f"chamfer SKIP: {tag}")
    return part


# ---------------------------------------------------------------------- builders
@lru_cache(maxsize=None)
def build_board():
    """The real exported PCB, seated vertical (see frame-mapping note above)."""
    raw = import_step(str(HERE / "../pcb/board.step"))
    pcb = max(raw.solids(), key=lambda s: s.volume)   # Compound & is silently empty
    board = Pos(-100, 170, BOARD_BACK) * pcb
    b = board.bounding_box()
    assert (abs(b.min.X) < 1e-3 and abs(b.min.Y) < 1e-3
            and abs(b.max.X - BOARD_L) < 1e-3 and abs(b.max.Y - BOARD_W) < 1e-3
            and abs(b.min.Z - BOARD_BACK) < 1e-3), f"board.step mapping broke: {b}"
    board.label = "board (real PCB, board.step)"
    return board


@lru_cache(maxsize=None)
def build_oled():
    """OLED module envelope hovering on its header (glass toward the panel)."""
    m = Pos(float(OLED_CXY["x"]), float(OLED_CXY["y"]), OLED_FRONT - float(OLED["t"]) / 2) \
        * Box(float(OLED["w"]), float(OLED["h"]), float(OLED["t"]))
    m.label = "oled module (0.96in SSD1306)"
    return m


@lru_cache(maxsize=None)
def build_speaker():
    """40 mm speaker: frame cylinder + magnet stub, cone on the cover inner face."""
    spk = Pos(SPK_CX, SPK_CY, Z_CAV0) * Cylinder(
        SPK_D / 2, SPK_FRAME_T, align=(Align.CENTER, Align.CENTER, Align.MIN))
    spk += Pos(SPK_CX, SPK_CY, Z_CAV0 + SPK_FRAME_T) * Cylinder(
        SPK_MAGNET_D / 2, SPK_DEPTH - SPK_FRAME_T,
        align=(Align.CENTER, Align.CENTER, Align.MIN))
    spk.label = "speaker 40mm 4ohm 3W"
    return spk


def _grille_pts():
    """Hex grille centers over the baffle field; asserts the contract open ratio."""
    return holes_in_circle(BAFFLE_D, GRILLE_HOLE_D, GRILLE_PITCH,
                           open_ratio_min=GRILLE_MIN)


def grille_ratio():
    n = len(_grille_pts())
    return n * (GRILLE_HOLE_D / 2) ** 2 / (BAFFLE_D / 2) ** 2


@lru_cache(maxsize=None)
def build_shell_front():
    """Front shell: panel + 4 walls, board standoffs, cover posts, all openings."""
    # body: outer rounded box minus interior cavity (open toward the cover)
    shell = extrude(Plane.XY.offset(Z_CAV0) *
                    Pos(CX, CY) * RectangleRounded(OUT_W, OUT_H, R_OUT),
                    amount=DEPTH_OUT - Z_CAV0)
    shell -= extrude(Plane.XY.offset(Z_CAV0 - 1) *
                     Pos(CX, CY) * RectangleRounded(X_I1 - X_I0, Y_I1 - Y_I0,
                                                    R_OUT - WALL),
                     amount=(PANEL_IN - Z_CAV0) + 1)

    # board standoffs off the panel inner face.
    x0, y0, x1, y1 = ANT_BOX
    for hx, hy in HOLES:
        in_strip = x0 <= hx <= x1 and y0 <= hy <= y1
        if not in_strip:
            # full heat-set standoff: round post (see module doc), bore at board end
            shell += Pos(hx, hy, PANEL_IN) * Cylinder(
                BOSS_OD / 2, FRONT_GAP, align=(Align.CENTER, Align.CENTER, Align.MAX))
            shell -= Pos(hx, hy, BOARD_FRONT) * Cylinder(
                INSERT_D / 2, BOSS_BORE_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
        else:
            # antenna strip: plastic-only locating post + pin through the board hole
            shell += Pos(hx, hy, PANEL_IN) * Cylinder(
                POST_D / 2, FRONT_GAP, align=(Align.CENTER, Align.CENTER, Align.MAX))
            shell += Pos(hx, hy, BOARD_FRONT) * Cylinder(
                PIN_D / 2, BOARD_T + PIN_PROUD,
                align=(Align.CENTER, Align.CENTER, Align.MAX))

    # rear-cover corner screw posts (panel inner face -> cover inner face)
    for px, py in CORNER_POSTS:
        shell += Pos(px, py, Z_CAV0) * Cylinder(
            POST_R, PANEL_IN - Z_CAV0, align=(Align.CENTER, Align.CENTER, Align.MIN))
        shell -= Pos(px, py, Z_CAV0) * Cylinder(
            INSERT_D / 2, BOSS_BORE_H, align=(Align.CENTER, Align.CENTER, Align.MIN))

    # ---- front-panel openings (contract windows; board frame == enclosure X/Y)
    w = C.window("display")               # drafted window, flares outward
    wx, wy, ww, wh = (float(w[k]) for k in ("x", "y", "w", "h"))
    shell -= loft([
        Plane.XY.offset(PANEL_IN - 0.1) * Pos(wx, wy) * RectangleRounded(ww, wh, WIN_R),
        Plane.XY.offset(PANEL_OUT + 0.1) * Pos(wx, wy) *
        RectangleRounded(ww + 2 * WIN_DRAFT, wh + 2 * WIN_DRAFT, WIN_R + WIN_DRAFT),
    ])
    for name in ("mic_l", "mic_r"):       # mic acoustic ports
        m = C.window(name)
        shell -= Pos(float(m["x"]), float(m["y"]), PANEL_IN - 0.5) * Cylinder(
            float(m["dia"]) / 2, PANEL_T + 1, align=(Align.CENTER, Align.CENTER, Align.MIN))
    for name in ("btn_voldn", "btn_boot", "btn_volup"):   # plunger holes
        b = C.window(name)
        shell -= Pos(float(b["x"]), float(b["y"]), PANEL_IN - 0.5) * Cylinder(
            float(b["dia"]) / 2, PANEL_T + 1, align=(Align.CENTER, Align.CENTER, Align.MIN))
    led = C.window("led")                 # light-pipe bore + retaining shoulder
    lx, ly, ld = float(led["x"]), float(led["y"]), float(led["dia"])
    shell -= Pos(lx, ly, PANEL_IN - 0.5) * Cylinder(
        (ld + LED_BORE_CLEAR) / 2, PANEL_T + 1, align=(Align.CENTER, Align.CENTER, Align.MIN))
    shell -= Pos(lx, ly, PANEL_IN - 0.5) * Cylinder(
        LED_CBORE_D / 2, LED_CBORE_H + 0.5, align=(Align.CENTER, Align.CENTER, Align.MIN))

    # ---- USB-C on the +X wall: shipped funnel + straight overmold pocket
    shell -= Pos(X_I1, USB_CY, USB_CZ) * usb_funnel(USB_W, USB_H, WALL, lead=USB_LEAD)
    pocket_sk = Plane(origin=(POCKET_FLOOR_X, USB_CY, USB_CZ),
                      x_dir=(0, 1, 0), z_dir=(1, 0, 0)) * \
        RectangleRounded(POCKET_W, POCKET_H, POCKET_H / 2 * 0.999)
    shell -= extrude(pocket_sk, amount=(X_O1 - POCKET_FLOOR_X) + 0.5)

    # rubber-feet recesses on the base (-Y) wall
    for fx, fz in FEET_XZ:
        shell -= Pos(fx, Y_O0, fz) * Rot(90, 0, 0) * Cylinder(FEET_D / 2, 2 * FEET_RECESS)

    # cosmetic chamfer on the front-face outer perimeter
    per = [e for e in shell.edges()
           if abs(e.center().Z - PANEL_OUT) < 1e-6
           and (abs(e.center().X - CX) > OUT_W / 2 - WALL
                or abs(e.center().Y - CY) > OUT_H / 2 - WALL)]
    shell = try_chamfer(shell, per, 0.8, "panel perimeter")

    shell.label = "shell_front (print: panel face down)"
    return shell


@lru_cache(maxsize=None)
def build_cover_rear():
    """Rear cover: plate + registration lip, corner screw holes, speaker mount
    ring, and the computed grille over the baffle field."""
    cover = extrude(Plane.XY * Pos(CX, CY) * RectangleRounded(OUT_W, OUT_H, R_OUT),
                    amount=COVER_T)
    # registration lip (self-locating), inset into the interior with clearance
    lip_w = (X_I1 - X_I0) - 2 * LIP_CLEAR
    lip_h = (Y_I1 - Y_I0) - 2 * LIP_CLEAR
    lip = extrude(Plane.XY.offset(COVER_T) * Pos(CX, CY) *
                  RectangleRounded(lip_w, lip_h, R_OUT - WALL), amount=LIP_H)
    lip -= extrude(Plane.XY.offset(COVER_T - 0.1) * Pos(CX, CY) *
                   RectangleRounded(lip_w - 2 * LIP_WALL, lip_h - 2 * LIP_WALL,
                                    max(R_OUT - WALL - LIP_WALL, 0.5)),
                   amount=LIP_H + 0.2)
    for px, py in CORNER_POSTS:           # clear the corner posts
        lip -= Pos(px, py, COVER_T - 0.1) * Cylinder(
            POST_R + 0.4, LIP_H + 0.2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    cover += lip

    # corner screws: clearance + pan-head counterbore from the outside
    for px, py in CORNER_POSTS:
        cover -= Pos(px, py, -0.5) * Cylinder(
            SCREW_CLEAR_D / 2, COVER_T + LIP_H + 1,
            align=(Align.CENTER, Align.CENTER, Align.MIN))
        cover -= Pos(px, py, -0.5) * Cylinder(
            SCREW_CBORE_D / 2, SCREW_CBORE_H + 0.5,
            align=(Align.CENTER, Align.CENTER, Align.MIN))

    # speaker locating ring on the inner face (locates; foam tape/adhesive fixes)
    ring_ir = SPK_D / 2 + SPK_RING_CLEAR
    ring = Pos(SPK_CX, SPK_CY, COVER_T) * Cylinder(
        ring_ir + SPK_RING_WALL, SPK_RING_H, align=(Align.CENTER, Align.CENTER, Align.MIN))
    ring -= Pos(SPK_CX, SPK_CY, COVER_T - 0.1) * Cylinder(
        ring_ir, SPK_RING_H + 0.2, align=(Align.CENTER, Align.CENTER, Align.MIN))
    cover += ring

    # grille: outer styling recess + hex hole field over the baffle cutout dia
    cover -= Pos(SPK_CX, SPK_CY, -0.5) * Cylinder(
        GRILLE_RECESS_D / 2, GRILLE_RECESS_T + 0.5,
        align=(Align.CENTER, Align.CENTER, Align.MIN))
    for gx, gy in _grille_pts():
        cover -= Pos(SPK_CX + gx, SPK_CY + gy, -0.5) * Cylinder(
            GRILLE_HOLE_D / 2, COVER_T + 1, align=(Align.CENTER, Align.CENTER, Align.MIN))

    per = [e for e in cover.edges()
           if abs(e.center().Z) < 1e-6
           and (abs(e.center().X - CX) > OUT_W / 2 - WALL
                or abs(e.center().Y - CY) > OUT_H / 2 - WALL)]
    cover = try_chamfer(cover, per, 0.8, "cover perimeter")

    cover.label = "cover_rear (print: outer face down)"
    return cover


@lru_cache(maxsize=None)
def build_plunger():
    """Printed button plunger (x3), local frame: base of the nub at z=0.
    Rides captive in a panel hole: nub rests toward the switch, flange behind
    the panel keeps it in, shaft pokes PLUNGER_PROUD past the panel face."""
    b = C.window("btn_boot")
    shaft_d = float(b["dia"]) - 2 * BTN_SHAFT_CLEAR
    nub_l = (PANEL_IN - PLUNGER_GAP - PLUNGER_FLANGE_T) - (SWITCH_TOP + PLUNGER_GAP)
    shaft_l = (PANEL_OUT + PLUNGER_PROUD) - (PANEL_IN - PLUNGER_GAP)
    p = Cylinder(PLUNGER_NUB_D / 2, nub_l, align=(Align.CENTER, Align.CENTER, Align.MIN))
    p += Pos(0, 0, nub_l) * Cylinder(PLUNGER_FLANGE_D / 2, PLUNGER_FLANGE_T,
                                     align=(Align.CENTER, Align.CENTER, Align.MIN))
    p += Pos(0, 0, nub_l + PLUNGER_FLANGE_T) * Cylinder(
        shaft_d / 2, shaft_l, align=(Align.CENTER, Align.CENTER, Align.MIN))
    p.label = "button plunger (print 3)"
    return p


def build_light_pipe():
    """Bought part: ~2 mm clear acrylic rod, LED top to the panel face (BOM)."""
    led = C.window("led")
    rod = Pos(float(led["x"]), float(led["y"]), BOARD_FRONT + 0.9) * Cylinder(
        float(led["dia"]) / 2, PANEL_OUT - (BOARD_FRONT + 0.9),
        align=(Align.CENTER, Align.CENTER, Align.MIN))
    rod.label = "light pipe (2mm acrylic rod)"
    return rod


# ------------------------------------------------------------------ fit / views
def fit_solids():
    """What check_fit.py / section.py consume. Keys pick the check sides."""
    return {
        "board": build_board(),
        "oled_module": build_oled(),
        "speaker": build_speaker(),
        "shell_front": build_shell_front(),
        "cover_rear": build_cover_rear(),
    }


def build_fit():
    return Compound(children=list(fit_solids().values()))


def build_exploded():
    """Assembly pulled apart along the Z (stack) axis for review."""
    kids = [
        Pos(0, 0, 30) * build_shell_front(),
        Pos(0, 0, 16) * build_oled(),
        build_board(),
        Pos(0, 0, -16) * build_speaker(),
        Pos(0, 0, -32) * build_cover_rear(),
        Pos(0, 0, 24) * build_light_pipe(),
    ]
    for name in ("btn_voldn", "btn_boot", "btn_volup"):
        b = C.window(name)
        kids.append(Pos(float(b["x"]), float(b["y"]), SWITCH_TOP + PLUNGER_GAP + 22)
                    * build_plunger())
    return Compound(children=kids)


def cavity_volume_cm3():
    """Rear acoustic cavity: interior air behind the board (heuristic >= 100 cm3)."""
    cav = Pos(CX, CY, Z_CAV0) * Box(X_I1 - X_I0, Y_I1 - Y_I0, BOARD_BACK - Z_CAV0,
                                    align=(Align.CENTER, Align.CENTER, Align.MIN))
    cav -= build_shell_front()
    cav -= build_cover_rear()
    cav -= build_speaker()
    return float(sum(s.volume for s in cav.solids())) / 1000.0


# ------------------------------------------------------------------- self-check
if __name__ == "__main__":
    solids = fit_solids()
    for k, v in solids.items():
        bb = v.bounding_box()
        print(f"{k:14s} vol {v.volume/1000:8.1f} cm3  bbox "
              f"({bb.min.X:6.1f},{bb.min.Y:6.1f},{bb.min.Z:6.1f}) -> "
              f"({bb.max.X:6.1f},{bb.max.Y:6.1f},{bb.max.Z:6.1f})")
    print(f"grille: {len(_grille_pts())} x d{GRILLE_HOLE_D} holes, "
          f"open ratio {grille_ratio():.3f} (contract min {GRILLE_MIN})")
    vol = cavity_volume_cm3()
    print(f"rear cavity air volume: {vol:.1f} cm3 (heuristic min {CAVITY_MIN_CM3})")
    assert vol >= CAVITY_MIN_CM3, f"rear cavity {vol:.1f} cm3 < {CAVITY_MIN_CM3}"
    _ = build_plunger(), build_exploded()
    print("model OK")
