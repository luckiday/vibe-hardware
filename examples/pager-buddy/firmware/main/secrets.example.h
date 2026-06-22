#pragma once
// Copy to secrets.h (gitignored) and fill in:  cp secrets.example.h secrets.h
// secrets.h is NEVER committed.
//
// The status link is BLE (components/bridge): the device advertises as "pg-XXXX"
// and the Mac connects — no Wi-Fi credentials, endpoint, or pairing secret needed,
// so the bridge needs nothing here today. These fields are reserved for later
// stages (a Wi-Fi fallback / OTA) and are NOT read by the current firmware.

// #define WIFI_SSID      "your-ssid"
// #define WIFI_PASSWORD  "your-password"
