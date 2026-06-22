# sim — desktop simulator for the pager UI (agent-in-the-loop)

Renders the device's **real** `components/ui/ui.c` on the desktop and writes a PNG per
screen, so an agent (or you) can *see* exactly what the StickC S3 draws, tweak `ui.c`,
and re-render — without flashing hardware. This is the faithful counterpart to
`../../design/` (which is a separate HTML/CSS mock and does **not** run `ui.c`).

## Why it's faithful

It compiles the same renderer against the same stack the firmware uses:

- the actual `components/ui/ui.c` — built with `-DUI_SIM`, which excludes **only** the
  ST7789/SPI bring-up (`ui_init`, the flush/tick glue, backlight/sleep). Every helper,
  screen, animation and `ui_render()` is shared verbatim.
- **LVGL v9** from `managed_components/lvgl__lvgl` (same resolved version as the device).
- the same **PuHui** CJK fonts (`font_puhui_basic_20_4/14_1`) + Montserrat 10/12/40.
- `lv_conf.h` mirrors the device `sdkconfig` (RGB565, 64 KB LVGL heap, same fonts).
- a 135×240 RGB565 framebuffer — the panel's real geometry and colour format.

**Not** reproduced (panel physics — tune those on real hardware): the ST7789's gamma /
colour cast (the `C_BG` "reads blue" note in `ui.c`), the on-wire RGB565 byte-swap +
colour inversion, backlight/contrast, viewing angle. Layout, typography, ellipsis/
marquee, flex sizing and the animations are faithful.

## Use

```bash
./shoot.sh                 # build + render every state to shots/*.png (3× upscale)
./shoot.sh idle            # just one state -> shots/idle.png
SCALE=1 ./shoot.sh         # real 135×240 pixels
TICK_MS=1400 ./shoot.sh    # advance the animation clock further before the snapshot
```

Or drive the binary directly:

```bash
cmake -S . -B build && cmake --build build -j
./build/pager_sim <state> <out.png> [tick_ms] [scale]
./build/pager_sim all <out_dir> [tick_ms] [scale]
```

States: `idle  idle-clear  list  working  approve  ask  done  offline  connecting  empty  cjk`.
Edit the scenarios (and add your own) in `sim_main.c` → `build_model()`. (`connecting` is
what the device shows until the first BLE snapshot arrives — see `../main/main.c`.)

## The agent loop

> render → read the PNGs → edit `components/ui/ui.c` → `./shoot.sh` → read again

Ask the agent to "run `sim/shoot.sh` and look at the screenshots, then adjust ui.c". It
reads the PNGs, critiques the layout/spacing/colour, edits, and re-renders — a closed
loop entirely in the terminal.

## Requirements / notes

- macOS: `cmake` + a C/C++ toolchain + `zlib` (all present with the Xcode CLT). No SDL.
- Needs `managed_components/` populated — run an ESP-IDF build once (`./idf.sh build`) so
  the component manager fetches LVGL + the fonts; the sim then builds offline.
- `build/` and `shots/` are gitignored (regenerated artifacts).
- Known finding from the first run: the **basic** PuHui subset is missing many common
  CJK glyphs (they render as `□` tofu in the `cjk`/`ask` shots). The HTML mock hides this
  by using a system CJK font — a concrete example of why this sim is worth having.
