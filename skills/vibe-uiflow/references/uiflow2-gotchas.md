# UIFlow2 bench gotchas

Each of these cost at least one debugging session. Measured on Cardputer-ADV, CoreS3 and
a StampS3-firmware board, UIFlow2 v2.5.0 (MicroPython v1.27).

## Boot and recovery

- **`boot_option` is a `u8`, and getting it wrong is silent.** UIFlow2's `boot.py` reads
  NVS `uiflow/boot_option` with **`get_u8`**, and `esp32.NVS` types its keys. Write it
  with `set_i32` and `get_i32` reads it back as 0 perfectly happily — while `boot.py`'s
  `get_u8` raises `ESP_ERR_NVS_NOT_FOUND`, falls back to `1` (startup menu + a 60 s
  network connect) and never runs `main.py`. **Nothing anywhere reports an error.**
  A wrongly-typed key of the same name also makes `set_u8` alone insufficient — `erase_key`
  first. Semantics: `0` run `main.py` · `1` menu + network (factory) · `2` network only.

  ```python
  nvs = esp32.NVS("uiflow")
  try: nvs.erase_key("boot_option")
  except Exception: pass
  nvs.set_u8("boot_option", 0); nvs.commit()
  ```

  Put this in a `make` target that `deploy` depends on, so it cannot be done by hand.

- **An ST7789 holds its last image without being refreshed.** A program that never started
  therefore does not show a blank screen — it shows the previous frame, frozen. Combined
  with the item above, the symptom of "main.py never ran" is a screen that looks like a
  hung app. Diagnose by writing a marker file from `main.py` and reading it back, not by
  looking at the panel.

- **GPIO0 is the download-mode strapping pin** on an ESP32-S3. Held low at reset the chip
  never starts the firmware at all. Never bind a runtime feature to the BOOT button: the
  one control you invite a user to press is the one that makes the screen stay black.

- **Some boards have a startup override, and some do not.** `boot.py` documents holding
  Cardputer-ADV's ESC, StickS3's BtnA, or touching the StackChan screen during a 100 ms
  window to reach the menu without deleting `main.py`. The **StampS3 build has none**, so
  on a board running that image the way back is `make undeploy`.

## Talking to the board

- **`mpremote` is the whole toolchain.** UIFlow2 firmware is plain MicroPython. There is
  no official UIFlow2 CLI — M5Burner is a GUI, the Web IDE is a browser tab, and
  `pip install CoreMP135-UiFlow2` is for a Debian Linux board and unrelated to ESP32.

- **`mpremote run host_script.py` imports from the DEVICE.** The script text comes from
  your machine; every module it imports comes from `/flash`. Benchmark or test a change
  without pushing first and you measure the old code — confidently, and wrongly. This
  turned a 10× improvement into an apparent 0× and got it reverted.

- **`mpremote exec` does not preserve globals between calls.** You cannot test "did
  `main.py` run at boot?" by checking whether a global still exists. Write a marker file.

- **The serial port is exclusive.** The Web IDE and `mpremote` cannot both hold it; a
  stuck "could not open port" is usually a forgotten browser tab.

- **Opening the port resets the chip.** On a native-USB S3, `pyserial`'s `open()` alone
  knocks it into download mode. A "passive" read is not passive — and a board that looks
  like it never booted may simply have been observed.

- **USB re-enumerates on reset.** Right after `deploy`, `mpremote` fails with
  `Errno 6 Device not configured` until the port comes back. Wait for the device node,
  then a couple of seconds more.

- **`while True` hangs automation.** `mpremote run app.py` never returns — which is why
  the self-test is bounded and ends in `raise SystemExit`.

- **Match the USB *product* string, not the manufacturer.** Several M5 boards on one desk
  are all `M5Stack`; a manufacturer match picks whichever enumerated first. And two
  boards will happily take the same port name at different times — keep one attached, or
  match on the product string in `find-port.sh`.

## The API surface

- **Never call a method you have not confirmed exists on *this* firmware.** The single
  most common failure here is a plausible method that UIFlow1 had, or another board has.
  Dump the surface (`make probe` / `make api OBJ=M5.Mic`), then write the call. Wrap every
  optional subsystem in `try/except` so the program degrades instead of dying at line 1.

