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
`windows`, `keepouts`.

## Source vs artifact (how `plm_check` treats a contract)

The check classifies a contract by file extension:

- **source** (`.yaml .yml .json .md .toml .csv`) → **must exist** (missing = error).
  These are hand-maintained / committed contracts.
- **artifact** (`.step .stp .glb .stl .gbr .zip .bin .elf .uf2`) → **generated**
  (missing = warning). These are produced by a domain's build/fab step.
- unknown extension → treated as source (must exist) — be explicit, prefer a known ext.

This keeps the gate honest: a not-yet-built `board.step` shouldn't fail integration, but
a missing `pinmap.yaml` (which firmware *needs* to build) should.

## Keeping a contract in sync

- A contract has **one producer**. Only the producer regenerates it; the consumer reads.
- When a contract changes in a way the other side sees, **bump `revision`** in
  `product.yaml`. That's the signal the consumer must re-pull / rebuild.
- The deeper cross-checks (pinmap signals vs the firmware config; constraints outline vs
  the actual pcb outline) are a `plm_check` TODO — for now keep them aligned by hand and
  cite the contract file from each domain's source (the brief already does this).
