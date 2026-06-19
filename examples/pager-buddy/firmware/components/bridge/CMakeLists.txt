idf_component_register(
    SRCS "bridge.c"
    INCLUDE_DIRS "include"
    REQUIRES ui bt nvs_flash json esp_timer
)
