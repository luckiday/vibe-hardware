// lv_conf.h — LVGL config for the DESKTOP simulator (sim/), mirroring the device's
// sdkconfig so the simulator draws the same way the StickC S3 does. Only the options
// that differ from LVGL's built-in defaults (src/lv_conf_internal.h) are set here;
// everything else falls through to those defaults.
//
// Kept in sync with firmware/sdkconfig (CONFIG_LV_*):
//   COLOR_DEPTH 16 · MEM_SIZE 64K · LOG off · fonts Montserrat 10/12/40 + default 14.
// The PuHui CJK fonts (font_puhui_basic_*) are compiled in via CMake, not toggled here.
#ifndef LV_CONF_H
#define LV_CONF_H

#include <stdint.h>

// 16-bit colour, same as the panel (CONFIG_LV_COLOR_DEPTH_16=y).
#define LV_COLOR_DEPTH 16

// Match the device's LVGL heap so a layout that would exhaust memory on hardware
// also fails here (CONFIG_LV_MEM_SIZE_KILOBYTES=64).
#define LV_MEM_SIZE (64 * 1024)

// Built-in Montserrat sizes used by ui.c (CONFIG_LV_FONT_MONTSERRAT_*).
#define LV_FONT_MONTSERRAT_10 1
#define LV_FONT_MONTSERRAT_12 1
#define LV_FONT_MONTSERRAT_14 1   // LV_FONT_DEFAULT (CONFIG_LV_FONT_DEFAULT_MONTSERRAT_14=y)
#define LV_FONT_MONTSERRAT_40 1
#define LV_FONT_DEFAULT &lv_font_montserrat_14

// The full PuHui faces exceed the small-font bitmap offsets — same as the device
// (CONFIG_LV_FONT_FMT_TXT_LARGE=y).
#define LV_FONT_FMT_TXT_LARGE 1

// Quiet, like the device (CONFIG_LV_USE_LOG is not set).
#define LV_USE_LOG 0

#endif // LV_CONF_H
