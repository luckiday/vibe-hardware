#pragma once
// Copy to secrets.h (gitignored) and fill in:  cp secrets.example.h secrets.h
// secrets.h is NEVER committed. Used by the Wi-Fi status client (a later stage).

#define WIFI_SSID      "your-ssid"
#define WIFI_PASSWORD  "your-password"

// The Claude Code hook bridge the device polls / subscribes for session status:
#define PAGER_ENDPOINT "http://192.168.1.50:8765/status"
