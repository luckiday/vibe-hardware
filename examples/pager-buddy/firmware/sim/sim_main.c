// sim_main.c — desktop simulator for the pager-buddy UI.
//
// Compiles the *real* components/ui/ui.c (with -DUI_SIM, which excludes only the
// ST7789/SPI bring-up) against desktop LVGL v9 + the same PuHui/Montserrat fonts the
// device uses. It builds a 135x240 memory-backed display, calls ui_render(model) for a
// chosen UI state, pumps LVGL, and writes the framebuffer to a PNG — so an agent can
// render a screen, read the PNG, tweak ui.c, and re-render in a tight loop.
//
//   pager_sim <state> <out.png> [tick_ms] [scale]   render one state
//   pager_sim all <out_dir>     [tick_ms] [scale]   render every state into <out_dir>/
//
// tick_ms (default 600) advances the animation clock before the snapshot, so the
// breathing-ring / VU-meter frames look representative. scale (default 3) is integer
// nearest-neighbour upscaling — the PNG stays pixel-exact, just easier to inspect.
//
// What this does NOT reproduce (panel physics, tune those on real hardware): the
// ST7789's gamma/colour cast (the C_BG "reads blue" note in ui.c), the RGB565 byte-swap
// + colour inversion done on the wire, backlight/contrast, and viewing angle. Layout,
// typography, ellipsis/marquee, flex sizing and the animations are faithful.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <zlib.h>

#include "lvgl.h"
#include "ui.h"

#define W 135
#define H 240

// Full-frame RGB565 buffer: in LV_DISPLAY_RENDER_MODE_FULL LVGL renders the whole
// screen into this and hands it back via flush_cb — so after a refresh it holds the frame.
static uint8_t s_frame[W * H * sizeof(uint16_t)];

static void flush_cb(lv_display_t *disp, const lv_area_t *area, uint8_t *px) {
    (void)area; (void)px;   // FULL mode: px == s_frame, already the complete frame
    lv_display_flush_ready(disp);
}

// ---------------------------------------------------------------- PNG (libz) ----------
static void be32(uint8_t *p, uint32_t v) { p[0]=v>>24; p[1]=v>>16; p[2]=v>>8; p[3]=v; }

static void png_chunk(FILE *f, const char *type, const uint8_t *data, uint32_t len) {
    uint8_t hdr[4]; be32(hdr, len); fwrite(hdr, 1, 4, f); fwrite(type, 1, 4, f);
    if (len) fwrite(data, 1, len, f);
    uLong c = crc32(0, (const Bytef *)type, 4);
    if (len) c = crc32(c, data, len);
    uint8_t crc[4]; be32(crc, (uint32_t)c); fwrite(crc, 1, 4, f);
}

static int write_png(const char *path, int w, int h, const uint8_t *rgb) {
    uLong raw_len = (uLong)h * (1 + (uLong)w * 3);           // 1 filter byte / row + RGB888
    uint8_t *raw = malloc(raw_len);
    for (int y = 0; y < h; y++) {
        raw[y * (1 + w * 3)] = 0;                            // filter type 0 (none)
        memcpy(raw + y * (1 + w * 3) + 1, rgb + (size_t)y * w * 3, (size_t)w * 3);
    }
    uLong clen = compressBound(raw_len);
    uint8_t *comp = malloc(clen);
    if (compress2(comp, &clen, raw, raw_len, 9) != Z_OK) { free(raw); free(comp); return -1; }

    FILE *f = fopen(path, "wb");
    if (!f) { free(raw); free(comp); return -1; }
    const uint8_t sig[8] = {137,80,78,71,13,10,26,10};
    fwrite(sig, 1, 8, f);
    uint8_t ihdr[13];
    be32(ihdr, w); be32(ihdr + 4, h);
    ihdr[8] = 8; ihdr[9] = 2; ihdr[10] = 0; ihdr[11] = 0; ihdr[12] = 0;   // 8-bit RGB
    png_chunk(f, "IHDR", ihdr, 13);
    png_chunk(f, "IDAT", comp, (uint32_t)clen);
    png_chunk(f, "IEND", NULL, 0);
    fclose(f); free(raw); free(comp);
    return 0;
}

