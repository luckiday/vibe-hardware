"""Scripted copper for voice-buddy (2-layer). Board frame mm, +y up."""
from pcblib import wire, via

WP, WS, WT = 0.4, 0.3, 0.2  # power / signal / QFN-stub widths


def route(brd, p):
    _audio_u2(brd, p)
    _audio_u3(brd, p)
    _mics(brd, p)
    _spk_paen(brd, p)
    _locals_br(brd, p)
    _pwr_5v(brd, p)
    _pwr_3v3_trunk(brd, p)
    _pwr_3v3_riser(brd, p)
    _en(brd, p)
    _pwr_3v3a(brd, p)


def _pwr_3v3a(brd, p):
    """+3V3A: FB1.2 -> C10 -> C18 -> U3.22/23 bridge; B.Cu riser -> C9/U2.11.
    Also +3V3 to C17.1/U3.1, and the U3.24 MICBIAS12 escape (interlocked)."""
    wire(brd, "+3V3", [(13.65, 30.94), (13.65, 23.0), (14.15, 23.0)], w=WT)
    wire(brd, "+3V3", [(13.65, 29.4), (16.42, 29.4)], w=WT)  # C17.1 (rot0 above C26)
    wire(brd, "+3V3", [(13.65, 25.4), (14.15, 25.4)], w=WT)   # U3.1
    wire(brd, "+3V3", [(13.65, 23.4), (14.15, 23.4)], w=WT)   # U3.6
    n = "+3V3A"
    wire(brd, n, [(8.0, 33.06), (7.0, 33.06), (7.0, 27.5), (7.6, 27.5)], w=WP)
    wire(brd, n, [(8.0, 27.5), (8.0, 26.55), (21.22, 26.55),
                  (21.22, 27.02)], w=WT)                   # C10.1 -> C18.1
    wire(brd, n, [(21.22, 27.5), (21.22, 24.8), (18.55, 24.8)], w=WT)
    wire(brd, n, [(17.85, 24.6), (18.55, 24.6), (18.55, 25.0),
                  (17.85, 25.0)], w=WT)                    # U3.22/23 bridge
    wire(brd, n, [(21.22, 27.5), (21.22, 28.6)], w=WS)
    via(brd, n, (21.22, 28.6), size=0.5)
    wire(brd, n, [(21.22, 28.6), (23.6, 28.6), (23.6, 38.9),
                  (21.22, 38.9), (21.22, 39.4)], layer="B.Cu", w=WP)
    via(brd, n, (21.22, 39.4), size=0.5)
    wire(brd, n, [(21.22, 39.4), (21.22, 40.5)], w=WS)     # C9.1
    wire(brd, n, [(21.22, 39.4), (21.6, 39.0), (21.6, 34.28), (18.3, 34.28),
                  (17.88, 34.15)], w=WT)                   # U2.11
    m = "MICBIAS12"
    wire(brd, m, [(17.85, 25.4), (20.3, 25.4), (20.3, 25.6)], w=WT)
    via(brd, m, (20.3, 25.6), size=0.5)
    wire(brd, m, [(20.3, 25.6), (20.3, 23.22), (21.9, 23.22)],
         layer="B.Cu", w=WS)
    via(brd, m, (21.9, 23.22), size=0.5)
    wire(brd, m, [(21.9, 23.22), (22.2, 23.22)], w=WT)     # C24.1


def _pwr_3v3_riser(brd, p):
    """+3V3 west riser: trunk -> C6, C5, R6.1, U1.2."""
    n = "+3V3"
    wire(brd, n, [(25.3, 26.7), (25.3, 44.2), (23.3, 44.2), (23.3, 61.49),
                  (25.6, 61.49)], w=WP)                    # riser -> U1.2
    wire(brd, n, [(25.3, 43.6), (22.4, 43.6)], w=WP)       # -> C6.1
    wire(brd, n, [(23.3, 47.22), (19.0, 47.22), (19.0, 48.4)], w=WP)  # C5+R6