- **Never `dir()` the `hardware` package.** `import hardware` is fine and fast.
  `dir(hardware)` makes MicroPython import every submodule, which initialises peripherals
  and **wedges the board until it is power-cycled** — it looks like a hung serial port.
  Import the class you want and `dir()` that.

- **Modules deploy flat.** `sys.path` is `['', '.frozen', '/lib', '/system', '/flash/libs']`
  — there is **no `/flash/lib`**. A `lib/` subdirectory uploads happily and then fails to
  import. Keep `lib/` in the repo, land it flat on the device.

- **Font names are aliases.** `FONTS.Montserrat12 is FONTS.DejaVu9` returns True. There is
  one typeface at eight heights (15, 16, 18, 21, 27, 44, 49, 52 on the boards measured).
  Pick by measuring with `textWidth()`, never by assuming a name means a size.

- **`M5.Speaker` and `M5.Mic` are mutually exclusive** on codecs that share a path — the
  official mic example calls `Speaker.end()` before `Mic.begin()`. This also means **you
  cannot use a board's own speaker to test its own microphone**; play sound from the host
  instead.

- **A microphone can "work" and capture nothing, and everything will report success.**
  On a Cardputer-ADV, `M5.Mic.begin()` returns True, `record()` fills buffers of exactly
  the right length, and every sample in them is the same constant (−8, across 364k
  samples of real recordings). The ES8311 codec is alive — it answers at 0x18 on the
  internal bus (scl 9 / sda 8) and `Speaker.tone()` is audible — but nothing drives its
  ADC path, and scanning `machine.I2S` RX across a dozen candidate data pins found no pin
  carrying audio. `M5.Mic` appears to be configured for the original Cardputer's mic
  (i2s_port 0, data_in 46, no MCLK) rather than the ADV's codec (Speaker is on i2s_port
  1, data_out 42).

  Before spending an afternoon on it: the official mic example on the docs site is
  written for a *different board*, and running it verbatim here changes nothing.
  Neither does the three-argument `record(buf, rate, stereo)`, sharing the
  speaker's `i2s_port`, setting `pin_mck`, or calling the firmware's own
  `es8311.microphone_config()`. `use_adc = True` looks like a hit — the first
  take shows a big span — but the samples are a smooth monotonic ramp, a DC
  settling curve rather than sound, and the next take is flat again. **A large
  span is not evidence of audio unless it RESPONDS to something**; play a tone
  and check.

  **Test for span, not level.** A DC constant has a large peak and zero
  max-minus-min; a live mic dithers even in silence. Any program that saves recordings
  should refuse a take whose span never rises off the floor, and say so *during* the
  recording — a saved file of nothing is indistinguishable from a real memo you cannot
  hear. Put the check in the on-device self-test too, so the day a firmware update fixes
  it, the test tells you.

## Keyboards (Cardputer / Cardputer-ADV)

**Read the keymap out of the firmware. Do not reconstruct it from keypresses.**
`hardware/keyboard.py` is plain Python on the device, and `asciimap` holds the constants:

```python
from hardware.keyboard import asciimap      # importing ONE submodule is safe;
                                            # it is dir(hardware) that wedges
print([(n, getattr(asciimap, n)) for n in dir(asciimap) if n.startswith("KEY_")])
```

On a Cardputer-ADV, UIFlow2 v1.27.0, that returns:

| constant | value | constant | value |
|---|---|---|---|
| `KEY_LEFT` | 180 (0xB4) | `KEY_ENTER` | 40 (0x28) |
| `KEY_UP` | 181 (0xB5) | `KEY_ESC` | 41 (0x29) |
| `KEY_DOWN` | 182 (0xB6) | `KEY_BACKSPACE` | 42 (0x2A) |
| `KEY_RIGHT` | 183 (0xB7) | `KEY_TAB` | 43 (0x2B) |
| `KEY_LEFT_CTRL` | 128 (0x80) | `KEY_FN` | 255 (0xFF) |

This is worth more than any amount of careful pressing. Working it out by asking a human
to press keys in a stated order and matching that order to the codes that arrived put the
fallible step on the human, and it produced a wrong mapping twice before anyone thought to
look for the table. There is also a `kb_asciimap` bytes object next to it — the full
scancode → value table, if you need the rest.

