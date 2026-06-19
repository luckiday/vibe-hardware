idf_component_register(
    SRCS "ui.c"
    INCLUDE_DIRS "include"
    REQUIRES driver esp_lcd esp_timer lvgl stick_s3_board
)