def _en(brd, p):
    """EN: U1.3 -> B.Cu -> R6.2 -> C7.1."""
    wire(brd, "EN", [(25.6, 60.22), (24.6, 60.22)], w=WS)
    via(brd, "EN", (24.6, 60.22), size=0.5)
    wire(brd, "EN", [(24.6, 60.22), (19.0, 60.22), (19.0, 51.4)],
         layer="B.Cu", w=WS)
    via(brd, "EN", (19.0, 51.4), size=0.5)
    wire(brd, "EN", [(19.0, 51.4), (19.0, 50.33), (18.1, 50.33),
                     (18.1, 47.6), (17.05, 47.6), (17.05, 48.7)], w=WS)


def _pwr_3v3_trunk(brd, p):
    """+3V3: U5.2 -> west trunk -> FB1.1; branches D1/C34, R5.1, R3/R4."""
    n = "+3V3"
    wire(brd, n, [(51.85, 28.0), (48.0, 28.0)], w=WT)      # C3 pad-gap neck
    wire(brd, n, [(48.0, 28.0), (34.0, 28.0), (34.0, 27.3), (26.6, 27.3),
                  (26.6, 26.7), (22.3, 26.7), (22.3, 30.94),
                  (8.0, 30.94)], w=WP)                     # trunk to FB1.1
    wire(brd, n, [(59.0, 27.05), (61.07, 27.05)], w=WP)    # tab -> C4.1
    wire(brd, n, [(58.15, 26.1), (58.15, 20.22), (61.32, 20.22)], w=WP)
    wire(brd, n, [(58.15, 22.65), (55.0, 22.65)], w=WP)    # -> D1.1
    wire(brd, n, [(42.6, 28.0), (42.6, 7.18), (42.05, 7.18)], w=WP)  # R5.1
    wire(brd, n, [(54.55, 22.65), (46.9, 22.65), (46.9, 43.67)], w=WP)
    wire(brd, n, [(46.0, 43.67), (47.95, 43.67)], w=WS)    # R3.1 + R4.1


def _pwr_5v(brd, p):
    """+5V: J1 pads (via-in-pad) -> B.Cu trunk y14.9 -> U6.5/C1/U5/C3,
    then B.Cu risers to C2/C33/U4.6."""
    n = "+5V"
    via(brd, n, (69.75, 14.45), size=0.5)   # J1.A4/B9
    via(brd, n, (69.75, 9.55), size=0.5)    # J1.A9/B4
    wire(brd, n, [(69.75, 9.55), (69.75, 9.0), (68.9, 9.0), (68.9, 14.9),
                  (69.75, 14.45)], layer="B.Cu", w=WP)
    wire(brd, n, [(68.9, 14.9), (32.5, 14.9)], layer="B.Cu", w=WP)  # trunk
    via(brd, n, (53.0, 14.9), size=0.5)                    # U6.5 tap
    wire(brd, n, [(53.0, 14.9), (51.0, 14.9)], w=WP)
    wire(brd, n, [(53.8, 14.9), (53.8, 25.7)], layer="B.Cu", w=WP)  # U5 riser
    via(brd, n, (53.8, 25.7), size=0.5)
    wire(brd, n, [(53.8, 25.7), (49.18, 25.7), (49.18, 27.22)], w=WP)
    wire(brd, n, [(45.0, 14.9), (45.0, 13.9)], layer="B.Cu", w=WP)  # C1 tap
    via(brd, n, (45.0, 13.9), size=0.5)
    wire(brd, n, [(45.0, 13.9), (45.0, 13.1)], w=WP)
    via(brd, n, (32.5, 15.6), size=0.5)
    wire(brd, n, [(32.5, 15.6), (32.5, 30.22)], w=WP)      # F riser through C2.1
    wire(brd, n, [(32.5, 30.22), (31.4, 30.22), (31.4, 36.1),
                  (28.64, 36.1), (28.64, 35.2)], w=WP)     # U4.6 from above


