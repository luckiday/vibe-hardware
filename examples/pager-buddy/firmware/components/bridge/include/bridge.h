#pragma once
// bridge — the link domain: BLE peripheral + Claude Code status receiver.
//
// Device side of examples/pager-buddy/bridge/protocol.yaml, carried over BLE
// (modeled on the voicestick NimBLE peripheral). The device is a GATT *server*;
// the Mac is the *central*. The Mac writes snapshot JSON to the snapshot
// characteristic (chunked with START/END framing — a snapshot is larger than one
// BLE write); this component reassembles it, parses with cJSON, and exposes the
// sessions as the shared app model. It is a pure data producer — it never calls
// `ui`; main borrows the model and renders.
//
// The wire JSON is identical to protocol.yaml (and design/data.js); only the
// transport differs from the Level-0 HTTP sketch. Battery is NOT on the wire
// (device-owned): main fills M.battery from the BSP and takes only the sessions
// + clock + date from here.

#include <stdbool.h>
#include <stdint.h>
#include "esp_err.h"
#include "ui.h"   // session_t / app_model_t — the shared app model lives in ui.h

// A borrowed, lock-protected view of the latest snapshot. Valid only between
// bridge_borrow() and bridge_release(); `sessions` point into bridge-owned
// storage. Render (which copies into LVGL), then release.
typedef struct {
    session_t  *sessions;
    int         n;
    const char *clock;      // "HH:MM" from the Mac (the time source)
    const char *date;       // e.g. "Fri Jun 19"
    uint32_t    seq;        // snapshot sequence (== bridge_seq())
} bridge_view_t;

// Bring up NimBLE + start advertising. Call once from app_main (after board_init).
void bridge_start(void);

bool        bridge_online(void);       // a central is connected
uint32_t    bridge_seq(void);          // bumps once per applied snapshot (0 = none yet)
const char *bridge_device_name(void);  // "pg-XXXX" — for an on-screen pairing hint

// Borrow the live model under the bridge lock. ALWAYS pair with bridge_release().
// Returns NULL when no snapshot has been applied yet (the lock is still held;
// you must still call bridge_release()).
const bridge_view_t *bridge_borrow(void);
void                 bridge_release(void);

// Audio settings pushed by the Mac over the control characteristic (Mac-owned).
// Returns true and fills *enabled/*volume only when the settings CHANGED since the
// last call (edge-triggered) — main then applies them to the audio component. The
// bridge stays a pure receiver; it never touches audio itself.
bool bridge_take_settings(bool *enabled, int *volume);

// Level-1 (reserved, two-way): notify a decision back to the Mac over the
// resolution characteristic. action = "allow" | "deny" | <option label>.
esp_err_t bridge_send_resolution(const char *session_id, const char *action);
