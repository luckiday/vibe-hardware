// bridge — BLE peripheral that receives Claude Code status snapshots.
//
// NimBLE GATT server (modeled on voicestick's firmware/components/voice_ble — see
// docs/awesome-firmware.md; clone under docs/references/_clones/voicestick).
// The Mac (central) writes snapshot JSON to the SNAPSHOT characteristic; because a
// snapshot is larger than one BLE write, the host frames it as chunks with a 2-byte
// header [ver, flags] where flags carry START/END. We reassemble, parse with cJSON
// into one of two double-buffered stores, then swap it in under a mutex. main borrows
// the live store, binds it onto app_model_t, renders (LVGL copies the strings), and
// releases. A failed/partial snapshot self-heals: the Mac re-sends a full snapshot on
// every change.

#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/semphr.h"
#include "esp_log.h"
#include "esp_mac.h"
#include "esp_timer.h"
#include "nvs_flash.h"
#include "cJSON.h"

#include "host/ble_hs.h"
#include "host/ble_gap.h"
#include "host/ble_gatt.h"
#include "host/ble_uuid.h"
#include "host/ble_att.h"
#include "nimble/nimble_port.h"
#include "nimble/nimble_port_freertos.h"
#include "services/gap/ble_svc_gap.h"
#include "services/gatt/ble_svc_gatt.h"

#include "bridge.h"

static const char *TAG = "bridge";

// ── model storage (transport-independent) ───────────────────────────────────────
#define BR_MAX_SESS 8
#define BR_MAX_OPTS 6      // ask options per session
#define BR_MAX_ACTS 6      // activity lines per session
#define BR_ARENA    6144   // string pool per store
#define BR_RX_MAX   8192   // reassembly buffer (a whole snapshot)
#define BR_IDLE_TTL 600    // protocol.yaml freshness.idle_ttl_seconds — drop sessions idle past this

typedef struct {
    session_t   s[BR_MAX_SESS];
    const char *opts[BR_MAX_SESS][BR_MAX_OPTS];
    const char *acts[BR_MAX_SESS][BR_MAX_ACTS];
    double      ts[BR_MAX_SESS];   // per-session last-update epoch (0 = unknown)
    int         n;
    char        clock[8];
    char        date[24];
    double      snap_ts;           // top-level epoch (serve time); 0 = no time anchor
    int64_t     rx_us;             // esp_timer at receipt — monotonic base for re-aging
    int         tz_off;            // local−UTC seconds, derived from clock vs snap_ts
    char        arena[BR_ARENA];
    size_t      used;
} store_t;

static store_t           s_store[2];     // double buffer
static store_t          *s_live;         // store main reads (NULL until first snapshot)
static bridge_view_t     s_view;         // filled by bridge_borrow()
static volatile uint32_t s_seq;          // snapshot counter
static SemaphoreHandle_t s_lock;         // guards s_live / s_view / settings

// ── audio settings (Mac-owned), received over the control characteristic ─────────
// The device never originates these — main applies them to the audio component when
// bridge_take_settings() reports a change. Defaults mirror the audio component's NVS
// defaults so behavior is sane before the Mac ever pushes.
static bool     s_set_enabled = true;
static int      s_set_volume  = 60;
static uint32_t s_set_seq;        // bumps on each received settings write
static uint32_t s_set_taken;      // last seq main consumed

// ── small JSON helpers ──────────────────────────────────────────────────────────
static const char *J_str(const cJSON *o, const char *k) {
    const cJSON *x = cJSON_GetObjectItemCaseSensitive(o, k);
    return (cJSON_IsString(x) && x->valuestring) ? x->valuestring : NULL;
}
static int J_int(const cJSON *o, const char *k, int dflt) {
    const cJSON *x = cJSON_GetObjectItemCaseSensitive(o, k);
    return cJSON_IsNumber(x) ? x->valueint : dflt;
}
static double J_double(const cJSON *o, const char *k) {
    const cJSON *x = cJSON_GetObjectItemCaseSensitive(o, k);
    return cJSON_IsNumber(x) ? x->valuedouble : 0;
}

// Humanized "since" string — matches the Python humanize_age (bridge/pager_stub.py).
static void humanize_age(double secs, char *out, size_t n) {
    long s = secs > 0 ? (long)secs : 0;
    if (s < 60)         snprintf(out, n, "%lds", s);
    else if (s < 3600)  snprintf(out, n, "%ldm", s / 60);
    else if (s < 86400) snprintf(out, n, "%ldh", s / 3600);
    else                snprintf(out, n, "%ldd", s / 86400);
}