**`get_key()` does not return that table.** It returns ASCII where one exists and the raw
keycode where none does: enter → 10, backspace → 8, backtick → 0x60, but the arrows come
through as 180–183 and tab as 43. So the constants tell you what the keys ARE; a short
press test tells you what `get_key()` hands you for them. Both, not either.

Then the traps:

- **`tick()` drops the event if no callback is installed.** The working pattern is
  `kb.set_callback(fn)` and then `kb.tick()` in the loop, with the callback calling
  `kb.get_key()`. A probe that calls `tick()` and then polls `get_key()` directly captures
  **nothing at all** — which reads as "the keyboard is dead" and sends you debugging
  hardware that is fine.

- **Arrow keys are outside the printable range.** Any dispatch shaped like
  `ch = chr(code) if 0x20 <= code <= 0x7E else ""` followed by `if not ch: return`
  swallows all four, and the arrows appear dead while every letter still works. Test the
  raw code before narrowing it to a character.

- **`fn` + anything reports `0x00` from `get_key()`**, so fn combinations cannot be told
  apart — including `fn + \``, which is where **esc** is printed on the keycap. A program
  that needs a cancel key should take the plain backtick (0x60) instead, at the cost of
  not being able to type one.

- **The ADV is not the original Cardputer.** It replaced the GPIO key matrix with a
  **TCA8418 I²C controller at 0x34**. Keycodes from the original board, and from the
  Arduino `M5Cardputer` library, do not transfer — that library reports **USB HID usage
  codes** (arrows 0x4F–0x52). The keys with arrows silkscreened on them (`; , . /`) still
  send their own characters when pressed plainly, so accepting those as aliases costs
  nothing and gives a one-handed fallback.

## Audio (`playRaw`, measured)

- **It interprets any buffer as int16**, whatever type you pass — `bytearray`,
  `array('B')` and `array('h')` behave identically. There is no uint8 path.
- **The sample-rate argument is how you pitch notes**: one buffer per voice, replayed at
  `rate * 2**(semitones/12)`. Usable range **700 Hz – 48 kHz**; outside it, fold by
  octaves — clamping puts the note out of tune.
- **`isPlaying()` leads the audio by ~39 ms** (one DMA buffer). Do not use it to measure
  durations without accounting for that.
- **Load per sound, never as one blob.** Free heap is not the largest free block: with an
  app running there may be ~66 KB free and no contiguous 36 KB, so reading a whole kit
  file at once dies with `MemoryError`. Twelve allocations of 1–4 KB fit fine.
- **Render sample data on the host.** Synthesising a drum kit on the device cost ~5.4 s —
  far too slow for boot. Build the blob with a host script and commit it as an artifact
  (seed the noise source so it is reproducible).

## Timing

- **Schedule against an absolute deadline**, accumulating (`ticks_add(next, interval)`),
  not by sleeping for the interval — otherwise the clock drifts. Measured under real
  playback: median 1 ms late, p90 2 ms, max 3 ms against a 133 ms sixteenth.
- **asyncio does not help and is not worth it here.** It is cooperative, so the thing that
  actually caused jitter — a 62 ms full-screen redraw — would block an event loop exactly
  as it blocks a plain one. The fix was to stop doing full redraws, not to change the
  concurrency model. asyncio helps when code *waits* on I/O; a panel-and-buttons device
  does not, and tasks allocate against an already-tight heap.

## Motion and sensing (when a board has a body)

- **Servo zero conventions do not survive a firmware change.** A base assembled and zeroed
  under one firmware reports a different neutral under another, and commanding the
  "official" rest angle silently does nothing because the servo's own EEPROM limits reject
  the excursion. Read where the head actually is at boot, call that neutral, choreograph
  relative to it, and clamp **once, at the exit**.
- **Power up without a lurch**: cut the servo rail, wait, restore it, torque on, read the
  pose, and command the pose you just read before anything else.
- **A servo is loud to its own microphone** — measured at roughly 20× the room floor on
  the same board. If the mic feeds a detector, either mask the detector while a move lands
  or move less: letting the *screen* carry the animation and the head mark only the bars
  is quieter and honest to the detector.
- **Give the servos time to settle before measuring anything acoustic.** A self-test that
  measured the mic floor right after homing the head read 1091 against a gate of 90, and
  warned every single run; after a 1.5 s settle it reads 48. A warning that always fires
  is a warning nobody reads.
