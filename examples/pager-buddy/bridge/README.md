# bridge — Mac → pager-buddy status bridge

Streams **Claude Code session status** from your Mac to the pager. This is the
"Claude Code hook bridge (a later stage)" the [display design](../design/README.md)
points at — the missing piece between a running agent and the device screen.

Modeled on [open-vibe-island](../reference/open-vibe-island/) (gitignored study
clone) and the [voicestick](../../../docs/references/_clones/voicestick/) BLE
peripheral. The device link is **BLE** (the firmware is a NimBLE GATT server); the
hub + hooks stay on HTTP.

## How it works

```
Claude Code ─hook event (JSON on stdin)─▶ claude_pager_hook.py
                                             │  updates ~/.pager-buddy/state.json
                                             │  (file-backed session registry)
                                             ▼
                                    HTTP POST /v1/snapshot
                                             ▼
                                      pager_stub.py  ── the hub: holds the latest
                                       │  ▲             snapshot; serves the web mock
                              GET poll │  │ render      (and an ASCII stand-in screen)
                                       ▼  │
                                    ble_push.py  ── BLE central
                                             │  writes framed snapshot chunks
                                       BLE write (GATT)
                                             ▼
                                   pager-buddy device  ── NimBLE peripheral
                                   (firmware/components/bridge)
```

