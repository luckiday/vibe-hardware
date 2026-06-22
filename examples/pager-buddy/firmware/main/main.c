// pager-buddy — display UI on the M5StickC S3, fed by the Mac bridge over BLE.
//
// Layered per vibe-firmware: BSP (stick_s3_board) owns pins/PMIC/buttons; ui owns the
// ST7789 + LVGL screens; bridge is a BLE peripheral that receives Claude Code status
// snapshots from the Mac. This thin main holds the UI state machine, binds whatever
// the bridge last received (showing "Connecting" until the first snapshot), pumps
// LVGL, and polls the two buttons. Mirrors examples/pager-buddy/design/.
//   SIDE (KEY2) = cycle highlight (wraps) · FRONT (KEY1) = OK · hold FRONT = back.

#include <stdio.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/rtc_io.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_pm.h"
#include "esp_sleep.h"
#include "esp_system.h"
#include "stick_s3_board.h"
#include "ui.h"
#include "bridge.h"
#include "audio.h"

static const char *TAG = "pager";

// --- low-power auto sleep (tiered, modeled on voicestick) ---
// Only sleeps when nothing is running — any working/waiting/asking session keeps the
// screen fully on (see sleep_eligible). When everything is done/idle:
// Tier 1 (screen off): after SCREEN_OFF_AFTER, blank the backlight and release the
//   no-light-sleep lock so the CPU light-sleeps between BLE events — the link stays up,
//   so a button or a Mac push lights the screen straight back up.
// Tier 2 (deep): once the screen has been off for DEEP_AFTER_SCREEN and we're still idle
//   AND unplugged, power down and wake on FRONT (GPIO11, ext1). NOTE: BLE is OFF in deep
//   sleep — the Mac can't wake the pager; the user presses FRONT, the chip reboots,
//   re-advertises, and the Mac reconnects. (ESP32-S3 can't BLE-wake from deep sleep;
//   that's why the light tier exists.)
#define SCREEN_OFF_AFTER_US   (60ULL  * 1000 * 1000)   // all-done idle → blank screen (tier 1)
#define DEEP_AFTER_SCREEN_US  (300ULL * 1000 * 1000)   // blanked → deep sleep (tier 2)
#define WAKE_GPIO             BOARD_PIN_BTN_FRONT       // FRONT (KEY1) wakes from deep sleep

static int64_t s_last_activity_us;   // monotonic time of the last button/BLE activity
static int64_t s_screen_off_us;      // when the screen blanked (starts the tier-2 countdown)
static bool    s_screen_off;         // tier-1 state: backlight blanked, BLE still up
static esp_pm_lock_handle_t s_no_light_sleep;  // held while the screen is ON (no light sleep → no LCD flicker)

static app_model_t M = {
    .clock = "--:--", .date = "", .battery = 78, .charging = false, .usb = false,
    .online = false, .connecting = true,
    .sessions = NULL, .n = 0, .view = VIEW_IDLE, .open = -1, .sel = 0,
};

// --- local clock (keeps the time correct between snapshots AND while unpaired) ---
// The Mac only sends "HH:MM" on a snapshot, and once the link drops it sends nothing at
// all. So we anchor the last received time to the local monotonic clock and extrapolate
// each tick — the display keeps ticking off the previous value, no Mac required. Every
// new snapshot re-anchors, correcting any drift. Minute resolution matches the display.
static bool    s_clock_valid;        // a "HH:MM" has been received at least once
static int     s_clock_anchor_min;   // minutes-since-midnight at the anchor
static int64_t s_clock_anchor_us;    // esp_timer_get_time() at the anchor
static char    s_clock_buf[16];      // "HH:MM" — what M.clock points at once valid (roomy: silences -Wformat-truncation)

static void clock_anchor(const char *hhmm) {
    if (!hhmm || !hhmm[0]) return;
    int h, mm;
    if (sscanf(hhmm, "%d:%d", &h, &mm) != 2) return;
    if (h < 0 || h > 23 || mm < 0 || mm > 59) return;
    s_clock_anchor_min = h * 60 + mm;
    s_clock_anchor_us  = esp_timer_get_time();
    s_clock_valid = true;
}

