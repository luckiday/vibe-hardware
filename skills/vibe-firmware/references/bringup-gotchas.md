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

## A piped build hides failures

`idf.sh build | tail` returns **`tail`'s** exit code (0), so a failed build looks like it
passed. Redirect to a file and check the real status (`idf.sh build > log 2>&1; echo $?`),
then grep the log for `error:` / `ninja: build stopped`. (Also seen: a wrapper script
losing its `+x` bit → `permission denied: ./idf.sh`; `chmod +x` and commit it.)
