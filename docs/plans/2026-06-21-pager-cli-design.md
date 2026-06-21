# Design — a unified `pager` CLI for the pager-buddy Mac bridge

*2026-06-21 · examples/pager-buddy/bridge*

## Problem

The bridge works but its surface is a pile of loose scripts (`install.sh`, `run.sh`,
`service.sh`, `install_hooks.py`, `ble_push.py`, `pager_stub.py`, `pager_settings.py`).
A user has to know which script does what, how they relate, and how to start it at
login. There's no single "is it up, and what's the device doing?" view.

## Goal

One friendly command — `pager` — with subcommands, modeled on **`tailscale`**: *one
command brings it up, one takes it down, one shows status.* Boot-at-login is a flag, not
a separate concept. Stdlib Python only (no new pip deps beyond `bleak`); the existing
Python workers are unchanged and the CLI orchestrates them.

## Command surface

```
pager up [--boot] [--port N]   start in background (hub + BLE relay); --boot = also at login
pager down                     stop now
pager status [--watch]         colored status block; --watch repaints ~every 2s
pager logs [-f]                tail the bridge log
pager run                      FOREGROUND (today's run.sh) — live [ble] lines, Ctrl-C to stop

pager install [--gate …] [--port N]   venv + bleak + register Claude hooks (today's install.sh)
pager uninstall                       reverse everything
pager boot on|off                     toggle auto-start at login (launchd RunAtLoad)
pager hooks on|off|status             Claude Code hooks (wraps install_hooks.py)
pager audio [on|off] [--volume N]     alert audio (wraps pager_settings.py)
pager doctor                          diagnose: bleak? device advertising? hub? hooks? BT perm?
```

## Architecture

`pager` is a stdlib-Python (argparse) orchestrator. The real workers stay as-is:
`pager_stub.py` (hub), `ble_push.py` (relay), `install_hooks.py`, `pager_settings.py`.
`run.sh` remains **the runtime** — the foreground hub+relay loop — and is what both
`pager run` (interactive) and the launchd agent exec.

**Background runtime = the launchd agent, always.** Routing every background run through
launchd keeps one honest answer to "is it running?" plus crash-restart and logging.
Rejected alternative: a detached/nohup background mode — it splits the runtime state.

- **launchd plist:** `ProgramArguments = bash run.sh`; `KeepAlive = {SuccessfulExit:
  false}` (restart on crash, *not* on a clean stop); `RunAtLoad = <boot pref>`.
- `up` → write plist (boot pref), bootstrap (load), kickstart (start now).
- `down` → `launchctl kill SIGTERM` → `run.sh` exits **0** on signal, so KeepAlive does
  not restart it. A crash (non-zero exit) *does* restart.
- `boot on|off` → rewrite plist `RunAtLoad` + reload; does not change running-now state.
- This requires `run.sh` to exit 0 on SIGTERM/SIGINT and propagate a non-zero hub crash.

`pager run` / `pager install` shell out to `run.sh` / `install.sh`. The old `service.sh`
becomes a 2-line shim to `pager boot`; `install.sh`/`run.sh` stay (called by `pager`).

## `pager status`

Reads `/healthz` + `/v1/snapshot` from the hub, the launchd job state, and the tail of
the log for the link line; prints a tailscale-style block (ANSI: green ●, dim ○, red ●):

```
pager-buddy
  hub      ● running    http://127.0.0.1:8787   (pid 12345)
  relay    ● connected  pg-3A7F   MTU 185   · last push 3s ago
  device   2 sessions   ▸ fix auth bug · working 3s
  boot     ○ off        → pager boot on
  hooks    ● 4 events   PreToolUse, Stop, …
  audio    ● on  · vol 60
```

Nothing running → every row is `○ stopped` with the next command; never an error.

## Error handling & testing

- Fail soft, always print the next step (`up` without bleak → "run `pager install`").
- No hardware needed for CLI tests: `pager status` parses `/healthz`; `boot on/off`
  round-trips the plist; `hooks status` reflects `install_hooks.py`; `doctor` runs clean.
  A small `smoke.sh` covers these; `--demo` is untouched.

## Out of scope (later)

Full-screen TUI dashboard (`pager top`); two-way approve/answer; Bonjour discovery.
