// ui.c — ST7789 + LVGL bring-up and the pager screens for the M5StickC S3.
// LCD init values (gap 52/40, invert, RGB565 + byte-swap) are the StickC S3's hardware
// facts. Screens mirror examples/pager-buddy/design/ (the web mock).

#include <stdio.h>
#include "driver/gpio.h"
#include "driver/spi_master.h"
#include "esp_lcd_panel_io.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_st7789.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "lvgl.h"
#include "stick_s3_board.h"
#include "ui.h"

static const char *TAG = "ui";

#define LCD_HOST       SPI2_HOST
#define HRES           135
#define VRES           240
#define X_GAP          52
#define Y_GAP          40
#define PCLK_HZ        (20 * 1000 * 1000)
#define BUF_LINES      24
#define TICK_MS        10

// palette (matches the web mock)
#define C_BG     0x0a0c10
#define C_FG     0xe6e9ef
#define C_DIM    0x8a93a0
#define C_LINE   0x20242c
#define C_SEL    0x16243f
#define C_CHIP   0x1a1e26
#define C_CHIPTX 0xb8c0cc
#define C_WORK   0x4aa3ff
#define C_WAIT   0xffb020
#define C_ASK    0x35d0d8
#define C_DONE   0x46d369
#define C_ERR    0xff5d5d

static lv_display_t *s_disp;
static esp_lcd_panel_handle_t s_panel;

// ---------- LVGL <-> esp_lcd glue ----------
static bool on_flush_done(esp_lcd_panel_io_handle_t io, esp_lcd_panel_io_event_data_t *e, void *ctx) {
    lv_display_flush_ready((lv_display_t *)ctx);
    return false;
}
static void flush_cb(lv_display_t *disp, const lv_area_t *area, uint8_t *px) {
    esp_lcd_panel_handle_t panel = lv_display_get_user_data(disp);
    lv_draw_sw_rgb565_swap(px, (area->x2 - area->x1 + 1) * (area->y2 - area->y1 + 1));
    esp_lcd_panel_draw_bitmap(panel, area->x1, area->y1, area->x2 + 1, area->y2 + 1, px);
}
static void tick_cb(void *arg) { lv_tick_inc(TICK_MS); }

void ui_init(void) {
    // backlight on (the rail is already powered by the PMIC in board_init)
    const gpio_config_t bl = { .pin_bit_mask = 1ULL << BOARD_PIN_LCD_BL, .mode = GPIO_MODE_OUTPUT };
    ESP_ERROR_CHECK(gpio_config(&bl));
    gpio_set_level(BOARD_PIN_LCD_BL, 1);

    const spi_bus_config_t bus = {
        .sclk_io_num = BOARD_PIN_LCD_SCLK,
        .mosi_io_num = BOARD_PIN_LCD_MOSI,
        .miso_io_num = -1,
        .quadwp_io_num = -1,
        .quadhd_io_num = -1,
        .max_transfer_sz = HRES * BUF_LINES * sizeof(uint16_t),
    };
    ESP_ERROR_CHECK(spi_bus_initialize(LCD_HOST, &bus, SPI_DMA_CH_AUTO));

    esp_lcd_panel_io_handle_t io = NULL;
    const esp_lcd_panel_io_spi_config_t io_cfg = {
        .dc_gpio_num = BOARD_PIN_LCD_DC,
        .cs_gpio_num = BOARD_PIN_LCD_CS,
        .pclk_hz = PCLK_HZ,
        .lcd_cmd_bits = 8,
        .lcd_param_bits = 8,
        .spi_mode = 0,
        .trans_queue_depth = 10,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_io_spi((esp_lcd_spi_bus_handle_t)LCD_HOST, &io_cfg, &io));

    const esp_lcd_panel_dev_config_t panel_cfg = {
        .reset_gpio_num = BOARD_PIN_LCD_RST,
        .rgb_ele_order = LCD_RGB_ELEMENT_ORDER_RGB,
        .bits_per_pixel = 16,
    };
    ESP_ERROR_CHECK(esp_lcd_new_panel_st7789(io, &panel_cfg, &s_panel));
    ESP_ERROR_CHECK(esp_lcd_panel_reset(s_panel));
    ESP_ERROR_CHECK(esp_lcd_panel_init(s_panel));
    ESP_ERROR_CHECK(esp_lcd_panel_invert_color(s_panel, true));
    ESP_ERROR_CHECK(esp_lcd_panel_mirror(s_panel, false, false));
    ESP_ERROR_CHECK(esp_lcd_panel_set_gap(s_panel, X_GAP, Y_GAP));
    ESP_ERROR_CHECK(esp_lcd_panel_disp_on_off(s_panel, true));

    lv_init();
    s_disp = lv_display_create(HRES, VRES);
    const size_t buf_sz = HRES * BUF_LINES * sizeof(uint16_t);
    void *b1 = spi_bus_dma_memory_alloc(LCD_HOST, buf_sz, 0);
    void *b2 = spi_bus_dma_memory_alloc(LCD_HOST, buf_sz, 0);
    lv_display_set_buffers(s_disp, b1, b2, buf_sz, LV_DISPLAY_RENDER_MODE_PARTIAL);
    lv_display_set_color_format(s_disp, LV_COLOR_FORMAT_RGB565);
    lv_display_set_user_data(s_disp, s_panel);
    lv_display_set_flush_cb(s_disp, flush_cb);

    const esp_lcd_panel_io_callbacks_t cbs = { .on_color_trans_done = on_flush_done };
    ESP_ERROR_CHECK(esp_lcd_panel_io_register_event_callbacks(io, &cbs, s_disp));

    const esp_timer_create_args_t targs = { .callback = tick_cb, .name = "lv_tick" };
    esp_timer_handle_t t;
    ESP_ERROR_CHECK(esp_timer_create(&targs, &t));
    ESP_ERROR_CHECK(esp_timer_start_periodic(t, TICK_MS * 1000));

    lv_obj_t *scr = lv_screen_active();
    lv_obj_set_style_bg_color(scr, lv_color_hex(C_BG), 0);
    lv_obj_set_style_text_color(scr, lv_color_hex(C_FG), 0);
    lv_obj_set_style_text_font(scr, &lv_font_montserrat_12, 0);
    ESP_LOGI(TAG, "display + LVGL ready");
}

