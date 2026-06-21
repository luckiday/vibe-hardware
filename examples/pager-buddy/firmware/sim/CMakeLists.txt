# Desktop simulator for the pager-buddy UI. Builds the REAL components/ui/ui.c with
# -DUI_SIM (which excludes only the ST7789/SPI bring-up) against desktop LVGL v9 + the
# same PuHui fonts the firmware uses, so the rendered PNGs match what the StickC S3 draws
# (modulo panel physics — see sim/README.md). No board, no flashing.
cmake_minimum_required(VERSION 3.16)
project(pager_sim C CXX)

set(CMAKE_C_STANDARD 11)
set(FW ${CMAKE_CURRENT_SOURCE_DIR}/..)                          # firmware/
set(LV ${FW}/managed_components/lvgl__lvgl)                     # resolved LVGL v9 source
set(FONTS_DIR ${FW}/managed_components/78__xiaozhi-fonts/src)   # PuHui CJK font .c files

if(NOT EXISTS ${LV}/lvgl.h)
  message(FATAL_ERROR
    "LVGL source not found at ${LV}.\n"
    "Run an ESP-IDF build once (idf.sh build) so the component manager populates "
    "managed_components/, then re-run cmake.")
endif()

# Point LVGL's desktop CMake at our lv_conf.h and skip the extras (smaller, fewer deps).
set(LV_BUILD_CONF_PATH ${CMAKE_CURRENT_SOURCE_DIR}/lv_conf.h CACHE PATH "" FORCE)
set(CONFIG_LV_BUILD_DEMOS        OFF CACHE BOOL "" FORCE)
set(CONFIG_LV_BUILD_EXAMPLES     OFF CACHE BOOL "" FORCE)
set(CONFIG_LV_USE_THORVG_INTERNAL OFF CACHE BOOL "" FORCE)
add_subdirectory(${LV} ${CMAKE_BINARY_DIR}/lvgl)

# LVGL globs in ARM Helium/NEON hand-asm (.S) that the macOS assembler can't parse.
# Our config is LV_DRAW_SW_ASM_NONE (matches sdkconfig), so those files are dead weight —
# drop them from the target rather than touching the vendored LVGL CMakeLists.
get_target_property(_lvgl_srcs lvgl SOURCES)
list(FILTER _lvgl_srcs EXCLUDE REGEX "\\.[sS]$")
set_target_properties(lvgl PROPERTIES SOURCES "${_lvgl_srcs}")

find_package(ZLIB REQUIRED)   # PNG writer in sim_main.c

add_executable(pager_sim
  sim_main.c
  ${FW}/components/ui/ui.c                  # the real renderer, shared verbatim with the device
  ${FONTS_DIR}/font_puhui_basic_20_4.c      # FONT_TITLE
  ${FONTS_DIR}/font_puhui_basic_14_1.c)     # FONT_BODY
target_compile_definitions(pager_sim PRIVATE UI_SIM)
target_include_directories(pager_sim PRIVATE ${FW}/components/ui/include)
target_link_libraries(pager_sim PRIVATE lvgl ZLIB::ZLIB)
