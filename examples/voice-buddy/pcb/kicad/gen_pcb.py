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
                    wire, via, fanout, bridge_pads, gnd_pours, plane_pours,
                    apply_ses)
import gen_footprints

HERE = os.path.dirname(os.path.abspath(__file__))
STAGE = os.environ.get("STAGE", "full")

gen_footprints.ensure()                       # local .pretty regenerates from source
os.environ.setdefault("KICAD_FOOTPRINT_DIRS", HERE)
os.chdir(HERE)

C = load_constraints("../../cad/constraints.yaml")
P = load_parts("../parts.yaml")
PM = load_pinmap("../pinmap.yaml")

# 4-layer board: F/B signal + In1 = GND plane + In2 = +3V3 plane (fanout-first:
# freerouting 2.2.x deleted its fanout pass and will NOT drop SMD pads onto a
# plane, so gen_pcb pre-fans every GND/+3V3 pad with LOCKED stubs+vias — exported
# as Specctra "(type fix)" — and autoroute.sh runs with FR_INC=power so the
# router only ever sees signals). 0.15mm track/clearance fans out the 0.45mm QFN;
# 0.3mm edge clearance is what lets copper legally reach the USB-C pads at the
# wall (KiCad's 0.5 default starves the router there).
pcb = pcbnew.NewBoard("voicebuddy.kicad_pcb")
brd = Board(pcb, C, copper_layers=4, min_track=0.15, min_clearance=0.15,
            min_hole=0.2,   # 0.2mm reaches the WROOM belly-via drill (JLC-capable)
            edge_clearance=0.3)


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
# ONE duplex codec (ES8388) left-of-center, rot=270 so its digital flank
# (MCLK/SCLK/DSDIN/LRCK/ASDOUT, datasheet left column) faces UP toward the
# module's lower-left I2S pads and its control/input flank (CCLK/CDATA/
# LIN1/RIN1, top row) faces RIGHT toward the OLED socket and the AEC chain.
# Amp to the right feeding the speaker JST below; every decouple/ref cap
# rides its IC by relation.
AUD = Cluster(brd, "AUDIO", (16, 30))
u2 = put(AUD, fp("U2"), "U2", at=(0, 3), rot=270)      # ES8388
u4 = put(AUD, fp("U4"), "U4", at=(12, 2), rot=90)      # NS4150B

# ES8388 support: VMID/VREF/ADCVREF 10u bank left of the chip (analog-quiet
# side after rot: datasheet right column faces LEFT), supplies above/below
c11 = put(AUD, fp("C11"), "C11", at=(-5.5, 4.5), rot=90)   # VMID
c12 = put(AUD, fp("C12"), "C12", at=(0, 0), rot=90)        # VREF
c13 = put(AUD, fp("C13"), "C13", at=(0, 0), rot=90)        # ADCVREF
beside(c11, c12, side="below", gap=0.6)                    # bank grows DOWN,
beside(c12, c13, side="below", gap=0.6)                    # away from the MCU
c8 = put(AUD, fp("C8"), "C8", at=(0.5, 8.5), rot=0)    # DVDD/PVDD 100n above chip
c9 = put(AUD, fp("C9"), "C9", at=(5, 8.5), rot=0)      # AVDD/HPVDD 100n
r12 = put(AUD, fp("R12"), "R12", at=(4.5, 6.2), rot=90)  # CE strap -> 0x10
# analog rail
fb1 = put(AUD, fp("FB1"), "FB1", at=(-8.5, 2), rot=90)
c10 = put(AUD, fp("C10"), "C10", at=(0, 0), rot=90)
beside(fb1, c10, side="below", gap=0.5)
# AEC reference chain: OUTP -> R8 -> AEC_IN (R9 to GND) -> C16 -> RIN1
r8 = put(AUD, fp("R8"), "R8", at=(4.5, -3.5), rot=90)
r9 = put(AUD, fp("R9"), "R9", at=(0, 0), rot=90)
c16 = put(AUD, fp("C16"), "C16", at=(0, 0), rot=90)
row([r8, r9, c16], axis="x", gap=0.6)
# amp support
c14 = put(AUD, fp("C14"), "C14", at=(9, 8.5), rot=0)     # OUTP coupling
c15 = put(AUD, fp("C15"), "C15", at=(0, 0), rot=0)       # IN+ AC ground
beside(c14, c15, side="below", gap=0.5)
r7 = put(AUD, fp("R7"), "R7", at=(15.5, 8.5), rot=90)    # PA_EN pulldown
c19 = put(AUD, fp("C19"), "C19", at=(16.5, 1), rot=90)   # amp 100n
c2 = put(AUD, fp("C2"), "C2", at=(0, 0), rot=90)         # amp bulk
beside(c19, c2, side="below", gap=0.5)

# speaker JST: its own compact block bottom-left (wires run to the rear speaker)
SPK = Cluster(brd, "SPK", (10, 8))
j2 = put(SPK, fp("J2"), "J2", at=(0, 0), rot=0)

