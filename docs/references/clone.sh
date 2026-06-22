#!/usr/bin/env bash
# Clone the firmware reference projects listed in ../awesome-firmware.md into the
# gitignored _clones/ dir for local study. Idempotent: skips repos already present.
# The links are versioned (awesome-firmware.md); the bulky third-party code is not.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
dest="$here/_clones"
mkdir -p "$dest"

# name|url   (keep in sync with the table in ../awesome-firmware.md)
refs=(
  "xiaozhi-esp32|https://github.com/78/xiaozhi-esp32"
  "esp-box|https://github.com/espressif/esp-box"
  "esp-bsp|https://github.com/espressif/esp-bsp"
  "esp-iot-solution|https://github.com/espressif/esp-iot-solution"
  "voicestick|https://github.com/78/voicestick"
)

for entry in "${refs[@]}"; do
  name="${entry%%|*}"
  url="${entry##*|}"
  target="$dest/$name"
  if [ -d "$target/.git" ]; then
    echo "✓ $name already cloned ($target) — skipping"
    continue
  fi
  echo "↓ cloning $name from $url …"
  git clone --depth 1 --single-branch "$url" "$target"
done

echo
echo "Done. Reference clones live in: $dest (gitignored)."
