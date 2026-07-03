#!/usr/bin/env python3
"""Generate voicebuddy.pretty — the two footprints KiCad's libraries don't ship.

Called by gen_pcb.py before placement (idempotent), so the .pretty regenerates
from source on every build and is never committed.

  ES7210 QFN-32 4x4mm P0.4  KiCad stock QFN-32 is 5x5/P0.5 — wrong part. Body
                            and pitch verified against LCSC C365743; EP size
                            2.6 mm is the family-typical value (EST: confirm
                            against the datasheet mechanical drawing pre-fab).
  MEMS mic OCLGA 3.76x2.95  generic analog bottom-port land (MSM381A3729-class):
                            4 terminals + a THROUGH-PCB acoustic port (0.8 mm
                            NPTH). Land + port dia are EST items — verify the
                            exact mic variant's drawing (top-port variants of
                            the same body exist and will NOT work here).
"""

import os

PRETTY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voicebuddy.pretty")


def _pad(num, x, y, w, h, shape="roundrect", extra=""):
    rr = ' (roundrect_rratio 0.25)' if shape == "roundrect" else ''
    return (f'  (pad "{num}" smd {shape} (at {x:.3f} {y:.3f}) '
            f'(size {w:.3f} {h:.3f}) (layers "F.Cu" "F.Paste" "F.Mask"){rr}{extra})')


def _npth(x, y, dia):
    return (f'  (pad "" np_thru_hole circle (at {x:.3f} {y:.3f}) '
            f'(size {dia:.3f} {dia:.3f}) (drill {dia:.3f}) (layers "*.Cu" "*.Mask"))')


def _outline(w, h, layer, width=0.1):
    x, y = w / 2, h / 2
    return (f'  (fp_rect (start {-x:.3f} {-y:.3f}) (end {x:.3f} {y:.3f}) '
            f'(stroke (width {width}) (type default)) (fill none) (layer "{layer}"))')


def qfn32_4x4_p04() -> str:
    """QFN-32-1EP 4x4mm P0.4mm EP2.6x2.6 — pads 1-32 CCW from top-left, EP=33."""
    lines = ['(footprint "QFN-32-1EP_4x4mm_P0.4mm_EP2.6x2.6mm"',
             '  (version 20221018) (generator gen_footprints)',
             '  (layer "F.Cu")',
             '  (attr smd)',
             '  (fp_text reference "REF**" (at 0 -3.1) (layer "F.SilkS")'
             ' (effects (font (size 1 1) (thickness 0.15))))',
             '  (fp_text value "QFN-32" (at 0 3.1) (layer "F.Fab")'
             ' (effects (font (size 1 1) (thickness 0.15))))']
    lines.append(_outline(4.0, 4.0, "F.Fab"))
    lines.append(_outline(4.7, 4.7, "F.CrtYd", 0.05))
    # pin-1 marks: silk dot + fab chamfer corner (top-left)
    lines.append('  (fp_circle (center -2.5 -2.1) (end -2.4 -2.1)'
                 ' (stroke (width 0.2) (type default)) (fill solid) (layer "F.SilkS"))')
    ys = [round(-1.4 + 0.4 * i, 3) for i in range(8)]
    for i, y in enumerate(ys):                       # 1-8 left, top->bottom
        lines.append(_pad(i + 1, -1.85, y, 0.8, 0.2))
    for i, x in enumerate(ys):                       # 9-16 bottom, left->right
        lines.append(_pad(i + 9, x, 1.85, 0.2, 0.8))
    for i, y in enumerate(reversed(ys)):             # 17-24 right, bottom->top
        lines.append(_pad(i + 17, 1.85, y, 0.8, 0.2))
    for i, x in enumerate(reversed(ys)):             # 25-32 top, right->left
        lines.append(_pad(i + 25, x, -1.85, 0.2, 0.8))
    lines.append(_pad(33, 0, 0, 2.6, 2.6, shape="rect"))   # EP -> GND
    lines.append(')')
    return "\n".join(lines)


def mems_mic_analog() -> str:
    """Analog bottom-port MEMS mic, OCLGA 3.76x2.95. Pads: 1 OUT, 2 GND, 3 VDD,
    4 GND. Acoustic port = 0.8 mm NPTH through the PCB (sound reaches the mic
    from the FRONT of the board; mic body sits on the BACK)."""
    lines = ['(footprint "MEMS_Analog_BottomPort_3.76x2.95"',
             '  (version 20221018) (generator gen_footprints)',
             '  (layer "F.Cu")',
             '  (attr smd)',
             '  (fp_text reference "REF**" (at 0 -2.6) (layer "F.SilkS")'
             ' (effects (font (size 1 1) (thickness 0.15))))',
             '  (fp_text value "MEMS-MIC" (at 0 2.6) (layer "F.Fab")'
             ' (effects (font (size 1 1) (thickness 0.15))))']
    lines.append(_outline(3.76, 2.95, "F.Fab"))
    lines.append(_outline(4.6, 3.8, "F.CrtYd", 0.05))
    # port offset toward pad-1 end (typical of the family; EST: verify drawing)
    port_x = -0.85
    lines.append(_npth(port_x, 0, 0.8))
    # keep silk clear of the port; mark pin 1
    lines.append('  (fp_circle (center -2.3 -1.6) (end -2.2 -1.6)'
                 ' (stroke (width 0.2) (type default)) (fill solid) (layer "F.SilkS"))')
    pads = [(1, -1.48, -0.95), (2, -1.48, 0.95), (3, 1.48, 0.95), (4, 1.48, -0.95)]
    for n, x, y in pads:
        lines.append(_pad(n, x, y, 0.65, 0.85))
    lines.append(')')
    return "\n".join(lines)


def ensure():
    os.makedirs(PRETTY, exist_ok=True)
    for name, gen in [("QFN-32-1EP_4x4mm_P0.4mm_EP2.6x2.6mm", qfn32_4x4_p04),
                      ("MEMS_Analog_BottomPort_3.76x2.95", mems_mic_analog)]:
        path = os.path.join(PRETTY, name + ".kicad_mod")
        with open(path, "w", encoding="utf-8") as f:
            f.write(gen() + "\n")
    return PRETTY


if __name__ == "__main__":
    print("wrote", ensure())
