# pager-buddy — UI design language

The visual rules the firmware UI ([../firmware/components/ui/ui.c](../firmware/components/ui/ui.c))
follows, in the spirit of **Teenage Engineering: simple, minimal, fun.** Design new
screens *here* (on paper / in the sim), keep them inside these rules, then build. The
device shows **program status + the one key choice** — never code, never a wall of text.

## Philosophy

- **One idea per screen.** A glance answers "what needs me?" The detail is one tap away.
- **Subtract.** If a line, box, or word isn't carrying meaning, cut it. Whitespace is a
  feature — leave room to breathe (see *Safe areas*), don't fill the panel.
- **Sharp & deliberate.** 1px hairlines, square corners (`radius 0`), procedural line-art
  icons — no rounded cards, no drop shadows, no gradients. The OP-1/TP-7 look.
- **Fun in the motion, calm in the layout.** Personality lives in the breathing ring, the
  VU meter, the marquee — not in clutter. The static frame stays quiet.

## Canvas & safe areas (135 × 240, portrait)

```
0    ┌───────────────────────┐  status bar:  BT · clock · battery
17   ├───────────────────────┤  ← 1px rule
     │                       │
     │       content         │  content region: y 19 … 224, 5px inner pad
     │                       │
224  ├───────────────────────┤  ← soft-white rule
240  └───────────────────────┘  footer: two button hints (glyph + label)
```

- **Never** put content under the status bar or footer — they own those bands.
- Keep a **≥5px** margin from every edge; **≥8px** before any text the eye must read fast.
- Center hero elements on the screen's **x = 67** axis (135 is odd → exact-center is fine
  to ±1px; verify with a centroid check, not by eye).

## Colour (roles, not decoration)

| token | hex | role |
|---|---|---|
| `C_BG` | `0x0a0a0a` | near-black background (neutral, not blue) |
| `C_FG` | `0xe6e9ef` | primary text (clock, menu, status band) |
| `C_DIM` | `0x8a93a0` | secondary text (meta, age, hints) |
| `C_LINE` | `0x2a2f38` | hairlines, chip borders |
| `C_WORK` | `0x4aa3ff` blue | working / charging |
| `C_WAIT` | `0xffb020` amber | needs you (permission) |
| `C_ASK` | `0x35d0d8` cyan | asks (a question) |
| `C_DONE` | `0x46d369` green | done / all clear |
| `C_ERR` | `0xff5d5d` red | error / low battery |

Home/idle glance colour = the **most action-needing** state present:
`err > needs-you/asks > working > all-clear`.

> Panel caveat: the ST7789's gamma reads colours a touch cooler than the sim. Pick hues in
> the sim, but confirm the final cast on real hardware (that's why `C_BG` dropped its blue).

## State vocabulary

Each session state has **three** representations, used by available space:

| state | dot (always) | abbr (cramped meta row) | full word (roomy session screen) |
|---|---|---|---|
| working | blue | `RUN` | `working` |
| needs you | amber | `YOU` | `needs you` |
| asks | cyan | `ASK` | `asks` |
| done | green | `FIN` | `done` |
| error | red | `ERR` | `error` |

The **dot colour is the primary signal**; the abbr/word is the terse confirmation. The
3-letter codes (`RUN/YOU/ASK/FIN/ERR`) are distinct at a glance and keep the list's meta
row inside 135px next to the agent + terminal chips.

## Typography

Two families, chosen per content — getting this wrong is the #1 source of "tofu" (□):

- **Montserrat** (`lv_font_montserrat_10/12/40`) — ASCII + the `LV_SYMBOL_*` set. Use for
  clock, battery %, footer hints, ages, and any `LV_SYMBOL_*` glyph. It has **no** CJK.
- **PuHui full** (`font_puhui_20_4` title / `font_puhui_14_1` body) — full common-CJK +
  Latin. Use for anything that can carry bridge text: **session names, tasks, questions,
  options**. The `*_basic_*` subset is ~700 glyphs and tofus most Chinese — don't use it.
- An inline "✓ name" must **split** the two (symbol in Montserrat, name in PuHui); PuHui
  carries no `LV_SYMBOL_*`.
- Cost: the full faces add ~1.6MB flash. Fits the 3MB OTA slots; if tight, build a subset
  font from the actual strings or drop the title to `font_puhui_16_4`.

## Components

- **Chip** — 1px border in its colour, square corners, 3×1 padding. The OP-1 boxed tag.
  Used for `agent`, terminal (abbreviated), the state code, and section labels.
- **Footer hint** — a line-art button glyph (FRONT pill / SIDE chevron / back chevron) +
  a short white UPPER label. Left = FRONT/OK, right = SIDE/next. Only offer real actions
  (the empty list shows just `MENU`, not a dead `OPEN`).
- **Breathing ring** — the hero/idle centerpiece: 3 concentric 1px rings, phase-offset,
  growing + fading, with a steady centre dot. Colour = glance state; `agitated` pulses
  faster. Reused as the "all clear / no sessions" mark.
- **VU bars / marquee** — working screen gets an animated level meter; long text on the
  *selected* row marquee-scrolls, collapsed rows ellipsise (`…`).

## Screen patterns

- **Home (idle)** — date · big clock · centered breathing ring · low white `status_band`
  (`N sessions / glance`). The clock lives here only (the bar drops its clock on home).
- **Empty list = home.** Zero sessions is the same "all clear" state, so an empty list
  renders `view_idle` (green ring, `0 sessions / all clear`) — pixel-identical to idle, not
  a separate screen. One predicate (`is_home`) gates this everywhere (the bar clock, the
  render route, the tick). Don't build a second empty-list layout.
- **List** — rows of `dot · name · age`, then the task (one line, ellipsised; the selected
  row marquee-scrolls it). The selected row gains a state-coloured left edge bar + a third
  meta line: `agent | term | STATE-abbr`.
- **Session** — big title (name / tool / "asks") in the state colour + the line-art state
  icon, the body text, then the action bar (Deny/Allow, options) or a `BACK`-only footer.

## Workflow — design on the sim first

Iterate locally before flashing: edit `ui.c`, run [../firmware/sim/shoot.sh](../firmware/sim/shoot.sh),
read `sim/shots/*.png`, refine. The sim runs the *real* `ui.c` + LVGL + these fonts, so
layout/typography/animation are faithful (only panel colour/gamma needs real hardware).
