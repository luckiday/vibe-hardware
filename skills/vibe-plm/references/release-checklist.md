# Cross-domain release gate

A release/fab is the one moment all three domains must be green **at the same
revision**. Each domain runs its **own** gate (with its own skill's scripts — vibe-plm
does not run them); this checklist is the cross-domain wrapper that says "ship it".

Run from the product dir. Pin everything to one `revision:` in `product.yaml`.

## 0. Manifest + contracts consistent

- [ ] `python3 …/skills/vibe-plm/scripts/plm_check.py product.yaml` → **no errors**
      (artifact-pending warnings are OK *until* you need that artifact below).
- [ ] `revision:` is today (or the intended tag) and reflects the latest cross-domain
      change. Every domain below is built against **this** revision.

## 1. PCB gate (vibe-pcb)

- [ ] `scripts/pcb_check.sh <proj>` → ERC clean + DRC **0 errors / 0 unconnected**
      (silk warnings are cosmetic, don't conflate).
- [ ] `BELLY_BOX=… scripts/pcb_check.sh <proj>` → no front copper/vias under a flush
      module's belly.
- [ ] Power is **live out of the fab** (default solder-jumpers closed).
- [ ] `board.step` exported (the `board_step` contract) so cad can fit-check it.
- [ ] Physical-verify-before-ordering checklist walked (pull-ups, VIN, header order,
      land pattern, mount-hole spacing, I²C address).

## 2. CAD gate (vibe-cad)

- [ ] `python check_fit.py` → board ↔ shell interference **0 mm³**, against the
      **current** `board.step`.
- [ ] The shell's cutouts (display window, USB exit, button/LED) match
      `cad/constraints.yaml` — and that file matches the board the pcb actually built.
- [ ] Print orientation + tooling caveats noted; mechanical BOM listed (screws,
      inserts, light pipe, feet).

## 3. Firmware gate (vibe-firmware)

- [ ] Pinned/reproducible build (image tag / locked SDK), not a host toolchain.
- [ ] Pins/bus/addresses match `pcb/pinmap.yaml` (config-as-code in sync).
- [ ] **Real-hardware test** — flashes, runs, no crashloop/heap-leak over a sustained
      run; failure paths exercised (peripheral unplugged, network loss). A clean
      compile is **not** enough.
- [ ] Secrets out of the repo (gitignored creds + a committed `.example`).

## 4. Cut the release

- [ ] All three gates green **at this one revision** — not "pcb from last week".
- [ ] Tag/record the revision; note what changed since the last (changelog).
- [ ] Fab via gerber upload (never an EasyEDA import); print the shell; flash firmware.
- [ ] Only **after** the real-hardware test, trigger any OTA/fleet publish.

## The failure this gate exists to stop

Fabbing the board, *then* finding the shell was modeled to an older outline, or the
firmware pinned to pins the board moved. The fix is cheap and boring: one `revision`,
one `plm_check`, three green gates, in that order. Don't order on a partial gate.
