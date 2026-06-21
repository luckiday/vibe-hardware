# Host UI simulation + the agent render-loop (hard-won)

How to let an agent **design and tune an on-device UI without flashing** — by running the
*real* render code on the host and screenshotting it, so the agent can *see* each frame and
iterate. Distilled from `examples/pager-buddy/firmware/sim/` (LVGL on the M5StickC S3). The
method is general; LVGL is the worked case.

## Why (not a web mock)

A hand-written HTML/CSS "mock" of the screen is a *separate* implementation — different
layout engine, different font rasteriser, different colour handling — so it drifts from what
the panel actually draws and hides real bugs (it'll happily render CJK with the system font
while the device shows tofu). **The fidelity move is to compile the firmware's own renderer
on the host** against the same UI library + the same fonts, into the same framebuffer
geometry, and emit a PNG per screen state. Then the loop is:

```
edit ui.c ─► ./shoot.sh ─► agent reads sim/shots/*.png ─► critique ─► edit ─► …
```

entirely in the terminal, no hardware in the loop. The agent reads the PNGs directly (it can
see images), so it closes its own loop: render → look → refine.

## How (LVGL → desktop, the pattern)

Carve the **hardware bring-up** out of the render code behind one macro, so the screens stay
a single source of truth shared verbatim with the device:

- In `ui.c`, wrap *only* the panel/SPI bring-up (`ui_init`, the flush/tick glue,
  backlight/sleep) in `#ifndef UI_SIM`. Everything else — every helper, screen, animation,
  `ui_render()` — compiles unchanged. The device builds with the macro undefined; the sim
  builds with `-DUI_SIM` and supplies its own `ui_init` + a memory-backed display.
- A tiny `sim/` CMake builds desktop LVGL (`add_subdirectory` of the resolved
  `managed_components/lvgl__lvgl`) + the real `ui.c` + the **same** font `.c` files, with an
  `lv_conf.h` that **mirrors `sdkconfig`** (colour depth, fonts, heap size).
- `sim_main.c` creates a `135×240 RGB565` display in `LV_DISPLAY_RENDER_MODE_FULL`, calls
  `ui_render(model)` for a chosen state, pumps `lv_timer_handler` a few ticks (so animations
  reach a representative frame), then writes the framebuffer to a PNG (a ~70-line zlib
  encoder — no image-lib dependency). One binary renders every state to `shots/`.

What's **faithful**: layout, flex sizing, ellipsis/marquee, typography, the animations.
What's **not** (tune on real hardware): the panel's gamma/colour cast, the on-wire RGB565
byte-swap + colour inversion, backlight/contrast, viewing angle. Treat the sim for
*geometry & type*, the panel for *colour*.

## Gotchas (each cost a build cycle)

- **RGB565 channel widths when decoding to PNG.** Red and blue are **5-bit** (scale by
  `*255/31`), green is **6-bit** (`*255/63`). Using a 4-bit divisor on blue makes pure white
  (`0xFFFF`) decode to yellow. If colours look wrong, dump the raw framebuffer and check the
  16-bit value *before* blaming the renderer — here LVGL was correct and the PNG decoder was
  the bug.
- **Desktop LVGL globs ARM hand-asm.** Its CMake pulls in `.S` files (Helium/NEON) that the
  macOS assembler can't parse. With `LV_DRAW_SW_ASM_NONE` they're dead weight — filter them
  off the target after `add_subdirectory` (`list(FILTER … EXCLUDE REGEX "\\.[sS]$")`) rather
  than editing vendored LVGL.
- **Keep `lv_conf.h` in lock-step with `sdkconfig`.** A minimal conf that sets only the
  deltas from LVGL's defaults works, but the deltas must match the device: colour depth 16,
  the exact Montserrat sizes, the heap size — and **`LV_FONT_FMT_TXT_LARGE`** if you use the
  full CJK faces (see bringup-gotchas → fonts). A mismatch silently diverges the sim.
- **The `#ifdef` must wrap *only* bring-up.** If a render helper ends up inside `#ifndef
  UI_SIM` the sim won't match the device. Carve at the hardware boundary, nothing more.

## Generality

The pattern is "compile the real render layer headless, screenshot, let the agent read it."
It ports to any framebuffer UI (LVGL, a custom blitter, e-paper buffers, even RP2040/STM32
render code): stub the panel transport, render into RAM, serialise to PNG. The expensive,
flash-bound visual-tuning loop becomes a sub-second host loop the agent drives itself.
