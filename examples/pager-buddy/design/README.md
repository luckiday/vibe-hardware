# pager-buddy — display design (StickC S3, 135×240)

An interactive **web mock** of the device UI, adapting [Vibe Island]'s four functions
(Monitor / Approve / Ask / Jump) onto the M5StickC S3's tiny **135×240** screen, driven
by the device's **two buttons**. It's both a clickable prototype and the **spec** the
firmware `ui_status` component will implement — design the display logic here (fast,
in-browser) before writing any ST7789 C.

[Vibe Island]: https://github.com/ (the macOS agent-session HUD this is modeled on)

## Run it

```bash
open index.html              # opens directly (file://), or:
python3 -m http.server       # then visit the printed URL in this dir
```

No build step. `data.js` holds the sample sessions + the demo scenario; `app.js` is the
state machine; `styles.css` renders the screen at **actual 135×240** inside a device
frame. Use the **Zoom 1×/2×/3×** toggle to inspect (1× = real pixel size).

### Live mode — show real Claude Code status

The same UI can render **live** status from the [bridge](../bridge/) instead of the demo
data. The wire format ([../bridge/protocol.yaml](../bridge/protocol.yaml)) was defined so
a snapshot's `session` objects are exactly what these renderers already draw — `live.js`
just swaps the data behind the screen and re-renders.

```bash
python3 ../bridge/pager_stub.py --ui            # serves THIS mock + the snapshot endpoint
                                                #   → open http://127.0.0.1:8787/
python3 ../bridge/claude_pager_hook.py --demo   # (other terminal) drive a scenario
```

Click **Bridge ▸ Connect** in the panel (or open `…/?live=1`); a new "needs you" flashes
the screen (stands in for the buzz). Point elsewhere with
`?bridge=http://host:port/v1/snapshot`. Offline it falls back to the demo data, and
`▶ Play scenario` still works.

The device deliberately shows **program status + the key selection** — never code or
diffs (a 135px screen is too small to read code; the firmware shows the *decision*, not
the source).

## The 2-button model

| Button | Short press | Long press (≈0.5 s) |
|---|---|---|
| **Side** (KEY2 / GPIO12, "right") | cycle highlight (down, wraps) | — |
| **Front** (KEY1 / GPIO11, "middle blue") | OK / confirm / enter | back / home |

Keyboard in the mock: `↓`/`→`/`j` = scroll · `Enter`/`Space` = OK · `Backspace`/`Esc` =
back · `p` = play scenario. (Same event model the firmware uses: button events → state
transitions.)

## Screens

Color language (status dot): **blue** working · **amber** needs-you (approve) ·
**cyan** asking · **green** done · **red** error.

1. **Idle / glance** — clock, date, battery, "N sessions · M need you", a status face.
   Side or OK → Monitor.
2. **Monitor (list)** — one row per session: dot · name · age, then agent + terminal
   chips + state. Side cycles; OK opens the highlighted session.
3. **Action** (by the session's state):
   - **Approve** — `⚠ Permission`, the tool + file + `+a -d` summary (no code/diff);
     `[Deny] [Allow]` (side switches, OK confirms).
   - **Ask** — `▣ Claude asks`, the question, an options list (side scrolls, OK selects).
   - **Done** — `✓ name`, summary + `files · tests`; `[Jump] [Dismiss]` (OK = Jump).
   - **Working** — live activity lines + a spinner; OK/back returns to the list.

`▶ Play scenario` drives `fix-auth-bug` through working → approve → ask → done, flashing
the screen on each page (stands in for the buzz).

## State → firmware mapping (the spec)

Each screen becomes an **intent verb** on the firmware `ui_status` component (the modular
pattern in [`skills/vibe-firmware/references/esp-idf-structure.md`](../../../skills/vibe-firmware/references/esp-idf-structure.md);
vocabulary echoes voicestick's `ui_status.h` + our `main.c` `APP_UI_STATE_*`). `main`
owns *what* state to show; the component owns *how* to render it:

| Screen | Firmware verb (proposed) |
|---|---|
| Idle | `ui_set_idle(clock, battery, counts)` |
| Monitor list | `ui_set_list(sessions[])` |
| Approve | `ui_set_approve(tool, file, diff, +a/-d)` |
| Ask | `ui_set_ask(agent, question, opts[])` |
| Done | `ui_set_done(name, summary, files, tests)` |
| Working | `ui_set_working(name, activity[])` |
| Battery (status bar) | `ui_set_battery(level, charging, usb)` |

**Power / battery** (learned from voicestick's `ui_status_set_battery`): a battery icon
(shell + proportional fill + tip) + `NN%` in the status bar, with a **3-state fill
color** — `≤20%` **red**, else `charging \|\| usb` **blue**, else **green** (low-red wins
even while charging). On the device this refreshes on a timer **and** the PMIC IRQ; in the
mock, toggle it with the **Power** buttons or `?batt=15&chg=1`. The board side exposes
`board_battery_level/charging/usb_powered()` (the BSP owns the PMIC).

Button events map to `app_event_t` (e.g. `APP_EVT_SCROLL`, `APP_EVT_OK`,
`APP_EVT_BACK`) consumed by the app task's state machine. Sessions/states arrive from the
Claude Code hook [bridge](../bridge/) — live via `live.js` (see **Live mode** above), or
mocked in `data.js` when offline.

## Scope

Front-end + an opt-in read-only live feed (`live.js` polling the bridge snapshot). No
firmware code; no two-way actions yet (approve/answer from the device is Level-1 — the
protocol reserves `POST /v1/resolution`). Portrait 135×240. The firmware `ui_status`
implementation is the next step, guided by this mock.