uint32_t ui_tick(void) { return lv_timer_handler(); }

// ---------- small helpers ----------
static uint32_t state_color(sess_state_t s) {
    switch (s) {
        case ST_WORKING: return C_WORK;
        case ST_WAITING: return C_WAIT;
        case ST_ASKING:  return C_ASK;
        case ST_DONE:    return C_DONE;
        default:         return C_ERR;
    }
}
static const char *state_label(sess_state_t s) {
    switch (s) {
        case ST_WORKING: return "working";
        case ST_WAITING: return "needs you";
        case ST_ASKING:  return "asks";
        case ST_DONE:    return "done";
        default:         return "error";
    }
}
static lv_obj_t *mk_label(lv_obj_t *p, const char *txt, const lv_font_t *f, uint32_t c) {
    lv_obj_t *l = lv_label_create(p);
    lv_label_set_text(l, txt);
    lv_obj_set_style_text_font(l, f, 0);
    lv_obj_set_style_text_color(l, lv_color_hex(c), 0);
    return l;
}
static lv_obj_t *mk_box(lv_obj_t *p) {  // a styleless container
    lv_obj_t *o = lv_obj_create(p);
    lv_obj_remove_style_all(o);
    lv_obj_remove_flag(o, LV_OBJ_FLAG_SCROLLABLE);
    return o;
}
static void rule(lv_obj_t *scr, int y) {
    lv_obj_t *r = mk_box(scr);
    lv_obj_set_size(r, HRES, 1);
    lv_obj_set_style_bg_color(r, lv_color_hex(C_LINE), 0);
    lv_obj_set_style_bg_opa(r, LV_OPA_COVER, 0);
    lv_obj_align(r, LV_ALIGN_TOP_MID, 0, y);
}

