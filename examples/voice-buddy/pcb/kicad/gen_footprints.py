#!/usr/bin/env python3
"""Generate voicebuddy.pretty — the one footprint KiCad's libraries don't ship.

Called by gen_pcb.py before placement (idempotent), so the .pretty regenerates
from source on every build and is never committed. (The v1 ES7210 QFN-32
generator left with the part — the ES8388 uses the stock
Package_DFN_QFN:QFN-28-1EP_4x4mm_P0.45mm_EP2.6x2.6mm, whose EP matches the
datasheet's 2.5-2.7mm range.)

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
    for name, gen in [("MEMS_Analog_BottomPort_3.76x2.95", mems_mic_analog)]:
        path = os.path.join(PRETTY, name + ".kicad_mod")
        with open(path, "w", encoding="utf-8") as f:
            f.write(gen() + "\n")
    return PRETTY


if __name__ == "__main__":
    print("wrote", ensure())