// RGB565 framebuffer -> integer-scaled RGB888 PNG.
static int frame_to_png(const char *path, int scale) {
    if (scale < 1) scale = 1;
    int w = W * scale, h = H * scale;
    uint8_t *rgb = malloc((size_t)w * h * 3);
    const uint16_t *src = (const uint16_t *)(const void *)s_frame;   // host is little-endian
    for (int y = 0; y < h; y++) {
        for (int x = 0; x < w; x++) {
            uint16_t p = src[(y / scale) * W + (x / scale)];
            uint8_t r = (p >> 11) & 0x1f, g = (p >> 5) & 0x3f, b = p & 0x1f;
            uint8_t *o = rgb + ((size_t)y * w + x) * 3;
            o[0] = (uint8_t)((r * 255 + 15) / 31);   // 5-bit red
            o[1] = (uint8_t)((g * 255 + 31) / 63);   // 6-bit green
            o[2] = (uint8_t)((b * 255 + 15) / 31);   // 5-bit blue
        }
    }
    int rc = write_png(path, w, h, rgb);
    free(rgb);
    if (getenv("SIM_DUMP_RAW")) {                       // debug: raw RGB565 framebuffer
        char rp[1100]; snprintf(rp, sizeof rp, "%s.565", path);
        FILE *f = fopen(rp, "wb"); if (f) { fwrite(s_frame, 1, sizeof s_frame, f); fclose(f); }
    }
    return rc;
}

// ---------------------------------------------------------- sample scenarios ----------
// Mirror firmware/main/main.c's stub data; the CJK case exercises the PuHui fonts.
static const char *deploy_opts[] = {"Production", "Staging", "Local only"};
static const char *act_fix[]     = {"Edit(src/auth/middleware.ts)"};
static const char *act_opt[]     = {"Analyzing the slow queries", "Read(schema.prisma)",
                                    "Edit(src/db/client.ts)"};

// Build an app_model for a named state. Uses file-static session storage so the
// pointers in app_model stay valid after the function returns.
static session_t g_sess[6];
static const char *g_cjk_opts[] = {"\xe5\x90\x88\xe5\xb9\xb6\xe5\x88\xb0 main", "\xe6\x96\xb0\xe5\xbb\xba PR", "\xe5\x85\x88\xe4\xb8\x8d\xe5\x90\x88"};

static int build_model(const char *state, app_model_t *m) {
    memset(m, 0, sizeof *m);
    memset(g_sess, 0, sizeof g_sess);
    m->clock = "14:32"; m->date = "Sat Jun 21";
    m->battery = 76; m->charging = false; m->usb = false; m->online = true;
    m->connecting = false; m->device = "pg-1a2b";
    m->sessions = g_sess; m->open = -1; m->sel = 0;

    // a default set of four mixed sessions (used by idle/list)
    g_sess[0] = (session_t){.id="s0", .name="vibe hardware", .agent="Claude", .term="VS Code",
        .age="27m", .state=ST_WORKING, .task="fix the auth bug in the login middleware",
        .appr_tool="Edit", .appr_file="src/auth/middleware.ts", .add=3, .del=1,
        .ask_q="Choose deploy target?", .ask_opts=deploy_opts, .ask_n=3,
        .done_summary="Fixed the auth bug in the login middleware.", .files=3, .tests="8 passed",
        .act=act_fix, .act_n=1};
    g_sess[1] = (session_t){.id="s1", .name="vibe hardware", .agent="Claude", .term="Terminal",
        .age="4m", .state=ST_WAITING, .task="add the OTA partition table and flash it",
        .appr_tool="Bash", .appr_file="idf.py flash --port /dev/cu.usbserial-0001", .add=0, .del=0};
    g_sess[2] = (session_t){.id="s2", .name="db migration", .agent="Claude", .term="iTerm",
        .age="12m", .state=ST_ASKING, .task="optimize the slow dashboard queries",
        .ask_q="Run the migration against which database?", .ask_opts=g_cjk_opts, .ask_n=3,
        .act=act_opt, .act_n=3};
    g_sess[3] = (session_t){.id="s3", .name="landing page", .agent="Claude", .term="VS Code",
        .age="1h", .state=ST_DONE, .task="restyle the hero section",
        .done_summary="Restyled the hero section and updated the copy.", .files=5, .tests="all green"};
    m->n = 4;

    if (!strcmp(state, "idle")) {
        m->view = VIEW_IDLE;                       // mixed -> amber "need you"
    } else if (!strcmp(state, "idle-clear")) {
        for (int i = 0; i < m->n; i++) g_sess[i].state = ST_DONE;
        m->view = VIEW_IDLE;                       // all done -> green "all clear"
    } else if (!strcmp(state, "list")) {
        m->view = VIEW_LIST; m->sel = 1;
    } else if (!strcmp(state, "working")) {
        m->view = VIEW_SESSION; m->open = 0;       // s0 is ST_WORKING
    } else if (!strcmp(state, "approve")) {
        m->view = VIEW_SESSION; m->open = 1; m->sel = 1;   // s1 ST_WAITING, Allow highlighted
    } else if (!strcmp(state, "ask")) {
        m->view = VIEW_SESSION; m->open = 2; m->sel = 0;   // s2 ST_ASKING
    } else if (!strcmp(state, "done")) {
        m->view = VIEW_SESSION; m->open = 3;       // s3 ST_DONE
    } else if (!strcmp(state, "offline")) {
        m->online = false; m->battery = 12;        // dim BT + red battery
        m->view = VIEW_IDLE;
    } else if (!strcmp(state, "connecting")) {
        m->online = false; m->connecting = true;   // no snapshot yet → "Connecting" screen
        m->n = 0; m->sessions = NULL; m->view = VIEW_IDLE;
    } else if (!strcmp(state, "empty")) {
        m->n = 0; m->view = VIEW_LIST;
    } else if (!strcmp(state, "cjk")) {
        g_sess[0].name = "\xe6\x9a\x96\xe6\xb0\x94\xe9\xa1\xb9\xe7\x9b\xae";          // 暖气项目
        g_sess[0].task = "\xe4\xbf\xae\xe5\xa4\x8d\xe7\x99\xbb\xe5\xbd\x95\xe4\xb8\xad\xe9\x97\xb4\xe4\xbb\xb6\xe7\x9a\x84\xe9\x89\xb4\xe6\x9d\x83 bug";  // 修复登录中间件的鉴权 bug
        g_sess[2].name = "\xe6\x95\xb0\xe6\x8d\xae\xe5\xba\x93\xe8\xbf\x81\xe7\xa7\xbb";  // 数据库迁移
        g_sess[2].ask_q = "\xe8\xbf\x81\xe7\xa7\xbb\xe5\x88\xb0\xe5\x93\xaa\xe4\xb8\xaa\xe6\x95\xb0\xe6\x8d\xae\xe5\xba\x93\xef\xbc\x9f";  // 迁移到哪个数据库？
        m->view = VIEW_SESSION; m->open = 2; m->sel = 0;
    } else {
        return 0;
    }
    return 1;
}

