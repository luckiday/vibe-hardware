idf_component_register(
    SRCS "main.c"
    INCLUDE_DIRS "."
    REQUIRES stick_s3_board ui bridge audio esp_timer driver esp_pm esp_hw_support esp_system
)
