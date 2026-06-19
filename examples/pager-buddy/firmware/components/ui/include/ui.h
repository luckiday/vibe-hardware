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
    sess_state_t state;
    const char *appr_tool, *appr_file; int add, del;          // ST_WAITING
    const char *ask_q; const char **ask_opts; int ask_n;       // ST_ASKING
    const char *done_summary; int files; const char *tests;    // ST_DONE
    const char **act; int act_n;                                // ST_WORKING
} session_t;

typedef struct {
    const char *clock, *date;
    int battery; bool charging, usb;
    session_t *sessions; int n;
    view_t view; int open; int sel;   // open = index of the open session (-1 if none)
} app_model_t;

void ui_init(void);                    // LCD + LVGL; call after board_init()
void ui_render(const app_model_t *m);  // redraw for the current model
uint32_t ui_tick(void);                // pump LVGL; returns ms until next call
