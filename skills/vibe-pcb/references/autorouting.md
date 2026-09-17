# Autorouting with freerouting (the headless detour for ③-routing)

Placement is judgment work the model does in the visual loop; **routing is a solved problem
you hand to freerouting**. This is the validated, fully-headless recipe — and the gotchas
that the one-line "freerouting runs headless" claim hides. Validated on a XIAO module-carrier
(5 nets, 2 layer, flush module + belly keep-out): the autorouted board matched the
hand-routed one exactly — **DRC 0/0/0, 0 unconnected, belly PASS, power 0.4 / signal 0.3 mm**.
Re-validated end to end on that board with **2.3.0 + JDK 25**: 18 tracks, 0 vias, power 400 /
signal 300 µm, **0 DRC errors · 0 unconnected · belly PASS** (the one warning is a cosmetic
`silk_edge_clearance`), and nothing appeared in the Dock for the length of the run.

Since **2.3.0** freerouting also ships agent-facing front ends (REST API, MCP server, A2A
card). They route the *same board with the same engine* — see
"[Three ways to drive it](#three-ways-to-drive-it--and-which-one-is-the-artifact)" for what
each is actually good for, and why the CLI stays the one that produces the artifact.

## The pipeline

```
gen_pcb.py STAGE=place     placement + nets + outline, NO copper
  -> export_dsn.py         + belly track/via keepout, export Specctra .dsn, inject per-net widths
  -> freerouting 2.x       headless:  java -jar freerouting.jar --gui.enabled=false -de in.dsn -do out.ses
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
FREEROUTING_JAR=/path/freerouting-2.3.0.jar JAVA=/path/jdk-25/bin/java \
  BELLY_BOX="94,91,115,109" scripts/autoroute.sh <proj>

# extra router settings go through FR_ARGS (see the settings table below):
FR_ARGS="-mp 20 --router.copper_to_edge_clearance_um=300" scripts/autoroute.sh <proj>
```

## Three ways to drive it — and which one is the artifact

freerouting 2.3.0 exposes the same router through four front ends. Measured on one board,
one jar: **the CLI, the local REST API and the local MCP server produced a byte-identical
`.ses`.** The interface is a UX choice, not a quality choice.

| Front end | How | Good for | Not for |
|---|---|---|---|
| **CLI** (`-de/-do`) | `java -jar fr.jar --gui.enabled=false -de b.dsn -do b.ses` | **the pipeline** — one deterministic call inside `autoroute.sh`; reproducible on any machine from committed sources | conversation |
| **Local REST API** | `--api_server.enabled=true` → `127.0.0.1:37864` | long boards you want to watch: job control, SSE progress/partial-output streams, `GET /jobs/{id}/drc` | anything you need reproducible without a running daemon |
| **Local MCP** | `--mcp_server.enabled=true --mcp_server.stdio=true` | *you*, at the keyboard: "try 30 passes, no optimizer" on an already-exported `.dsn` and compare | producing the committed artifact |
| **Public API / NPX bridge** | `npx -y @freerouting/freerouting-mcp-server` + `FREEROUTING_API_KEY` | a machine with no JRE | **any board you don't want published** — see below |

**MCP hands the model the router, not the pipeline.** This is the thing to internalize before
wiring it up. A `.dsn` routed straight through MCP skips every step `autoroute.sh` performs
around freerouting: the belly track/via keep-out injection, the power/signal net-class width
split, the GND *solid* pour on import, the silk→fab fix, and the DRC/belly gates. What comes
back is copper with none of the constraints this skill exists to enforce. So:

- **Production route → `autoroute.sh`.** It is the only path that carries the constraints, and
  its output is regenerable from committed sources.
- **Exploration → MCP, on the `.dsn` that `export_dsn.py` already produced**
  (`autoroute-work/<proj>.dsn` — it already carries the keep-out and the width classes). Then
  feed the settings that won back into `autoroute.sh` via `FR_ARGS`, so the improvement lands
  in the reproducible path instead of in a chat log.
- **The accepted artifact is still `routing.ses` committed beside the generator**, replayed by
  `pcblib.route.apply_ses`. An MCP session is never the artifact.

**Privacy: the public API and the NPX bridge upload your board.** The bridge is a thin
forwarder to `api.freerouting.app`; the `.dsn` — your full placement, net map and outline —
leaves the machine to a third-party server. For anything unpublished use the **local** jar
(Option B below): with `--api_server.enabled=true` and `mcp_server.target_api_base_url`
pointing at `127.0.0.1`, no board data leaves the host. If you do use the public API, its key
is a **secret** — gitignored file + a `.example`, per the repo rule, never in a committed
`.mcp.json`.

