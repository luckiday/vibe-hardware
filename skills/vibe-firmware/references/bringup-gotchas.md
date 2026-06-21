# ESP-IDF bring-up & flashing gotchas (hard-won)

Concrete traps hit bringing up the `examples/pager-buddy/firmware/` M5StickC S3 (display
+ NimBLE status link). Each cost a build/flash cycle to diagnose; they recur on any
ESP32-S3 native-USB board. Keep your own code generic — this is the method.

## `sdkconfig.defaults` only takes effect on a FRESH `sdkconfig`

`idf.py` applies `sdkconfig.defaults` **only when it generates `sdkconfig`** (which is
gitignored). If a `sdkconfig` already exists, editing `sdkconfig.defaults` does
**nothing** — the old config persists.

- **Symptom:** you enable a subsystem (e.g. `CONFIG_BT_NIMBLE_ENABLED=y`), rebuild, and
  get `fatal error: host/ble_hs.h: No such file or directory` — the component's headers
  aren't on the include path because the build still thinks BT is off.
- **Fix:** delete the stale `sdkconfig` and rebuild (`rm sdkconfig && idf.py build`), or
  `idf.py set-target`/`reconfigure`. After *any* `sdkconfig.defaults` change, regenerate.

## The task that runs LVGL needs a big stack

If you pump LVGL (`lv_timer_handler` + your screen builders) from `app_main`, it runs on
the **main task**, whose default stack is `CONFIG_ESP_MAIN_TASK_STACK_SIZE` = **3584 B**.
That overflows when LVGL builds a deeper screen (wrapped text, several widgets).

- **Symptom:** `***ERROR*** A stack overflow in task main has been detected.` →
  `vApplicationStackOverflowHook` → reboot, triggered by a *specific* UI action (e.g.
  opening a detail screen), not at boot.
- **Fix:** bump it — `CONFIG_ESP_MAIN_TASK_STACK_SIZE=8192` (or run LVGL in its own
  `xTaskCreate`'d task with a generous stack). Cheap in internal RAM; size for the
  deepest render path, not the idle one.

## A full LVGL rebuild on every tick flickers (and resets animations)

A 1 Hz heartbeat that updates the clock/ages by **rebuilding the whole screen**
(`lv_obj_clean` + recreate) flickers visibly and restarts any marquee/scroll animation
every second — it looks like the screen is "flashing."

- **Fix:** split *structural* redraws from *time* ticks. Full `ui_render()` only when the
  content/view actually changes (new data, navigation); for the per-second clock/age tick,
  update the existing labels in place (`lv_label_set_text` on cached handles), no rebuild.
- **Watch the other periodic redraw:** a battery/sensor read that flips a displayed value
  on ±1 LSB jitter triggers a full rebuild on its own timer. Add hysteresis (only redraw on
  a ≥2-unit change) so noise doesn't repaint the screen.

## LVGL's built-in fonts are ASCII-only — CJK/Unicode needs a real glyph set

`lv_font_montserrat_*` (the `CONFIG_LV_FONT_MONTSERRAT_*` built-ins) carry only ASCII +
the `LV_SYMBOL_*` icon range. Any other codepoint — Chinese, `•`, `▼`, `—` — renders as a
"tofu" box. Don't try to subset Montserrat; pull in a font that actually has the glyphs.

- **Fix:** add a CJK font *component* and assign it per label — `78/xiaozhi-fonts` (from
  xiaozhi-esp32, MIT) covers common CJK *and* Latin, so one label renders English or Chinese.
  List `78/xiaozhi-fonts` in the component's `idf_component.yml`, declare with
  `LV_FONT_DECLARE(font_puhui_20_4)`, and pass `&font_puhui_20_4`. Pick by display size
  (≈16 px for 240², 20 px for 240×320). It's a font *binary*, not a Kconfig flag.
- **Use the FULL face, not the `*_basic_*` subset.** `font_puhui_basic_*` is only ~700 glyphs
  and still tofus most everyday Chinese (迁/移/数/据/库, 合/并/建…) — a trap, because it looks
  CJK-capable until real text arrives from the link. The full `font_puhui_<size>` faces carry
  the ~6 k common set. They need **`CONFIG_LV_FONT_FMT_TXT_LARGE=y`** (the small-font bitmap
  offsets overflow otherwise — the build errors with exactly that hint). Cost: the full 20 px
  + 14 px faces are ~1.6 MB; a measured app went 1.24 MB → 2.59 MB (still 18 % free in a 3 MB
  slot). If flash gets tight, build a subset font from your actual strings or drop the title a
  size. `--gc-sections` still drops every size you don't reference. (Caught in the host sim —
  see [`host-ui-simulation.md`](host-ui-simulation.md).)
