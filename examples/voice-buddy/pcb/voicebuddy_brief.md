# voice-buddy carrier — PCB spec / brief

> **v2 (revision v2026-07-13).** One ES8388 duplex codec replaced the v1
> ES8311+ES7210 pair; GPIO map is placement-driven. Routing status and the
> remaining finish steps live in `../TODO.md`. `parts.yaml` is the net source
> of truth; this brief is the rationale.

## 0. Overview
A xiaozhi-style AI-speaker carrier: ESP32-S3-WROOM-1-N16R8 + **ES8388** (one
duplex codec: mono DAC → NS4150B → 4 Ω/3 W rear speaker; stereo ADC used as
mic + echo reference) + one analog MEMS mic + SSD1306 OLED on a socket + 3
buttons + WS2812. 70 × 70 mm, 4-layer, USB-C 5 V powered. Front (F) faces the
enclosure front panel; the mic is on B, listening through a PCB port hole.

Stackup: **4-layer, F/B signal + In1 = GND plane + In2 = +3V3 plane**, 0.15 mm
track/clearance. Routed **fanout-first**: freerouting 2.2.x deleted its SMD→plane
fanout pass (PR #605), so `gen_pcb.py` pre-fans every GND/+3V3 pad with locked
stubs+vias (Specctra `(type fix)`) and `autoroute.sh` runs `-inc power` — the
router only ever handles signals. The single 0.45 mm-pitch QFN escapes cleanly
at 0.15 mm; a 0.3 mm copper-edge-clearance rule is what lets the USB-C pads route
at the wall.

Reference design lineage: the xiaozhi `78/xiaozhi-esp32` **yunliao-s3** board
(MIT) — ES8388 with `AUDIO_INPUT_REFERENCE true` for hardware AEC. Codec facts
verified 2026-07-13 against the ES8388 datasheet Rev 5.0 + Olimex ESP32-ADF and
Ai-Thinker ESP32-A1S / ESP32-Audio-Kit schematics.

## 1. Why this board is light
One rail conversion (5 V → 3.3 V LDO), no battery, no RF beyond the module,
audio is all chip-level I²S/I²C. The only fine-pitch part is the single 0.45 mm
QFN-28 codec.

## 2. Net map — THE single source of truth
The machine-readable net map is `parts.yaml` (both generators derive from it)
plus `pinmap.yaml` (signal ↔ GPIO, cross-checked against the firmware header by
plm_check). ES8388 pin table came from datasheet Rev 5.0; verification record is
in §10.

Key GPIO plan (see pinmap.yaml — **placement-driven**, ES8388 I2C 0x10):
I²C SDA/SCL = 11/12; duplex I²S MCLK/BCLK/WS/DOUT/DIN = 17/18/8/9/10; PA_EN = 13;
BOOT/VOL−/VOL+ = 0/21/47; WS2812 = 38; native USB = 19/20. The audio pins were
chosen to face the codec cluster (lower-left) through the ESP32-S3 GPIO matrix,
which carries I2S (MCLK included) + I2C to any pad at audio rates — this frees
the IO45/46/3 strapping pins that v1 was forced to use.

## 3. Power — how the board comes up
USB-C VBUS (CC 5.1 k pulldowns → 5 V sink) → C1 bulk → AMS1117-3.3 (U5) →
+3V3 (module, codec DVDD/PVDD, OLED, WS2812) → FB1 → +3V3A (codec AVDD+HPVDD,
mic supply). NS4150B runs from +5V directly (C2 bulk at the amp). EN = 10 k + 1 µ
RC. PA_EN has a 100 k pulldown: the amp stays in shutdown until firmware raises it.

## 4. I²C pull-ups
R3/R4 = 4.7 k on SDA/SCL (one pair for the shared bus; the OLED module usually
carries its own — still fine at 400 kHz). ES8388 CE = 10 k to GND → 7-bit 0x10
(CE must be strapped, never MCU-driven, per the ES8388 user guide).

## 5. Decoupling & bias
Per Everest app notes + the Olimex/A1S schematics: DVDD/PVDD 100 n; AVDD/HPVDD
100 n + 10 µ on the filtered rail (they share +3V3A; a series ferrite stands in
for the datasheet's 10 Ω AVDD–HPVDD resistor). VMID / VREF / ADCVREF each 10 µF
(Olimex values). No MICBIAS pin exists on the ES8388 — the analog MEMS mic is
powered from +3V3A through a 1 k + 10 µ filter (the A1S MBIAS pattern) with its
OUT AC-coupled (100 n) into LIN1.

## 6. Audio path
DAC LOUT1 (pin 12) → 1 µF (C14) → NS4150B IN−; IN+ AC-grounded via 100 n (C15) —
the Ai-Thinker ESP32-Audio-Kit single-ended wiring. Get L+R mono digitally
(ES8388 reg 29 mono bit) rather than shorting outputs. AEC reference: LOUT1 →
R8/R9 divider → 1 µF (C16) → RIN1 (pin 23), so the right ADC channel captures the
amp drive for echo cancellation.

## 7. Connectors
J1 USB-C 16P (power + native USB), J2 JST-PH-2 speaker, J3 1×4 socket for the
SSD1306 module (GND/VCC/SCL/SDA order — verify against the actual module before
soldering the socket!).

## 8. Enclosure interlock (feeds vibe-cad)
All shared numbers live in `../cad/constraints.yaml`: outline 70×70×1.6 r3,
M2.5 holes at (4,4)(66,4)(4,66)(66,66), USB-C on +X at y=13.5, front windows
(display/mic/buttons/led — single mic now), rear-firing 40 mm speaker.
gen_pcb.py READS that file and exports `placement.json` as evidence; plm_check
compares them.

## 9. On-board layout hard constraints
- Antenna keepout: +Y edge, 6 mm deep, no copper/parts (module excepted) —
  drawn as a rule area from the contract AND gated by `pcblib.gates`.
- Module belly: the WROOM is body-mounted on F; no F.Cu/vias under the body
  (routing uses B.Cu beneath it).
- QFN 0.45 mm fanout: locked 0.2 mm stubs + 0.4/0.2 vias out of the pad row to
  the inner planes (`route.fanout`, collision-checked).
- USB-C J1: pin row **inboard** (rot=90); copper-edge clearance 0.3 mm.

## 10. Process, ordering & verify-before-ordering
JLCPCB 4-layer 1.6 mm, min track/clearance 0.15/0.15, min drill 0.2 mm, no
via-in-pad (not standard on 4-layer, and not needed — the QFN is perimeter-only).
`fab_export.sh voicebuddy` builds gerbers/CPL/BOM. LCSC parts tagged in
parts.yaml (`lcsc:`).

The UNVERIFIED-before-money checklist and the routing finish steps are tracked in
**`../TODO.md`** (ES8388 audio wiring against the Audio-Kit schematic, CE strap,
MEMS mic variant, NS4150B orientation, OLED pin order, ERC on KiCad ≥ 8, 1:1
gerber dry-fit, and the `routing.ses` acceptance).