def _locals_br(brd, p):
    """Buttons twin-pad bridges, BOOT pullup, CC pulldowns."""
    for ref, net in (("sw1", "BTN_BOOT"), ("sw2", "BTN_VOLDN"),
                     ("sw3", "BTN_VOLUP")):
        a, b = sorted(p[ref].pads("1"))
        wire(brd, net, [a, b], w=WS)
    # R5.2 -> SW1 right pad
    wire(brd, "BTN_BOOT", [p["r5"].pad("2"), (38.98, 10.25)], bend="y", w=WS)
    # CC1: J1.A5 -> B.Cu down the shield-pad gap -> R1.1 from above
    wire(brd, "CC1", [(70.32, 13.25), (69.0, 13.25), (68.0, 13.55)], w=WS)
    via(brd, "CC1", (68.0, 13.55), size=0.5)
    wire(brd, "CC1", [(68.0, 13.55), (67.2, 13.55), (67.2, 6.8),
                      (54.18, 6.8)], layer="B.Cu", w=WS)
    via(brd, "CC1", (54.18, 6.8), size=0.5)
    wire(brd, "CC1", [(54.18, 6.8), (54.18, 6.0)], w=WS)
    # CC2: J1.B5 -> B.Cu low road -> R2.1 from below
    wire(brd, "CC2", [(70.32, 10.25), (68.5, 10.25), (68.1, 9.8)], w=WS)
    via(brd, "CC2", (68.1, 9.8), size=0.5)
    wire(brd, "CC2", [(68.1, 9.8), (67.9, 9.8), (67.9, 3.0),
                      (54.18, 3.0)], layer="B.Cu", w=WS)
    via(brd, "CC2", (54.18, 3.0), size=0.5)
    wire(brd, "CC2", [(54.18, 3.0), (54.18, 4.05)], w=WS)


def _audio_u2(brd, p):
    """ES8311 nest: line out -> coupling caps/amp, AEC chain, VMID/VREF/CE."""
    n = "OUTP"   # one F lane x18.75 serves both directions
    wire(brd, n, [(17.45, 34.6), (18.75, 34.6)], w=WT)
    wire(brd, n, [(18.75, 34.6), (18.75, 38.5), (22.72, 38.5)], w=WS)
    wire(brd, n, [(18.75, 34.6), (18.75, 24.68), (19.5, 24.68)], w=WS)
    n = "OUTN"   # B hop to C15.1 (via lands in-pad, same net)
    wire(brd, n, [(17.45, 35.0), (18.2, 35.35)], w=WT)
    via(brd, n, (18.2, 35.35), size=0.5)
    wire(brd, n, [(18.2, 35.35), (22.3, 35.35), (22.3, 36.55)], layer="B.Cu", w=WS)
    via(brd, n, (22.3, 36.55), size=0.5)
    wire(brd, n, [(22.3, 36.55), (22.72, 36.55)], w=WS)
    n = "AMP_INP"   # C14.2 -> B lane x25.25 -> U4.2 from below
    wire(brd, n, [(24.28, 38.5), (25.25, 38.5)], w=WS)
    via(brd, n, (25.25, 38.5), size=0.5)
    wire(brd, n, [(25.25, 38.5), (25.25, 28.6), (27.36, 28.6)], layer="B.Cu", w=WS)
    via(brd, n, (27.36, 28.6), size=0.5)
    wire(brd, n, [(27.36, 28.6), (27.36, 29.53)], w=WS)
    n = "AMP_INN"   # C15.2 -> B lane x25.8 -> U4.1 from below
    wire(brd, n, [(24.28, 36.55), (25.8, 36.55)], w=WS)
    via(brd, n, (25.8, 36.55), size=0.5)
    wire(brd, n, [(25.8, 36.55), (25.8, 28.2), (26.09, 28.2)], layer="B.Cu", w=WS)
    via(brd, n, (26.09, 28.2), size=0.5)
    wire(brd, n, [(26.09, 28.2), (26.09, 29.53)], w=WS)
    n = "AEC_IN"    # the attenuator column x19.5 (skirt around R9's GND pad)
    wire(brd, n, [(19.5, 26.32), (19.5, 28.22)], w=WS)
    wire(brd, n, [(19.5, 28.22), (20.15, 28.22), (20.15, 31.4),
                  (19.95, 31.82), (19.5, 31.82)], w=WS)
    n = "AEC_REF"   # C16.2 -> B -> straight down into U3.31
    wire(brd, n, [(19.5, 33.38), (19.15, 33.0)], w=WS)
    via(brd, n, (19.15, 33.0), size=0.5)
    wire(brd, n, [(19.15, 33.0), (14.6, 33.0), (14.6, 28.3),
                  (15.0, 28.3)], layer="B.Cu", w=WS)
    via(brd, n, (15.0, 28.3), size=0.5)
    wire(brd, n, [(15.0, 28.3), (15.0, 25.85)], w=WT)
    n = "MIC3N"     # U3.32 -> B hop -> C26.1 (via-in-pad, same net)
    wire(brd, n, [(14.6, 25.85), (14.6, 26.5), (14.2, 26.5)], w=WT)
    via(brd, n, (14.2, 26.9), size=0.5)
    wire(brd, n, [(14.2, 26.9), (16.42, 26.9), (16.42, 27.4)], layer="B.Cu", w=WS)
    via(brd, n, (16.42, 27.4), size=0.5)
    n = "VMID"      # U2.16 up-left to C11.1
    wire(brd, n, [(16.8, 36.45), (16.8, 37.6), (14.62, 37.6),
                  (14.62, 38.7)], w=WT)
    n = "ES8311_CE"  # U2.20 -> B hop over the VMID lane -> R12.1
    wire(brd, n, [(15.2, 36.45), (15.2, 37.1)], w=WT)
    via(brd, n, (15.2, 37.55), size=0.5)
    wire(brd, n, [(15.2, 37.55), (20.5, 37.55), (20.5, 36.9)], layer="B.Cu", w=WS)
    via(brd, n, (20.5, 36.9), size=0.5)
    wire(brd, n, [(20.5, 36.9), (20.5, 35.18)], w=WS)
    n = "VREF_DAC"  # U2.14 -> lane x18.35 -> C12.1 (pocket right of R12)
    wire(brd, n, [(17.45, 35.4), (18.35, 35.4)], w=WT)
    wire(brd, n, [(18.35, 35.4), (18.35, 33.2), (23.6, 33.2),
                  (23.6, 32.28)], w=WS)
    n = "VREF_ADC"  # U2.15 -> lane x18.75? no — short B hop under x18.35 lane
    wire(brd, n, [(17.45, 35.8), (18.1, 36.15)], w=WT)
    via(brd, n, (18.55, 36.15), size=0.5)
    wire(brd, n, [(18.55, 36.15), (21.35, 36.15), (21.35, 33.6)],
         layer="B.Cu", w=WS)
    via(brd, n, (21.35, 33.6), size=0.5)
    wire(brd, n, [(21.35, 33.6), (21.35, 32.28)], w=WS)