// Re-point M.clock at the extrapolated current time. No-op (leaves "--:--") until the
// first snapshot has anchored the clock.
static void clock_tick(void) {
    if (!s_clock_valid) return;
    int64_t mins = (esp_timer_get_time() - s_clock_anchor_us) / 60000000LL;
    int64_t tod = ((int64_t)s_clock_anchor_min + mins) % 1440;
    if (tod < 0) tod += 1440;                       // normalise to [0,1439]
    snprintf(s_clock_buf, sizeof s_clock_buf, "%02d:%02d", (int)(tod / 60), (int)(tod % 60));
    M.clock = s_clock_buf;
}

// Point M at live bridge data when a snapshot has arrived, else show "Connecting". Call
// with the bridge lock held (bridge_borrow). Clamps open/selection to the current count.
static void bind_model(const bridge_view_t *lv) {
    if (lv) {                       // a snapshot has been received (n may be 0 = all clear)
        M.connecting = false;
        M.sessions = lv->sessions;
        M.n = lv->n;
        if (lv->date && lv->date[0]) M.date = lv->date;
    } else {                        // no snapshot yet → "Connecting" screen (clock keeps ticking)
        M.connecting = true;
        M.sessions = NULL;
        M.n = 0;
    }
    if (M.open >= M.n) { M.open = -1; if (M.view == VIEW_SESSION) M.view = VIEW_LIST; }
}

static int item_count(void) {
    if (M.view == VIEW_LIST) return M.n;
    if (M.view == VIEW_SESSION && M.open >= 0 && M.open < M.n) {
        switch (M.sessions[M.open].state) {
            case ST_WAITING: return 2;
            case ST_ASKING:  return M.sessions[M.open].ask_n;
            case ST_DONE:    return 0;   // no action bar — back returns to the list, leaves it done
            default:         return 0;
        }
    }
    return 0;
}

static void do_scroll(void) {
    if (M.view == VIEW_IDLE) {
        if (M.n == 0) return;           // nothing to list; stay on idle / all-clear screen
        M.view = VIEW_LIST; M.sel = 0; return;
    }
    int n = item_count();
    if (n) M.sel = (M.sel + 1) % n;
}
static void do_ok(void) {
    if (M.view == VIEW_IDLE) {
        if (M.n == 0) return;           // nothing to list; stay on idle / all-clear screen
        M.view = VIEW_LIST; M.sel = 0; return;
    }
    if (M.view == VIEW_LIST) {
        if (M.n == 0) return;
        M.open = M.sel;
        M.view = VIEW_SESSION;
        M.sel = (M.sessions[M.open].state == ST_WAITING) ? 1 : 0;  // default Allow
        return;
    }
    if (M.view == VIEW_SESSION && M.open >= 0 && M.open < M.n) {
        session_t *s = &M.sessions[M.open];
        const char *action = NULL;
        if (s->state == ST_WAITING) {
            action = (M.sel == 1) ? "allow" : "deny";  // M.sel=1 is Allow (line 120: default Allow)
        } else if (s->state == ST_ASKING && M.sel >= 0 && M.sel < s->ask_n) {
            action = s->ask_opts[M.sel];
        }
        if (action && s->id) {                         // drive Claude Code: send the decision to the Mac
            bridge_send_resolution(s->id, action);
        }
        if (s->state == ST_WAITING || s->state == ST_ASKING) {  // optimistic ACK; Mac's next snapshot corrects it
            s->state = ST_WORKING;                     // (DONE just goes back — it stays done, not blue)
        }
        M.open = -1; M.view = VIEW_LIST;
    }
}
static void do_back(void) {
    if (M.view == VIEW_SESSION) { M.open = -1; M.view = VIEW_LIST; }
    else if (M.view == VIEW_LIST) { M.view = VIEW_IDLE; M.sel = 0; }
}

// --- sleep helpers ---