### Local MCP server for Claude Code

Needs **2.3.0+** (2.2.x parses `--mcp_server.*` as an unknown property and carries on without
a server). Project-scoped `.mcp.json` — keep it out of git if the jar path is personal:

```json
{
  "mcpServers": {
    "freerouting": {
      "command": "java",
      "args": [
        "-jar", "/absolute/path/freerouting-2.3.0.jar",
        "--gui.enabled=false", "-da",
        "--api_server.enabled=true", "--api_server.authentication.enabled=false",
        "--mcp_server.enabled=true", "--mcp_server.authentication.enabled=false",
        "--mcp_server.stdio=true"
      ]
    }
  }
}
```

The MCP server is a bridge in front of the local REST API — `--api_server.enabled=true` is
required, and `mcp_server.target_api_base_url` (default `http://127.0.0.1:37864`) must point
at the REST server, not at an MCP route. 27 tools are exposed; the routing loop is
`create_session` → `enqueue_job` → `upload_job_input_from_local_file` → (`update_job_settings`)
→ `start_job` → poll `get_job_details` (2–5 s) → `download_job_output_to_local_file`. Use the
`*_local_file` pair — they read and write disk in-memory, so a 50 k `.dsn` never enters the
context window as base64.

## Gotchas (each one cost real time — this is why the section exists)

1. **kicad-cli has no Specctra.** `kicad-cli pcb export` has no `dsn`; `pcb import` only takes
   Eagle/Altium/etc. The only headless path is the **bundled pcbnew Python**:
   `pcbnew.ExportSpecctraDSN(board, f)` and `pcbnew.ImportSpecctraSES(board, f)` (KiCad 10).
   That is what keeps the whole loop GUI-free and inside the generator flow.

2. **`--gui.enabled=false` is the headless switch — the display trap was a 1.9.0 problem.**
   Both 1.9.0 and 2.x take the same `-de/-do` batch flags, but they differ in what they need
   around them:
   - **2.x + `--gui.enabled=false`: genuinely headless.** Verified to route and save with
     `-Djava.awt.headless=true` *forced* — AWT is never touched, so it runs on a no-display CI
     box. **2.2.4+ is compiled for Java 25** (class-file 69) and dies on JDK 24 with
     `UnsupportedClassVersionError`; on macOS `brew install openjdk@25` is the least-friction
     source (validated 25.0.3). Pin the **versioned** `openjdk@25` formula, not the bare
     `openjdk` (tracks latest GA); the Homebrew `temurin` *cask* needs sudo (fails
     non-interactively).
   - **1.9.0 — runs on JDK 11+, but needs a *display session*.** Its batch path still inits AWT
     (`MainApplication` touches `getScreenSize()`), so it throws `HeadlessException` **only when
     you force `-Djava.awt.headless=true`** — so do NOT pass that flag, and don't pass
     `--gui.enabled=…` either (the unified settings framework is 2.0+). Run it **plain** on a
     machine with a logged-in desktop. This is the path that shipped a real Rev B carrier on
     JDK 24.
   - **Rule of thumb:** use **2.3.x + JDK 25 + `--gui.enabled=false`** everywhere; keep 1.9.0
     only as the fallback for a host stuck on an old JDK. `autoroute.sh` detects the jar's major
     version and adds the flag only when it's ≥ 2.

3. **`--gui.enabled=false` is not enough on macOS — it still grabs the Dock and your
   focus.** With that flag alone the JVM registers as a **`type="Foreground"`** app called
   "Freerouting" (`lsappinfo list`): an icon lands in the Dock and the window server pulls focus
   mid-route, which is intolerable when a route runs for minutes while you work. The cure is a
   **JVM** flag, not a freerouting flag, and the two differ per version:
   - **2.x — `-Djava.awt.headless=true`.** Verified: the process registers **no app at all**, and
     the CLI, the REST server and MCP all still work. This is the one that matters.
   - **1.9.0 — `-Dapple.awt.UIElement=true`.** It cannot take forced headless (gotcha 2:
     `HeadlessException`, no `.ses` written), but UIElement demotes it to `type="UIElement"` —
     an accessory app with no Dock icon and no focus steal — and it still routes.
   - `-Dapple.awt.UIElement=true` **alone** on 2.x is the weaker fix: still registered, just
     demoted. `autoroute.sh` picks the right pair from the detected version; `JAVA_OPTS`
     overrides it.

