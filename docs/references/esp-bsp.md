# espressif/esp-bsp — study note

**Repo:** https://github.com/espressif/esp-bsp · **Framework:** ESP-IDF 5.2–6.0 ·
**License:** Apache-2.0 · **Local clone:** `_clones/esp-bsp/` (run [`clone.sh`](clone.sh))

Board-support packages for 25+ Espressif / M5Stack boards behind one unified API, plus
`esp_lvgl_port`. This is the canonical version of the **BSP pattern** our firmware
skill teaches — the single place pins + peripheral init live, so domain code stays
board-agnostic.

## What to read, and why

| Area | Maps to in this repo |
|---|---|
| `bsp/<board>/` — one API over display / touch / audio / SD / camera | our `<board>_board` BSP — [esp-idf-structure.md → BSP](../../skills/vibe-firmware/references/esp-idf-structure.md) |
| Display driver init (ST7789, ILI9341, GC9A01, …) | `stick_s3_board` ST7789P3 bring-up |
| `esp_lvgl_port` (LVGL ↔ display / touch glue) | our `ui` component |
| Audio codec abstraction (ES8311 et al.) | pager-buddy audio bring-up |

## Caveats

- Components ship via the ESP Component Manager (`idf_component.yml`) — that's the
  intended way to consume them; the clone is for reading.
- Has submodules; the depth-1 clone doesn't fetch them (fine for studying structure).
