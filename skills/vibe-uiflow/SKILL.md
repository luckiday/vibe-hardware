---
name: vibe-uiflow
description: >-
  Build a screen-and-input device on UIFlow2 / MicroPython (M5Stack Cardputer, CoreS3,
  StickS3, StampS3, AtomS3, Dial — and non-M5 ESP32-S3 boards) with an AI coding agent
  driving the loop. Use when the device has a small panel and buttons, when a C/ESP-IDF
  build is more ceremony than the job needs, or when you want a change on the screen in
  seconds instead of a flash cycle. Key facts this skill encodes: UIFlow2 firmware is
  PLAIN MICROPYTHON, so `mpremote` is the whole toolchain — there is no official CLI, and
  M5Burner/the Web IDE are not it; build TWO LOOPS, a host simulator that runs the app's
  OWN draw calls against a Pillow stub of `M5.Lcd` (with FONT METRICS DUMPED OFF THE REAL
  DEVICE, so geometry is pixel-exact) and a bounded `selftest.py` that runs on the board
  and PRINTS what a human would otherwise read off the screen; NEVER call an M5 API you
  have not confirmed exists on that firmware (`make probe` first — the top failure mode);
  redraw only what changed and ERASE ONLY THE BOX YOU ARE ABOUT TO PAINT, because clearing
  a region then painting into it IS the flicker, and TEXT is the expensive primitive
  (4 short drawStrings cost more than clearing the whole band); gate it all with a GHOST
  CHECK that drives N live frames with no clearing and diffs against a clean redraw.
  Modules deploy FLAT (there is no /flash/lib). Board differences belong in the Makefile
  (`make BOARD=…` copies one of boards/<board>/x.py under the same name), not in runtime
  `if`s. UIFlow2 also runs on boards M5 never made: flash the StampS3 image (the only bare
  S3 build) and drive an arbitrary SPI panel with `M5.UserDisplay` —
  references/non-m5-boards.md. Companion to `vibe-firmware` (C/ESP-IDF); same philosophy,
  cheaper loop, less control.
---

# UIFlow2 → a device with a screen (agent-driven, seconds per iteration)

> **Companion to [`vibe-firmware`](../vibe-firmware/)**, not a replacement. That skill is
> C/ESP-IDF: layered components, pinned Docker builds, OTA. This one is the same
> philosophy at a different operating point — MicroPython on the M5 stack, where a change
> reaches the screen in seconds and you give up compile-time checking, tight memory
> control and OTA to get it. Pick this for a panel-and-buttons device, a bench
> instrument, a demo, a shape you are still finding. Pick `vibe-firmware` when you need
> determinism, power discipline, or to ship a fleet.

## Why this operating point exists

The expensive step in firmware is not compiling — it is **finding out what the change
did**. Flash, unplug, look, guess: 30–60 seconds with a human in the loop, which means
an agent cannot run it at all. UIFlow2 removes the compile, and the two loops below
remove the human. What is left is an agent that can *see* what it drew.

## The loop

```
        host loop                              device loop
        ─────────                              ───────────
edit ─► render the app's OWN draw calls   edit ─► mpy-cross every module
     ─► PNG per screen state                   ─► upload (flat, to /flash)
     ─► the AGENT LOOKS at the PNGs            ─► run selftest.py ON THE BOARD
     ─► critique ─► edit ─► …                  ─► it PRINTS what a human would
                                                  otherwise read off the screen
   sub-second, no hardware                    ~30 s, proves it on silicon
   geometry · typography · RGB565             dispatch · timing · memory · peripherals
```

```bash
make shots        # host loop: render every screen state, then LOOK at the PNGs
make check        # device loop: compile + upload + selftest on hardware
make probe        # what this firmware actually exposes — before you call it
make run          # run live, tracebacks come back to the terminal
make deploy       # install as main.py, start on power-up
```

**Both loops, always.** The host loop is honest about geometry and typography and lies
about colour, gamma, backlight and refresh. The device loop is honest about everything
the host cannot see and blind to whether the result looks good. Neither judges taste —
that is still you, looking at the panel.