4. **An unknown `--setting` is a WARNING, not an error.** A typo, or a setting from a newer
   release, logs `Unknown settings property: …` / `Failed to apply CLI router setting: …` and
   the run continues **with the default** — you get a silently unconstrained route that looks
   like a success. `autoroute.sh` greps the captured log for both strings and fails. When you
   add a setting, read the log, don't just read the exit code.

5. **The release notes' `--router.copperToEdgeClearanceUm` does not work.** CLI settings resolve
   by the field's *serialized* (snake_case) name, so the working form is
   **`--router.copper_to_edge_clearance_um=400`** (same for `hole_clearance_um`,
   `neck_width_um`). The camelCase form from the 2.3.0 notes hits gotcha 4 and is dropped.
   This setting matters here: **KiCad's DSN export omits copper-to-edge clearance**, so the
   router will happily lay copper onto the outline and KiCad DRC flags it after import — set it
   explicitly when your board has a tight edge.

6. **`-drc <file>` is a DRC-*only* mode — it does not route.** With `-de in.dsn -do out.ses -drc
   r.json`, freerouting loads the DSN, writes a KiCad-schema DRC report **of the unrouted
   input**, and exits; no `.ses` is written. To get both, either run twice, or use the REST/MCP
   path where `GET /jobs/{id}/drc` after a completed job reports the **routed** board. Either
   way this is a convenience signal, not a gate — `pcb_check.sh` on the imported board is.

