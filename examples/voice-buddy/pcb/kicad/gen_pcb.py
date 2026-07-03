#!/usr/bin/env python3
"""voice-buddy board — generated with pcblib (relations in, coordinates out).

Everything cross-domain comes from a contract: outline/mount-holes/ports/
keepouts from ../cad/constraints.yaml, nets from ../parts.yaml (shared with
gen_sch.py), signal<->GPIO from ../pinmap.yaml. Cluster origins are the only
tuned numbers in this file — nudge them with MOVE="AUDIO:-2,3" and re-render;
everything inside a cluster is placed by relation and follows.

Stages (pcb_skeleton.sh drives these):
    STAGE=floorplan   outline + clusters + anchors only -> <proj>.floorplan.kicad_pcb
    STAGE=place       everything placed, scorecard, placement.json -> .place
    (unset) full      + scripted copper (route.wire, pad-anchored) + pours

Front (F) = the face toward the front panel. Mics sit on B with their
bottom-port holes through the PCB, so they listen through the panel.

Run with a pcbnew python (pcb_check.sh / pcb_skeleton.sh resolve it).
"""
import os
import sys

# --- pcblib shim: walk up to the repo root (launchers also set PYTHONPATH) ---
_d = os.path.dirname(os.path.abspath(__file__))
while _d != "/" and not os.path.isdir(os.path.join(_d, "skills", "vibe-pcb", "scripts")):
    _d = os.path.dirname(_d)
sys.path.insert(0, os.path.join(_d, "skills", "vibe-pcb", "scripts"))

import pcbnew
from pcblib import (load_constraints, load_parts, load_pinmap, Board, Cluster,
                    place, beside, align_pads, row, at_edge, apply_move_env,
                    scorecard, export_placement, draw_cluster_boxes,
                    wire, via, gnd_pours)
import gen_footprints

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = os.environ.get("STAGE", "full")

gen_footprints.ensure()                       # local .pretty regenerates from source
os.environ.setdefault("KICAD_FOOTPRINT_DIRS", HERE)
os.chdir(HERE)

C = load_constraints("../../cad/constraints.yaml")
P = load_parts("../parts.yaml")
PM = load_pinmap("../pinmap.yaml")

pcb = pcbnew.NewBoard("voicebuddy.kicad_pcb")
brd = Board(pcb, C)


def put(cl, lib_name, ref, **kw):
    """Cluster place with parts.yaml as the only net/value source."""
    lib, name = lib_name.rsplit(":", 1) if ":" in lib_name else P[ref].footprint.rsplit(":", 1)
    return cl.place(lib, name, ref, value=P[ref].value, nets=P.netmap(ref), **kw)


def fp(ref):
    return P[ref].footprint


# ============================ MCU ============================
# Module top-center, antenna section INSIDE the +Y antenna keepout (the one
# part allowed there). EN RC left of the module, I2C pullups bottom-right.
MCU = Cluster(brd, "MCU", (35, 57.5))
u1 = put(MCU, fp("U1"), "U1", at=(0, 0), rot=0)
c5 = put(MCU, fp("C5"), "C5", at=(-13, -9.5), rot=90)  # 100n at 3V3 entry (pin 2 side)
c6 = put(MCU, fp("C6"), "C6", at=(0, 0), rot=90)
beside(c5, c6, side="below", gap=0.5)
r6 = put(MCU, fp("R6"), "R6", at=(-16, -8), rot=90)    # EN pullup
c7 = put(MCU, fp("C7"), "C7", at=(0, 0), rot=90)       # EN RC
beside(r6, c7, side="left", gap=0.5)
r3 = put(MCU, fp("R3"), "R3", at=(11, -13), rot=90)    # I2C pullups near pins 38/39
r4 = put(MCU, fp("R4"), "R4", at=(0, 0), rot=90)
beside(r3, r4, side="right", gap=0.5)

# ============================ AUDIO ============================
# Codec pair left-of-center; amp to their right feeding the speaker JST below;
# every decouple/ref cap rides its IC by relation.
AUD = Cluster(brd, "AUDIO", (16, 30))
u2 = put(AUD, fp("U2"), "U2", at=(0, 5))               # ES8311
u3 = put(AUD, fp("U3"), "U3", at=(0, -6))              # ES7210
u4 = put(AUD, fp("U4"), "U4", at=(12, 2), rot=90)      # NS4150B

