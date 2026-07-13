#!/usr/bin/env python3
"""DRC via the pcbnew python API — the fallback gate for KiCad < 8, where
kicad-cli has no `pcb drc` subcommand (pcb_check.sh detects and calls this).
Writes the same style of report kicad-cli produces (violations tagged
"; error" / "; warning", plus the "Found N unconnected pads" line), so the
gate parsing in pcb_check.sh works unchanged.

Run with KiCad's python:  drc_report.py <proj>.kicad_pcb <out.rpt>
Exit 0 always — pcb_check.sh owns the gate decision.
"""
import sys

import pcbnew

if len(sys.argv) != 3:
    sys.exit(__doc__)
board = pcbnew.LoadBoard(sys.argv[1])
# refill zones so pour-dependent violations (starved thermals, clearance to
# fill) are judged on real copper — same as kicad-cli drc --refill-zones
filler = pcbnew.ZONE_FILLER(board)
filler.Fill(board.Zones())
ok = pcbnew.WriteDRCReport(board, sys.argv[2], pcbnew.EDA_UNITS_MILLIMETRES, True)
if not ok:
    sys.exit(f"WriteDRCReport failed on {sys.argv[1]}")

# WriteDRCReport emits GUI-style severity lines ("Local override; Severity: error"),
# while kicad-cli ends violation lines with "; error" — and pcb_check.sh greps the
# latter. Normalize so the same gate parsing works on both. (This mismatch once
# made the gate read 444 real violations as ZERO. Parsers lie; verify formats.)
with open(sys.argv[2], "r+", encoding="utf-8") as f:
    text = f.read()
    text = text.replace("Severity: error", "Severity: error ; error")
    text = text.replace("Severity: warning", "Severity: warning ; warning")
    f.seek(0)
    f.write(text)
    f.truncate()
print(f"wrote {sys.argv[2]}")
