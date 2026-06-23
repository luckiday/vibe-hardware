# Autorouting with freerouting (the headless detour for ③-routing)

Placement is judgment work the model does in the visual loop; **routing is a solved problem
you hand to freerouting**. This is the validated, fully-headless recipe — and the gotchas
that the one-line "freerouting runs headless" claim hides. Validated on a XIAO module-carrier
(5 nets, 2 layer, flush module + belly keep-out): the autorouted board matched the
hand-routed one exactly — **DRC 0/0/0, 0 unconnected, belly PASS, power 0.4 / signal 0.3 mm**.

## The pipeline

```
gen_pcb.py STAGE=place     placement + nets + outline, NO copper
  -> export_dsn.py         + belly track/via keepout, export Specctra .dsn, inject per-net widths
  -> freerouting 2.2.x     headless:  java -jar freerouting.jar -de in.dsn -do out.ses
  -> import_ses.py         ImportSpecctraSES + GND solid pour + (optional) silk->fab
  -> pcb_check.sh          ERC / DRC / belly  (the same gates as the hand-routed flow)
```

Driver: [`scripts/autoroute.sh <proj>`](../scripts/autoroute.sh). It sits **between P4
(placement gates) and P6 (pour)** of the gated flow — routing is *added* to the gated
pipeline, never a replacement for it. The board the model accepts is still the one that
passes `pcb_check.sh` + `belly_check.py`.

> **The routed board is a SEPARATE artifact (`autoroute-work/<proj>.routed.kicad_pcb`); the
> placement source stays unrouted and regenerable.** This is deliberate: a later `gen_pcb.py`
> (or any regen, e.g. `pcb_check.sh`) can then never wipe your copper. **If you instead choose
> to overwrite the source `<proj>.kicad_pcb` in place** (folding the route back), then the SES
> import must be the **last** step in that file's life — any subsequent regen silently erases
> every track. Either keep the routed copy separate, or treat "route" as terminal; don't regen
> past it.

```bash
# from the project kicad/ dir:
FREEROUTING_JAR=/path/freerouting-2.2.4.jar JAVA=/path/jdk-25/bin/java \
  BELLY_BOX="94,91,115,109" scripts/autoroute.sh <proj>
```

## Gotchas (each one cost real time — this is why the section exists)

1. **kicad-cli has no Specctra.** `kicad-cli pcb export` has no `dsn`; `pcb import` only takes
   Eagle/Altium/etc. The only headless path is the **bundled pcbnew Python**:
   `pcbnew.ExportSpecctraDSN(board, f)` and `pcbnew.ImportSpecctraSES(board, f)` (KiCad 10).
   That is what keeps the whole loop GUI-free and inside the generator flow.

2. **freerouting version ↔ JRE ↔ display — pick by *where* you run.** Both 1.9.0 and 2.x take
   the same `-de in.dsn -do out.ses` batch flags (`autoroute.sh`'s driver line works with either
   jar — only `FREEROUTING_JAR` changes); they differ in the display + JDK they need.
   - **1.9.0 — runs on JDK 11+, but needs a *display session*.** Its batch path still inits AWT
     (`MainApplication` touches `getScreenSize()`), so it throws `HeadlessException` **only when
     you force `-Djava.awt.headless=true`** — so do NOT pass that flag. Run it **plain** on a
     machine with a logged-in desktop (macOS / X11) and `-de/-do` routes fine. This is the path
     that shipped a real Rev B carrier **on JDK 24** — least-friction, and it sidesteps the
     JDK-25 hunt entirely. It will **not** work on a truly headless CI box (no display) — there,
     use 2.x.
   - **2.x — genuinely headless (no display), but needs a newer JDK.** `-de/-do` works on a
     no-display CI box. **2.2.4 is compiled for Java 25** (class-file 69), so it needs a JDK 25 —
     it dies on JDK 24 with `UnsupportedClassVersionError`. A no-sudo Temurin `tar.gz` extract
     works; the Homebrew `temurin` *cask* needs sudo (fails non-interactively), and the `openjdk`
     *formula* currently only ships JDK 24 (class-file 68 < the 69 the 2.2.4 jar needs).
   - **Rule of thumb:** on a workstation with a display, **1.9.0 plain** (any JDK 11+) is the
     least-friction route; for unattended CI, **2.x + JDK 25**. The earlier "1.9.0 is unusable,
     use 2.x" was over-stated — it's unusable *headless*, not unusable.

3. **freerouting saves the `.ses` LATE.** It logs `session completed` ~10–15 s **before** it
   actually writes the output file. Run java in the **foreground** (the process stays alive
   until the save) or poll for the file — never read the `.ses` the instant you see
   "completed", or you'll import an empty board.

4. **The belly keep-out must be a REAL keepout for the router.** `gen_pcb.py` P6 only does
   `SetDoNotAllowZoneFills(True)` — enough to hold the GND *pour* out of the belly, but the
   autorouter will happily run F.Cu and drop vias there. For the DSN you must also:
   ```python
   z.SetDoNotAllowTracks(True)
   z.SetDoNotAllowVias(True)
   ```
   so the exported DSN carries a true track + via keepout. (`belly_check.py` is still the
   final mechanical gate.)

5. **A GND pour over routed GND trips `[starved_thermal]`.** freerouting routes GND as
   copper; if the pour then connects the same pads with the default THERMAL relief, KiCad
   flags incomplete thermals. Pour GND with **solid** connection so it merges with the
   routed copper:
   ```python
   z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
   ```
   (Do NOT instead drop GND from the routing and rely on the pour alone: signal traces that
   wrap a connector can fence the pour into islands and leave a GND pad unconnected.)

6. **Per-net widths.** The exported DSN uses one default class width. Split it into
   power/signal classes (post-process the DSN text) so the router matches `gen_pcb.py`'s
   `NET_W` (e.g. power 0.4 mm / signal 0.3 mm) — see `export_dsn.py`.

## When to autoroute vs hand-route with `trk`

- **Autoroute** when there is more than a handful of nets, or when hand-coordinates would be
  brittle. freerouting is the same engine tscircuit's cloud uses; it routed the reference
  board in ~0.3 s and kept all under-belly copper on the back layer with 0 vias.
- **Hand-route with `trk`** for a trivial board, or when no JRE is available — and document
  it. Either way the model only ever **reads the render to accept/reject**; it never
  hand-places copper blind.

## Tooling (not vendored)

- freerouting jar — <https://github.com/freerouting/freerouting/releases>
- a JDK 25 (Temurin tarball) — <https://adoptium.net>