// Copy a string into the store's arena; returns "" on null or if the arena is full.
static const char *dup_arena(store_t *m, const char *s) {
    if (!s) return "";
    size_t len = strlen(s) + 1;
    if (m->used + len > sizeof(m->arena)) return "";
    char *p = m->arena + m->used;
    memcpy(p, s, len);
    m->used += len;
    return p;
}

static sess_state_t parse_state(const char *s) {
    if (!s) return ST_WORKING;
    if (!strcmp(s, "waiting")) return ST_WAITING;
    if (!strcmp(s, "asking"))  return ST_ASKING;
    if (!strcmp(s, "done"))    return ST_DONE;
    if (!strcmp(s, "error"))   return ST_ERROR;
    return ST_WORKING;
}

// Fill one session from its JSON object into store slot i.
static void parse_session(store_t *m, int i, const cJSON *js) {
    session_t *s = &m->s[i];
    m->ts[i] = J_double(js, "ts");                 // last-update epoch (for re-age + prune)
    s->id    = dup_arena(m, J_str(js, "id"));
    s->name  = dup_arena(m, J_str(js, "name"));
    s->agent = dup_arena(m, J_str(js, "agent"));
    s->term  = dup_arena(m, J_str(js, "term"));
    s->age   = dup_arena(m, J_str(js, "age"));
    s->task  = dup_arena(m, J_str(js, "task"));    // the user's ask — disambiguates same-name sessions
    s->state = parse_state(J_str(js, "state"));

    // approve {tool,file,add,del}  (state == waiting)
    const cJSON *ap = cJSON_GetObjectItemCaseSensitive(js, "approve");
    s->appr_tool = dup_arena(m, J_str(ap, "tool"));
    s->appr_file = dup_arena(m, J_str(ap, "file"));
    s->add = J_int(ap, "add", 0);
    s->del = J_int(ap, "del", 0);

    // ask {q, opts[]}  (state == asking)
    const cJSON *ak = cJSON_GetObjectItemCaseSensitive(js, "ask");
    s->ask_q = dup_arena(m, J_str(ak, "q"));
    s->ask_opts = m->opts[i];
    s->ask_n = 0;
    const cJSON *opts = cJSON_GetObjectItemCaseSensitive(ak, "opts"), *o;
    cJSON_ArrayForEach(o, opts) {
        if (s->ask_n >= BR_MAX_OPTS) break;
        if (cJSON_IsString(o)) m->opts[i][s->ask_n++] = dup_arena(m, o->valuestring);
    }

    // done {summary, files, tests}  (state == done)
    const cJSON *dn = cJSON_GetObjectItemCaseSensitive(js, "done");
    s->done_summary = dup_arena(m, J_str(dn, "summary"));
    s->files = J_int(dn, "files", 0);
    s->tests = dup_arena(m, J_str(dn, "tests"));

    // activity[] {tool,detail} → one display line each (state == working)
    const cJSON *acts = cJSON_GetObjectItemCaseSensitive(js, "activity"), *a;
    s->act = m->acts[i];
    s->act_n = 0;
    cJSON_ArrayForEach(a, acts) {
        if (s->act_n >= BR_MAX_ACTS) break;
        const char *tool = J_str(a, "tool"), *detail = J_str(a, "detail");
        char buf[96];
        if (tool && detail)   snprintf(buf, sizeof buf, "%s(%s)", tool, detail);
        else if (detail)      snprintf(buf, sizeof buf, "%s", detail);
        else if (tool)        snprintf(buf, sizeof buf, "%s", tool);
        else                  buf[0] = '\0';
        m->acts[i][s->act_n++] = dup_arena(m, buf);
    }
}