def _audio_u3(brd, p):
    """ES7210 refs/bias + the U3-side mic pins."""
    wire(brd, "REF12P", [(17.85, 22.6), (24.4, 22.6), (24.4, 24.22),
                         (25.05, 24.22)], w=WT)            # -> C19.1
    wire(brd, "REF12Q", [(17.85, 23.0), (24.0, 23.0), (24.0, 20.78),
                         (25.05, 20.78)], w=WT)            # -> C20.1
    wire(brd, "REF34P", [(15.8, 25.85), (15.8, 26.35), (15.55, 26.35)], w=WT)
    via(brd, "REF34P", (15.55, 26.35), size=0.5)
    wire(brd, "REF34P", [(15.55, 26.35), (12.6, 26.35), (12.6, 19.2),
                         (12.22, 19.2)], layer="B.Cu", w=WS)
    via(brd, "REF34P", (12.22, 19.2), size=0.5)
    wire(brd, "REF34P", [(12.22, 19.2), (12.22, 18.45)], w=WS)
    wire(brd, "REF34Q", [(15.4, 25.85), (15.4, 26.6)], w=WT)
    via(brd, "REF34Q", (15.4, 27.15), size=0.5)
    wire(brd, "REF34Q", [(15.4, 27.15), (13.3, 27.15), (13.3, 19.6),
                         (15.77, 19.6)], layer="B.Cu", w=WS)
    via(brd, "REF34Q", (15.77, 19.6), size=0.5)
    wire(brd, "REF34Q", [(15.77, 19.6), (15.77, 18.45)], w=WS)
    wire(brd, "REFQM", [(17.4, 25.85), (17.4, 26.5), (18.0, 26.5)], w=WT)
    via(brd, "REFQM", (18.35, 26.85), size=0.5)
    wire(brd, "REFQM", [(18.35, 26.85), (19.32, 26.85), (19.32, 19.6)],
         layer="B.Cu", w=WS)
    via(brd, "REFQM", (19.32, 19.6), size=0.5)
    wire(brd, "REFQM", [(19.32, 19.6), (19.32, 18.45)], w=WS)
    wire(brd, "MICBIAS34", [(17.0, 25.85), (17.0, 26.3), (16.7, 26.3)], w=WT)
    via(brd, "MICBIAS34", (16.55, 25.95), size=0.5)
    wire(brd, "MICBIAS34", [(16.55, 25.95), (21.7, 25.95), (21.7, 21.44),
                            (22.1, 21.44)], layer="B.Cu", w=WS)
    via(brd, "MICBIAS34", (22.1, 21.44), size=0.5)
    wire(brd, "MICBIAS34", [(22.1, 21.44), (22.5, 21.05)], w=WS)  # C25.1
    n = "MICBIAS12"   # C24.1 -> R10.1 (west) and R11.1 (east, via B y44.3)
    wire(brd, n, [(22.5, 23.22), (22.5, 22.6), (24.75, 22.6)], w=WS)
    via(brd, n, (25.3, 22.15), size=0.5)
    wire(brd, n, [(25.3, 22.15), (56.1, 22.15), (56.1, 44.3), (56.68, 45.3)],
         layer="B.Cu", w=WS)
    via(brd, n, (56.68, 45.3), size=0.5)
    wire(brd, n, [(56.68, 45.3), (56.68, 46.03)], w=WS)   # R11.1
    wire(brd, n, [(22.5, 23.22), (21.7, 23.9)], w=WS)
    via(brd, n, (21.15, 24.4), size=0.5)
    wire(brd, n, [(21.15, 24.4), (20.3, 25.6)], layer="B.Cu", w=WS)
    # (existing jog continues 20.3,25.6 -> 17.85,25.4 tap; extend west to R10)
    wire(brd, n, [(21.15, 24.4), (13.05, 44.0), (12.6, 44.9)],
         layer="B.Cu", w=WS)
    via(brd, n, (12.6, 44.9), size=0.5)
    wire(brd, n, [(12.6, 44.9), (11.67, 45.4), (11.67, 46.03)], w=WS)  # R10.1


