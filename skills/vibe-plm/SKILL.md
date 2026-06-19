---
name: vibe-plm
description: >-
  The integration / product-lifecycle layer ABOVE vibe-firmware · vibe-pcb · vibe-cad:
  turn a small embedded product into a single PRODUCT MANIFEST plus the INTERFACE
  CONTRACTS the three domains must agree on, keep them in sync across a revision, and
  gate a release/fab on all three being green at once. Use when STARTING a new product
  (scaffold the firmware/pcb/cad dirs + manifest), CHANGING something that crosses a
  domain boundary (a pin move, a board-outline change, a shared fit number), CUTTING a
  revision, or wiring up a fab/release. Key facts this skill encodes: the product is one
  `product.yaml` — identity + per-domain status + the interface contracts — and it is the
  single source of truth (the architecture's "fit numbers + net map" box made concrete);
  there are exactly three contracts — `pinmap.yaml` (pcb -> firmware), `board.step`
  (pcb -> cad, a GENERATED artifact), `constraints.yaml` (cad <-> pcb, the shared fit
  numbers) — direction is producer -> consumer; `revision` (vYYYY-MM-DD) bumps on ANY
  cross-domain change so all three move together; the release gate is cross-domain (pcb
  ERC/DRC 0/0/0 + belly, cad 0 mm^3 fit, firmware hardware-tested) and must be green at
  ONE revision before fab. Critically, vibe-plm is self-contained: its scripts read the
  contract FILES and never import/call another skill's code — cross-skill coupling is
  DATA (the manifest + the contracts) and PROSE hand-offs, never a runtime dependency.
  Validate with `scripts/plm_check.py` (manifest sanity + interface-drift gate). Worked
  reference: `examples/pager-buddy/product.yaml`. Siblings: vibe-firmware/pcb/cad.
---

# Vibe-PLM — the product manifest + cross-domain integration

A small embedded product is **three things that must agree** (see
[`docs/architecture.md`](../../docs/architecture.md)): firmware, PCB, enclosure. Each
has its own skill and its own self-contained loop. **vibe-plm is the thin layer that
holds them together** — it owns the *contracts between* the domains, not the work
inside any one of them. It answers: *what is this product, at which revision, and do
the three halves still agree?*

> This is **not** a fourth design tool. It writes **no** KiCad, **no** build123d, **no**
> firmware. It owns one manifest + three interface files and a check that they're
> consistent. The actual work stays in `vibe-firmware` / `vibe-pcb` / `vibe-cad`.

## The product is ONE manifest

The source of truth is **`product.yaml`** at the product root. It holds product
identity, the **revision**, the per-domain status, and — the important part — the
**interface contracts**. Everything cross-cutting lives here so a beginner changes one
file and knows what else must move. See `examples/pager-buddy/product.yaml` and
`references/manifest-and-interfaces.md` for the full schema.

```yaml
product: pager-buddy
revision: v2026-06-19            # vYYYY-MM-DD — bump on ANY cross-domain change
firmware: { dir: firmware/, status: stub }
pcb:      { dir: pcb/, status: stub }
cad:      { dir: cad/, status: stub }
interfaces:
  pinmap: pcb/pinmap.yaml                       # pcb  -> firmware
  board_step: pcb/board.step                    # pcb  -> cad  (generated artifact)
  enclosure_constraints: cad/constraints.yaml   # cad <-> pcb
```

## The three interface contracts (the only cross-skill coupling allowed)

The repo rule is that **a skill's code never calls another skill's code**. So the
domains are coupled only through **data files** — these three contracts. Each has a
**producer** and a **consumer**; the producer regenerates it, the consumer reads it.

| Contract | Direction | File | What it carries | Kind |
|---|---|---|---|---|
| **pinmap** | pcb → firmware | `pcb/pinmap.yaml` | the net map: pin ↔ signal ↔ bus/address | source (must exist) |
| **board_step** | pcb → cad | `pcb/board.step` | the board 3D for the 0 mm³ fit-check | **artifact** (generated; warn until built) |
| **enclosure_constraints** | cad ↔ pcb | `cad/constraints.yaml` | the shared fit numbers (outline, holes, stack, ports, windows) | source (must exist) |

`pinmap` is the *net map* the architecture doc calls shared between firmware ↔ PCB.
`enclosure_constraints` is the *fit numbers* shared between PCB ↔ enclosure. `board_step`
is the one **generated** artifact: it appears only after the pcb 3D/fab step runs, so
`plm_check` warns (not fails) when it's missing.

## The loop

```
define product ─► set contracts ─► each domain builds to its contract ─► plm_check ─► bump revision ─► release gate
 product.yaml      pinmap.yaml       (vibe-firmware/pcb/cad,             interface     vYYYY-MM-DD     all 3 green
 (identity +       board.step         each its OWN loop + gate)          drift = 0     on any          at ONE rev
  domains)         constraints.yaml                                                    cross change    ─► fab
```

1. **Define the product** — write/scaffold `product.yaml` (identity, the three domain
   dirs, the interface paths). For a new product this is the scaffold step.
2. **Set the contracts** — fill the *source* contracts: `pinmap.yaml` (the net map) and
   `constraints.yaml` (the fit numbers). These are the numbers both sides will read.
3. **Each domain builds to its contract** — hand off to the sibling skills. `vibe-pcb`
   generates the board *from* the net map + fit numbers and exports `board.step`;
   `vibe-firmware` generates its config-as-code *from* the pinmap; `vibe-cad` models the
   shell *from* the fit numbers and fit-checks against `board.step`. Each runs its **own**
   gate (this skill does not run them — it points at them).
4. **plm_check** — `scripts/plm_check.py product.yaml`: manifest sane, every domain dir
   present, every contract resolves (source missing = error; artifact missing = warn),
   revision well-formed. Drive interface drift to **0**.
5. **Bump the revision** — any change that crosses a boundary (a pin, the outline, a
   shared number) bumps `revision` so the three halves are versioned **together**.
6. **Release gate** — before fab/OTA, all three domain gates must be green **at one
   revision**: pcb ERC/DRC 0/0/0 + belly, cad 0 mm³ fit, firmware hardware-tested. See
   `references/release-checklist.md`.

## Run it

```bash
# from the product dir (the one with product.yaml):
python3 ../../skills/vibe-plm/scripts/plm_check.py product.yaml
#   → manifest sanity + interface-drift gate (errors fail, artifact-pending warns)
# (no special toolchain — plain python3, stdlib only; uses PyYAML if present)
```

`plm_check.py` is **self-contained**: it parses the manifest and stats the contract
files; it never imports or shells out to `pcb_check.sh` / `check_fit.py` / a firmware
build. The domains' own scripts run their own gates; this one only proves the *contracts
between them* are consistent.

## Scaffolding a new product

```
examples/<product>/            (or hardware/<product>/)
  product.yaml                 # the manifest — START HERE (this skill owns it)
  firmware/  README.md         # vibe-firmware sources    (consumes pinmap.yaml)
  pcb/       README.md         # vibe-pcb sources         (produces pinmap.yaml + board.step)
             pinmap.yaml       #   contract: pcb -> firmware
  cad/       README.md         # vibe-cad sources         (produces constraints.yaml)
             constraints.yaml  #   contract: cad <-> pcb
```

Copy `examples/pager-buddy/` as the template, then point each domain dir at its sibling
skill. (A one-command scaffolder is a TODO — see below.)

## Hard rules

- **The manifest is the single source of truth.** Product identity, revision, and the
  contract paths live in `product.yaml` — not duplicated into each domain.
- **Cross-skill coupling is DATA + PROSE, never runtime.** Domains agree through the
  three contract files; vibe-plm's scripts never import another skill's code (mirrors
  the repo-wide rule). A "hand off to vibe-pcb" pointer is prose, not a function call.
- **One number, one place.** A shared value (a pin, an outline dim, a stack height)
  lives in exactly one contract; the other side *reads* it. Don't fork it.
- **Bump `revision` on any cross-domain change** (vYYYY-MM-DD) so the three halves stay
  versioned together; a release pins all three to one revision.
- **Never fab/release on a partial gate.** All three domain gates green at one revision
  first; firmware needs a real-hardware test, not just a clean compile.

## When to reach for this vs others

- The **board** → `vibe-pcb`. The **enclosure** → `vibe-cad`. The **firmware** →
  `vibe-firmware`. Each is its own loop and gate.
- **Tying them together** — the manifest, the contracts, the revision, the release gate,
  scaffolding a new product → **here**.
- The agent-status **hook→bridge→device** glue (a runtime feature of an example, not a
  cross-domain hardware contract) is a different concern — the roadmap's `vibe-glue` idea.
  It's a *runtime/service wire contract*, though, so the same discipline applies; the
  hard-won lessons (versioned wire format, wire-shape == mock data, device- vs
  link-owned fields, in-contract freshness/TTL, transport-independence) are captured in
  [`references/manifest-and-interfaces.md`](references/manifest-and-interfaces.md)
  ("Beyond the three"), worked in `examples/pager-buddy/bridge/protocol.yaml`.

## TODO (fill in as products teach you)

- [ ] `scripts/plm_init.py` — scaffold `product.yaml` + the three dirs + contract stubs
      in one command (the roadmap's "new-project scaffolds the three dirs").
- [ ] Deepen `plm_check.py` cross-checks: pinmap signals ↔ the firmware config-as-code,
      `constraints.yaml` outline ↔ the pcb board outline (read both files, compare).
- [ ] A `references/revisioning.md` — when a change is "cross-domain", changelog format.

## Keeping this current (living doc)

vibe-plm exists to **compound** the integration lessons — the cross-domain bugs that
only show up where two skills meet (a pin that drifted, an outline that didn't, a fab
ordered on a stale revision). When a real build teaches one, fold it back here
(SKILL.md / `references/` / `scripts/`) and commit it with the work. Same for the
sibling skills.