static void status_bar(lv_obj_t *scr, const app_model_t *m) {
    lv_obj_t *clk = mk_label(scr, m->clock, &lv_font_montserrat_12, C_DIM);
    lv_obj_align(clk, LV_ALIGN_TOP_LEFT, 4, 2);

    bool chg = m->charging || m->usb;
    uint32_t fillc = m->battery <= 20 ? C_ERR : chg ? 0x5ec4ff : C_DONE;
    char pct[8];
    snprintf(pct, sizeof pct, "%d%%", m->battery);
    lv_obj_t *lp = mk_label(scr, pct, &lv_font_montserrat_12, m->battery <= 20 ? C_ERR : C_DIM);
    lv_obj_align(lp, LV_ALIGN_TOP_RIGHT, -3, 2);

    lv_obj_t *shell = mk_box(scr);
    lv_obj_set_size(shell, 16, 9);
    lv_obj_set_style_border_width(shell, 1, 0);
    lv_obj_set_style_border_color(shell, lv_color_hex(0x6b7280), 0);
    lv_obj_set_style_radius(shell, 2, 0);
    lv_obj_set_style_pad_all(shell, 1, 0);
    lv_obj_align_to(shell, lp, LV_ALIGN_OUT_LEFT_MID, -3, 0);
    lv_obj_t *fill = mk_box(shell);
    int w = m->battery * 12 / 100;
    if (w < 2) w = 2;
    lv_obj_set_size(fill, w, 5);
    lv_obj_set_style_radius(fill, 1, 0);
    lv_obj_set_style_bg_color(fill, lv_color_hex(fillc), 0);
    lv_obj_set_style_bg_opa(fill, LV_OPA_COVER, 0);
    lv_obj_align(fill, LV_ALIGN_LEFT_MID, 0, 0);
    if (chg) {
        lv_obj_t *b = mk_label(scr, LV_SYMBOL_CHARGE, &lv_font_montserrat_12, 0x5ec4ff);
        lv_obj_align_to(b, shell, LV_ALIGN_OUT_LEFT_MID, -2, 0);
    }
    rule(scr, 17);
}

static void footer(lv_obj_t *scr, const char *l, const char *r) {
    rule(scr, VRES - 16);
    if (l && l[0]) {
        lv_obj_t *L = mk_label(scr, l, &lv_font_montserrat_10, C_DIM);
        lv_obj_align(L, LV_ALIGN_BOTTOM_LEFT, 4, -3);
    }
    if (r && r[0]) {
        lv_obj_t *R = mk_label(scr, r, &lv_font_montserrat_10, C_DIM);
        lv_obj_align(R, LV_ALIGN_BOTTOM_RIGHT, -4, -3);
    }
}

// content container between the status bar and the footer
static lv_obj_t *content(lv_obj_t *scr) {
    lv_obj_t *c = mk_box(scr);
    lv_obj_set_pos(c, 0, 19);
    lv_obj_set_size(c, HRES, VRES - 19 - 16);
    lv_obj_set_style_pad_all(c, 5, 0);
    return c;
}

static void choices(lv_obj_t *scr, const char *a, const char *b, int sel, bool danger_left) {
    lv_obj_t *c = mk_box(scr);
    lv_obj_set_size(c, HRES - 10, 24);
    lv_obj_align(c, LV_ALIGN_BOTTOM_MID, 0, -19);
    lv_obj_set_flex_flow(c, LV_FLEX_FLOW_ROW);
    lv_obj_set_style_pad_column(c, 6, 0);
    const char *txt[2] = {a, b};
    for (int i = 0; i < 2; i++) {
        lv_obj_t *bt = mk_box(c);
        lv_obj_set_flex_grow(bt, 1);
        lv_obj_set_height(bt, 22);
        lv_obj_set_style_radius(bt, 5, 0);
        bool on = (i == sel);
        bool dng = danger_left && i == 0;
        lv_obj_set_style_bg_opa(bt, LV_OPA_COVER, 0);
        lv_obj_set_style_bg_color(bt, lv_color_hex(on ? (dng ? 0x3a1620 : 0xffffff) : 0x14181f), 0);
        lv_obj_set_style_border_width(bt, 1, 0);
        lv_obj_set_style_border_color(bt, lv_color_hex(on ? (dng ? C_ERR : 0xffffff) : 0x262c36), 0);
        lv_obj_t *l = mk_label(bt, txt[i], &lv_font_montserrat_12,
                               on ? (dng ? 0xffd6da : 0x111111) : C_FG);
        lv_obj_center(l);
    }
}

