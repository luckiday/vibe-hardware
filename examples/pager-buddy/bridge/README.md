# bridge — Mac → pager-buddy status bridge

Streams **Claude Code session status** from your Mac to the pager. This is the
"Claude Code hook bridge (a later stage)" the [display design](../design/README.md)
points at — the missing piece between a running agent and the device screen.

Modeled on [open-vibe-island](../reference/open-vibe-island/) (gitignored study
clone). Its pipeline is `agent hook → CLI (stdin) → socket → app → HTTP/SSE → device`;
this is the **Level-0** slice of that — no Swift app yet, just hooks + HTTP.

## How it works

```
Claude Code  ──hook event (JSON on stdin)──▶  claude_pager_hook.py
                                                 │  updates ~/.pager-buddy/state.json
                                                 │  (file-backed session registry)
                                                 ▼
                                        HTTP POST /v1/snapshot
                                                 │  full snapshot per protocol.yaml
                                                 ▼
                                   pager_stub.py   ←—— stands in for the ESP32 device
                                   (renders an ASCII 135×240 screen)
```

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

./service.sh install          # auto-start on login + restart on crash (macOS LaunchAgent)
./service.sh status           # is it running?
./service.sh logs             # tail the log
./service.sh uninstall        # remove the agent
```

`run.sh` is best while iterating; `service.sh install` is the "always-on desk
pager" setup. Both free port 8787 first and serve the design UI via `--ui`.
Override the port with `PAGER_BUDDY_PORT` (and re-point the hook with
`install_hooks.py install --url http://127.0.0.1:<port>/v1/snapshot`).

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
| [protocol.yaml](protocol.yaml) | **The contract.** Wire format = the design mock's session shape. Versioned. |
| [claude_pager_hook.py](claude_pager_hook.py) | Hook command: stdin event → registry → POST snapshot. `--demo` to self-drive. |
| [pager_stub.py](pager_stub.py) | Fake device: `POST/GET /v1/snapshot`, renders the screen. ESP32 replaces it. |
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