// Parse a reassembled snapshot into the inactive store and swap it in under the lock.
static void apply_snapshot(const char *body) {
    cJSON *root = cJSON_Parse(body);
    if (!root) { ESP_LOGW(TAG, "snapshot: invalid JSON (%u bytes)", (unsigned)strlen(body)); return; }

    store_t *m = (s_live == &s_store[0]) ? &s_store[1] : &s_store[0];  // the inactive one
    m->used = 0;
    m->n = 0;
    strlcpy(m->clock, J_str(root, "clock") ? J_str(root, "clock") : "", sizeof m->clock);
    strlcpy(m->date,  J_str(root, "date")  ? J_str(root, "date")  : "", sizeof m->date);
    m->snap_ts = J_double(root, "ts");

    // Derive the tz offset (local−UTC) from the clock string vs the epoch, so the
    // device can show a correct *local* clock with no RTC — it has only the snapshot.
    m->tz_off = 0;
    int hh, mm;
    if (m->snap_ts > 0 && m->clock[0] && sscanf(m->clock, "%d:%d", &hh, &mm) == 2) {
        long off = (long)(hh * 3600 + mm * 60) - ((long)m->snap_ts % 86400);
        while (off < -43200) off += 86400;
        while (off >=  43200) off -= 86400;
        m->tz_off = (int)off;
    }

    const cJSON *arr = cJSON_GetObjectItemCaseSensitive(root, "sessions"), *js;
    cJSON_ArrayForEach(js, arr) {
        if (m->n >= BR_MAX_SESS) break;
        parse_session(m, m->n, js);
        m->n++;
    }
    cJSON_Delete(root);

    m->rx_us = esp_timer_get_time();   // monotonic base: now ≈ snap_ts + (esp_timer − rx_us)
    xSemaphoreTake(s_lock, portMAX_DELAY);
    s_live = m;
    s_seq++;
    xSemaphoreGive(s_lock);
    ESP_LOGI(TAG, "snapshot #%lu applied — %d session(s)", (unsigned long)s_seq, m->n);
}

// ── BLE: NimBLE GATT peripheral ──────────────────────────────────────────────────
// 128-bit UUIDs (role byte varies; canonical strings, role is the LAST byte):
//   service     00010000-7265-6761-702d-796464756200
//   snapshot    00010000-7265-6761-702d-796464756201   (WRITE — Mac → device)
//   resolution  00010000-7265-6761-702d-796464756202   (NOTIFY — device → Mac, Level-1)
//   control     00010000-7265-6761-702d-796464756203   (WRITE — Mac → device; settings)
#define PB_UUID(role) BLE_UUID128_INIT( \
    (role), 0x62, 0x75, 0x64, 0x64, 0x79, 0x2d, 0x70, \
    0x61, 0x67, 0x65, 0x72, 0x00, 0x00, 0x01, 0x00)

static const ble_uuid128_t s_svc_uuid  = PB_UUID(0x00);
static const ble_uuid128_t s_snap_uuid = PB_UUID(0x01);
static const ble_uuid128_t s_res_uuid  = PB_UUID(0x02);
static const ble_uuid128_t s_ctrl_uuid = PB_UUID(0x03);

// snapshot framing: 2-byte header [ver, flags] + payload chunk
#define PB_FRAME_VER   1
#define PB_FLAG_START  0x01
#define PB_FLAG_END    0x02

static volatile bool s_connected;
static uint16_t      s_conn_handle = BLE_HS_CONN_HANDLE_NONE;
static uint16_t      s_res_attr_handle;
static uint8_t       s_own_addr_type;
static char          s_device_name[8] = "pg-0000";

static char   s_rx[BR_RX_MAX];   // snapshot reassembly buffer
static size_t s_rx_len;

static char   s_ctrl_rx[256];    // control (settings) reassembly buffer — messages are tiny
static size_t s_ctrl_rx_len;

static void start_advertising(void);

// Mac → device: reassemble framed snapshot chunks; parse on END.
static int snapshot_write_cb(uint16_t conn_handle, uint16_t attr_handle,
                             struct ble_gatt_access_ctxt *ctxt, void *arg) {
    (void)conn_handle; (void)attr_handle; (void)arg;
    if (ctxt->op != BLE_GATT_ACCESS_OP_WRITE_CHR) return BLE_ATT_ERR_UNLIKELY;

    uint16_t len = OS_MBUF_PKTLEN(ctxt->om);
    if (len < 2) return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;

    uint8_t frame[517];   // one ATT write ≤ MTU; headroom for a 512-byte negotiated MTU
    if (len > sizeof(frame)) return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
    if (ble_hs_mbuf_to_flat(ctxt->om, frame, len, NULL) != 0) return BLE_ATT_ERR_UNLIKELY;

    if (frame[0] != PB_FRAME_VER) return BLE_ATT_ERR_UNLIKELY;
    uint8_t flags = frame[1];
    const uint8_t *payload = frame + 2;
    uint16_t plen = len - 2;

    if (flags & PB_FLAG_START) s_rx_len = 0;
    if (s_rx_len + plen >= sizeof(s_rx)) {       // overflow → drop, wait for next snapshot
        ESP_LOGW(TAG, "snapshot too large, dropping");
        s_rx_len = 0;
        return 0;
    }
    memcpy(s_rx + s_rx_len, payload, plen);
    s_rx_len += plen;

    if (flags & PB_FLAG_END) {
        s_rx[s_rx_len] = '\0';
        apply_snapshot(s_rx);
        s_rx_len = 0;
    }
    return 0;
}

