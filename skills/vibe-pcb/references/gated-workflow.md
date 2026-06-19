# The gated workflow (schematic → fab), and how each gate is enforced

A board moves through fixed **stages**, each with a **gate** that must pass before the next.
The generators emit the design in this order (`gen_pcb.py` phases P1–P8 map to these), and the
scripts mechanize the gates so "looks done" can't pass for "is done."

| # | Stage | Gate (pass =) | Enforced by |
|---|---|---|---|
| 1 | **Schematic, by block** | organized by function (power / MCU / interface / peripheral) — **not a pile** | `gen_sch.py` block frames + cluster grid; read the PDF |
| 2 | **Annotation** | refdes **unique, no `U?`/`R?`** left | generator assigns explicit refs (placeholders impossible) |
| 3 | **ERC** | **no floating input · no power conflict · every rail has a driver/PWR_FLAG** | `kicad-cli sch erc` → 0 errors; know the warning classes |
| 4 | **Netlist + footprints** | every part has a footprint; standard parts **IPC-7351**; sch↔pcb consistent | std lib for passives; custom lands flagged **EST**; `cross_analysis` |
| 5 | **Place** | decoupling hugs the power pin · xtal by the MCU · connectors at the edge · heat spread | `gen_pcb.py` P2 clusters; courtyard + cluster-box no-overlap gate |
| 6 | **Route** | **power widened · critical nets first · continuous return · antenna keep-out** | P5 net-class widths; P6 GND pour + belly/antenna rule-area |
| 7 | **DRC** | **0 violations / 0 unconnected** (zones filled) | `pcb_check.sh` → `kicad-cli pcb drc --refill-zones` + `belly_check.py` |
| 8 | **Fab + review** | gerber/BOM/CPL out; design reviewed; physical-verify checklist | `fab_export.sh`; `REVIEW.md`; kicad-happy cross/EMC |

## Notes that bite

- **Gate 3 — drivers.** GND/main rails as power symbols are `power_in`; they need a `power_out`
  pin (regulator/MCU) **or a `PWR_FLAG`** on the net, else ERC says *power input not driven*.
  Derived rails kept as net labels don't trigger this.
- **Gate 4 — IPC-7351 is for *standard* parts.** A custom module/connector land (a castellated
  XIAO footprint, a breakout landing) is **not** IPC-7351 by definition — mark it **EST** and
  put it on the brief's verify-against-datasheet list; don't claim IPC compliance for it.
- **Gate 6 — return path on 2 layers.** Add a **GND pour** (both layers) for a continuous return;
  it auto-clears around traces, so a DRC-clean trace layout stays clean once poured. **Zones save
  UNFILLED** from headless pcbnew (`ZONE_FILLER.Fill()` segfaults) — fill at check/fab time with
  `--refill-zones`. **Antenna keep-out**: an on-board-antenna module needs copper kept out under
  the antenna (a rule-area); an *external*-antenna module (e.g. XIAO ESP32-S3's U.FL) moves that
  concern off-board — state which applies, don't silently skip it.
- **Gate 6 — power widening is per-net-class, not heroics.** Widen power vs signal (e.g. 0.4 vs
  0.3 mm); width sets ampacity, not corner angle. On a low-current sensor carrier this is margin,
  not necessity — but the gate still wants the *intent* in the source (`NET_W`).
- **Gate 7 — DRC must run on FILLED zones.** Unfilled-zone DRC silently skips pour clearance.
  `pcb_check.sh` passes `--refill-zones` so the gate checks the real copper.
- **Don't claim a gate you didn't run.** If `cross_analysis`/EMC (gate 4/8) weren't run this
  session, say so; if the fab pack predates the last regen, it's **stale** — regenerate.

## Honest scorecard (do this, don't self-congratulate)

For each gate: **✅ met / ⚠️ partial / ❌ gap / N/A (with reason)**, backed by the command output —
not a vibe. A small board legitimately has N/A gates (no xtal, external antenna, low current); say
*why* it's N/A rather than quietly skipping. The point of the gates is to make the gaps visible.