// ---------- screens ----------
static void view_idle(lv_obj_t *scr, const app_model_t *m) {
    int need = 0;
    for (int i = 0; i < m->n; i++)
        if (m->sessions[i].state == ST_WAITING || m->sessions[i].state == ST_ASKING) need++;

    lv_obj_t *face = mk_label(scr, need ? "•_•" : "•‿•", &lv_font_montserrat_16,
                              need ? C_WAIT : C_DONE);
    lv_obj_align(face, LV_ALIGN_CENTER, 0, -46);
    lv_obj_t *clk = mk_label(scr, m->clock, &lv_font_montserrat_28, C_FG);
    lv_obj_align(clk, LV_ALIGN_CENTER, 0, -16);
    lv_obj_t *date = mk_label(scr, m->date, &lv_font_montserrat_12, C_DIM);
    lv_obj_align(date, LV_ALIGN_CENTER, 0, 12);

    char sum[40];
    if (need) snprintf(sum, sizeof sum, "%d sessions  %d need you", m->n, need);
    else      snprintf(sum, sizeof sum, "%d sessions  all clear", m->n);
    lv_obj_t *s = mk_label(scr, sum, &lv_font_montserrat_12, need ? C_WAIT : C_FG);
    lv_obj_align(s, LV_ALIGN_CENTER, 0, 30);
    footer(scr, "— open", "▼ menu");
}

