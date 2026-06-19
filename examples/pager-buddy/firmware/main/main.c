// pager-buddy — display UI on the M5StickC S3, fed by the Mac bridge over BLE.
//
// Layered per vibe-firmware: BSP (stick_s3_board) owns pins/PMIC/buttons; ui owns the
// ST7789 + LVGL screens; bridge is a BLE peripheral that receives Claude Code status
// snapshots from the Mac. This thin main holds the UI state machine, binds whatever
// the bridge last received (falling back to stub data until the first snapshot), pumps
// LVGL, and polls the two buttons. Mirrors examples/pager-buddy/design/.
//   SIDE (KEY2) = cycle highlight (wraps) · FRONT (KEY1) = OK · hold FRONT = back.

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "stick_s3_board.h"
#include "ui.h"
#include "bridge.h"

static const char *TAG = "pager";

// --- stub data (shown until the first BLE snapshot arrives; same sample as the mock) ---
static const char *deploy_opts[] = {"Production", "Staging", "Local only"};
static const char *act_fix[]     = {"Edit(src/auth/middleware.ts)"};
static const char *act_backend[] = {"Write(src/routes/users.ts)"};
static const char *act_opt[]     = {"Analyzing the slow queries", "Read(schema.prisma)",
                                    "Edit(src/db/client.ts)"};

static session_t stub_sessions[] = {
    {.name = "fix auth bug", .agent = "Claude", .term = "iTerm", .age = "27m", .state = ST_WORKING,
     .appr_tool = "Edit", .appr_file = "src/auth/middleware.ts", .add = 3, .del = 1,
     .ask_q = "Which deployment target?", .ask_opts = deploy_opts, .ask_n = 3,
     .done_summary = "Fixed the auth bug.", .files = 3, .tests = "8 passed",
     .act = act_fix, .act_n = 1},
    {.name = "backend server", .agent = "Codex", .term = "Terminal", .age = "1h", .state = ST_WORKING,
     .act = act_backend, .act_n = 1},
    {.name = "optimize queries", .agent = "Gemini", .term = "Ghostty", .age = "5h", .state = ST_WORKING,
     .act = act_opt, .act_n = 3},
};
#define STUB_N ((int)(sizeof(stub_sessions) / sizeof(stub_sessions[0])))

static app_model_t M = {
    .clock = "--:--", .date = "", .battery = 78, .charging = false, .usb = false,
    .sessions = stub_sessions, .n = STUB_N, .view = VIEW_IDLE, .open = -1, .sel = 0,
};

// Point M at live bridge data when a snapshot has arrived, else the stub. Call with
// the bridge lock held (bridge_borrow). Clamps open/selection to the current count.
static void bind_model(const bridge_view_t *lv) {
    if (lv) {                       // a snapshot has been received (n may be 0 = all clear)
        M.sessions = lv->sessions;
        M.n = lv->n;
        if (lv->clock && lv->clock[0]) M.clock = lv->clock;
        if (lv->date  && lv->date[0])  M.date  = lv->date;
    } else {                        // no snapshot yet → stub sample
        M.sessions = stub_sessions;
        M.n = STUB_N;
    }
    if (M.open >= M.n) { M.open = -1; if (M.view == VIEW_SESSION) M.view = VIEW_LIST; }
}

static int item_count(void) {
    if (M.view == VIEW_LIST) return M.n;
    if (M.view == VIEW_SESSION && M.open >= 0 && M.open < M.n) {
        switch (M.sessions[M.open].state) {
            case ST_WAITING: return 2;
            case ST_ASKING:  return M.sessions[M.open].ask_n;
            case ST_DONE:    return 2;
            default:         return 0;
        }
    }
    return 0;
}

static void do_scroll(void) {
    if (M.view == VIEW_IDLE) { M.view = VIEW_LIST; M.sel = 0; return; }  // SIDE opens the menu
    int n = item_count();
    if (n) M.sel = (M.sel + 1) % n;
}
static void do_ok(void) {
    if (M.view == VIEW_IDLE) { M.view = VIEW_LIST; M.sel = 0; return; }
    if (M.view == VIEW_LIST) {
        if (M.n == 0) return;
        M.open = M.sel;
        M.view = VIEW_SESSION;
        M.sel = (M.sessions[M.open].state == ST_WAITING) ? 1 : 0;  // default Allow
        return;
    }
    if (M.view == VIEW_SESSION && M.open >= 0 && M.open < M.n) {
        sess_state_t st = M.sessions[M.open].state;
        if (st == ST_WAITING || st == ST_ASKING || st == ST_DONE) {
            M.sessions[M.open].state = ST_WORKING;  // optimistic; the Mac's next snapshot corrects it
        }
        M.open = -1; M.view = VIEW_LIST;
    }
}
static void do_back(void) {
    if (M.view == VIEW_SESSION) { M.open = -1; M.view = VIEW_LIST; }
    else if (M.view == VIEW_LIST) { M.view = VIEW_IDLE; M.sel = 0; }
}

void app_main(void) {
    ESP_ERROR_CHECK(board_init());
    ui_init();
    bridge_start();                       // BLE peripheral; advertises for the Mac bridge
    ui_render(&M);
    ESP_LOGI(TAG, "ready — SIDE=scroll  FRONT=OK  hold FRONT=back");

    bool pf = false, ps = false, front_long = false;
    int64_t front_down = 0, last_batt = 0, last_tick = 0;
    uint32_t last_seq = 0;

    for (;;) {
        uint32_t wait = ui_tick();          // pump LVGL; returns ms to next call
        if (wait > 30) wait = 30;
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

        // battery ~2 s — device-owned (not on the wire); real if the PMIC answers
        if (esp_timer_get_time() - last_batt > 2000000) {
            last_batt = esp_timer_get_time();
            int pct; bool chg = false, usb = false;
            if (board_battery_level(&pct) == ESP_OK && pct != M.battery) { M.battery = pct; dirty = true; }
            board_battery_charging(&chg);
            board_usb_powered(&usb);
            if (chg != M.charging || usb != M.usb) { M.charging = chg; M.usb = usb; dirty = true; }
        }

        // new snapshot from the bridge?
        uint32_t seq = bridge_seq();
        if (seq != last_seq) { last_seq = seq; dirty = true; }

        // ~1 Hz heartbeat so the bridge-anchored clock + session ages tick on screen
        // (the bridge re-ages/prunes locally; this just forces the redraw to show it)
        if (esp_timer_get_time() - last_tick > 1000000) { last_tick = esp_timer_get_time(); dirty = true; }

        // bind + apply events + render, all under the bridge lock (the live session
        // strings the renderer reads stay stable until bridge_release()).
        const bridge_view_t *lv = bridge_borrow();
        bind_model(lv);
        if (act_scroll) { do_scroll(); dirty = true; }
        if (act_back)   { do_back();   dirty = true; }
        else if (act_ok){ do_ok();     dirty = true; }
        if (dirty) ui_render(&M);
        bridge_release();
    }
}