- **Keep `LV_SYMBOL_*` in a Montserrat label.** The CJK fonts don't carry the icon range, so
  an inline `"✓ name"` in a PuHui label loses the check mark. Split it: symbol in a
  Montserrat label, text in the CJK one (a flex row). xiaozhi does the same — a separate
  `font_awesome_*` for icons alongside the text font.

## Native USB-Serial/JTAG: never toggle DTR/RTS by hand

On an S3 whose USB-C goes straight to the chip, a **raw `pyserial` open with DTR/RTS**
straps the chip into **ROM download mode** instead of running your app.

- **Symptom:** after a "monitor"/read attempt the screen goes dark and the boot log shows
  `rst:... boot:0x3 (DOWNLOAD(USB/UART0))` — it's sitting in the bootloader, not crashed.
- **Fix:** read the console with `idf.py monitor` / `esp_idf_monitor` (they drive the
  USB-JTAG reset correctly) — **not** a hand-rolled serial reader. Note `idf_monitor`
  needs a real TTY (it errors if stdout is redirected to a file).
- **Recover** without reflashing: `esptool.py -p <PORT> --after hard_reset flash_id`
  (connects, then hard-resets into the app).

## A serial monitor holds the port — release it before flashing

`esptool` needs exclusive access. If a monitor (or any process) has the port open you get
`Could not exclusively lock port ... Resource temporarily unavailable`.

- **Fix:** stop the monitor first (`Ctrl-]` in `idf.py monitor`); confirm with
  `lsof /dev/cu.usbmodem*`. The same native-USB port serves both flashing and console, so
  they can't be open at once.

## `-Werror=format-truncation` on small `snprintf` buffers

