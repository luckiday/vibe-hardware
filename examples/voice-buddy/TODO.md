# voice-buddy — v2 respin TODO (2026-07-13)

This board was re-architected in one pass to make it routable. Three co-design
moves, all landed in source; the routing loop is close but **not yet DRC-clean,
so no `routing.ses` is committed** — the board currently regenerates as a
fanout-only placement (see below to finish it).

## What changed (the co-design)

1. **Fanout-first routing** (`skills/vibe-pcb`). freerouting 2.2.x deleted its
   own SMD→plane fanout pass, which is exactly what stalled v1. So `gen_pcb.py`
   now pre-fans every GND/+3V3 pad with **locked** stubs+vias (exported to
   Specctra as `(type fix)`), restores the two inner planes (In1=GND, In2=+3V3),
   and `autoroute.sh` runs `-inc power` so the router only sees signals.
   New pcblib primitives: `route.fanout()` (collision-checked, slides vias out
   until they fit), `route.bridge_pads()`, `Board(edge_clearance=)`,
   `Board` min-via rule.
2. **Placement-driven pin-swap** (`pinmap.yaml`). ESP32-S3's GPIO matrix routes
   I2S (MCLK included) + I2C to any pad at audio rates, so the codec bus was
   reassigned to the module pads that physically face the audio cluster. Frees
   the IO45/46/3 straps (v1 abused IO45). Firmware `config.h` + selftest BSP
   kept in lockstep — **plm_check: 12 defines agree**.
3. **One ES8388 replaces ES8311+ES7210** (`parts.yaml`). One 0.45 mm QFN-28
   instead of two 0.4 mm QFNs — the fine-pitch escape problem shrinks by a
   chip. Duplex codec: L-ADC = the single mic, R-ADC = amp echo reference
   (hardware AEC, the xiaozhi `yunliao-s3` pattern; driver = `Es8388AudioCodec`,
   `AUDIO_INPUT_REFERENCE true`). Mic count 2→1 in CAD + constraints.

## Routing status — last run (before finish edits)

`freerouting 2.2.4 -inc power -mp 60` → **36 unrouted → 5 unconnected** after SES
import, DRC tail:

| count | type | nature |
|------:|------|--------|
| 4 | GND zone-internal "unconnected" | cosmetic — vanish on `--refill-zones`/pour rebuild |
| 1 | OUTP unconnected | **fixed in source**: added a locked escape stub off QFN pad 12 |
| 1 | `via_dangling` +3V3A | **fixed in source**: dropped the +3V3A fanout (it has no plane) |
| 1 | `courtyards_overlap` H2↔J1 | **fixed in source**: `usb_c` port center_y 12→13.5 (clears the (66,4) boss) |
| ~42 | silk_over_copper / silk_overlap / silk_edge | cosmetic; needs a silk-declutter pass |

The three "fixed in source" items landed AFTER that run, so they need one more
freerouting pass to confirm 0. **The clearance/short/edge-clearance/hole
violations that plagued v1 are already gone** (0 in the last run) — the fanout +
edge-clearance + J1 rotation fix did their job.

## To finish (next session)

1. **Re-run the loop and accept the session:**
   ```sh
   cd examples/voice-buddy/pcb/kicad
   FREEROUTING_JAR=~/.freerouting/freerouting-2.2.4.jar \
   FR_INC=power POWER_NETS="GND,+3V3" W_SIGNAL=250 CLEARANCE=150 \
   BELLY_BOX="<sheet-frame belly box>" \
   ../../../../skills/vibe-pcb/scripts/autoroute.sh voicebuddy
   # if DRC is 0 err / 0 unconnected (silk aside):
   cp autoroute-work/voicebuddy.ses ../routing.ses   # commit it
   ```
   NB the BELLY_BOX is in KiCad **sheet** frame (origin 100,100; y-down). For
   the WROOM at board (35,57.5) the belly is roughly `126.25,99.75,143.75,125.25`
   — confirm against the placed U1 body before trusting it.
2. **Silk declutter** — the ~42 silk violations are cosmetic but should be
   cleared (move refs to F.Fab where they collide, shrink text). Consider a
   `pcblib` silk-cleanup helper so every board benefits.
3. **Regenerate + commit the routed board** only via `routing.ses` replay — never
   hand-edit `voicebuddy.kicad_pcb` (it's gitignored; regenerates from source).

## Verify-before-ordering (carried over + new)

- [ ] **ES8388 wiring** now that it's the only codec: confirm LOUT1(12)→NS4150
      single-ended coupling (C14 1µ / C15 100n IN+ AC-gnd) against the
      Ai-Thinker ESP32-Audio-Kit schematic; confirm R8/R9 AEC divider level into
      RIN1(23). Register init: `reg 0x2B = 0x80` (ADC+DAC share LRCK).
- [ ] **CE pull** = 10k to GND → I2C 7-bit 0x10 (never drive CE from MCU).
- [ ] Analog MEMS mic: MSM381A3729 family, ANALOG + BOTTOM-port, land + 0.8 mm
      acoustic port from the exact suffix's drawing (top-port variants exist).
- [ ] NS4150B pin-1 orientation + ESOP-8 EP; exact gain.
- [ ] OLED module pin order GND/VCC/SCL/SDA matches the purchased module.
- [ ] Print gerbers 1:1, dry-fit USB-C / speaker JST / OLED socket.
- [ ] ERC on a KiCad ≥ 8 host.

## Deferred (not blockers)

- `plm_check.py` `_port_center` reports a false "usb_c drift" for any +X edge
  connector (measures wall-to-body-center, inherent to receptacle depth). The
  contract IS correct. Fix the checker, don't move the part.
- freerouting **master** has a rewritten fanout pre-pass (unreleased). If it
  matures, `route.fanout()` could become a fallback rather than the primary
  path. A/B against the 1.9.0 jar is a cheap experiment if 2.2.4 ever stalls.
