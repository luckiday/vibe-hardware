// pager-buddy — display UI on the M5StickC S3 (stub data, no network yet).
//
// Layered per vibe-firmware: BSP (stick_s3_board) owns pins/PMIC/buttons; ui owns the
// ST7789 + LVGL screens; this thin main holds the stub model + state machine and pumps
// LVGL while polling the two buttons. Mirrors examples/pager-buddy/design/.
//   SIDE (KEY2) = cycle highlight (wraps) · FRONT (KEY1) = OK · hold FRONT = back.

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "stick_s3_board.h"
#include "ui.h"

static const char *TAG = "pager";

// --- stub data (same sample as the web mock) ---
static const char *deploy_opts[] = {"Production", "Staging", "Local only"};
static const char *act_fix[]     = {"Edit(src/auth/middleware.ts)"};
static const char *act_backend[] = {"Write(src/routes/users.ts)"};
static const char *act_opt[]     = {"Analyzing the slow queries", "Read(schema.prisma)",
                                    "Edit(src/db/client.ts)"};

static session_t sessions[] = {
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

static app_model_t M = {
    .clock = "10:20", .date = "Fri Jun 19", .battery = 78, .charging = false, .usb = false,
    .sessions = sessions, .n = 3, .view = VIEW_IDLE, .open = -1, .sel = 0,
};

static int item_count(void) {
    if (M.view == VIEW_LIST) return M.n;
    if (M.view == VIEW_SESSION && M.open >= 0) {
        switch (sessions[M.open].state) {
            case ST_WAITING: return 2;
            case ST_ASKING:  return sessions[M.open].ask_n;
            case ST_DONE:    return 2;
            default:         return 0;
        }
    }
    return 0;
}

static void do_scroll(void) {
    int n = item_count();
    if (n) M.sel = (M.sel + 1) % n;
}
static void do_ok(void) {
    if (M.view == VIEW_IDLE) { M.view = VIEW_LIST; M.sel = 0; return; }
    if (M.view == VIEW_LIST) {
        M.open = M.sel;
        M.view = VIEW_SESSION;
        M.sel = (sessions[M.open].state == ST_WAITING) ? 1 : 0;  // default Allow
        return;
    }
    if (M.view == VIEW_SESSION && M.open >= 0) {
        sess_state_t st = sessions[M.open].state;
        if (st == ST_WAITING || st == ST_ASKING || st == ST_DONE) {
            sessions[M.open].state = ST_WORKING;  // resolved (stub)
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
    ui_render(&M);
    ESP_LOGI(TAG, "ready — SIDE=scroll  FRONT=OK  hold FRONT=back");

    bool pf = false, ps = false, front_long = false;
    int64_t front_down = 0, last_batt = 0;

    for (;;) {
        uint32_t wait = ui_tick();          // pump LVGL; returns ms to next call
        if (wait > 30) wait = 30;
        if (wait < 5) wait = 5;
        vTaskDelay(pdMS_TO_TICKS(wait));
        bool dirty = false;

        // FRONT (KEY1): short = OK, long (>500 ms) = back
        bool f = board_btn_front();
        if (f && !pf) { front_down = esp_timer_get_time(); front_long = false; }
        if (f && !front_long && esp_timer_get_time() - front_down > 500000) {
            front_long = true; do_back(); dirty = true;
        }
        if (!f && pf && !front_long) { do_ok(); dirty = true; }
        pf = f;

        // SIDE (KEY2): tap = scroll
        bool s = board_btn_side();
        if (s && !ps) { do_scroll(); dirty = true; }
        ps = s;

        // battery ~2 s (real if the PMIC answers; else keep the stub value)
        if (esp_timer_get_time() - last_batt > 2000000) {
            last_batt = esp_timer_get_time();
            int pct; bool chg = false, usb = false;
            if (board_battery_level(&pct) == ESP_OK && pct != M.battery) { M.battery = pct; dirty = true; }
            board_battery_charging(&chg);
            board_usb_powered(&usb);
            if (chg != M.charging || usb != M.usb) { M.charging = chg; M.usb = usb; dirty = true; }
        }

        if (dirty) ui_render(&M);
    }
}
