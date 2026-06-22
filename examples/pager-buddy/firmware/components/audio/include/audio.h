#pragma once
// audio — notification tones on the M5StickC S3 speaker (ES8311 codec + AW8737 amp).
//
// The board has real audio hardware wired over I²S (see pcb/pinmap.yaml); this
// component drives the ES8311 in DAC/playback mode (mirrors the voicestick audio
// pipeline, which used the same codec in ADC/mic mode). It owns a small FreeRTOS
// task: callers enqueue an alert with audio_alert() and the task generates a short
// tone pattern on demand — distinct per session state — and writes it to the codec.
//
// Triggering is device-owned: main decides WHEN to alert from the snapshots the
// bridge receives. The Mac only controls the *settings* (enable + volume), pushed
// over BLE and applied via audio_set_enabled()/audio_set_volume(). Settings persist
// in NVS so the first alert after a cold boot honors the last choice before the Mac
// reconnects.

#include <stdbool.h>
#include "esp_err.h"

// Which session state triggered the alert — selects the tone pattern.
typedef enum {
    AUDIO_ALERT_WAITING,   // needs a permission approval → urgent double-beep
    AUDIO_ALERT_ASKING,    // agent asked a question      → single mid tone
    AUDIO_ALERT_DONE,      // turn finished               → soft descending tone
} audio_alert_t;

// Bring up I²S + ES8311 (DAC), load persisted settings, spawn the audio task.
// Call once from app_main AFTER board_init() (the codec shares the board I²C bus).
// Safe to ignore the error: a missing codec just means no sound, never a crash.
esp_err_t audio_init(void);

// Enqueue an alert tone. Non-blocking; a no-op when audio is disabled. Safe to call
// from any task (e.g. the main UI loop on a new snapshot).
void audio_alert(audio_alert_t kind);

// Silence an in-progress tone and drop any queued alerts (FRONT button = ACK/silence).
void audio_stop(void);

// Settings — applied live and persisted to NVS. Called by main when the Mac pushes
// new settings over the bridge control characteristic.
void audio_set_enabled(bool on);
void audio_set_volume(int vol_0_100);   // clamped to 0..100
bool audio_enabled(void);
int  audio_volume(void);