def _mics(brd, p):
    """MEMS mics (B side) -> couplers -> U3 inputs; VDD RC feeds."""
    n = "MICL_OUT"
    wire(brd, n, [(6.52, 49.05), (6.52, 45.6), (11.0, 45.6), (11.72, 45.3)],
         layer="B.Cu", w=WS)
    via(brd, n, (11.72, 45.3), size=0.5)
    wire(brd, n, [(11.72, 45.3), (11.72, 45.02)], w=WS)   # C29.1
    n = "MIC1P"
    wire(brd, n, [(13.28, 44.55), (13.28, 44.15)], w=WS)
    via(brd, n, (13.7, 43.9), size=0.5)
    wire(brd, n, [(13.7, 43.9), (13.7, 21.3)], layer="B.Cu", w=WS)
    via(brd, n, (13.7, 21.3), size=0.5)
    wire(brd, n, [(13.7, 21.3), (17.4, 21.3), (17.4, 22.15)], w=WT)
    n = "MIC1N"
    wire(brd, n, [(17.0, 22.15), (17.0, 20.7), (6.4, 20.7), (6.4, 54.5),
                  (11.72, 54.5), (11.72, 55.0)], w=WS)    # west-edge scenic route
    n = "MICL_VDD"
    wire(brd, n, [(13.33, 46.97), (13.33, 52.7), (11.72, 52.7),
                  (11.72, 53.05)], w=WS)                  # R10.2 -> C27.1
    wire(brd, n, [(11.72, 52.7), (10.6, 52.7), (10.6, 51.6)], w=WS)
    via(brd, n, (10.6, 51.6), size=0.5)
    wire(brd, n, [(10.6, 51.6), (9.48, 50.95)], layer="B.Cu", w=WS)
    n = "MICR_OUT"
    wire(brd, n, [(60.52, 49.05), (60.52, 45.4), (57.4, 45.4)],
         layer="B.Cu", w=WS)
    via(brd, n, (57.4, 45.4), size=0.5)
    wire(brd, n, [(57.4, 45.4), (56.72, 45.4), (56.72, 45.02)], w=WS)
    n = "MICR_VDD"
    wire(brd, n, [(58.32, 46.97), (58.32, 52.7), (56.72, 52.7),
                  (56.72, 53.05)], w=WS)                  # R11.2 -> C28.1
    wire(brd, n, [(58.32, 52.7), (64.6, 52.7), (64.6, 51.6)], w=WS)
    via(brd, n, (64.6, 51.6), size=0.5)
    wire(brd, n, [(64.6, 51.6), (63.48, 50.95)], layer="B.Cu", w=WS)
    n = "MIC2P"   # C30.2 -> east B lane x53.2 -> south -> west y16.0 -> U3.19
    wire(brd, n, [(58.28, 44.55), (58.28, 43.9)], w=WS)
    via(brd, n, (58.28, 43.9), size=0.5)
    wire(brd, n, [(58.28, 43.9), (53.2, 43.7), (53.2, 16.0), (20.17, 16.0)],
         layer="B.Cu", w=WS)
    via(brd, n, (20.17, 16.0), size=0.5)
    wire(brd, n, [(20.17, 16.0), (20.17, 20.3)], w=WT)    # through the C23 pad gap
    via(brd, n, (20.17, 20.6), size=0.5)
    wire(brd, n, [(20.17, 20.6), (19.4, 21.6), (19.4, 22.6)],
         layer="B.Cu", w=WS)
    via(brd, n, (19.4, 22.6), size=0.5)
    wire(brd, n, [(19.4, 22.6), (19.4, 23.4), (17.85, 23.4)], w=WT)
    n = "MIC2N"   # U3.20 -> B y26.35 east (F-hop over the SPK_N lane) -> C32
    wire(brd, n, [(17.85, 23.8), (18.7, 23.8), (18.7, 26.0)], w=WT)
    via(brd, n, (18.7, 26.35), size=0.5)
    wire(brd, n, [(18.7, 26.35), (23.65, 26.35)], layer="B.Cu", w=WS)
    via(brd, n, (23.65, 26.35), size=0.5)
    wire(brd, n, [(23.65, 26.35), (26.1, 26.35)], w=WS)   # F hop over SPK_N/B
    via(brd, n, (26.1, 26.35), size=0.5)
    wire(brd, n, [(26.1, 26.35), (52.6, 26.35), (52.6, 52.2)],
         layer="B.Cu", w=WS)
    via(brd, n, (52.6, 52.2), size=0.5)
    wire(brd, n, [(52.6, 52.2), (55.3, 52.2), (55.3, 55.45),
                  (56.27, 55.45)], w=WS)


