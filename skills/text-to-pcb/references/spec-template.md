# PCB spec / brief — fill-in template

This is the **text** in "text-to-pcb": the human-controlled source of truth. Claude
Code turns it into the generators. Keep it in `<proj>_brief.md`. Modeled on the
worked `examples/your-board/xiao-carrier_brief.md` — read that
for a fully-filled example.

A carrier board is "light": the module (XIAO, dev kit) already integrates
power/USB/reset/regulator/antenna, so the carrier only does the **bridge** (module
↔ sensor wiring + I²C pull-up positions + local decoupling). State that up front so
you don't redraw a power supply you don't need.

---

## 0. Overview
- Board outline: **L × W × thickness**, corner radius, layer count, fab process /
  finish. Note any growth from a previous rev and *why* (e.g. "+3 mm on −X for two
  M2 mount-hole margins").
- Region plan in one line: where the module solders, where the connector/passives
  sit, what must stay clear.
- **Hard isolation constraints** here (the belly keep-out, antenna keep-out) — see §8.

## 1. Why this board is light
What the module already provides (don't duplicate) vs what this board adds.

## 2. Net map — THE single source of truth (verify pin-by-pin)
Cite the firmware pin config (file + lines) it must match.

| Net | Module pin | GPIO | → Target pin | Sensor/connector pad | Notes |
|---|---|---|---|---|---|
| 3V3 | 3V3 | — | J1-1 | VIN | supply |
| GND | GND | — | J1-2 | GND | |
| SCL | D5 | GPIO6 | J1-3 | SCL | I²C clock |
| SDA | D4 | GPIO5 | J1-4 | SDA | I²C data |

- Bus speed / address, and any firmware change implied by the chosen module
  (e.g. a swapped sensor → different I²C address).

## 3. Power — how the board comes up
- Source path and the **default solder-jumper state**. Default must be **closed**
  (functional out of fab). List jumpers in a table (name · connects · factory state
  · purpose). Note any dropped supply rail and why (e.g. "+5V removed: breakout is
  3V3-only and the +5V trace ran under the module belly").

## 4. I²C pull-ups (leave-position)
- Values, and **DNP by default** if the module already has pull-ups (photo-verify).
  State when they'd be fitted (a bare sensor with no pull-ups).

## 5. Decoupling (optional, leave-position)
- Bulk + HF caps at the supply pin root; what's populated by default.

## 6. Connector(s)
- Type (THT header / land), pitch, pin order **copied from the sensor's pad order**
  (no crossing), keying (▲ pin-1 + silk line order = anti-mis-assembly).
- Why this connector vs alternatives (height, rigidity, alignment).

## 7. Enclosure interlock (feeds the `text-to-cad` enclosure)
- How the board mounts (mount holes + standoffs), how tall the stack sits, where
  USB exits, FOV/aperture clearances, antenna placement. These numbers become the
  enclosure params on the CAD side — keep them consistent.

## 8. On-board layout hard constraints
- **Belly keep-out**: under a flush-soldered module's body (give the x/y box), **no
  front copper, no vias** — its exposed back-pads short to carrier copper. All
  under-belly traversal on the back layer; front copper + vias in the margins only.
- **Antenna keep-out** (only if using the module's on-board PCB antenna): no copper
  under/around the antenna segment.
- Connector orientation, decoupling-first-then-route, silk content.

## 9. Process & ordering
- Fab process, hand-assembly vs SMT, generic parts, BOM reference.

## 10. EST / verify-before-ordering checklist
The items you must confirm with **photo / calipers / multimeter** on the real
module before committing the order (each is a `- [ ]`):
- module already has I²C pull-ups? (→ DNP yours)
- VIN is direct-3V3 or 5V+LDO?
- sensor header **actual** line order vs assumed
- module land pattern / castellation row pitch vs official footprint
- mount-hole spacing vs the enclosure standoffs
- I²C address vs firmware
- connector pitch / count / pin length (reaches through both boards)
