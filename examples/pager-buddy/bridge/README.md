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

## Running the bridge

The bridge must be up to receive hook events. Two ways:

```bash
./run.sh                      # foreground in a terminal tab (Ctrl-C to stop)
                              #   → http://127.0.0.1:8787/ — open it, click Connect
                              #   → also starts the BLE relay (ble_push.py) to the pager

./service.sh install          # auto-start on login + restart on crash (macOS LaunchAgent)
./service.sh status           # is it running?
./service.sh logs             # tail the log
./service.sh uninstall        # remove the agent
```

`run.sh` is best while iterating; `service.sh install` is the "always-on desk
pager" setup. Both free port 8787 first and serve the design UI via `--ui`.
`run.sh` also brings up the **BLE relay** to the device — best-effort: it's skipped
with a note if `bleak` isn't installed (`pip install bleak`), and `PAGER_BUDDY_BLE=0`
disables it (hub only). Override the port with `PAGER_BUDDY_PORT` (and re-point the
hook with `install_hooks.py install --url http://127.0.0.1:<port>/v1/snapshot`).

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
| [protocol.yaml](protocol.yaml) | **The contract.** Wire format + the two transports (HTTP hub, BLE device). Versioned. |
| [claude_pager_hook.py](claude_pager_hook.py) | Hook command: stdin event → registry → POST snapshot. `--demo` to self-drive. |
| [pager_stub.py](pager_stub.py) | The hub: `POST/GET /v1/snapshot`, ASCII screen, serves the web mock (`--ui`). |
| [ble_push.py](ble_push.py) | BLE central: polls the hub, writes framed snapshots **and audio settings** to the device. `pip install bleak`. |
| [pager_settings.py](pager_settings.py) | The **audio settings session**: enable/disable alert audio + set volume (interactive, or `--audio on/off --volume N`). Talks to the hub; the relay forwards to the device. |
| [install_hooks.py](install_hooks.py) | Idempotent install / uninstall / status for `~/.claude/settings.json`. |

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