# ES8311 support: refs row under the chip, supplies beside it
c11 = put(AUD, fp("C11"), "C11", at=(-6, 6), rot=90)   # VMID
c12 = put(AUD, fp("C12"), "C12", at=(-6.5, 10.5), rot=0)  # DACVREF
c13 = put(AUD, fp("C13"), "C13", at=(0, 0), rot=0)        # ADCVREF
beside(c12, c13, side="right", gap=0.6)
c8 = put(AUD, fp("C8"), "C8", at=(0.5, 10.5), rot=0)   # PVDD/DVDD 100n above chip
c9 = put(AUD, fp("C9"), "C9", at=(6, 10.5), rot=0)     # AVDD 100n
r12 = put(AUD, fp("R12"), "R12", at=(4.5, 6), rot=90)  # CE strap
# analog rail
fb1 = put(AUD, fp("FB1"), "FB1", at=(-8, 2), rot=90)
c10 = put(AUD, fp("C10"), "C10", at=(0, 0), rot=90)
beside(fb1, c10, side="below", gap=0.5)
# ES7210 support: ref/bias caps flank the chip
c17 = put(AUD, fp("C17"), "C17", at=(-5, -2.5), rot=0)
c18 = put(AUD, fp("C18"), "C18", at=(6, -2.5), rot=0)
c19 = put(AUD, fp("C19"), "C19", at=(-5.5, -6), rot=90)
c20 = put(AUD, fp("C20"), "C20", at=(0, 0), rot=90)
beside(c19, c20, side="below", gap=0.5)
c24 = put(AUD, fp("C24"), "C24", at=(6.5, -6), rot=90)   # MICBIAS12
c25 = put(AUD, fp("C25"), "C25", at=(0, 0), rot=90)      # MICBIAS34
beside(c24, c25, side="below", gap=0.5)
c21 = put(AUD, fp("C21"), "C21", at=(-3, -12), rot=0)  # REF34P
c22 = put(AUD, fp("C22"), "C22", at=(0, 0), rot=0)       # REF34Q
c23 = put(AUD, fp("C23"), "C23", at=(0, 0), rot=0)       # REFQM
row([c21, c22, c23], axis="x", gap=0.6)
# AEC reference chain between the two codecs
r8 = put(AUD, fp("R8"), "R8", at=(3.5, -4.5), rot=90)
r9 = put(AUD, fp("R9"), "R9", at=(0, 0), rot=90)
c16 = put(AUD, fp("C16"), "C16", at=(0, 0), rot=90)
row([r8, r9, c16], axis="y", gap=0.6)
c26 = put(AUD, fp("C26"), "C26", at=(9, -11.5), rot=0)   # MIC3N return
# amp support
c14 = put(AUD, fp("C14"), "C14", at=(7.5, 8.5), rot=0)   # OUTP coupling
c15 = put(AUD, fp("C15"), "C15", at=(0, 0), rot=0)
beside(c14, c15, side="below", gap=0.5)
r7 = put(AUD, fp("R7"), "R7", at=(15.5, 8.5), rot=90)    # PA_EN pulldown
c33 = put(AUD, fp("C33"), "C33", at=(16.5, 1), rot=90)   # amp 100n
c2 = put(AUD, fp("C2"), "C2", at=(0, 0), rot=90)         # amp bulk
beside(c33, c2, side="below", gap=0.5)

# speaker JST: its own compact block bottom-left (wires run to the rear speaker)
SPK = Cluster(brd, "SPK", (10, 8))
j2 = put(SPK, fp("J2"), "J2", at=(0, 0), rot=0)

# ============================ PWR ============================
# USB-C at the contract port on the +X wall; ESD + CC + LDO chain inward.
PWR = Cluster(brd, "PWR", (55, 25))
j1 = put(PWR, fp("J1"), "J1", at=(5, -13), rot=270)
at_edge(brd, j1, "usb_c", overhang=1.3)                  # receptacle lip past the wall
u6 = put(PWR, fp("U6"), "U6", at=(-5, -10), rot=0)        # USBLC6 near D+/D-
r1 = put(PWR, fp("R1"), "R1", at=(0, -19), rot=0)         # CC pulldowns
r2 = put(PWR, fp("R2"), "R2", at=(0, 0), rot=0)
beside(r1, r2, side="below", gap=0.5)
c1 = put(PWR, fp("C1"), "C1", at=(-10, -11), rot=90)      # VBUS bulk
u5 = put(PWR, fp("U5"), "U5", at=(0, 3), rot=0)           # LDO
c3 = put(PWR, fp("C3"), "C3", at=(0, 0), rot=90)         # in
c4 = put(PWR, fp("C4"), "C4", at=(0, 0), rot=90)         # out
beside(u5, c3, side="left", gap=0.7)
beside(u5, c4, side="right", gap=0.7)

