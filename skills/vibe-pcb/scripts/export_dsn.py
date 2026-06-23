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
"""
import os, re, sys, pcbnew
from pcbnew import VECTOR2I, FromMM as MM

if len(sys.argv) != 3:
    sys.exit(__doc__)
SRC, DSN = sys.argv[1], sys.argv[2]

def _nets(env, default):
    return [n.strip() for n in os.environ.get(env, default).split(",") if n.strip()]
POWER_NETS  = _nets("POWER_NETS",  "+3V3,GND,VIN")
SIGNAL_NETS = _nets("SIGNAL_NETS", "SDA,SCL")
W_POWER  = int(os.environ.get("W_POWER",  "400"))
W_SIGNAL = int(os.environ.get("W_SIGNAL", "300"))
CLEAR    = int(os.environ.get("CLEARANCE", "200"))
BELLY    = os.environ.get("BELLY_BOX")

board = pcbnew.LoadBoard(SRC)

# Belly keep-out. NOTE: gen_pcb P6's rule area only sets SetDoNotAllowZoneFills (enough to
# hold the GND pour out). For the autorouter that is NOT enough -- it needs a real track +
# via keepout, or it will run front copper / drop vias under the module.
if BELLY:
    x0, y0, x1, y1 = (float(v) for v in BELLY.split(","))
    z = pcbnew.ZONE(board)
    z.SetLayer(pcbnew.F_Cu)
    z.SetIsRuleArea(True)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowTracks(True)
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    o = z.Outline(); o.NewOutline()
    for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]:
        o.Append(VECTOR2I(MM(x), MM(y)))
    board.Add(z)
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