static const char *ALL_STATES[] = {
    "idle", "idle-clear", "list", "working", "approve", "ask", "done", "offline", "connecting", "empty", "cjk",
};
#define N_STATES ((int)(sizeof ALL_STATES / sizeof ALL_STATES[0]))

// ----------------------------------------------------------------- engine -------------
static lv_display_t *s_disp;

static void sim_init(void) {
    lv_init();
    s_disp = lv_display_create(W, H);
    lv_display_set_color_format(s_disp, LV_COLOR_FORMAT_RGB565);
    lv_display_set_buffers(s_disp, s_frame, NULL, sizeof s_frame, LV_DISPLAY_RENDER_MODE_FULL);
    lv_display_set_flush_cb(s_disp, flush_cb);

    // Mirror ui_init()'s base screen styling (the device sets these in its bring-up,
    // which -DUI_SIM excludes). Keep the literals in sync with C_BG/C_FG in ui.c.
    lv_obj_t *scr = lv_screen_active();
    lv_obj_set_style_bg_color(scr, lv_color_hex(0x0a0a0a), 0);
    lv_obj_set_style_text_color(scr, lv_color_hex(0xe6e9ef), 0);
    lv_obj_set_style_text_font(scr, &lv_font_montserrat_12, 0);
}

static void render_state(const app_model_t *m, int tick_ms) {
    ui_render(m);
    for (int t = 0; t < tick_ms; t += 10) { lv_tick_inc(10); lv_timer_handler(); }
    lv_tick_inc(10);
    lv_refr_now(s_disp);   // force the snapshot frame into s_frame
}

int main(int argc, char **argv) {
    if (argc < 3) {
        fprintf(stderr,
            "usage: %s <state> <out.png> [tick_ms] [scale]\n"
            "       %s all      <out_dir> [tick_ms] [scale]\n"
            "states:", argv[0], argv[0]);
        for (int i = 0; i < N_STATES; i++) fprintf(stderr, " %s", ALL_STATES[i]);
        fprintf(stderr, "\n");
        return 2;
    }
    const char *state = argv[1];
    const char *out   = argv[2];
    int tick_ms = argc > 3 ? atoi(argv[3]) : 600;
    int scale   = argc > 4 ? atoi(argv[4]) : 3;

    sim_init();
    app_model_t m;

    if (!strcmp(state, "all")) {
        for (int i = 0; i < N_STATES; i++) {
            char path[1024];
            snprintf(path, sizeof path, "%s/%s.png", out, ALL_STATES[i]);
            if (!build_model(ALL_STATES[i], &m)) { fprintf(stderr, "unknown state\n"); return 1; }
            render_state(&m, tick_ms);
            if (frame_to_png(path, scale)) { fprintf(stderr, "write failed: %s\n", path); return 1; }
            printf("wrote %s (%dx%d)\n", path, W * scale, H * scale);
        }
        return 0;
    }

    if (!build_model(state, &m)) { fprintf(stderr, "unknown state: %s\n", state); return 1; }
    render_state(&m, tick_ms);
    if (frame_to_png(out, scale)) { fprintf(stderr, "write failed: %s\n", out); return 1; }
    printf("wrote %s (%dx%d)\n", out, W * scale, H * scale);
    return 0;
}
