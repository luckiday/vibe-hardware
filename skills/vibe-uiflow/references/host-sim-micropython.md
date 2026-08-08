# Host simulation for MicroPython UIs, and the ghost check

The MicroPython form of
[`vibe-firmware/references/host-ui-simulation.md`](../../vibe-firmware/references/host-ui-simulation.md).
Same idea — run the app's *real* render code on the host and let the agent look at the
result — but the hardware boundary is drawn somewhere much cheaper, and the check that
keeps it honest is different.

## Where to cut

In the C++/LVGL version you carve the panel bring-up behind `#ifndef UI_SIM` and link
desktop LVGL. In MicroPython there is no link step and no LVGL: the app draws by calling
`M5.Lcd` primitives, so **the boundary is the `M5.Lcd` method surface itself**. Put a
Pillow-backed stand-in into `sys.modules["M5"]` before importing anything, and the app's
own `draw_*` functions run against it unchanged:

```python
# sim/m5stub.py
class _Lcd:
    def __init__(self, w, h):
        self.img = Image.new("RGB", (w, h), (0, 0, 0))
        self.d = ImageDraw.Draw(self.img)
    def fillRect(self, x, y, w, h, c): ...
    def fillCircle(self, x, y, r, c): ...
    def drawString(self, s, x, y): ...
    def startWrite(self): pass          # batching is a no-op here, but it is called
    def endWrite(self): pass

def install(board="default"):
    m5 = _M5(BOARDS[board])             # panel size per board
    sys.modules["M5"] = m5
    ...
    return m5
```

Then `shoot.py` sets a state, calls the app's real `draw()`, and saves a PNG. The agent
reads the PNGs directly, so it closes its own loop: render → look → refine.

Two things make this faithful rather than approximate.

### 1. Font metrics dumped off the real device

This is the part that decides whether the sim is worth anything. Do **not** guess a point
size. Run a script on the board that measures `textWidth()` for every character of every
font and dumps it to JSON:

```python
# sim/dump_metrics.py — run with `make metrics`, output redirected to metrics.json
for name in FONT_NAMES:
    M5.Lcd.setFont(getattr(M5.Lcd.FONTS, name))
    print({"h": M5.Lcd.fontHeight(),
           "w": [M5.Lcd.textWidth(chr(32 + i)) for i in range(95)]})
```

On the host, load that table, then pick the TTF pixel size whose advances best fit it,
and draw **glyph by glyph, advancing by the device's width** rather than letting Pillow
lay out the string. A centred string then lands on the same pixel it does on the panel.

Re-dump after any firmware update (`make metrics`); the fonts are firmware, not app.

### 2. Colour quantised through RGB565

Quantise every colour the way the panel does — red and blue to 5 bits, green to 6 —
before drawing:

```python
def rgb565(c):
    r, g, b = (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF
    r, g, b = r >> 3, g >> 2, b >> 3
    return (r * 255 // 31, g * 255 // 63, b * 255 // 31)
```

Otherwise the sim shows you a grey the panel will render with a green cast. This is how
the "greys must be multiples of `0x10`" rule was found.

**Faithful**: geometry, layout, typography, RGB565 banding.
**Not faithful** (judge on hardware): panel gamma and colour cast, backlight, viewing
angle, refresh/tearing.

## The ghost check

A screenshot proves a *state* looks right. It cannot prove that the transition between
states leaves nothing behind — and the moment you stop clearing the whole screen each
frame (which you must, or it flickers), that becomes the main source of visual bugs.

So the sim runs the app the way the music runs it, with no clearing in between, and
diffs:

```python
def ghost_check(view):
    redraw_all()                       # clean start, caches reset
    for i in range(40):                # drive it like the real animation does
        set_state(i)
        draw_frame()                   # exactly what the app's animate() calls
    dirty = lcd.img.crop(band)

    set_state(39)                      # the SAME final state...
    redraw_all()                       # ...drawn onto a clean band
    clean = lcd.img.crop(band)

    diff = [p for p in pixels if dirty[p] != clean[p]]
    # any difference is a pixel some element failed to erase — or erased wrongly
```

Make it **fail the build** and **print the coordinates**. Notes from using it:

- **Crop to the region the code under test owns.** If the header and footer are repainted
  by the app loop's own change-detection rather than by `draw_frame()`, including them
  compares the harness against itself. The first run reported 516 "ghosts" that were all
  the header.
- **Read the direction of the difference.** Left-over pixels mean an erase box that is too
  small. *Missing* pixels mean one that is too big — it ate a neighbour. Both are bugs and
  they look identical in a diff count.
- **It finds old bugs immediately.** On its first real run it caught two spark pixels that
  had been drawn outside their clearing rectangle since the feature was written.
- **Then it caught its author.** Converting a ring of dots to per-dot erasing reported
  missing pixels: adjacent dots were 9 px apart and the erase boxes 13 px wide, so erasing
  dot B took a bite out of dot A. Fix: **all erasing before any drawing**.

## Erase-what-moved, concretely

The pattern the ghost check exists to protect:

```python
_box = None                            # where this element was last drawn

def draw_thing(...):
    global _box
    if _box:
        lcd.fillRect(*_box, BG)        # erase where it WAS
    ...compute the new geometry...
    lcd.fillRect(x, y, w, h, FG)       # draw where it IS
    _box = (x - pad, y - pad, w + 2 * pad, h + 2 * pad)
```

- The stored box must cover **everything the function can paint**, including decorations
  that stick out (sparks, marks) — compute the worst case from the same constants the
  drawing uses, so the two cannot drift.
- A full repaint (view switch) still clears the region wholesale and **resets the caches
  to `None`**.
- Wrap the frame in `startWrite()` / `endWrite()`, in a `try/finally`. LovyanGFX then
  holds the SPI bus for the whole repaint instead of taking and dropping it per primitive.
  Worth 5–19 % on its own; the erase-what-moved change is worth much more.

## Cost, measured

On a 240×135 panel with a 240×69 animation band, one frame:

| primitive | cost |
|---|---|
| 4× `drawString`, 4 chars each | **7.6 ms** |
| `fillRect` over the whole band | 6.8 ms |
| `fillRect` over a 128×52 box | 2.8 ms |
| 4× `fillRect` over a bar column | 1.2 ms |
| 4× `textWidth` | 0.07 ms |

**Text dominates.** Four short strings cost more than clearing the entire band, so the
biggest single win in a meter-style view is caching the labels against whatever they
depend on. Guessing this wrong twice is what produced the table.