# ============================ PWR ============================
# USB-C at the contract port on the +X wall; ESD + CC + LDO chain inward.
PWR = Cluster(brd, "PWR", (55, 25))
j1 = put(PWR, fp("J1"), "J1", at=(5, -13), rot=90)       # rot=90: pin row INBOARD,
at_edge(brd, j1, "usb_c", overhang=1.3)                  # receptacle lip past the wall
# (v1 shipped rot=270 — pin row 0.3mm OUTSIDE the board edge. Every USB net was
# unroutable and 21 copper_edge_clearance violations traced back to this.)
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
c20 = put(UI, fp("C20"), "C20", at=(0, 0), rot=90)
beside(d1, c20, side="right", gap=0.6)
oled = C.offboard["oled_module"]
j3 = put(UI, fp("J3"), "J3", at=(0, 0), rot=90)
j3.set(w("display")["x"], w("display")["y"] + float(oled["header_offset_y"]))
r5 = put(UI, fp("R5"), "R5", at=(0, 0), rot=90)          # BOOT pullup
beside(sw1, r5, side="right", gap=0.8)

# ============================ MIC (B side) ============================
# Bottom-port mic ON its contract window (port hole through the PCB);
# supply RC (1k + 10u, the A1S MBIAS pattern) + coupling on F right next to it.
win = C.window("mic")
MIC = Cluster(brd, "MIC", (win["x"], win["y"]), pinned=True)
mk1 = put(MIC, fp("MK1"), "MK1", at=(0, 0), flip=True)
r10 = put(MIC, fp("R10"), "R10", at=(4.5, 3.5), rot=0)   # +3V3A -> MIC_VDD
c17 = put(MIC, fp("C17"), "C17", at=(0, 0), rot=0)
beside(r10, c17, side="below", gap=0.5)
c18 = put(MIC, fp("C18"), "C18", at=(4.5, -3.5), rot=0)  # MIC_OUT -> LIN1 coupling

apply_move_env()

# ===================== fanout-first locked copper =====================
# Everything freerouting can't/won't do, done deterministically and LOCKED
# (Specctra "(type fix)") BEFORE the placement save that feeds export_dsn:
#   - every +3V3 SMD pad -> stub + via to the In2 plane
#   - the QFN / amp GND+analog-power pads -> stubs/EP grids to the In1 plane
# autoroute.sh then runs with FR_INC=power POWER_NETS="GND,+3V3" so the router
# only sees signals (+5V and +3V3A stay routable — they have no plane).
# J1 needs NO manual copper: its GND/+5V A/B mirror pads are coincident
# (stacked) in the 16P footprint, and DP/DN interleave ABAB — a crossing the
# router must make with a via anyway. GND pads reach the F pour (0.3mm edge
# clearance); +5V/CC/DP/DN are ordinary signal routes.
for _ref, _part in list(brd.parts.items()):
    if _ref in ("U1", "J1") or _ref.startswith("H"):
        continue                       # module belly + edge connector: no blind stubs
    fanout(brd, _part, ("+3V3",))
fanout(brd, u2, ("GND",))              # QFN escape: GND stubs + EP thermal grid
fanout(brd, u4, ("GND",))              # amp EP grid + GND stubs
fanout(brd, u1, ("+3V3",))             # module 3V3 pin escapes off the left edge
# (+3V3A has NO plane — freerouting routes it as a signal; fanning it out would
#  only leave dangling vias.)
# OUTP (LOUT1, QFN pad 12) sits between the codec's GND fanout vias — give it
# a LOCKED escape stub so the router starts outside the congested pad ring.
_p12 = u2.pad(12)
wire(brd, "OUTP", [_p12, (_p12[0] - 1.5, _p12[1])], w=0.2, lock=True)
# inner planes must exist on the PLACED board so export_dsn emits them as
# Specctra (type power) layers
plane_pours(brd, {"In1.Cu": "GND", "In2.Cu": "+3V3"})

# ============================ stages & gates ============================
if STAGE == "floorplan":
    draw_cluster_boxes(brd)
    brd.save("voicebuddy.floorplan.kicad_pcb")
    sys.exit(0)

fails = scorecard(brd, budgets={"hpwl_mm": 2000}, keepout_allow=("U1",))
export_placement(
    brd, "../placement.json",
    kinds={"J1": "usb_c", "SW1": "btn_boot", "SW2": "btn_voldn",
           "SW3": "btn_volup", "D1": "led", "MK1": "mic",
           "J2": "speaker_conn"},
    extras=[{"ref": "J3", "kind": "display",
             "center": [round(j3.pos[0], 2),
                        round(j3.pos[1] - float(oled["header_offset_y"]), 2)],
             "w": float(oled["w"]), "h": float(oled["h"])}],
    product="voice-buddy", revision="v2026-07-13")

if STAGE == "place":
    brd.save("voicebuddy.place.kicad_pcb")
    sys.exit(fails)
if fails:
    sys.exit(f"placement gate failed ({fails}) — fix before routing")

# ============================ copper ============================
# Primary path: replay the accepted freerouting session (pcb/routing.ses) so the
# routed board regenerates from committed sources (the locked fanout copper is
# already on the board; SES import adds the signal routes around it). Without a
# session the board still saves — fanout + planes only — so the autoroute flow
# has something to start from.
_ses = os.path.join(HERE, "..", "routing.ses")
if os.path.isfile(_ses):
    apply_ses(brd, _ses)
    print("routed by freerouting session replay (routing.ses)")
else:
    print("WARNING: no ../routing.ses — saving fanout-only board "
          "(run skills/vibe-pcb/scripts/autoroute.sh, then accept the .ses)")
gnd_pours(brd)
brd.save("voicebuddy.kicad_pcb")
print("wrote voicebuddy.kicad_pcb")