## Structure

One-way imports, a single mutable-state object, and the hardware boundary drawn where
the simulator can stand in for it:

```
conf      constants only — palette, layout tables, key maps      (no state, no imports)
  ^
state     S — every mutable field, in one object
  ^
board     THE ONLY module that knows which machine this is       (see below)
  ^
domain    the beat detector / sequencer / renderer …             (pure where it can be)
  ^
app.py    setup() / loop(), and nothing else
```

- **`app.py` must stay importable.** Everything behind `if __name__ == '__main__':`;
  `selftest.py` and the simulator both import the modules and drive them by hand.
- **Keep the pure logic pure.** A beat detector or a step clock that takes numbers and
  returns numbers can be fed synthetic input by the self-test *on the host and on the
  device alike*. Push hardware to the edges so this stays possible.
- **Board differences belong in the build, not in an `if`.** When one program targets two
  machines, put everything that differs in `boards/<board>/board.py` and have
  `make BOARD=…` copy exactly one of them to the device **under the same name**. Then no
  file at runtime asks which board it is running on — the answer was decided before
  anything was uploaded. (Two 240-px screens are not one 320-px screen scaled; letting
  each board have its own layout table is the point.)

## Rules this skill encodes

- **Ask the board before you call it.** Calling an M5 API that this firmware does not
  expose is the number-one failure — a plausible method UIFlow1 had, or another board
  has. `make probe`, then write the call. Wrap every optional subsystem (keyboard,
  speaker, power, RTC) in `try/except` so the program degrades instead of dying at line 1.
- **Never `dir()` the `hardware` package.** Importing it is fine and fast. Enumerating it
  makes MicroPython import every submodule, which initialises peripherals and **wedges the
  board until it is power-cycled**. Import the class and inspect that.
- **Modules deploy flat.** `sys.path` is `['', '.frozen', '/lib', '/system', '/flash/libs']`
  — there is **no `/flash/lib`**. A `lib/` subdirectory uploads happily and then fails to
  import. Keep `lib/` in the repo; land it flat on the device.
- **Never hardcode a resolution or a font size.** Read `width()`/`height()` in a
  `layout()`. Font names are **aliases** — on this firmware `FONTS.Montserrat12 is
  FONTS.DejaVu9` is True; there is one typeface at eight heights. Pick by measuring with
  `textWidth()`.
- **Greys must be multiples of `0x10`.** RGB565 keeps 6 bits of green and 5 of red/blue,
  so `0x0E0E0E` quantises to `rgb(8,12,8)` and the background picks up a green cast. The
  simulator quantises the same way, which is how you catch it before flashing.
- **Redraw only what changed, and erase only what you are about to paint.** Clearing a
  region and then painting into it **is** the flicker: the panel spends part of every
  frame showing the cleared state. And **text is the expensive primitive** — measured on
  a 240×135 panel, four 4-character `drawString`s cost 7.6 ms, more than clearing the
  entire 240×69 animation band (6.8 ms). Cache what text depends on. Wrap a frame in
  `startWrite`/`endWrite` so it reaches the panel as one SPI transaction.
- **Gate redraw logic with a ghost check.** Erase-what-moved is easy to get subtly wrong
  in both directions, and no single screenshot shows it. Drive each animated view N
  frames with no clearing between them, diff against the same state drawn clean, fail the
  build on any difference and print the coordinates. See
  [`references/host-sim-micropython.md`](references/host-sim-micropython.md).
- **A self-test is a report, not an assertion suite.** It should print the numbers a human
  would otherwise read off the screen — frame times, heap floor, the mic's noise floor,
  where the servos actually are — and *then* assert on them. The printout is what makes a
  failure diagnosable without the board in front of you.
- **Measure, but check what you are measuring.** `mpremote run host_script.py` takes the
  script from the host and imports everything it uses **from the device's flash**. Benchmark
  without pushing first and you measure the old code. This turned a 10× win into an
  apparent 0× and got it reverted.

