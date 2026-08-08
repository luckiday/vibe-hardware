# UIFlow2 on ESP32-S3 boards M5 never made

You want the MicroPython workflow — `mpremote`, `M5.Lcd`, the host simulator — on a cheap
ESP32-S3 board with a screen that is not an M5Stack product. It works. Verified end to end
on a Waveshare/XINGZHI **xiaozhi-cube 1.54** (ESP32-S3, 16 MB flash, 8 MB PSRAM, 240×240
ST7789, I²S MEMS mic, three buttons).

## 1. Get the pin map for free

A great many cheap Chinese ESP32 boards already have a maintained pin map in
[`xiaozhi-esp32`](https://github.com/78/xiaozhi-esp32), under
`main/boards/<board>/config.h` — display bus and controller, audio I²S pins and rates,
buttons, backlight, battery ADC. Find the board there and copy the numbers; then confirm
each on the bench rather than trusting them.

For the cube:

```c
#define AUDIO_I2S_MIC_GPIO_WS   GPIO_NUM_4   // I2S in: ws 4 / sck 5 / din 6
#define AUDIO_I2S_MIC_GPIO_SCK  GPIO_NUM_5
#define AUDIO_I2S_MIC_GPIO_DIN  GPIO_NUM_6
#define DISPLAY_SDA GPIO_NUM_10  // SPI3: mosi 10 / sclk 9 / dc 8 / cs 14 / rst 18
#define DISPLAY_SCL GPIO_NUM_9
#define DISPLAY_DC  GPIO_NUM_8
#define DISPLAY_CS  GPIO_NUM_14
#define DISPLAY_RES GPIO_NUM_18
#define DISPLAY_BACKLIGHT_PIN GPIO_NUM_13
```

## 2. Flash the StampS3 image, not the one that matches your screen

**UIFlow2 for M5Stack StampS3 is the only build that is a *bare* ESP32-S3** — no panel, no
PMIC, no codec. `M5.begin()` on any other board's image hunts for peripherals that are not
there (a CoreS3 image wants an AXP2101 over I²C) and hangs or fails.

M5Burner's backend is a public HTTP API, so this needs no GUI:

- Catalogue: `GET https://m5burner-api.m5stack.com/api/firmware` — a JSON array of every
  public firmware. Find the entry whose `description` is `UIFlow2.0 (StampS3)`; each
  version gives a `file` hash.
- Image: `https://m5burner-cdn.m5stack.com/firmware/<file>.bin` — a **whole-flash image**,
  so `esptool write_flash 0x0` with no partition offsets. Check it with `image_info` first.
- Then set `boot_option` — **as a `u8`**, see
  [`uiflow2-gotchas.md`](uiflow2-gotchas.md#boot-and-recovery).

**Back up first.** `esptool read_flash 0x0 0x1000000 stock.bin` takes ~100 s for 16 MB and
makes the whole thing reversible; the board's original firmware goes straight back with
`write_flash 0x0`.

The image's own flash-size header may be smaller than the board's (the StampS3 build says
8 MB). That is fine — it lands at 0x0, the partition table inside it governs, and the rest
of the flash is simply unused. PSRAM the build does not enable is also just unused, which
costs you heap: budget ~50 KB free rather than the 8 MB the chip has.

## 3. Drive the panel with `M5.UserDisplay`

This is the piece that makes the whole thing work, and it is easy to miss.
**`M5.UserDisplay` is a full LovyanGFX device you construct with a panel type and a pin
list**, and it returns the same drawing surface `M5.Lcd` is — so render code moves across
unchanged.

```python
lcd = M5.UserDisplay(
    panel=M5.UserDisplay.PANEL.ST7789,
    w=240, h=240, ox=0, oy=0,
    invert=True, rgb=False,
    spi_host=2, spi_freq=40, spi_mode=0,          # spi_host=2 is SPI3_HOST
    sclk=9, mosi=10, miso=-1, dc=8, cs=14, rst=18, busy=-1,
    bl=13, bl_invert=False, bl_pwm_freq=44100, bl_pwm_chn=7,
)
```

Supported panels: `ILI9342`, `ST7735`, `ST7735S`, `ST7789`, `GC9A01`, `GC9107`,
`GDEW0154M09`, `IT8951`, plus I²C `SSD1306` / `SH110x`.

- **It is not `M5.addDisplay`.** That only knows M5's own Units and Modules (LCD Unit,
  OLED Unit, Atom/Module Display) and will refuse an arbitrary panel.
- **The `rgb=` argument is ignored** — `rgb_order` is hardcoded `false` in the C. If red
  and blue come out swapped you must compensate in your palette. Check with a labelled
  R/G/B test card and your own eyes; the sim cannot tell you.
- `invert=` does work, and most of these panels need `True`.
- Source, if you need to confirm behaviour:
  `m5stack/components/M5Unified/mpy_user_lcd.txt` in `m5stack/uiflow-micropython`, with a
  usage example at `tests/display/user_lcd.py`.

## 4. `M5.Mic` will probably lie to you

**M5Unified drives I²S at 16 bits.** A common MEMS microphone (INMP441 and friends) puts
24-bit samples **MSB-aligned in 32-bit slots**. Reading that as 16-bit returns a DC level
and nothing else: mono reads a constant, stereo reads a slow drift, and **neither moves
when you play music at it**. It is a convincing failure because `Mic.begin()` returns
`True` and frames keep arriving.

Use `machine.I2S` directly:

```python
for release in (M5.Speaker.end, M5.Mic.end):     # M5Unified holds a port from boot;
    try: release()                               # without this: ESP_ERR_NOT_FOUND
    except Exception: pass

i2s = I2S(1, sck=Pin(5), ws=Pin(4), sd=Pin(6), mode=I2S.RX,
          bits=32, format=I2S.MONO, rate=16000, ibuf=FRAME * 16)
i2s.irq(cb)          # registering an irq makes readinto() NON-BLOCKING
i2s.readinto(buf)    # → double-buffer exactly like M5.Mic's DMA recorder
```

Reading energy cheaply: the sample is MSB-aligned, so **bytes 2–3 of each 32-bit slot
*are* the sample shifted right by 16** — one uint16 load per sample, the same cost as a
16-bit path. The DC term is large and drifts, so remove it per frame
(`var = E[v²] − E[v]²`) rather than assuming it away, and scale the result so it lands on
whatever numeric range your thresholds were tuned against.

Sanity numbers from one room, on that scale: quiet 24–80, music at desk distance ~590
mean / 2500 peak, noise gate at 140. A 120 bpm kick played across the room locked the
tempo readout to 120.

**Test it with sound from the host**, not the board's own speaker: `M5.Speaker` and
`M5.Mic` are mutually exclusive, so starting the speaker silently kills the mic. Generate
a percussive WAV (a real transient — a 250 ms tone is a bad test signal and reads as the
wrong tempo) and `afplay` it while the board reports.

## 5. Buttons

Plain GPIO with internal pull-ups, read with edge detection so one press is one action:

```python
pins = (Pin(39, Pin.IN, Pin.PULL_UP), Pin(40, Pin.IN, Pin.PULL_UP))
edge = tuple(prev == 1 and cur == 0 for prev, cur in zip(_prev, level))
```

**Do not use GPIO0.** It is the download-mode strapping pin — held low at reset the chip
never starts the firmware, so binding a feature to the BOOT button hands the user a
guaranteed black screen.

## 6. Structure: one program, two boards

When the same app targets an M5 board and a non-M5 one, do not branch at runtime. Put
everything board-specific in `boards/<board>/board.py` and have the Makefile copy exactly
one of them to the device **under the same name**:

```make
BOARD ?= cores3
LIBS  := $(wildcard lib/*.py) $(wildcard boards/$(BOARD)/*.py)
push:
	@for f in $(LIBS) $(ART); do $(DEV) fs cp "$$f" ":$$(basename $$f)"; done
```

The module answers for the screen, the microphone, the controls and whatever body exists
(`on_beat` / `tick` / `rest` become no-ops on a board with no servos). Then no file at
runtime asks which machine it is on — and the two boards are free to have genuinely
different layouts rather than one scaled, which for a 320×240 and a 240×240 they should.

Worked example: `31-yunqi-utility/exp/stackchan-dance/`.
