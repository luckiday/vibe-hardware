# Reference projects

Study notes for the upstream firmware we learn from. The curated index lives one
level up in [`../awesome-firmware.md`](../awesome-firmware.md); this folder holds the
per-project deep dives and the fetch helper.

```
references/
  README.md             ← you are here
  xiaozhi-esp32.md      ← per-project study notes …
  esp-box.md
  esp-bsp.md
  esp-iot-solution.md
  voicestick.md
  clone.sh              ← clone every listed repo into _clones/ (depth-1, idempotent)
  _clones/              ← gitignored — the actual third-party code lands here
```

Run `./clone.sh` to populate `_clones/`. Nothing under `_clones/` is committed (it's
in [`../../.gitignore`](../../.gitignore)); only the links + notes here are. To add a
project, follow the steps in [`../awesome-firmware.md`](../awesome-firmware.md#adding-a-reference).
