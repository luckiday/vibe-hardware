#!/usr/bin/env python3
"""Export a route-ready Specctra .dsn from a placed (un-routed) .kicad_pcb.

Part of the vibe-pcb autoroute flow (see references/autorouting.md). Adds the belly
keep-out as a REAL track/via keepout (not just a no-fill rule area) so the autorouter
keeps front copper + vias off a flush module's belly, then rewrites the single exported
net class into power/signal classes so freerouting honours per-net widths.

Why this script exists: kicad-cli has NO Specctra export. The bundled pcbnew Python is the
only headless way out -> pcbnew.ExportSpecctraDSN(board, file) (KiCad 10).

Run with KiCad's BUNDLED python (the one with pcbnew):
  export_dsn.py <place.kicad_pcb> <out.dsn>

Env (all optional; defaults shown):
  BELLY_BOX="x0,y0,x1,y1"   front-copper/via keepout box in board mm (default: none)
  POWER_NETS="+3V3,GND,VIN" nets routed at the wider width
  SIGNAL_NETS="SDA,SCL"     nets routed at the signal width
  W_POWER=400  W_SIGNAL=300  CLEARANCE=200   (microns)

When the project has a parts.yaml next to the board (the pcblib net source),
POWER_NETS/SIGNAL_NETS default from it (power_nets: + everything else) so the
class split needs no hand-typed net list.
"""
import os, re, sys, pcbnew
from pcbnew import VECTOR2I, FromMM as MM

if len(sys.argv) != 3:
    sys.exit(__doc__)
SRC, DSN = sys.argv[1], sys.argv[2]

def _yaml_nets():
    """(power, signal) from the project's parts.yaml, or (None, None)."""
    for cand in ("parts.yaml", os.path.join(os.path.dirname(SRC), "parts.yaml"),
                 os.path.join(os.path.dirname(SRC), "..", "parts.yaml")):
        if os.path.isfile(cand):
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from pcblib import load_parts
                p = load_parts(cand)
                return (p.power_nets or None), (p.signal_nets() or None)
            except Exception as e:
                print(f"note: could not read {cand}: {e}")
                return None, None
    return None, None

_yp, _ys = _yaml_nets()

def _nets(env, default, from_yaml=None):
    if env in os.environ:
        return [n.strip() for n in os.environ[env].split(",") if n.strip()]
    if from_yaml:
        return from_yaml
    return [n.strip() for n in default.split(",") if n.strip()]
POWER_NETS  = _nets("POWER_NETS",  "+3V3,GND,VIN", _yp)
SIGNAL_NETS = _nets("SIGNAL_NETS", "SDA,SCL", _ys)
W_POWER  = int(os.environ.get("W_POWER",  "400"))
W_SIGNAL = int(os.environ.get("W_SIGNAL", "300"))
CLEAR    = int(os.environ.get("CLEARANCE", "200"))
BELLY    = os.environ.get("BELLY_BOX")

board = pcbnew.LoadBoard(SRC)

# Belly keep-out. NOTE: gen_pcb P6's rule area only sets SetDoNotAllowZoneFills (enough to
# hold the GND pour out). For the autorouter that is NOT enough -- it needs a real track +
# via keepout, or it will run front copper / drop vias under the module.
if BELLY:
    from pcblib.route import _kicad_rule_area   # one zone implementation
    box = tuple(float(v) for v in BELLY.split(","))
    _kicad_rule_area(board, box, layers=(pcbnew.F_Cu,), name="belly")
    board.BuildConnectivity()

if not pcbnew.ExportSpecctraDSN(board, DSN):
    sys.exit("ExportSpecctraDSN failed")

# Split the single (class kicad_default ...) into power + signal classes for per-net widths.
s = open(DSN).read()
m = re.search(r'\(use_via "[^"]+"\)', s)
via = m.group(0) if m else '(use_via "Via[0-1]_600:300_um")'
def cls(name, nets, w):
    if not nets:
        return ""
    return (f'    (class {name} {" ".join(nets)}\n'
            f'      (circuit\n        {via}\n      )\n'
            f'      (rule\n        (width {w})\n        (clearance {CLEAR})\n      )\n    )\n')
new = cls("power", POWER_NETS, W_POWER) + cls("signal", SIGNAL_NETS, W_SIGNAL)
if new:
    s2 = re.sub(r'    \(class kicad_default.*?\n    \)\n', new, s, flags=re.S)
    if s2 == s:
        sys.exit("could not rewrite net classes -- DSN format changed?")
    open(DSN, "w").write(s2)
print(f"wrote {DSN}  (belly={BELLY}; power {W_POWER}um / signal {W_SIGNAL}um)")
