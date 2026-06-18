# CAD Viewer — update + use (the latest)

The Viewer is a vendored skill (from `earthtojake/text-to-cad`), not in this repo.
It is how you review `.step` / `.stl` / `.glb` / `.gcode` interactively. These are
the things that bit us; `scripts/cad_viewer.sh` automates the launch around them.

## Install / update

```bash
npx skills install earthtojake/text-to-cad
```

Drops the whole bundle (`cad`, `cad-viewer`, `implicit-cad`, `sdf`, `step-parts`,
`gcode`, `bambu-labs`, `urdf`, …) into the **gitignored** `.agents/skills/`
(universal install) and symlinks it for Claude Code. Re-run it to pull the latest;
it overwrites in place. The pins live in `skills-lock.json` (see the repo's
"In-repo skills convention"). Nothing here is committed — it's vendored per-clone.

## Launch (use the script)

```bash
skills/text-to-cad/scripts/cad_viewer.sh <abs-models-dir> [port]
```

It locates the installed skill, frees the port, picks the right npm script, and
launches the server (foreground — start it in the background). Then open:

```
http://127.0.0.1:<port>/?file=<name>.step        # file= is RELATIVE to <models-dir>
```

The raw command it runs (for reference / non-mac):

```bash
cd <skill>/cad-viewer          # .agents/skills/cad-viewer
npm --prefix scripts/viewer run start -- --host 127.0.0.1 --dir <abs-models-dir> \
    --port 4178 --shutdown-after 12h
```

## The three gotchas (and why the script exists)

### 1. `.step` renders ONLY via a hidden GLB sidecar
The Viewer has **no CAD kernel** — it cannot tessellate STEP itself. It looks for a
hidden `.<basename>.step.glb` next to the file. If it's missing you get
**"Generated GLB is missing"**. So every exporter must emit it:

```python
from build123d import export_step, export_stl, export_gltf
def export_part(name, part, stl=True):
    step = OUT / f"{name}.step"
    export_step(part, str(step))
    if stl:
        export_stl(part, str(OUT / f"{name}.stl"))
    export_gltf(part, str(OUT / f".{step.name}.glb"), binary=True)   # <- the sidecar
```

`.stl`, `.glb`, `.gcode` render natively (no sidecar). Gitignore the sidecars:
`models/.*.glb`.

### 2. Fixed port + a lingering server → `EADDRINUSE`
The server binds a **fixed** port (default **4178**) and does **not** auto-increment;
a previous session's `--shutdown-after 12h` server is often still listening, so a
fresh launch crashes with `Error: listen EADDRINUSE 127.0.0.1:4178`. Free it first:

```bash
old=$(lsof -nP -tiTCP:4178 -sTCP:LISTEN); [ -n "$old" ] && kill $old
```

`lsof` can miss it without `-nP`; if a `curl http://127.0.0.1:4178/` returns 200 but
`lsof` shows nothing, retry with `lsof -nP -iTCP:4178 -sTCP:LISTEN` (it's the old
server, kill its PID). Always pass `--shutdown-after 12h` so forgotten servers
self-clean.

### 3. The launcher script was renamed
Older bundles exposed `npm run agent:start` (a launcher that owned port selection +
server reuse). Newer bundles replaced it with plain `start` / `serve`
(`node backend/server.mjs`) which takes `--host --dir --port --shutdown-after`
directly. **The SKILL.md text can lag the package.json** — it may still say
`agent:start` while only `start` exists, so a copy-pasted command fails with
`npm error Missing script: "agent:start"`. Detect it:

```bash
script=start
grep -q '"agent:start"' scripts/viewer/package.json && script=agent:start
```

## After a model rebuild

You do **not** need to restart the server — it serves the `models/` dir live. Just
re-run `build_all.py` (regenerates the STEP + GLB sidecars) and **refresh the
browser**. Only restart the server to point at a *different* directory or to pick up
a Viewer update.