The hooks + hub are unchanged; **ble_push.py** is the new leg that relays the hub's
latest snapshot to the device over BLE (it also stands in for the future menubar
app's BLE central). `pager_stub.py` still renders an ASCII screen / serves the web
mock, so you can develop without hardware.

Claude fires a hook on each lifecycle event and pipes a JSON payload to the hook
command's **stdin**. The command maps it into the [protocol](protocol.yaml),
updates a tiny on-disk registry (so each one-shot process can still emit a *full*
snapshot), and POSTs the snapshot to the device. The device is a dumb renderer.

**Hooks fail open**: if the device/stub is down, the hook exits 0 silently and
Claude is unaffected. Nothing is ever written to stdout.

## The `pager` command

One command runs the whole bridge — modeled on `tailscale`: one brings it up, one
takes it down, one shows status. It's a thin stdlib-Python orchestrator over the
pieces below (no extra deps); background runs always go through a macOS LaunchAgent,
so "is it running?" has one honest answer (plus crash-restart + a log file).

```bash
pager up [--boot]       # start hub + BLE relay in the background (--boot = also at login)
pager status [--watch]  # colored status block (hub · relay · device · boot · hooks · audio)
pager down              # stop now
pager run               # foreground instead — live [ble] lines, Ctrl-C to stop

pager install [--gate …] [--port N]   # venv + bleak + register Claude hooks
pager boot on|off                     # toggle auto-start at login
pager hooks on|off|status             # Claude Code hooks
pager audio [on|off] [--volume N]     # alert audio
pager logs [-f]                       # tail the bridge log
pager doctor                          # diagnose the whole chain
```

`pager status` at a glance:

```
pager-buddy
  hub      ● running    http://127.0.0.1:8787   (pid 12345)
  relay    ● connected  pg-3A7F   MTU 185
  device   2 session(s) ▸ fix auth bug · working 3s
  boot     ○ off        → pager boot on
  hooks    ● 9 event(s) PreToolUse, Stop, …
  audio    ● on  · vol 60
```

The sections below document the scripts `pager` wraps (`install.sh`, `run.sh`,
`install_hooks.py`, …) — reach for them directly if you like, or just use `pager`.
Hardware-free CLI checks: `./smoke.sh`.

## Quickstart (no Claude, no hardware)

Two terminals:

```bash
# 1) the fake device — watch the screen here
python3 pager_stub.py

# 2) feed a scripted scenario through the REAL mapping code
python3 claude_pager_hook.py --demo
```

The stub screen walks `fix auth bug` through working → needs-you → asks → done
(plus two background sessions) — the same flow as the design mock's `▶ Play`.

### …in the rich design UI instead of ASCII

`--ui` makes the stub also serve the [design mock](../design/) on the same origin,
so you can watch live status in the real 135×240 device UI:

```bash
python3 pager_stub.py --ui          # → open http://127.0.0.1:8787/  then click "Connect"
python3 claude_pager_hook.py --demo # (other terminal)
```

The design's `live.js` polls `GET /v1/snapshot` and renders it with the same
screens. (Responses send `Access-Control-Allow-Origin: *`, so a UI served
elsewhere can poll too — but `--ui` keeps it same-origin and CORS-free.)

## Install (one command)

```bash
./install.sh                  # venv + bleak, register Claude Code hooks, print next steps
```

That is the whole setup: it creates a self-contained `.venv` with `bleak` (so the BLE
relay works even on a PEP 668 / externally-managed system python), registers the Claude
Code hooks in `~/.claude/settings.json`, and tells you what to do next. Options:

```bash
./install.sh --gate Bash      # scope the device approval gate (default: Bash,Edit,Write,…)
./install.sh --service        # also auto-start the bridge on login (LaunchAgent)
./install.sh --no-hooks       # relay only; don't touch ~/.claude/settings.json
./install.sh --port 8788      # non-default hub port
./install.sh uninstall        # reverse everything: hooks + LaunchAgent + venv
```

Then: flash the device, run `./run.sh` (unless you used `--service`), and restart
Claude Code so it loads the hooks. The steps below are the manual equivalents.

## Running the bridge

The bridge must be up to receive hook events. The simplest path is `pager`:

```bash
pager up          # background (LaunchAgent): hub + BLE relay, restarts on crash
pager status      # is it up? what's the device doing?
pager down        # stop
pager run         # or foreground in a terminal tab (Ctrl-C to stop)
```

`pager up` is the always-on desk-pager setup; `pager run` is best while iterating
(live `[ble]` lines). Under the hood `run.sh` is the runtime both use — it frees the
port, serves the design UI (`--ui`), and brings up the **BLE relay** best-effort
(skipped with a note if `bleak` is missing; `PAGER_BUDDY_BLE=0` = hub only). Override
the port with `pager up --port N` (or `PAGER_BUDDY_PORT`).

`service.sh` is now a deprecated shim to `pager boot` (kept so older docs / muscle
memory keep working); prefer `pager boot on|off` to toggle auto-start at login.

## Use it for real (with your Claude Code)

```bash
python3 pager_stub.py                 # leave running (or point at your device)
python3 install_hooks.py install      # registers hooks in ~/.claude/settings.json
# …restart Claude Code so it reloads settings, then work as usual…

python3 install_hooks.py status       # which events carry our hook
python3 install_hooks.py uninstall    # surgical removal (only hooks we added)
```

`install` backs up `settings.json` → `settings.json.bak` and only ever removes
hooks whose command contains `claude_pager_hook.py`. Point at a real device with
`--url`, e.g. `install_hooks.py install --url http://pager.local/v1/snapshot`.

Config via env (read by the hook): `PAGER_BUDDY_URL`, `PAGER_BUDDY_STATE`,
`PAGER_BUDDY_DEBUG` (logs to stderr).

## Files

| File | Role |
|---|---|
| [pager](pager) | **The entry point.** tailscale-style CLI wrapping everything below: `up`/`down`/`status`/`run`/`install`/`boot`/`hooks`/`audio`/`logs`/`doctor`. Stdlib only. |
| [protocol.yaml](protocol.yaml) | **The contract.** Wire format + the two transports (HTTP hub, BLE device). Versioned. |
| [claude_pager_hook.py](claude_pager_hook.py) | Hook command: stdin event → registry → POST snapshot. `--demo` to self-drive. |
| [pager_stub.py](pager_stub.py) | The hub: `POST/GET /v1/snapshot`, ASCII screen, serves the web mock (`--ui`). |
| [ble_push.py](ble_push.py) | BLE central: polls the hub, writes framed snapshots **and audio settings** to the device. Writes are change-gated (idle = zero BLE traffic) and the hub poll **backs off** when nothing changes (`--idle-interval`, default 10 s; snaps back to `--interval` on the next change). `pip install bleak`. |
| [pager_settings.py](pager_settings.py) | The **audio settings session**: enable/disable alert audio + set volume (interactive, or `--audio on/off --volume N`). Talks to the hub; the relay forwards to the device. |
| [install.sh](install.sh) | **One-command setup**: venv + `bleak`, register hooks, optional LaunchAgent. `uninstall` reverses it. |
| [install_hooks.py](install_hooks.py) | Idempotent install / uninstall / status for `~/.claude/settings.json` (called by `install.sh`). |
| [run.sh](run.sh) · [lib.sh](lib.sh) · [service.sh](service.sh) | Runtime (hub + relay, launchd-friendly), shared shell helpers, and a deprecated `pager boot` shim. |
| [smoke.sh](smoke.sh) | Hardware-free CLI checks (argparse wiring, status/doctor/hooks, plist round-trip) under an isolated `$HOME`. |

## What the device gets

A `snapshot` = `{ clock, date, sessions[] }`, each session
`{ id, name, agent, term, age, state, task, activity[], approve?, ask?, done? }`
where `state ∈ working | waiting | asking | done | error`. Field-for-field the
same object the firmware's `ui_status` verbs already consume. See
[protocol.yaml](protocol.yaml) for the full schema + the Claude-hook→state map.

## Roadmap → Level-1

This slice is intentionally minimal. The robust version (a small menubar app,
following open-vibe-island) adds:

- **Cold-start recovery** — parse `~/.claude/projects/**/<session>.jsonl` on
  launch so sessions already running before the bridge started still appear
  (see `ClaudeTranscriptDiscovery.swift` in the reference clone).
- **Two-way approve/answer** — the device POSTs `/v1/resolution`; the bridge
  blocks the `PermissionRequest` hook and returns the decision (reference:
  `WatchHTTPEndpoint` + `WatchNotificationRelay`). The protocol already reserves
  this endpoint.
- **Discovery + transport for battery** — Bonjour (`_pagerbuddy._tcp`) so the
  device finds the Mac with no hardcoded IP; device **polls on wake** or the Mac
  **pushes to the device's** HTTP server, rather than holding a socket open.

The wire `protocol.yaml` is the stable seam across both levels.