# ============================ UI ============================
# Buttons + LED sit exactly on their contract windows; OLED socket derives
# from the display window + module geometry (one number, one place).
UI = Cluster(brd, "UI", (35, 10), pinned=True)   # members sit on contract windows
w = C.window
sw1 = put(UI, fp("SW1"), "SW1", at=(0, 0)); sw1.set(w("btn_boot")["x"], w("btn_boot")["y"])
sw2 = put(UI, fp("SW2"), "SW2", at=(0, 0)); sw2.set(w("btn_voldn")["x"], w("btn_voldn")["y"])
sw3 = put(UI, fp("SW3"), "SW3", at=(0, 0)); sw3.set(w("btn_volup")["x"], w("btn_volup")["y"])
d1 = put(UI, fp("D1"), "D1", at=(0, 0)); d1.set(w("led")["x"], w("led")["y"])
c34 = put(UI, fp("C34"), "C34", at=(0, 0), rot=90)
beside(d1, c34, side="right", gap=0.6)
oled = C.offboard["oled_module"]
j3 = put(UI, fp("J3"), "J3", at=(0, 0), rot=90)
j3.set(w("display")["x"], w("display")["y"] + float(oled["header_offset_y"]))
r5 = put(UI, fp("R5"), "R5", at=(0, 0), rot=90)          # BOOT pullup
beside(sw1, r5, side="right", gap=0.8)

# ============================ MICS (B side) ============================
# Bottom-port mics ON their contract windows (port hole through the PCB);
# bias RC + coupling on F right next to each.
for name, mic_ref, rc, cc, cvdd, cn in (
        ("MICL", "MK1", "R10", "C29", "C27", "C31"),
        ("MICR", "MK2", "R11", "C30", "C28", "C32")):
    win = C.window("mic_l" if name == "MICL" else "mic_r")
    cl = Cluster(brd, name, (win["x"], win["y"]), pinned=True)
    mk = put(cl, fp(mic_ref), mic_ref, at=(0, 0), flip=True)
    inward = 1 if name == "MICL" else -1
    r = put(cl, fp(rc), rc, at=(inward * 4.5, -3.5), rot=0)
    c_c = put(cl, fp(cc), cc, at=(0, 0), rot=0)
    beside(r, c_c, side="below", gap=0.5)
    c_v = put(cl, fp(cvdd), cvdd, at=(inward * 4.5, 3.5), rot=0)
    c_n = put(cl, fp(cn), cn, at=(0, 0), rot=0)
    beside(c_v, c_n, side="above", gap=0.5)

apply_move_env()

# ============================ stages & gates ============================
if STAGE == "floorplan":
    draw_cluster_boxes(brd)
    brd.save("voicebuddy.floorplan.kicad_pcb")
    sys.exit(0)

fails = scorecard(brd, budgets={"hpwl_mm": 2000}, keepout_allow=("U1",))
export_placement(
    brd, "../placement.json",
    kinds={"J1": "usb_c", "SW1": "btn_boot", "SW2": "btn_voldn",
           "SW3": "btn_volup", "D1": "led", "MK1": "mic_l", "MK2": "mic_r",
           "J2": "speaker_conn"},
    extras=[{"ref": "J3", "kind": "display",
             "center": [round(j3.pos[0], 2),
                        round(j3.pos[1] - float(oled["header_offset_y"]), 2)],
             "w": float(oled["w"]), "h": float(oled["h"])}],
    product="voice-buddy", revision="v2026-07-03")

if STAGE == "place":
    brd.save("voicebuddy.place.kicad_pcb")
    sys.exit(fails)
if fails:
    sys.exit(f"placement gate failed ({fails}) — fix before routing")

# ============================ copper ============================
import routing
routing.route(brd, dict(u1=u1, u2=u2, u3=u3, u4=u4, u5=u5, u6=u6,
                        j1=j1, j2=j2, j3=j3, sw1=sw1, sw2=sw2, sw3=sw3, d1=d1,
                        **{k.lower(): v for k, v in brd.parts.items()
                           if k[0] in "RCF" or k.startswith("MK")}))
gnd_pours(brd)
brd.save("voicebuddy.kicad_pcb")
print("wrote voicebuddy.kicad_pcb")
