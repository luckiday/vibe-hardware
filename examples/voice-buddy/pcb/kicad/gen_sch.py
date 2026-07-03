#!/usr/bin/env python3
"""voice-buddy schematic — generated from parts.yaml (the single net source).

Plain python (no pcbnew needed): pcblib.sch writes box symbols with typed pins
+ global net labels + PWR_FLAGs. Run via pcb_check.sh, or directly:
    python3 gen_sch.py
"""
import os
import sys

# --- pcblib shim: walk up to the repo root (launchers also set PYTHONPATH) ---
_d = os.path.dirname(os.path.abspath(__file__))
while _d != "/" and not os.path.isdir(os.path.join(_d, "skills", "vibe-pcb", "scripts")):
    _d = os.path.dirname(_d)
sys.path.insert(0, os.path.join(_d, "skills", "vibe-pcb", "scripts"))

from pcblib import load_parts, Sheet

P = load_parts(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "parts.yaml"))
sheet = Sheet("voicebuddy", title="voice-buddy — ESP32-S3 + ES8311/ES7210 speaker",
              paper="A2", cols=6, cell=(70.0, 0.0))
for spec in P:
    sheet.symbol(spec, power_nets=P.power_nets)
sheet.write("voicebuddy.kicad_sch")