// Reset the idle clock and, if the screen was blanked (tier 1), wake it back on.
// Returns true if it un-blanked (so the caller forces a redraw).
static bool note_activity(void) {
    s_last_activity_us = esp_timer_get_time();
    if (s_screen_off) {
        ui_set_backlight(true);
        s_screen_off = false;
        if (s_no_light_sleep) esp_pm_lock_acquire(s_no_light_sleep);  // screen on → block light sleep
        return true;
    }
    return false;
}

// Eligible for deep sleep = nothing needs attention. A live snapshot with any
// session WORKING/WAITING/ASKING blocks sleep (it will transition, or it needs the
// user); DONE/ERROR are settled. No live snapshot (unpaired/connecting) is also eligible.
static bool sleep_eligible(bool have_live) {
    if (!have_live) return true;
    for (int i = 0; i < M.n; i++) {
        switch (M.sessions[i].state) {
            case ST_WORKING: case ST_WAITING: case ST_ASKING: return false;
            default: break;
        }
    }
    return true;
}

// Power down and arm the front button as the wake source. Returns (after resetting
// the idle clock) only if it bailed — plugged in, button held, or wake-arm failed;
// otherwise it never returns (the chip reboots on wake). Mirrors voicestick.
static void enter_deep_sleep(void) {
    // Re-read power at the last moment — never deep-sleep on USB/charger.
    bool chg = false, usb = false;
    board_battery_charging(&chg);
    board_usb_powered(&usb);
    if (chg || usb) {
        ESP_LOGI(TAG, "skip deep sleep: charging=%d usb=%d", chg, usb);
        note_activity();
        return;
    }
    if (!esp_sleep_is_valid_wakeup_gpio(WAKE_GPIO)) {
        ESP_LOGE(TAG, "GPIO%d cannot wake from deep sleep", WAKE_GPIO);
        note_activity();
        return;
    }
    if (gpio_get_level(WAKE_GPIO) == 0) {           // FRONT held → don't sleep into a press
        note_activity();
        return;
    }

    ESP_LOGI(TAG, "entering deep sleep — wake on FRONT (GPIO%d low)", WAKE_GPIO);
    ui_prepare_deep_sleep();         // panel + backlight off
    board_prepare_deep_sleep();      // cut the LCD rail via the PMIC

    // Clear any stale wake bits, keep the RTC pull-up effective on the wake pin so
    // it doesn't float low and self-wake, then arm ext1 on a low level.
    (void)esp_sleep_disable_wakeup_source(ESP_SLEEP_WAKEUP_ALL);
    (void)esp_sleep_pd_config(ESP_PD_DOMAIN_RTC_PERIPH, ESP_PD_OPTION_ON);
    (void)rtc_gpio_pulldown_dis(WAKE_GPIO);
    (void)rtc_gpio_pullup_en(WAKE_GPIO);
    esp_err_t err = esp_sleep_enable_ext1_wakeup_io(1ULL << WAKE_GPIO, ESP_EXT1_WAKEUP_ANY_LOW);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "arm ext1 wake failed: %s", esp_err_to_name(err));
        note_activity();
        return;
    }

    // Wait for the pin to settle high (release bounce); if it stays low we'd just
    // wake immediately, so abort and retry on the next idle window.
    int wait_ms = 0;
    while (gpio_get_level(WAKE_GPIO) == 0 && wait_ms < 200) { vTaskDelay(pdMS_TO_TICKS(10)); wait_ms += 10; }
    if (gpio_get_level(WAKE_GPIO) == 0) {
        ESP_LOGW(TAG, "FRONT still low after %d ms — abort deep sleep", wait_ms);
        note_activity();
        return;
    }
    esp_deep_sleep_start();          // does not return; wake = reset → app_main re-runs
}