static int notify_only_cb(uint16_t conn_handle, uint16_t attr_handle,
                          struct ble_gatt_access_ctxt *ctxt, void *arg) {
    (void)conn_handle; (void)attr_handle; (void)ctxt; (void)arg;
    return 0;   // resolution char is notify-only; nothing to read/write here
}

// Parse a reassembled control message — {"audio":0|1,"vol":0..100} — and store the
// settings under the lock, bumping s_set_seq so main picks them up. Pure receiver:
// we never touch the audio component here; main applies it (bridge_take_settings).
static void apply_settings(const char *body) {
    cJSON *root = cJSON_Parse(body);
    if (!root) { ESP_LOGW(TAG, "settings: invalid JSON"); return; }
    const cJSON *a = cJSON_GetObjectItemCaseSensitive(root, "audio");
    const cJSON *v = cJSON_GetObjectItemCaseSensitive(root, "vol");

    xSemaphoreTake(s_lock, portMAX_DELAY);
    if (cJSON_IsBool(a))        s_set_enabled = cJSON_IsTrue(a);
    else if (cJSON_IsNumber(a)) s_set_enabled = (a->valueint != 0);
    if (cJSON_IsNumber(v)) {
        int vol = v->valueint;
        if (vol < 0) vol = 0; else if (vol > 100) vol = 100;
        s_set_volume = vol;
    }
    s_set_seq++;
    bool en = s_set_enabled; int vol = s_set_volume;
    xSemaphoreGive(s_lock);
    cJSON_Delete(root);
    ESP_LOGI(TAG, "settings: audio=%s volume=%d", en ? "on" : "off", vol);
}

// Mac → device: reassemble framed control chunks (same framing as snapshot); apply on END.
static int control_write_cb(uint16_t conn_handle, uint16_t attr_handle,
                            struct ble_gatt_access_ctxt *ctxt, void *arg) {
    (void)conn_handle; (void)attr_handle; (void)arg;
    if (ctxt->op != BLE_GATT_ACCESS_OP_WRITE_CHR) return BLE_ATT_ERR_UNLIKELY;

    uint16_t len = OS_MBUF_PKTLEN(ctxt->om);
    if (len < 2) return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;

    uint8_t frame[260];
    if (len > sizeof(frame)) return BLE_ATT_ERR_INVALID_ATTR_VALUE_LEN;
    if (ble_hs_mbuf_to_flat(ctxt->om, frame, len, NULL) != 0) return BLE_ATT_ERR_UNLIKELY;

    if (frame[0] != PB_FRAME_VER) return BLE_ATT_ERR_UNLIKELY;
    uint8_t flags = frame[1];
    const uint8_t *payload = frame + 2;
    uint16_t plen = len - 2;

    if (flags & PB_FLAG_START) s_ctrl_rx_len = 0;
    if (s_ctrl_rx_len + plen >= sizeof(s_ctrl_rx)) { s_ctrl_rx_len = 0; return 0; }
    memcpy(s_ctrl_rx + s_ctrl_rx_len, payload, plen);
    s_ctrl_rx_len += plen;

    if (flags & PB_FLAG_END) {
        s_ctrl_rx[s_ctrl_rx_len] = '\0';
        apply_settings(s_ctrl_rx);
        s_ctrl_rx_len = 0;
    }
    return 0;
}

static const struct ble_gatt_svc_def s_gatt_services[] = {
    {
        .type = BLE_GATT_SVC_TYPE_PRIMARY,
        .uuid = &s_svc_uuid.u,
        .characteristics = (struct ble_gatt_chr_def[]) {
            {
                .uuid = &s_snap_uuid.u,
                .access_cb = snapshot_write_cb,
                .flags = BLE_GATT_CHR_F_WRITE | BLE_GATT_CHR_F_WRITE_NO_RSP,
            },
            {
                .uuid = &s_res_uuid.u,
                .access_cb = notify_only_cb,
                .val_handle = &s_res_attr_handle,
                .flags = BLE_GATT_CHR_F_NOTIFY,
            },
            {
                .uuid = &s_ctrl_uuid.u,
                .access_cb = control_write_cb,
                .flags = BLE_GATT_CHR_F_WRITE | BLE_GATT_CHR_F_WRITE_NO_RSP,
            },
            {0},
        },
    },
    {0},
};