static void view_list(lv_obj_t *scr, const app_model_t *m) {
    lv_obj_t *c = content(scr);
    lv_obj_set_flex_flow(c, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(c, 3, 0);
    for (int i = 0; i < m->n; i++) {
        session_t *s = &m->sessions[i];
        lv_obj_t *row = mk_box(c);
        lv_obj_set_width(row, lv_pct(100));
        lv_obj_set_height(row, LV_SIZE_CONTENT);
        lv_obj_set_style_pad_all(row, 3, 0);
        lv_obj_set_style_radius(row, 4, 0);
        lv_obj_set_flex_flow(row, LV_FLEX_FLOW_COLUMN);
        lv_obj_set_style_pad_row(row, 1, 0);
        if (i == m->sel) {
            lv_obj_set_style_bg_color(row, lv_color_hex(C_SEL), 0);
            lv_obj_set_style_bg_opa(row, LV_OPA_COVER, 0);
        }
        // line 1: dot + name + age
        lv_obj_t *l1 = mk_box(row);
        lv_obj_set_width(l1, lv_pct(100));
        lv_obj_set_height(l1, LV_SIZE_CONTENT);
        lv_obj_set_flex_flow(l1, LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(l1, LV_FLEX_ALIGN_START, LV_FLEX_ALIGN_CENTER, LV_FLEX_ALIGN_CENTER);
        lv_obj_set_style_pad_column(l1, 5, 0);
        lv_obj_t *d = mk_box(l1);
        lv_obj_set_size(d, 6, 6);
        lv_obj_set_style_radius(d, 3, 0);
        lv_obj_set_style_bg_color(d, lv_color_hex(state_color(s->state)), 0);
        lv_obj_set_style_bg_opa(d, LV_OPA_COVER, 0);
        lv_obj_t *nm = mk_label(l1, s->name, &lv_font_montserrat_12, C_FG);
        lv_obj_set_flex_grow(nm, 1);
        lv_label_set_long_mode(nm, LV_LABEL_LONG_DOT);
        lv_obj_set_width(nm, lv_pct(60));
        mk_label(l1, s->age, &lv_font_montserrat_10, C_DIM);
        // line 2: agent + state
        lv_obj_t *l2 = mk_box(row);
        lv_obj_set_width(l2, lv_pct(100));
        lv_obj_set_height(l2, LV_SIZE_CONTENT);
        lv_obj_set_flex_flow(l2, LV_FLEX_FLOW_ROW);
        lv_obj_set_style_pad_column(l2, 6, 0);
        lv_obj_set_style_pad_left(l2, 11, 0);
        mk_label(l2, s->agent, &lv_font_montserrat_10, C_CHIPTX);
        mk_label(l2, state_label(s->state), &lv_font_montserrat_10, state_color(s->state));
    }
    footer(scr, "— open", "▼ next");
}

static void scr_working(lv_obj_t *scr, session_t *s) {
    lv_obj_t *c = content(scr);
    lv_obj_set_flex_flow(c, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(c, 3, 0);
    lv_obj_t *h = mk_label(c, s->name, &lv_font_montserrat_14, C_WORK);
    (void)h;
    for (int i = 0; i < s->act_n; i++) {
        lv_obj_t *a = mk_label(c, s->act[i], &lv_font_montserrat_10, C_DIM);
        lv_obj_set_width(a, lv_pct(100));
        lv_label_set_long_mode(a, LV_LABEL_LONG_DOT);
    }
    mk_label(c, "working...", &lv_font_montserrat_12, C_WORK);
    footer(scr, "— back", "");
}

static void scr_approve(lv_obj_t *scr, session_t *s) {
    lv_obj_t *c = content(scr);
    lv_obj_set_flex_flow(c, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(c, 2, 0);
    mk_label(c, LV_SYMBOL_WARNING " Permission", &lv_font_montserrat_12, C_WAIT);
    mk_label(c, s->appr_tool, &lv_font_montserrat_16, C_FG);
    lv_obj_t *f = mk_label(c, s->appr_file, &lv_font_montserrat_10, C_FG);
    lv_obj_set_width(f, lv_pct(100));
    lv_label_set_long_mode(f, LV_LABEL_LONG_WRAP);
    char d[24];
    snprintf(d, sizeof d, "+%d -%d change", s->add, s->del);
    mk_label(c, d, &lv_font_montserrat_10, C_DIM);
    footer(scr, "— confirm", "▼ switch");  // the Deny/Allow bar is drawn by ui_render (knows sel)
}

static void scr_ask(lv_obj_t *scr, session_t *s, int sel) {
    lv_obj_t *c = content(scr);
    lv_obj_set_flex_flow(c, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(c, 3, 0);
    mk_label(c, "Claude asks", &lv_font_montserrat_12, C_ASK);
    lv_obj_t *q = mk_label(c, s->ask_q, &lv_font_montserrat_12, C_FG);
    lv_obj_set_width(q, lv_pct(100));
    lv_label_set_long_mode(q, LV_LABEL_LONG_WRAP);
    for (int i = 0; i < s->ask_n; i++) {
        lv_obj_t *o = mk_box(c);
        lv_obj_set_width(o, lv_pct(100));
        lv_obj_set_height(o, LV_SIZE_CONTENT);
        lv_obj_set_style_pad_all(o, 4, 0);
        lv_obj_set_style_radius(o, 4, 0);
        lv_obj_set_style_bg_opa(o, LV_OPA_COVER, 0);
        bool on = i == sel;
        lv_obj_set_style_bg_color(o, lv_color_hex(on ? 0x0e2d33 : 0x12161d), 0);
        lv_obj_set_style_border_width(o, 1, 0);
        lv_obj_set_style_border_color(o, lv_color_hex(on ? C_ASK : 0x20262f), 0);
        mk_label(o, s->ask_opts[i], &lv_font_montserrat_12, on ? 0xc9fbff : C_FG);
    }
    footer(scr, "— select", "▼ next");
}

static void scr_done(lv_obj_t *scr, session_t *s) {
    lv_obj_t *c = content(scr);
    lv_obj_set_flex_flow(c, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_row(c, 3, 0);
    char h[40];
    snprintf(h, sizeof h, LV_SYMBOL_OK " %s", s->name);
    mk_label(c, h, &lv_font_montserrat_14, C_DONE);
    lv_obj_t *sm = mk_label(c, s->done_summary, &lv_font_montserrat_12, C_FG);
    lv_obj_set_width(sm, lv_pct(100));
    lv_label_set_long_mode(sm, LV_LABEL_LONG_WRAP);
    char d[32];
    snprintf(d, sizeof d, "%d files - %s", s->files, s->tests ? s->tests : "");
    mk_label(c, d, &lv_font_montserrat_10, C_DIM);
    footer(scr, "— Jump", "▼ switch");
}

void ui_render(const app_model_t *m) {
    lv_obj_t *scr = lv_screen_active();
    lv_obj_clean(scr);
    status_bar(scr, m);

    if (m->view == VIEW_IDLE) {
        view_idle(scr, m);
    } else if (m->view == VIEW_LIST) {
        view_list(scr, m);
    } else if (m->view == VIEW_SESSION && m->open >= 0) {
        session_t *s = &m->sessions[m->open];
        switch (s->state) {
            case ST_WAITING:
                scr_approve(scr, s);
                // highlight Deny/Allow per the model's selection
                choices(scr, "Deny", "Allow", m->sel, true);
                break;
            case ST_ASKING: scr_ask(scr, s, m->sel); break;
            case ST_DONE:
                scr_done(scr, s);
                choices(scr, LV_SYMBOL_UP " Jump", "Dismiss", m->sel, false);
                break;
            default: scr_working(scr, s); break;
        }
    } else {
        view_list(scr, m);
    }
}
