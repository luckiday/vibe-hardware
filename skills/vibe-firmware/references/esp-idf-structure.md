# ESP-IDF: modular firmware structure

How to lay out an ESP-IDF firmware as **layered components** so it stays testable,
reusable across boards, and OTA-ready — instead of one giant `main.c`. Distilled from
the in-repo worked example (`examples/pager-buddy/firmware/`) and a studied reference
design (`78/voicestick` — ESP-IDF firmware for the same M5StickC S3; clone it locally
to read — see [`docs/awesome-firmware.md`](../../../docs/awesome-firmware.md)). Keep
your own code generic; this is the method.

## Contents
- [The shape: three layers, thin main](#the-shape)
- [Board-support layer (BSP)](#bsp)
- [Domain components](#domains)
- [Connectivity: a transport-agnostic link component](#connectivity)
- [main: thin orchestrator](#main)
- [sdkconfig.defaults: the platform contract](#sdkconfig)
- [Partitions + OTA: dual-slot from day one](#ota)
- [Managed components: idf_component.yml + the lockfile](#managed)
- [Power management (battery devices)](#pm)
- [Bring-up & flashing gotchas](bringup-gotchas.md)

<a name="the-shape"></a>
## The shape: three layers, thin main

```
firmware/
  CMakeLists.txt              # 3 lines: include project.cmake + project(<name>)
  sdkconfig.defaults          # the platform contract (target/flash/PSRAM/partitions/PM/console)
  partitions_ota.csv          # dual-slot OTA layout
  main/
    CMakeLists.txt            # REQUIRES the board + domain components + system deps
    idf_component.yml         # third-party managed deps (e.g. espressif/button)
    main.c                    # THIN: init each layer, then run the app loop
  components/
    <board>_board/            # BSP — the only place pins live  (see below)
      include/<board>_board.h
      <board>_board.c
      CMakeLists.txt
    <domain>/                 # one component per function: ui/display, audio, net, ...
      include/<domain>.h      # the component's ONLY public surface
      <domain>.c
      assets/                 # EMBED_FILES (icons/sprites) live with the component
      CMakeLists.txt
      idf_component.yml       # the domain's own managed deps (lvgl, esp_codec_dev, ...)
```

**Dependency rule:** `domains → BSP → IDF drivers`, and `main → everything`. Lower
layers never call up. **Each peripheral is touched in exactly one place** — so a board
swap or a sensor swap is a localized edit, and a domain is unit-reasonable on its own.

<a name="bsp"></a>
## Board-support layer (BSP)

The `<board>_board` component is the **single home for board specifics**. Its public
header is the config-as-code the skill preaches — and it must mirror the PCB
[`pinmap.yaml`](../../vibe-pcb/references/spec-template.md) contract.

```c
// components/<board>_board/include/<board>_board.h — the ONLY place pin numbers live
#pragma once
#include "esp_err.h"
#include "driver/i2c_master.h"

#define BOARD_PIN_I2C_SDA 47
#define BOARD_PIN_I2C_SCL 48
// ... every pin. Add a perspective comment where a name is ambiguous, e.g. codec
//     DIN/DOUT are named from the CODEC's view (DIN = MCU->codec = speaker path).

esp_err_t board_init(void);                       // bring up clocks, I2C, PMIC, ...
i2c_master_bus_handle_t board_i2c_bus(void);      // hand out the shared bus
esp_err_t board_battery_level(int *pct);          // via the PMIC (hide the register map)
bool board_button_front_pressed(void);
void board_prepare_deep_sleep(void);
```

- CMake stays minimal: `REQUIRES driver esp_driver_i2c` — only the low-level drivers it
  needs. The BSP depends *down*, never on a domain.
- **Nothing outside the BSP reads a raw GPIO or talks to the PMIC.** Domains ask the
  board (`board_i2c_bus()`, `board_battery_level()`), so they're board-agnostic.

<a name="domains"></a>
## Domain components

One component per function (display/UI, audio, connectivity, sensors). Each:

- exposes **one public header** `include/<domain>.h` — `init` + intent verbs + callback
  typedefs. Keep the implementation (and private headers) out of `INCLUDE_DIRS`'s public
  entry. The header is the contract; the `.c` is hidden.
- declares deps in **two** places: sibling/IDF components in CMake `REQUIRES`;
  third-party in `idf_component.yml`.
- bundles its own assets and embeds them:

```cmake
idf_component_register(
    SRCS "ui_status.c" "ui_status_icons.c"
    INCLUDE_DIRS "include" "."          # "include" = public API; "." = private impl hdrs
    EMBED_FILES "assets/icon_ready.bin" "assets/icon_error.bin"
    REQUIRES esp_lcd lvgl <board>_board  # IDF components + the BSP
)
```

**Drive a domain by intent, not internals.** The UI component owns *how* it renders;
callers say *what* state to show: `ui_status_set_ready()`, `ui_status_set_error(msg)`,
`ui_status_set_ota_progress(written, size)`. The display logic never leaks into `main`.

<a name="connectivity"></a>
## Connectivity: a transport-agnostic link component

A network/link domain (the "talk to a host service" component) is just another domain —
but two patterns earn their keep:

**Keep the API transport-agnostic.** Expose *what data arrived*, not *how*: e.g.
`bridge_start()`, `bridge_online()`, `bridge_seq()` (bumps per message), and a
borrow/release pair that hands `main` the parsed model under a lock. In the worked
example this exact surface survived a **Wi-Fi+HTTP → BLE swap with zero changes to
`main`** — only the component's `.c` changed. The link is a *data producer*; it never
calls the UI.

**BLE: the device is a GATT _peripheral_ (server); the host is the _central_.** Modeled
on the studied `voice_ble` reference (NimBLE). Minimal shape:

- **Inbound** (host → device) = a characteristic with `BLE_GATT_CHR_F_WRITE`; its
  `access_cb` receives the bytes. **Outbound** (device → host) = a `…_F_NOTIFY`
  characteristic (`ble_gatts_notify_custom`).
- **Chunk anything bigger than one ATT write.** A write carries ≤ `MTU − 3` bytes
  (≈ 244 at MTU 247). Frame a larger payload (e.g. a JSON snapshot) as
  `[ver, flags] + chunk` with START/END flags and **reassemble device-side** into a
  buffer, parse on END. A bad/partial message self-heals if the host re-sends.
- **Initiate the MTU exchange from the device** (`ble_gattc_exchange_mtu`) on connect —
  some centrals never do, leaving you stuck at the 23-byte default.
- No bonding for a LAN-local toy (`ble_hs_cfg.sm_bonding = 0`); advertise a service UUID
  + a name (`pg-XXXX` from the MAC). Match on the **service UUID** host-side — the GAP
  *name* is cached by the OS and can be stale (a re-flashed unit may still show an old name).

**A clock-less device gets its time from the link.** No RTC/NTP → the device has no wall
clock. Carry an epoch + a human clock string in the message, anchor on it plus a
**monotonic timer** (`now ≈ msg_ts + esp_timer_elapsed`), and derive/age everything from
that — so the display stays correct *between* messages and while disconnected. Have the
host re-stamp the time fields on each serve so the anchor never goes stale. (Wire-format
+ freshness semantics belong in the contract — see `vibe-plm`.)

<a name="main"></a>
## main: thin orchestrator

`main` is itself a component. Its `CMakeLists.txt` `REQUIRES` the BSP + every domain +
system/managed deps; `app_main` initializes each layer then runs the app. Keep app-level
*policy* here (interaction modes, dim/sleep timers, PM locks) and peripheral *detail* in
the components.

**Decouple with callbacks + a queue + a state machine** — don't call between domains
directly:

```c
typedef enum { APP_EVT_BTN_DOWN, APP_EVT_BLE_CONNECTED, APP_EVT_OTA_PROGRESS, /*...*/ } app_event_type_t;
typedef struct { app_event_type_t type; uint32_t a, b; char text[96]; } app_event_t;
static QueueHandle_t s_events;            // ISRs / BLE cbs / timers POST; one task CONSUMES

// app_main():
//   board_init(); ui_status_init(); audio_pipeline_init(); voice_ble_init();
//   voice_ble_set_control_callback(on_control);     // components report UP via callbacks
//   s_events = xQueueCreate(...); xTaskCreate(app_task, ...);
// app_task(): for(;;){ xQueueReceive(...); switch(evt.type){ ... drive app_ui_state_t ... } }
```

This keeps each domain independent (it only posts events / invokes a registered
callback) and makes `main` the single conductor with one explicit state enum.

<a name="sdkconfig"></a>
## sdkconfig.defaults: the platform contract

Check this in; the generated `sdkconfig` is gitignored. Declare the whole platform:

```
CONFIG_IDF_TARGET="esp32s3"
CONFIG_ESPTOOLPY_FLASHMODE_QIO=y
CONFIG_ESPTOOLPY_FLASHSIZE_8MB=y
CONFIG_SPIRAM=y
CONFIG_SPIRAM_MODE_OCT=y
CONFIG_SPIRAM_USE_MALLOC=y                 # let malloc use PSRAM
CONFIG_PARTITION_TABLE_CUSTOM=y
CONFIG_PARTITION_TABLE_CUSTOM_FILENAME="partitions_ota.csv"
CONFIG_FREERTOS_HZ=1000
CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y       # see gotcha
# + subsystems you use: NimBLE (CONFIG_BT_NIMBLE_ENABLED), PM (below), LVGL fonts, ...
```

> **Gotcha — no serial on a native-USB S3.** An ESP32-S3 whose USB-C goes straight to
> the chip (no UART bridge) shows **nothing on UART0**. Set
> `CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG=y`, or you'll think the board is dead when it's
> just logging to a console you're not watching. (M5StickC S3 is native-USB.)

<a name="ota"></a>
## Partitions + OTA: dual-slot from day one

```
# partitions_ota.csv  — Name, Type, SubType, Offset,  Size
nvs,      data, nvs,     0x9000,   0x4000,
otadata,  data, ota,     0xd000,   0x2000,
phy_init, data, phy,     0xf000,   0x1000,
ota_0,    app,  ota_0,   0x10000,  0x300000,
ota_1,    app,  ota_1,   0x310000, 0x300000,
storage,  data, spiffs,  0x610000, 0x1f0000,
```

- Ship the dual-slot table **even before OTA exists**, so a field update never forces a
  flash re-layout (which would wipe user data).
- Enable rollback (`CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE`) and only
  `esp_ota_mark_app_valid_cancel_rollback()` **after** a self-health-check passes.
- The transfer protocol (begin/data/end/abort + progress events) belongs in the
  connectivity component, surfaced to `main` via a callback — not in `main` itself.
- **Never publish an OTA without a real-hardware test first** (the skill's hard rule).

<a name="managed"></a>
## Managed components: idf_component.yml + the lockfile

```yaml
# main/idf_component.yml (or a component's own)
dependencies:
  espressif/button: "^4.1.6"
  espressif/esp_codec_dev: "*"
```

- `idf.py` resolves these into `managed_components/` and writes `dependencies.lock`.
- **Commit `dependencies.lock`** (exact resolved versions = reproducible builds);
  **gitignore `managed_components/`** (re-fetched on build). This is the firmware analog
  of the skill's "pinned, reproducible" rule.

<a name="pm"></a>
## Power management (battery devices)

```
CONFIG_PM_ENABLE=y
CONFIG_FREERTOS_USE_TICKLESS_IDLE=y
CONFIG_FREERTOS_IDLE_TIME_BEFORE_SLEEP=3
```

- Hold an `esp_pm_lock` (`ESP_PM_NO_LIGHT_SLEEP` / `ESP_PM_CPU_FREQ_MAX`) **only across
  latency- or throughput-critical phases** (recording, an OTA transfer); release it
  after, so the device idles cheaply the rest of the time.
- Drive display-dim and deep-sleep off inactivity timers; let the BSP own
  `board_prepare_deep_sleep()` (configure wake pins, quiesce peripherals).