void app_main(void) {
    ESP_LOGI(TAG, "boot reset=%d wake=%d ext1=0x%llx", esp_reset_reason(),
             esp_sleep_get_wakeup_cause(),
             (unsigned long long)esp_sleep_get_ext1_wakeup_status());

    ESP_ERROR_CHECK(board_init());
    ui_init();
    bridge_start();                       // BLE peripheral; advertises for the Mac bridge
    M.device = bridge_device_name();      // "pg-XXXX" — pairing hint on the Connecting screen
    audio_init();                         // ES8311 speaker for alert tones (shares board I²C)
    ui_render(&M);
    ESP_LOGI(TAG, "ready — SIDE=scroll  FRONT=OK  hold FRONT=back");

    // Automatic light sleep: park the CPU between BLE events while keeping the link
    // up (needs CONFIG_PM_ENABLE + BT modem sleep). Configure after the BLE stack is
    // running so the controller registers its sleep callbacks first.
    const esp_pm_config_t pm = {
        .max_freq_mhz = CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ,
        .min_freq_mhz = CONFIG_XTAL_FREQ,
        .light_sleep_enable = true,
    };
    ESP_ERROR_CHECK_WITHOUT_ABORT(esp_pm_configure(&pm));

    // Hold a no-light-sleep lock while the screen is ON: automatic light sleep glitches
    // the SPI/LCD mid-use (visible flicker). It's released only when the screen blanks
    // (tier 1), so the light-sleep battery win — with BLE still up — kicks in exactly then.
    ESP_ERROR_CHECK_WITHOUT_ABORT(
        esp_pm_lock_create(ESP_PM_NO_LIGHT_SLEEP, 0, "screen_on", &s_no_light_sleep));
    if (s_no_light_sleep) esp_pm_lock_acquire(s_no_light_sleep);

    bool pf = false, ps = false, front_long = false;
    int64_t front_down = 0, last_batt = 0, last_tick = 0;
    uint32_t last_seq = 0;
    int last_n = -1;   // detect sessions appearing/pruning between snapshots (forces a rebuild)
    int prev_waiting = 0, prev_asking = 0, prev_done = 0;   // per-state counts → alert on a new one
    s_last_activity_us = esp_timer_get_time();   // start the idle clock at boot/wake

    for (;;) {
        uint32_t wait = ui_tick();          // pump LVGL; returns ms to next call
        uint32_t cap = s_screen_off ? 150 : 30;   // blanked → poll slower, light-sleep longer
        if (wait > cap) wait = cap;
        if (wait < 5) wait = 5;
        vTaskDelay(pdMS_TO_TICKS(wait));
        bool dirty = false;
        bool act_ok = false, act_back = false, act_scroll = false;

        // FRONT (KEY1): short = OK, long (>500 ms) = back
        bool f = board_btn_front();
        if (f && !pf) { front_down = esp_timer_get_time(); front_long = false; }
        if (f && !front_long && esp_timer_get_time() - front_down > 500000) {
            front_long = true; act_back = true; ESP_LOGI(TAG, "FRONT long -> back");
        }
        if (!f && pf && !front_long) { act_ok = true; ESP_LOGI(TAG, "FRONT short -> ok"); }
        pf = f;

        // SIDE (KEY2): tap = scroll
        bool s = board_btn_side();
        if (s && !ps) { act_scroll = true; ESP_LOGI(TAG, "SIDE -> scroll"); }
        ps = s;

        // FRONT = ACK/silence: cut any tone still playing (pinmap: "KEY1 front — ACK/silence")
        if (act_ok || act_back) audio_stop();

        // battery ~2 s — device-owned (not on the wire); real if the PMIC answers
        if (esp_timer_get_time() - last_batt > 2000000) {
            last_batt = esp_timer_get_time();
            int pct; bool chg = false, usb = false;
            if (board_battery_level(&pct) == ESP_OK) {
                int d = pct - M.battery; if (d < 0) d = -d;
                if (d >= 2) { M.battery = pct; dirty = true; }   // ignore ±1% PMIC jitter → no needless rebuild/flash
            }
            board_battery_charging(&chg);
            board_usb_powered(&usb);
            if (chg != M.charging || usb != M.usb) { M.charging = chg; M.usb = usb; dirty = true; }
        }

        // new snapshot from the bridge?
        uint32_t seq = bridge_seq();
        bool new_snap = (seq != last_seq);
        if (new_snap) { last_seq = seq; dirty = true; }

        // BLE link state for the status-bar Bluetooth glyph — flips without a snapshot
        // when the central connects/drops, so poll it and repaint on change.
        bool online = bridge_online();
        if (online != M.online) { M.online = online; dirty = true; }

        // audio settings the Mac pushed over the control characteristic. Done OUTSIDE
        // the bridge lock (bridge_take_settings takes it itself — calling it between
        // bridge_borrow/bridge_release would deadlock the non-recursive mutex).
        bool aud_en; int aud_vol;
        if (bridge_take_settings(&aud_en, &aud_vol)) {
            audio_set_enabled(aud_en);
            audio_set_volume(aud_vol);
        }

        // ~1 Hz heartbeat so the bridge-anchored clock + session ages tick on screen.
        // Update those labels IN PLACE (ui_refresh_time) rather than a full ui_render,
        // so the marquee scroll of long names/tasks isn't reset every second.
        bool tick = (esp_timer_get_time() - last_tick > 1000000);
        if (tick) last_tick = esp_timer_get_time();

        // Any button or a fresh snapshot is activity: reset the idle clock and, if the
        // screen was blanked (tier 1), light it back on. This is how a Mac push wakes
        // the screen while the link is alive in light sleep.
        if (f || s || act_ok || act_back || act_scroll || new_snap) {
            if (note_activity()) dirty = true;   // un-blanked → force a redraw
        }

        // bind + apply events + render, all under the bridge lock (the live session
        // strings the renderer reads stay stable until bridge_release()).
        const bridge_view_t *lv = bridge_borrow();
        bool have_live = (lv != NULL);
        bind_model(lv);
        if (new_snap && lv) clock_anchor(lv->clock);   // re-sync the local clock to the Mac
        clock_tick();                                  // extrapolate "HH:MM" so it ticks unpaired too
        if (M.n != last_n) { last_n = M.n; dirty = true; }   // a session appeared/pruned → rebuild

        // Alert tones: on a fresh snapshot, beep once when a needs-you/done state newly
        // appears (count went up). Distinct tone per state; waiting wins if several rise
        // at once. Count-based (no per-session id at this layer) — fine for the demo.
        if (new_snap) {
            int cw = 0, ca = 0, cd = 0;
            for (int i = 0; i < M.n; i++) {
                switch (M.sessions[i].state) {
                    case ST_WAITING: cw++; break;
                    case ST_ASKING:  ca++; break;
                    case ST_DONE:    cd++; break;
                    default: break;
                }
            }
            if      (cw > prev_waiting) audio_alert(AUDIO_ALERT_WAITING);
            else if (ca > prev_asking)  audio_alert(AUDIO_ALERT_ASKING);
            else if (cd > prev_done)    audio_alert(AUDIO_ALERT_DONE);
            prev_waiting = cw; prev_asking = ca; prev_done = cd;
        }

        if (act_scroll) { do_scroll(); dirty = true; }
        if (act_back)   { do_back();   dirty = true; }
        else if (act_ok){ do_ok();     dirty = true; }
        bool eligible = sleep_eligible(have_live);   // reads session states under the lock
        if (!s_screen_off) {                         // skip drawing into a blanked panel
            if (dirty)     ui_render(&M);
            else if (tick) ui_refresh_time(&M);      // clock/age tick only — marquee preserved
        }
        bridge_release();

        // --- sleep tiers (only when nothing is running) ---
        int64_t now = esp_timer_get_time();
        int64_t idle = now - s_last_activity_us;
        // Tier 1: everything done/idle for a minute → blank the screen and allow light
        // sleep (release the lock). A running session (eligible=false) keeps it lit.
        if (!s_screen_off && eligible && idle > SCREEN_OFF_AFTER_US) {
            ui_set_backlight(false); s_screen_off = true; s_screen_off_us = now;
            if (s_no_light_sleep) esp_pm_lock_release(s_no_light_sleep);
            ESP_LOGI(TAG, "screen off (all done %llus) — BLE stays up", idle / 1000000);
        }
        // Tier 2: blanked long enough, still idle AND unplugged → deep sleep.
        if (s_screen_off && eligible && !M.charging && !M.usb &&
            (now - s_screen_off_us) > DEEP_AFTER_SCREEN_US) {
            enter_deep_sleep();   // never returns unless it bailed (then idle clock is reset)
        }
    }
}