def _spk_paen(brd, p):
    """Speaker pair to the JST; PA_EN drop."""
    n = "SPK_P"
    wire(brd, n, [(29.91, 34.47), (30.55, 34.47), (30.55, 33.4)], w=WP)
    via(brd, n, (30.55, 33.4), size=0.6)
    wire(brd, n, [(30.55, 33.4), (30.55, 17.4), (11.5, 17.4), (10.0, 15.9),
                  (10.0, 8.0)], layer="B.Cu", w=WP)
    n = "SPK_N"
    wire(brd, n, [(26.09, 34.47), (25.4, 34.47), (24.9, 33.9)], w=WP)
    via(brd, n, (24.9, 33.9), size=0.6)
    wire(brd, n, [(24.9, 33.9), (24.9, 16.9), (13.4, 16.9), (12.0, 15.5),
                  (12.0, 8.0)], layer="B.Cu", w=WP)
    n = "PA_EN"
    wire(brd, n, [(31.82, 45.0), (31.82, 43.9), (31.5, 43.9),
                  (31.5, 37.68)], w=WS)                   # -> R7.1
    via(brd, n, (30.7, 39.5), size=0.5)
    wire(brd, n, [(31.5, 39.5), (30.7, 39.5)], w=WS)
    wire(brd, n, [(30.7, 39.5), (30.7, 28.2), (28.63, 28.2)],
         layer="B.Cu", w=WS)
    via(brd, n, (28.63, 28.2), size=0.5)
    wire(brd, n, [(28.63, 28.2), (28.63, 29.53)], w=WS)   # U4.3
