# 78/xiaozhi-esp32 — study note

**Repo:** https://github.com/78/xiaozhi-esp32 · **Framework:** ESP-IDF ≥ 5.4 ·
**License:** MIT · **Local clone:** `_clones/xiaozhi-esp32/` (run [`clone.sh`](clone.sh))

An open-source AI-chatbot firmware that runs on 70+ ESP32-C3 / S3 / P4 boards (~27k ★).
Voice in → streaming ASR + LLM + TTS → voice out, with offline wake-word, on-device
display / emoji, and IoT control over MCP. It's the largest *well-structured* ESP-IDF
app we know of — the reference for keeping a big firmware modular instead of one giant
`main.c`.

## What to read, and why

| Area | Where (roughly) | Maps to in this repo |
|---|---|---|
| Layered components (board / audio / display / protocol) | `main/boards/`, `main/audio/`, `main/display/`, `main/protocols/` | [`vibe-firmware/references/esp-idf-structure.md`](../../skills/vibe-firmware/references/esp-idf-structure.md) — "three layers, thin main" |
| Per-board BSP behind one board interface | `main/boards/<board>/` | our `<board>_board` BSP pattern |
| Transport-agnostic link (WebSocket *and* MQTT+UDP behind one API) | `main/protocols/` | the `bridge` / link component idea |
| OPUS audio pipeline (encode / decode, 16 kHz) | `main/audio/` | pager-buddy audio bring-up (next peripheral) |
| OTA + version / activation flow | the `Ota` class + OTA flow | dual-slot OTA in esp-idf-structure.md |
| Power management / battery | per-board PM code | `sdkconfig` PM + tiered deep-sleep |

## Caveats

- Big and fast-moving — pin to a tag/commit when you cite it; don't track `main` blindly.
- MIT-licensed, so patterns *and* snippets are reusable — keep attribution if you lift code.
- The backend / LLM plumbing is out of scope for us; read it for the **firmware structure**.