static int gap_event_cb(struct ble_gap_event *event, void *arg) {
    (void)arg;
    switch (event->type) {
    case BLE_GAP_EVENT_CONNECT:
        if (event->connect.status == 0) {
            s_connected = true;
            s_conn_handle = event->connect.conn_handle;
            ESP_LOGI(TAG, "central connected (handle=%u)", s_conn_handle);
            // Initiate MTU exchange from our side — some centrals don't, and the
            // default 23-byte MTU would force tiny snapshot chunks. (voicestick gotcha)
            ble_gattc_exchange_mtu(s_conn_handle, NULL, NULL);
        } else {
            ESP_LOGW(TAG, "connect failed status=%d", event->connect.status);
            start_advertising();
        }
        return 0;
    case BLE_GAP_EVENT_DISCONNECT:
        ESP_LOGI(TAG, "central disconnected (reason=%d)", event->disconnect.reason);
        s_connected = false;
        s_conn_handle = BLE_HS_CONN_HANDLE_NONE;
        s_rx_len = 0;
        s_ctrl_rx_len = 0;
        start_advertising();
        return 0;
    case BLE_GAP_EVENT_MTU:
        ESP_LOGI(TAG, "MTU = %u", event->mtu.value);
        return 0;
    default:
        return 0;
    }
}

static void start_advertising(void) {
    if (s_connected || ble_gap_adv_active()) return;

    struct ble_hs_adv_fields fields = {0};
    fields.flags = BLE_HS_ADV_F_DISC_GEN | BLE_HS_ADV_F_BREDR_UNSUP;
    fields.uuids128 = &s_svc_uuid;
    fields.num_uuids128 = 1;
    fields.uuids128_is_complete = 1;
    if (ble_gap_adv_set_fields(&fields) != 0) { ESP_LOGE(TAG, "adv set_fields failed"); return; }

    struct ble_hs_adv_fields rsp = {0};
    rsp.name = (const uint8_t *)s_device_name;
    rsp.name_len = strlen(s_device_name);
    rsp.name_is_complete = 1;
    if (ble_gap_adv_rsp_set_fields(&rsp) != 0) { ESP_LOGE(TAG, "adv rsp failed"); return; }

    struct ble_gap_adv_params params = {0};
    params.conn_mode = BLE_GAP_CONN_MODE_UND;
    params.disc_mode = BLE_GAP_DISC_MODE_GEN;
    int rc = ble_gap_adv_start(s_own_addr_type, NULL, BLE_HS_FOREVER, &params, gap_event_cb, NULL);
    if (rc != 0) { ESP_LOGW(TAG, "adv start failed rc=%d", rc); return; }
    ESP_LOGI(TAG, "advertising as %s", s_device_name);
}

static void on_sync(void) {
    if (ble_hs_id_infer_auto(0, &s_own_addr_type) != 0) {
        ESP_LOGE(TAG, "infer addr type failed");
        return;
    }
    start_advertising();
}

static void on_reset(int reason) { ESP_LOGE(TAG, "BLE reset, reason=%d", reason); }

static void nimble_host_task(void *param) {
    (void)param;
    nimble_port_run();
    nimble_port_freertos_deinit();
}