7. **`-help` under-reports the CLI.** It lists ~10 flags and omits `-drc`, `-inc`, `-da` and the
   entire `--setting=value` surface. `docs/command_line_arguments.md` in the freerouting repo is
   the real list. (`-inc <net classes>` was a no-op on both 2.2.4 and 2.3.0 in our test — verify
   it on your jar before relying on it, and see gotcha 12 for why you don't want it for GND.)

8. **freerouting's own "unrouted connections" and violation counts LIE on a castellated
   land — KiCad's DRC is the gate.** On the XIAO carrier the router ended with *"4 unrouted
   and 84 violations"* and printed a scary block:
   ```
   Net 'SDA' (1 unrouted connection):
       - A1-5@2  ->  A1-5@1
   ```
   `A1-5@2 → A1-5@1` is **the same pad**. KiCad's Specctra export emits one DSN pin per pad
   *instance*, so a module land whose pad number repeats (castellated pads exist on F.Cu, on
   B.Cu, and in the half-hole) becomes `A1-5 A1-5@1 A1-5@2 A1-5@3` in the net — four points
   freerouting believes it must wire together, and whose overlapping copper it then scores as
   clearance violations. On import KiCad knows they are one pad: **0 unconnected, 0 DRC
   errors**. So read the router's summary as advisory only; `pcb_check.sh` / the DRC report is
   what accepts the board. (If the unrouted list names *different* pads, that's a real failure.)

9. **`autoroute.sh` regenerates the PCB only — never the schematic.** The DSN is exported from
   the placed `.kicad_pcb` and never reads the schematic, so a `gen_sch.py` call here is pure
   side effect. It used to be one, and on a project that **commits** its `.kicad_*` (against
   this skill's convention) the schematic regen also rewrote `.kicad_pro` and dropped 332 lines
   of board design settings — net classes and DRC rules — out of a clean checkout. ERC owns the
   schematic; it regenerates it in `pcb_check.sh`, where that is the point.

10. **freerouting saves the `.ses` LATE.** It logs `session completed` ~10–15 s **before** it
   actually writes the output file. Run java in the **foreground** (the process stays alive
   until the save) or poll for the file — never read the `.ses` the instant you see
   "completed", or you'll import an empty board.

11. **The belly keep-out must be a REAL keepout for the router.** `gen_pcb.py` P6 only does
   `SetDoNotAllowZoneFills(True)` — enough to hold the GND *pour* out of the belly, but the
   autorouter will happily run F.Cu and drop vias there. For the DSN you must also:
   ```python
   z.SetDoNotAllowTracks(True)
   z.SetDoNotAllowVias(True)
   ```
   so the exported DSN carries a true track + via keepout. (`belly_check.py` is still the
   final mechanical gate.) A blunter instrument for the same intent:
   **`--router.layers.routable=false,true`** routes the whole board on B.Cu only (verified —
   every wire came back on `B.Cu`). Useful for a single-sided carrier; too blunt when you need
   F.Cu everywhere *except* under the module.

12. **A GND pour over routed GND trips `[starved_thermal]`.** freerouting routes GND as
   copper; if the pour then connects the same pads with the default THERMAL relief, KiCad
   flags incomplete thermals. Pour GND with **solid** connection so it merges with the
   routed copper:
   ```python
   z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
   ```
   (On a small board, do NOT instead drop GND from the routing — via `-inc GND` or otherwise —
   and rely on the pour alone: signal traces that wrap a connector can fence the pour into
   islands and leave a GND pad unconnected. On a DENSE board that trade flips — a netted GND
   makes the router wire ground pads together through a connector's pad column, which is
   worse — so you drop GND *and* deal with the islands this warning correctly predicts. See
   "Freerouting at scale" below, and `scripts/zone_islands.py` for finding them.)

13. **Per-net widths.** The exported DSN uses one default class width. Split it into
    power/signal classes (post-process the DSN text) so the router matches `gen_pcb.py`'s
    `NET_W` (e.g. power 0.4 mm / signal 0.3 mm) — see `export_dsn.py`.

14. **MCP tool arguments are not flat.** The tools that mirror a REST endpoint take the HTTP
    shape — `{"path": {"jobId": "…"}, "body": {…}}` — while the local-file helpers
    (`upload_job_input_from_local_file`, `download_job_output_to_local_file`) take flat
    arguments. Upstream `docs/API/MCP.md` shows `update_job_settings` as flat
    `{"jobId": …, "settings": {…}}`; the real schema is `{"path": {"jobId": …}, "body":
    {"maxPasses": 5}}` (and the body keys are camelCase, unlike the REST doc's `max_passes`).
    Read `tools/list` rather than the prose. Every tool result is an envelope —
    `{"status": 200, "contentType": …, "body": {…}}` — so unwrap `body` before reading `id`.

15. **The MCP *HTTP* transport still needs a profile header even with auth off.** With
    `--mcp_server.authentication.enabled=false`, `POST /v1/mcp` without
    `Freerouting-Profile-ID` returns `-32602 Authentication failed`, and `tools/list` then
    reports **0 tools** — which reads like an empty server rather than a rejected caller. The
    **stdio** transport supplies the identity itself from `freerouting.json`, which is one more
    reason it's the right transport for Claude Code. Note `--mcp_server.stdio=true` must be a
    **CLI arg** (or `FREEROUTING__MCP_SERVER__STDIO=true`) — setting it in `freerouting.json`
    is ignored, because the stdout redirect has to happen before logging starts.

16. **The jar phones home for a version check on every run** (`New version available: v2.3.0`).
    `-da` disables *analytics*, not that check. Harmless, but don't mistake it for the router
    reaching the network with your board — and on an air-gapped host expect the delay.

## Freerouting at scale: the locked skeleton

The gotchas above were learned on a 5-net carrier. On a denser board (30
parts, 19 nets, a rotated USB-C whose pad column interleaves both differential
pairs) freerouting still routes — but only if you stop treating it as a
one-shot oracle. Worked reference: [`examples/mic-macropad`](../../../examples/mic-macropad).

**Pre-place and LOCK everything that must hold across runs.** `SetLocked(True)`
on a track or via exports as Specctra `(type fix)`, and freerouting honours it:
it routes around the copper instead of ripping it up. Without locking, its
optimizer moved a pre-placed CC line into a shield pad. So the shape that works
is: the generator emits placement + pours + a **skeleton** (power tree, the
connector fanout, GND stubs, stitching vias), and the router only fills in leaf
signals — the ones it cannot get wrong.

**Freerouting is nondeterministic — the accepted `.ses` is an INPUT.** Two runs
of the same DSN leave different nets unrouted and fence off different pour
pockets. Chasing those differences with hand-added vias never converges. Commit
the session that passed the gate and replay it by default; re-route only
deliberately (`FRESH=1` in the example's `route_fr.sh`).

**`-mt 1`.** freerouting's own log says it: *"Multi-threaded route optimization
is broken and it is known to generate clearance violations."* Observed on a
27-part board: the multi-threaded optimization stage took the router's own
violation count from 16 to **17** (it optimised the board worse), while the
single-threaded run held at 16. Now the default in
[`autoroute.sh`](../scripts/autoroute.sh).

**On a dense board, do not let the router see GND.** Gotcha 5 above warns
against dropping GND from routing, and it is right about the consequence — the
pour fences into islands. But the DSN has no plane concept, so on a board with
a 16-pad connector a netted GND makes freerouting *wire ground pads together
straight through the connector column*, which is worse. What works on both
counts: export a **GND-less variant** (strip the net from GND *pads* only),
keep the locked GND stubs and stitching vias so the router still sees them as
obstacles, and replay the session onto the real board where the pours carry
ground. Then fix the islands the warning predicts — with
[`zone_islands.py`](../scripts/zone_islands.py), not by guessing.

**Netless vias vanish from the DSN.** A via with no net is simply not exported
(measured), so it stops being an obstacle and the router happily crosses it.
Vias you place as obstacles must keep their net.

**Per-net widths: a netclass beats a text rewrite.** `export_dsn.py` splits the
class by post-processing the DSN text, which works but is regex-fragile. KiCad
netclasses ride into the export natively — set them on the board and the widths
are simply right:

```python
ds = board.GetDesignSettings()
pwr = pcbnew.NETCLASS("PWR"); pwr.SetTrackWidth(pcbnew.FromMM(0.5))
ds.m_NetSettings.SetNetclass("PWR", pwr)
for n in ("VBUS", "V3V3"):
    ds.m_NetSettings.SetNetclassPatternAssignment(n, "PWR")
```

Without any class, the router uses its own minimum: 22 `track_width`
violations on a board whose power was supposed to be 0.5 mm.

**Do not attribute a fix to your last edit while the router is in the loop.**
Freerouting's nondeterminism makes the obvious inference unsafe: change one
thing, re-route, see the count drop, conclude the change did it. Twice that
inference was wrong here — once about a zone-layer call and once about island
removal (`pcbnew.ZONE()` already defaults to `ISLAND_REMOVAL_MODE_ALWAYS`;
setting it was a no-op). Verify a mechanism against a *minimal* board, not
against a full re-route.

## Reading a "Zone <-> Zone" unconnected item

DRC reports a fenced-off pour as one line that points at the board corner:

```
Zone [GND] on B.Cu, priority 0  <->  Zone [GND] on F.Cu, priority 0
```

That can mean a pocket with nothing tying it down, or an **enclave** — a
B-layer pocket plus an F-layer pocket plus the via joining them, connected to
each other and to nothing else. [`scripts/zone_islands.py`](../scripts/zone_islands.py)
prints every island with the pads and vias of that net inside it, so the fix is
a coordinate you can read off rather than a guess:

```bash
zone_islands.py board.kicad_pcb --net GND --max-mm 70 --strict
# F.Cu GND island x[  6.0, 18.6] y[  2.1,  9.0]  12.6 x  6.9 mm  pads 0 vias 0  << ORPHAN
```

Two pcbnew traps it exists to route around, both measured on KiCad 10.0.3:
`ZONE.GetLayerName()` returns `"F.Cu"` for a B.Cu zone (`GetLayer()` and
`GetLayerSet()` are both correct — only the *name* lies), and
`GetFilledPolysList()` takes a layer, so passing the wrong one means analysing
a fill that isn't there. A diagnostic dump using the name accessor is how one
afternoon went into "fixing" a zone-layer bug that did not exist.

## When to autoroute vs hand-route with `trk`

- **Autoroute** when there is more than a handful of nets, or when hand-coordinates would be
  brittle. freerouting is the same engine tscircuit's cloud uses; it routed the reference
  board in ~0.3 s and kept all under-belly copper on the back layer with 0 vias.
- **Hand-route with `trk`** for a trivial board, or when no JRE is available — and document
  it. Either way the model only ever **reads the render to accept/reject**; it never
  hand-places copper blind.

## Settings worth knowing (all `--name=value`, all silently ignored if misspelled — gotcha 4)

| Setting / flag | Effect |
|---|---|
| `--gui.enabled=false` | headless; required for CLI/API/MCP on 2.x |
| `-mp <n>` / `-mt <n>` | max autorouter passes / optimizer threads (`-mt 0` disables optimization) |
| `--router.copper_to_edge_clearance_um=<µm>` | board-edge clearance KiCad's DSN export leaves out |
| `--router.layers.routable=false,true` | per-layer routability, top→bottom (bottom-only routing) |
| `--router.via_costs=<n>` | raise to push the router toward fewer vias |
| `-da` | disable analytics |
| `--user_data_path=<dir>` | where `freerouting.json` + `freerouting.log` live (keep it out of the project) |
| `--api_server.enabled=true` `--api_server.authentication.enabled=false` | local REST on `127.0.0.1:37864` (+ Swagger UI at `/swagger-ui`) |
| `--mcp_server.enabled=true` `--mcp_server.stdio=true` | local MCP over stdio (2.3.0+) |

## Tooling (not vendored)

- freerouting jar — <https://github.com/freerouting/freerouting/releases> (2.3.0 = the MCP/A2A
  release; `freerouting-<ver>.jar`, ~63 MB)
- a JDK 25 — `brew install openjdk@25` (macOS), or a Temurin tarball <https://adoptium.net>
- upstream docs worth reading before trusting a flag: `docs/command_line_arguments.md`,
  `docs/API/API_v1.md`, `docs/API/MCP.md` (all in the freerouting repo)
