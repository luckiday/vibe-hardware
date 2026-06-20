#pragma once
// ui — the display domain: ST7789 + LVGL bring-up and the pager screens.
// Public surface only: init + render(model) + a tick to pump LVGL. The renderer
// is driven by *what* state to show (the model); it owns *how* to draw it. The
// screens mirror examples/pager-buddy/design/ (the web mock spec).

#include <stdbool.h>
#include <stdint.h>

typedef enum { ST_WORKING, ST_WAITING, ST_ASKING, ST_DONE, ST_ERROR } sess_state_t;
typedef enum { VIEW_IDLE, VIEW_LIST, VIEW_SESSION } view_t;

typedef struct {
    const char *name, *agent, *term, *age;
    const char *task;                                          // the user's ask (one line) — disambiguates same-name sessions
    sess_state_t state;
    const char *appr_tool, *appr_file; int add, del;          // ST_WAITING
    const char *ask_q; const char **ask_opts; int ask_n;       // ST_ASKING
    const char *done_summary; int files; const char *tests;    // ST_DONE
    const char **act; int act_n;                                // ST_WORKING
} session_t;

typedef struct {
    const char *clock, *date;
    int battery; bool charging, usb;
    bool online;                      // BLE link to the Mac bridge (drives the status-bar Bluetooth glyph)
    session_t *sessions; int n;
    view_t view; int open; int sel;   // open = index of the open session (-1 if none)
} app_model_t;

void ui_init(void);                    // LCD + LVGL; call after board_init()
void ui_render(const app_model_t *m);  // full rebuild for the current model
void ui_refresh_time(const app_model_t *m);  // update only clock/age labels in place (no
                                       // rebuild) so marquee scroll animations aren't reset
uint32_t ui_tick(void);                // pump LVGL; returns ms until next call

// Power saving. ui_set_backlight(false) blanks the screen for the idle light-sleep
// tier (panel + LVGL stay live so a button/BLE wake repaints instantly); (true)
// restores it. ui_prepare_deep_sleep() additionally turns the panel off — call it
// just before deep sleep, alongside board_prepare_deep_sleep().
void ui_set_backlight(bool on);
void ui_prepare_deep_sleep(void);
