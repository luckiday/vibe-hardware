"""patterns — computed-geometry helpers for enclosure models (import, don't retype).

Pure math where possible (hex grille packing, boss sizing) so a model can plan a
feature without a CAD kernel; build123d only where a solid is actually needed
(imported lazily). Each helper encodes a DfM rule from this skill's references —
change the rule there and here together.

    from patterns import holes_in_circle, boss, heat_set_boss, usb_funnel
"""

from __future__ import annotations

import math


# ------------------------------------------------------------------ grille packing

def holes_in_circle(area_dia: float, hole_d: float, pitch: float,
                    open_ratio_min: float = 0.0) -> list:
    """Hex-packed grille hole centers filling a circle -> [(x, y), ...].

    Rows at pitch*sqrt(3)/2, alternate rows offset pitch/2; a center is kept only
    if its hole lies FULLY inside area_dia (no clipped holes at the rim). Checks
    the achieved open-area ratio (sum of hole area / circle area) against
    open_ratio_min and raises AssertionError with the achieved number if short —
    so an acoustic/vent requirement fails loudly instead of shipping a quiet speaker.
    """
    if pitch < hole_d:
        raise ValueError(f"pitch {pitch} < hole_d {hole_d}: holes would merge")
    r_max = area_dia / 2 - hole_d / 2          # center must keep the hole inside
    dy = pitch * math.sqrt(3) / 2
    pts = []
    j = 0
    while j * dy <= r_max + 1e-9:
        for y in {j * dy, -j * dy}:            # set{} deduplicates the j=0 row
            x0 = (pitch / 2) if (j % 2) else 0.0
            i = 0
            while True:
                for x in {x0 + i * pitch, -(x0 + i * pitch)}:
                    if math.hypot(x, y) <= r_max + 1e-9:
                        pts.append((x, y))
                if x0 + i * pitch > r_max:
                    break
                i += 1
        j += 1
    pts = sorted(set(pts))
    achieved = len(pts) * math.pi * (hole_d / 2) ** 2 / (math.pi * (area_dia / 2) ** 2)
    assert achieved >= open_ratio_min, (
        f"grille open ratio {achieved:.3f} < required {open_ratio_min:.3f} "
        f"({len(pts)} x d{hole_d} in d{area_dia}; shrink pitch or grow the area)")
    return pts


# ------------------------------------------------------------- heat-set insert boss

BOSS_RELIEF = 1.0    # mm of bore past the seated insert: melt relief + screw-tip room


def boss(insert_d: float, insert_l: float, wall: float = 1.6):
    """Heat-set insert boss envelope -> (outer_d, height), mm.

    insert_d = the manufacturer's PILOT BORE for the insert (typically nominal
    insert OD - 0.3..0.5), NOT the thread size. wall >= 1.6 around the bore or
    the insert splits the boss when it melts in; height = insert length + melt
    relief so displaced plastic and the screw tip have somewhere to go.
    """
    return insert_d + 2 * wall, insert_l + BOSS_RELIEF


def heat_set_boss(insert_d: float, insert_l: float, wall: float = 1.6):
    """build123d solid for a heat-set insert boss: RECTANGULAR body, round bore.

    Per the DfM rule (references/build123d-patterns.md): a free-standing round
    boss prints a curved overhang and sinks in tooling — the backing solid is a
    cuboid to merge into a wall/floor; only the bore is round. The bore is cut
    through the boss (the host wall it sits on closes the bottom).

    Orientation: base face at z=0 (union it onto the wall/floor), bore opening
    +Z where the insert is pressed in. `part += Pos(x, y, floor_z) * heat_set_boss(...)`.
    """
    from build123d import Align, Box, Cylinder, Pos
    outer_d, height = boss(insert_d, insert_l, wall)
    body = Box(outer_d, outer_d, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    bore = Pos(0, 0, height) * Cylinder(insert_d / 2, height,
                                        align=(Align.CENTER, Align.CENTER, Align.MAX))
    return body - bore


# ---------------------------------------------------------------- USB port funnel

def usb_funnel(port_w: float, port_h: float, wall_t: float,
               throat_clear: float = 0.3, mouth_grow: float = 1.6,
               lead: float = 1.6):
    """Conforming USB funnel cutter: snug obround throat -> flared mouth.

    Implements references/usb-connector-cutouts.md: size the throat to clear the
    RECEPTACLE on the board (port_w x port_h, e.g. USB-C 8.94 x 3.26) by
    throat_clear per side — never the bare plug — then flare through the wall by
    mouth_grow per side so the cable overmold clears. The validated XIAO USB-C
    cut (throat 9.8 x 4.2, mouth 13 x 7) is throat_clear~0.45, mouth_grow~1.5.
    Sections are true obrounds (full-radius ends), and the throat runs `lead` mm
    past the inner face to guarantee a clean cut through ribs/bosses.

    Orientation convention: funnel axis = +X (out of the box), centered on
    (0, 0, 0) = the receptacle axis at the INNER wall face; throat at x<=0,
    mouth at x = wall_t + 0.3 (past the outer face for a clean boolean). Place
    it yourself: `shell -= Pos(x_inner_wall, cy, cz) * usb_funnel(...)`, with a
    `Rot(0, 0, ..)` first for a non-+X wall. Subtract it; don't union it.
    """
    from build123d import Plane, RectangleRounded, extrude, loft
    tw, th = port_w + 2 * throat_clear, port_h + 2 * throat_clear
    mw, mh = tw + 2 * mouth_grow, th + 2 * mouth_grow

    def _sk(x, w, h):   # obround cross-section in the wall plane at X = x
        return Plane(origin=(x, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0)) \
            * RectangleRounded(w, h, h / 2 * 0.999)   # *0.999: full-radius edge case

    funnel = loft([_sk(0, tw, th), _sk(wall_t + 0.3, mw, mh)])   # flared mouth
    funnel += extrude(_sk(0, tw, th), amount=-lead)              # snug throat, inward
    return funnel