GCC can't prove a `long`/`int` fits a small buffer, so `snprintf(buf8, …, "%02ld:%02ld",
h, m)` fails the build even when *you* know `h,m < 60`.

- **Fix:** bound the value so the compiler can see the range (`int hh = x % 100;`) and/or
  size the buffer generously. Don't `-Wno-…` it away — the bound is free and documents intent.

## Flash scope: full image vs app-only

- **Config / partition / bootloader change** (e.g. enabling BT, editing
  `partitions_ota.csv`): flash the **full** image —
  `bootloader.bin@0x0 + partition-table.bin@0x8000 + ota_data_initial.bin@0xd000 +
  app.bin@0x10000` (copy the exact args `idf.py build` prints).
- **Code-only iteration:** flash just the app at `0x10000` — faster. Hash-verify is
  printed either way; "Hash of data verified" + a clean `rst:0x...SPI_FAST_FLASH_BOOT` boot
  is your confirmation.

## Deep-sleep `ext1` wake: three ways to self-wake instantly

You arm the front button as an `ext1` wake source, call `esp_deep_sleep_start()`, and the
device **wakes immediately** (or loops sleep→wake→sleep) instead of staying down. Three
distinct causes, all seen on the StickC S3 (front button = GPIO11, an RTC-capable pad):

- **Stale wake sources.** Light sleep / `esp_pm` may have left other wakeup bits armed (e.g.
  a PMIC-IRQ `gpio_wakeup`). Clear them first: `esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL)`.
- **The wake pin floats low.** An active-low button idles high *only* while its pull-up is
  powered — but the digital pull-up dies in deep sleep, the pad floats low, and `ANY_LOW`
  fires. Keep the RTC pull-up alive: `esp_sleep_pd_config(ESP_PD_DOMAIN_RTC_PERIPH, ESP_PD_OPTION_ON)`
  then `rtc_gpio_pulldown_dis()` + `rtc_gpio_pullup_en()` on the wake pin. (Costs a little
  deep-sleep current to keep the RTC domain on — a deliberate trade for a reliable wake.)
- **The button is still held/bouncing at sleep time.** If the pin is low when you sleep, you
  wake on it instantly. Poll it high (with a short timeout) before sleeping; if it won't
  settle, abort and retry on the next idle window. Also bail if it's held at entry.

Verify the pin with `esp_sleep_is_valid_wakeup_gpio()` and arm with the IDF-5 API
`esp_sleep_enable_ext1_wakeup_io(1ULL << pin, ESP_EXT1_WAKEUP_ANY_LOW)`. On wake the chip
**resets** (it does not resume) — `esp_reset_reason()` / `esp_sleep_get_wakeup_cause()` /
`esp_sleep_get_ext1_wakeup_status()` logged at the top of `app_main` tell you why you booted.
Design consequence: deep sleep **drops the BLE link** — the host sees a disconnect and can't
reconnect until the user wakes the device. If the host must be able to wake it, use light
sleep, not deep sleep (see `esp-idf-structure.md` → Power management).

## A piped build hides failures

`idf.sh build | tail` returns **`tail`'s** exit code (0), so a failed build looks like it
passed. Redirect to a file and check the real status (`idf.sh build > log 2>&1; echo $?`),
then grep the log for `error:` / `ninja: build stopped`. (Also seen: a wrapper script
losing its `+x` bit → `permission denied: ./idf.sh`; `chmod +x` and commit it.)

## Docker build + host flash: a Docker `build/` won't cross to the host

The pinned build runs in Docker (`./idf.sh build`), which bakes container paths (`/project`)
into `build/CMakeCache.txt`. A later host `idf.py flash`/`build` re-runs CMake, sees the path
mismatch, and aborts: *"CMakeCache.txt directory is different … HINT: run idf.py fullclean."*
`fullclean` itself runs CMake and hits the same wall, so it can't clean either.

- **Flash without re-configuring.** Docker can't reach `/dev/cu.*` on macOS anyway, so flash
  from the host straight from the built binaries with esptool, driven by
  `build/flasher_args.json` — no CMake involved. `examples/pager-buddy/firmware/flash.sh` does
  exactly this, so **`./idf.sh build` then `./flash.sh [PORT]`** is the standard cycle. Because
  it never touches the cmake cache or `managed_components/`, it also works unchanged **from a
  git worktree**.
- **If you must host-build** (e.g. quick iteration, or the host sim), `rm -rf build` first —
  *not* `idf.py fullclean`, which is wedged by the same mismatch — then `idf.py build`. A
  Docker `build/` and a host `build/` can't share one directory; clean between, or keep them
  in separate checkouts.

## ES8311 audio: playback ≠ capture, and the amp may need a kick

`esp_codec_dev` + ES8311 is the same part for record and play, but the config differs:
an output path is an I²S **TX** channel (`i2s_new_channel(&cfg, &tx, NULL)`),
`es8311_codec_cfg.codec_mode = ESP_CODEC_DEV_WORK_MODE_DAC`, and
`esp_codec_dev_cfg.dev_type = ESP_CODEC_DEV_TYPE_OUT` — mirror an existing capture
component but flip those three. Loudness is free: `esp_codec_dev_set_out_vol(dev, 0..100)`
— don't scale the PCM for volume, generate it near full-scale and let the codec attenuate.
Reuse the board's shared I²C bus handle for codec control (pass `.bus_handle`); don't open a
second bus. **The speaker amp enable is easy to miss:** a class-D PA (e.g. M5's AW8737) has a
shutdown/enable line, and the DAC opens cleanly with *no error* while the speaker stays
silent if it's not asserted. It is **not always an ESP32 GPIO** — on the M5StickC S3 the PA
enable is a **PMIC pin (M5PM1 GPIO3)**, so the codec's `pa_pin` stays `-1` and you toggle the
amp through the PMIC instead (cross-checked against xiaozhi-esp32's `m5stack-stick-s3` board:
`AUDIO_CODEC_GPIO_PA = GPIO_NUM_NC`, "PA control via PM1_G3"). Gate the amp to the playback
window and only enable it once the I²S line is driving silence (`auto_clear`) — powering it
into a floating input hisses/pops. If a board reference exists for your exact part, read its
PA wiring before guessing `pa_pin`.
