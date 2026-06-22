# product.yaml schema + the interface contracts

The full reference for the manifest `vibe-plm` owns and the three files the domains
agree through. The worked example is
[`examples/pager-buddy/product.yaml`](../../../examples/pager-buddy/product.yaml).

## `product.yaml`

```yaml
product: <slug>                  # required — product identity (kebab-case)
revision: vYYYY-MM-DD            # required — bump on ANY cross-domain change
summary: "one line"             # optional — what it is

# one block per domain; each is a self-contained vibe-* project
firmware:
  dir: firmware/                 # path (relative to product.yaml) — checked to exist
  status: stub                   # stub | wip | clean | released   (informational)
  toolchain: TBD                 # optional — e.g. esp-idf (pinned tag) / platformio
pcb:
  dir: pcb/
  status: stub
  gate: "ERC/DRC 0/0/0 + belly keep-out"   # optional — the domain's own gate, for humans
cad:
  dir: cad/
  status: stub
  gate: "fit-check 0 mm^3"

# the contracts the domains agree on (see below)
interfaces:
  pinmap: pcb/pinmap.yaml
  board_step: pcb/board.step
  enclosure_constraints: cad/constraints.yaml
```

`plm_check.py` requires `product` + `revision`, checks each domain `dir:` exists, and
resolves every `interfaces:` path. `status`/`gate`/`toolchain` are informational (not
gated) — they're the human-readable state of each domain.

## Why these three contracts (and only these)

The repo forbids one skill's *code* from calling another's. So the three domains are
coupled **only through data files**. There are exactly three boundaries in a small
product, so exactly three contracts:

```
        pinmap.yaml                board.step                 constraints.yaml
firmware ◄──────────── pcb ──────────────► cad        pcb ◄──────────────► cad
 (consumer)         (producer)         (consumer)    (consumer)        (producer)
   net map: pins         board 3D for             the shared fit numbers
   & addresses           the 0 mm^3 fit           (outline, holes, stack, ports)
```

### 1. `pinmap` — pcb → firmware  (`pcb/pinmap.yaml`, source)

The **net map** as machine-readable data: the structured form of the PCB brief's §2.
The PCB produces it (it mirrors `gen_sch.py` / the brief); firmware consumes it (its
config-as-code header is generated from / checked against it). A swapped sensor → one
edit here → both the board net and the firmware pin/address move.

Shape (see the pager-buddy stub): `mcu`, a `bus:` block (i2c/spi speeds + addresses),
and a `pins:` list of `{ signal, gpio, dir, net, to, [pull] }`.

### 2. `board_step` — pcb → cad  (`pcb/board.step`, **generated artifact**)

The board's 3D model, the input to `vibe-cad`'s `check_fit.py` (board ↔ shell must be
0 mm³). It is **generated** by the pcb 3D/fab step, so it may not exist yet —
`plm_check` **warns** (does not fail) when an artifact contract is missing. Don't
hand-create it; regenerate it from the board.

### 3. `enclosure_constraints` — cad ↔ pcb  (`cad/constraints.yaml`, source)

The **shared fit numbers**: the structured form of the PCB brief's §7 enclosure
interlock. One set of numbers both the board outline (pcb) and the shell (cad) read —
board L×W×t, mount-hole spacing, standoff/stack height, USB exit, display/button/LED
windows, antenna keep-out. Change a number here and both sides move; that's the whole
point of keeping it in one file.

Shape (see the stub): `board.outline`, `board.mount_holes`, `stack`, `ports`,
`windows`, `keepouts`. A `frame_mapping` block (the PCB↔CAD coordinate transform) is
worth adding when one side renders the other's geometry — e.g. the PCB 3D view loading
the real `cad/tray.step`, or the cad fit-check importing `pcb/board.step`.

> **Consumers include the PCB's own reference 3D models, not just the outline.** The
> standoff / baseplate / enclosure `.step` you `add_model()` into the board's 3D view
> are reference-only — and they must **read these numbers**, never hardcode a copy. A
> magic `STANDOFF_H = 16` that disagrees with `stack.car_bot` makes the part poke
> through the real shell in the codesign view (`tools/codesign-viewer`). That view is
> the cross-check: a visual clash = a real number to reconcile *here*. See `vibe-pcb`
> `references/fab-and-3d.md` → "Drive the reference models from the shared contract".

## Source vs artifact (how `plm_check` treats a contract)

The check classifies a contract by file extension:

- **source** (`.yaml .yml .json .md .toml .csv`) → **must exist** (missing = error).
  These are hand-maintained / committed contracts.
- **artifact** (`.step .stp .glb .stl .gbr .zip .bin .elf .uf2`) → **generated**
  (missing = warning). These are produced by a domain's build/fab step.
- unknown extension → treated as source (must exist) — be explicit, prefer a known ext.

This keeps the gate honest: a not-yet-built `board.step` shouldn't fail integration, but
a missing `pinmap.yaml` (which firmware *needs* to build) should.

## Beyond the three: runtime / service contracts (the vibe-glue concern)

The three contracts above are the **hardware** seams (pins, board 3D, fit numbers). A
product often also has a **runtime** seam: a wire protocol between the device and an
external service — e.g. pager-buddy's Claude-status link
([`examples/pager-buddy/bridge/protocol.yaml`](../../../examples/pager-buddy/bridge/protocol.yaml),
hook → bridge → device). That's adjacent to vibe-plm's core (the roadmap's *vibe-glue*),
**not** a fourth hardware contract — but the same contract discipline applies, and these
lessons (learned wiring it over HTTP, then BLE) generalize:

- **Versioned wire format; one producer, many consumers.** Bump the protocol `version`
  on any breaking change — same rule as a hardware contract's `revision`.
- **Make the wire shape == the design/mock data shape.** When the message is field-for-
  field identical to the UI mock's data, every consumer (firmware, web mock, an ASCII
  stub) renders a received message directly — **no translation layer**.
- **Declare field ownership.** Say which fields are *device-owned* vs *link-provided*:
  battery is device-owned and is **not** on the wire; the clock/time **is** link-provided
  because a clock-less device has no RTC. Ambiguity here causes drift.
- **Put liveness/expiry in the contract, not just code.** Carry a per-item `ts` and a
  TTL; every renderer re-ages + drops stale items **on its own clock** — so a missing
  "end" event or a dropped link can't strand stale state on screen.
- **Keep it transport-independent.** The same JSON rode HTTP (Level-0) then BLE with no
  schema change — declare the transport(s) separately from the message schema, so a
  transport swap isn't a contract break.
- **A forward-on-change relay dedupes on meaningful fields only** — ignore volatile
  derived fields (re-stamped time, recomputed age) or it pushes every tick.

## Keeping a contract in sync

- A contract has **one producer**. Only the producer regenerates it; the consumer reads.
- When a contract changes in a way the other side sees, **bump `revision`** in
  `product.yaml`. That's the signal the consumer must re-pull / rebuild.
- The deeper cross-checks (pinmap signals vs the firmware config; constraints outline vs
  the actual pcb outline) are a `plm_check` TODO — for now keep them aligned by hand and
  cite the contract file from each domain's source (the brief already does this).