## Bench facts that will cost you an hour

Full list in [`references/uiflow2-gotchas.md`](references/uiflow2-gotchas.md). The three
that bite hardest:

- **GPIO0 is the download-mode strapping pin.** Held low at reset the chip never starts
  the firmware. Do not bind a runtime feature to the BOOT button.
- **`boot_option` is a `u8`.** UIFlow2's `boot.py` reads NVS `uiflow/boot_option` with
  `get_u8`, and `esp32.NVS` types its keys — write it with `set_i32` and `get_i32` reads
  it back happily while `boot.py` raises NOT_FOUND, falls back to the startup menu and
  spends 60 s on a network connect. `main.py` never runs and nothing reports an error.
- **An ST7789 holds its last image without being refreshed.** So a program that never
  started does not show a blank screen — it shows the previous frame, frozen, which reads
  as a hang. Combined with the two above, this is a very convincing wrong diagnosis.
- **The keymap is readable from the firmware — never reconstruct it from keypresses.**
  `from hardware.keyboard import asciimap` gives `KEY_UP`/`KEY_DOWN`/`KEY_LEFT`/`KEY_RIGHT`
  and friends as plain integers. Inferring them instead, by asking someone to press keys in
  a stated order and matching that order against the codes that arrived, puts the fallible
  step on the human — it produced a wrong mapping twice here before anyone looked for the
  table. Two related traps: `tick()` drops the event when no `set_callback()` is installed,
  so a polling probe captures nothing and the keyboard looks dead; and the arrows (0xB4–
  0xB7 on the ADV) are outside the printable range, so the usual `chr(code)` filter
  swallows them while every letter still works.

## Non-M5 boards

UIFlow2 runs on ESP32-S3 boards M5 never made: flash the **StampS3** image (the only
*bare* S3 build — nothing for `M5.begin()` to hunt for), drive an arbitrary SPI panel
with **`M5.UserDisplay`**, and reach for `machine.I2S` when `M5.Mic` returns a DC level.
Pin maps for many cheap boards already exist in `xiaozhi-esp32`'s `main/boards/*/config.h`.
Method + the traps: [`references/non-m5-boards.md`](references/non-m5-boards.md).

## Worked example

**[`ToyWorks/op-cp`](https://github.com/ToyWorks/op-cp)** carries the whole method in
working form — `make check` (compile + upload + on-device self-test), `make shots` (host
render + ghost check), `make probe`, and a `CLAUDE.md` of the rules that keep both loops
honest. Every measurement quoted in this skill came off those boards.

- **OP-CP** (repo root) — an OP-1 flavoured step sequencer for the M5Stack Cardputer-ADV:
  a PCM synth rendered on the host, eight save slots, a ctrl key layer, four animated
  views, and an ESP-NOW broadcast. The flicker and profiling numbers above are from here.
- **[`dance/`](https://github.com/ToyWorks/op-cp/tree/main/dance)** — the same program on
  two very different machines, split at deploy time by `make BOARD=…`, one of which is a
  non-M5 board running UIFlow2 by the route in
  [`references/non-m5-boards.md`](references/non-m5-boards.md).

## When to leave for `vibe-firmware`

Move to C/ESP-IDF when you need: deterministic timing under load, real power management
and deep sleep, OTA with rollback, tight control of a heap that MicroPython's GC will
otherwise touch, a peripheral with no MicroPython binding, or a build you must reproduce
bit-for-bit. The host-simulator idea survives the move —
[`vibe-firmware/references/host-ui-simulation.md`](../vibe-firmware/references/host-ui-simulation.md)
is the LVGL/C++ form of the same loop.

## Keeping this current (living doc)

When a bring-up teaches you a gotcha, fold it back here and commit it. Everything above
was distilled from the two worked examples; the profiling table and the ghost check came
from a single flicker complaint that turned out to have three separate causes. See the
other skills' "Keeping this current" notes.
