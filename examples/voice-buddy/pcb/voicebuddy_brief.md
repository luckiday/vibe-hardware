# voice-buddy carrier — PCB spec / brief

## 0. Overview
A xiaozhi-style AI-speaker carrier: ESP32-S3-WROOM-1-N16R8 + ES8311 (mono DAC →
NS4150B → 4 Ω/3 W rear speaker) + ES7210 (2 analog MEMS mics + amp echo
reference for AEC) + SSD1306 OLED on a socket + 3 buttons + WS2812. 70 × 70 mm,
4-layer, USB-C 5 V powered. Front (F) faces the enclosure front panel; the two
mics are on B, listening through PCB port holes.

Stackup note: started 2-layer but the dual-codec bus (I2S ×5 + I2C) plus the
analog mic nets do not fit — freerouting stalled at 58 unrouted, and adding two
layers alone did NOT help (still 58): the true bottleneck is fanning out the
0.4 mm-pitch QFN codecs, which needs 0.15 mm track/clearance, not more layers.
Now 4-layer (all signal) + 0.15/0.15 rules; GND poured F+B.

Reference design lineage: `78/xiaozhi-esp32` `lichuang-dev` board (MIT), minus
its PCA9557 expander (PA_EN is a direct GPIO) and with the OLED sharing the
codec I²C bus.

## 1. Why this board is light
One rail conversion (5 V → 3.3 V LDO), no battery, no RF beyond the module,
audio is all chip-level I²S/I²C. The only fine-pitch parts are the two 0.4 mm
QFN codecs.

## 2. Net map — THE single source of truth
The machine-readable net map is `parts.yaml` (both generators derive from it)
plus `pinmap.yaml` (signal ↔ GPIO, cross-checked against the firmware header by
plm_check). Chip pin tables came from datasheet research; **pin-by-pin
verification status is tracked in §10** — do not order boards before closing it.

Key GPIO plan (see pinmap.yaml for the full table): I²C SDA/SCL = 1/2 (ES8311
0x18, ES7210 0x41, SSD1306 0x3C); duplex I²S MCLK/BCLK/WS/DOUT/DIN =
38/14/13/45/12; PA_EN = 10; BOOT/VOL+/VOL− = 0/40/39; WS2812 = 48; native USB =
19/20.

## 3. Power — how the board comes up
USB-C VBUS (CC 5.1 k pulldowns → 5 V sink) → C1 bulk → AMS1117-3.3 (U5) →
+3V3 (module, codecs digital, OLED, WS2812) → FB1 → +3V3A (codec analog).
NS4150B runs from +5V directly (C2 bulk at the amp). EN = 10 k + 1 µ RC.
PA_EN has a 100 k pulldown: the amp stays in shutdown until firmware raises it.

## 4. I²C pull-ups
R3/R4 = 4.7 k on SDA/SCL (one pair for the shared bus; the OLED module usually
carries its own — still fine at 400 kHz).

## 5. Decoupling
100 n + bulk per supply pin domain; ES8311 VMID/DACVREF/ADCVREF and ES7210
REFxx/MICBIAS caps per datasheet app notes (values EST — §10).

## 6. Connectors
J1 USB-C 16P (power + native USB), J2 JST-PH-2 speaker, J3 1×4 socket for the
SSD1306 module (GND/VCC/SCL/SDA order — verify against the actual module
before soldering the socket!).

## 7. Enclosure interlock (feeds vibe-cad)
All shared numbers live in `../cad/constraints.yaml`: outline 70×70×1.6 r3,
M2.5 holes at (4,4)(66,4)(4,66)(66,66), USB-C on +X at y=12, front windows
(display/mics/buttons/led), rear-firing 40 mm speaker. gen_pcb.py READS that
file and exports `placement.json` as evidence; plm_check compares them.

## 8. On-board layout hard constraints
- Antenna keepout: +Y edge, 6 mm deep, no copper/parts (module excepted) —
  drawn as a rule area from the contract AND gated by `pcblib.gates`.
- Module belly: the WROOM is body-mounted on F; no F.Cu/vias under the body
  (routing uses B.Cu beneath it).
- Mic analog runs (MIC1/2 P/N) keep ≥1 mm from the I²S trunk.
- QFN 0.4 mm fanout: 0.2 mm stubs straight out of the pad row.

## 9. Process & ordering
JLCPCB 4-layer 1.6 mm, min track/clearance 0.15/0.15, min through-drill 0.2 mm
(the WROOM belly-via array), NPTH mount holes — all within JLC standard
capability. `fab_export.sh voicebuddy` builds gerbers/CPL/BOM. LCSC parts are
tagged in parts.yaml (`lcsc:`).

## 10. EST / verify-before-ordering checklist
Unverified numbers that MUST be closed against real datasheets/schematics
before money is spent (datasheet hosts were unreachable from the build
environment; values marked came from indexed summaries):

- [ ] **ES7210 QFN-32 4×4 exposed-pad size** (footprint uses 2.6 mm typ) and
      **pin names 6/7/8 and 23/25** (VDDP/VDDD/GNDD, VDDM/REFQM) — confirm the
      supply/bias mapping in parts.yaml against the mechanical + pin tables.
- [ ] **ES8311 QFN-20 EP size** (KiCad footprint EP 1.65 vs datasheet).
- [ ] **NS4150B pin-1 orientation** (IN−/IN+/CTRL/GND | VO+/VDD/GND/VO−
      assumed) and its ESOP-8 EP dimensions; exact gain (≈15 dB assumed).
- [ ] **MEMS mic variant**: MSM381A3729-family, must be ANALOG and
      BOTTOM-port; land pattern + acoustic hole (0.8 mm assumed) from the
      exact suffix's drawing. Top-port variants of the same body exist.
- [ ] **AEC reference divider** (R8 47 k / R9 4.7 k / C16 1 µ assumed): check
      against the lichuang-dev / Korvo-2 schematic levels into MIC3P.
- [ ] OLED module pin order GND/VCC/SCL/SDA matches the purchased module.
- [ ] ERC on a KiCad ≥ 8 host (`pcb_check.sh` prints PASS* until then).
- [ ] Print §9 gerbers 1:1 and dry-fit the USB-C, speaker JST, OLED socket.