// ── public API ───────────────────────────────────────────────────────────────────
void bridge_start(void) {
    if (!s_lock) s_lock = xSemaphoreCreateMutex();   // borrow/release work even pre-connect

    uint8_t mac[6] = {0};
    if (esp_efuse_mac_get_default(mac) == ESP_OK)
        snprintf(s_device_name, sizeof s_device_name, "pg-%02X%02X", mac[4], mac[5]);

    esp_err_t err = nvs_flash_init();
    if (err == ESP_ERR_NVS_NO_FREE_PAGES || err == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        err = nvs_flash_init();
    }
    ESP_ERROR_CHECK(err);

    ESP_ERROR_CHECK(nimble_port_init());
    ble_svc_gap_init();
    ble_svc_gatt_init();

    ble_hs_cfg.reset_cb = on_reset;
    ble_hs_cfg.sync_cb = on_sync;
    ble_hs_cfg.sm_bonding = 0;          // open link, like voicestick (no pairing)

    ESP_ERROR_CHECK(ble_svc_gap_device_name_set(s_device_name) == 0 ? ESP_OK : ESP_FAIL);
    ESP_ERROR_CHECK(ble_gatts_count_cfg(s_gatt_services) == 0 ? ESP_OK : ESP_FAIL);
    ESP_ERROR_CHECK(ble_gatts_add_svcs(s_gatt_services) == 0 ? ESP_OK : ESP_FAIL);

    nimble_port_freertos_init(nimble_host_task);
    ESP_LOGI(TAG, "BLE up — %s (waiting for the Mac bridge to connect)", s_device_name);
}

bool        bridge_online(void)      { return s_connected; }
uint32_t    bridge_seq(void)         { return s_seq; }
const char *bridge_device_name(void) { return s_device_name; }

// Freshened projection of the live store (rebuilt each borrow), per protocol.yaml
// `freshness`: re-age every session from its `ts`, DROP any idle past the TTL, and
// tick the local clock — all on the device's own monotonic clock anchored to the
// snapshot's epoch, so the display stays correct between pushes (and while the BLE
// link is down) with no RTC.
static session_t s_view_sess[BR_MAX_SESS];
static char      s_view_age[BR_MAX_SESS][8];
static char      s_view_clock[12];

const bridge_view_t *bridge_borrow(void) {
    if (!s_lock) return NULL;
    xSemaphoreTake(s_lock, portMAX_DELAY);
    if (!s_live) return NULL;            // lock held — caller still calls bridge_release()

    store_t *m = s_live;
    bool have_clock = m->snap_ts > 0;
    double now = have_clock ? m->snap_ts + (esp_timer_get_time() - m->rx_us) / 1e6 : 0;

    int k = 0;
    for (int i = 0; i < m->n; i++) {
        if (have_clock && m->ts[i] > 0) {
            double idle = now - m->ts[i];
            if (idle > BR_IDLE_TTL) continue;            // prune idle/closed sessions
            s_view_sess[k] = m->s[i];
            humanize_age(idle, s_view_age[k], sizeof s_view_age[k]);
            s_view_sess[k].age = s_view_age[k];          // re-aged on our clock
        } else {
            s_view_sess[k] = m->s[i];                    // no `ts` → trust the wire age
        }
        k++;
    }

    const char *clock = m->clock;
    if (have_clock && m->clock[0]) {                     // tick HH:MM locally
        long local = ((long)now + m->tz_off) % 86400;
        if (local < 0) local += 86400;
        int hh = (int)(local / 3600) % 100, mm = (int)((local % 3600) / 60) % 100;
        snprintf(s_view_clock, sizeof s_view_clock, "%02d:%02d", hh, mm);
        clock = s_view_clock;
    }

    s_view.sessions = s_view_sess;
    s_view.n        = k;
    s_view.clock    = clock;
    s_view.date     = m->date;
    s_view.seq      = s_seq;
    return &s_view;
}

void bridge_release(void) {
    if (s_lock) xSemaphoreGive(s_lock);
}

bool bridge_take_settings(bool *enabled, int *volume) {
    if (!s_lock) return false;
    bool changed = false;
    xSemaphoreTake(s_lock, portMAX_DELAY);
    if (s_set_seq != s_set_taken) {
        s_set_taken = s_set_seq;
        if (enabled) *enabled = s_set_enabled;
        if (volume)  *volume  = s_set_volume;
        changed = true;
    }
    xSemaphoreGive(s_lock);
    return changed;
}

esp_err_t bridge_send_resolution(const char *session_id, const char *action) {
    if (!s_connected || s_conn_handle == BLE_HS_CONN_HANDLE_NONE) return ESP_ERR_INVALID_STATE;
    char json[160];
    int n = snprintf(json, sizeof json, "{\"session_id\":\"%s\",\"action\":\"%s\"}",
                     session_id ? session_id : "", action ? action : "");
    struct os_mbuf *om = ble_hs_mbuf_from_flat(json, n);
    if (!om) return ESP_ERR_NO_MEM;
    return ble_gatts_notify_custom(s_conn_handle, s_res_attr_handle, om) == 0 ? ESP_OK : ESP_FAIL;
}
