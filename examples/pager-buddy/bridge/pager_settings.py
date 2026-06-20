#!/usr/bin/env python3
"""pager_settings.py — the pager-buddy *audio settings session*.

Enable/disable the pager's alert audio and set its volume. This talks to the bridge
hub (pager_stub.py) over HTTP at /v1/settings; the already-running BLE relay
(ble_push.py) polls the hub and forwards changes to the device's control
characteristic. So the bridge must be up — start it with run.sh and leave it running.

    Claude hook ─▶ hub (pager_stub.py) ◀─ pager_settings.py   (you are here)
                        │  /v1/settings
                        ▼
                  ble_push.py ─BLE write→ pager (audio component)

Interactive (default — the "settings session"):
    python3 pager_settings.py

One-shot (scriptable):
    python3 pager_settings.py --audio on --volume 70
    python3 pager_settings.py --audio off
    python3 pager_settings.py --show

Env: PAGER_BUDDY_URL (the hub's snapshot URL; the settings URL is derived from it).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request


def settings_url() -> str:
    """Where the hub serves audio settings — next to the snapshot endpoint."""
    base = os.environ.get("PAGER_BUDDY_URL", "http://127.0.0.1:8787/v1/snapshot")
    if "/v1/snapshot" in base:
        return base.replace("/v1/snapshot", "/v1/settings")
    return base.rstrip("/") + "/v1/settings"


def get_settings(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=3) as r:
        return json.loads(r.read())


def post_settings(url: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method="POST",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=3) as r:
        return json.loads(r.read())


def _fmt(s: dict) -> str:
    return f"audio {'ON ' if s.get('audio_enabled') else 'off'} · volume {s.get('volume')}"


def interactive(url: str) -> int:
    print("pager-buddy · audio settings   (the bridge forwards changes to the device)")
    while True:
        try:
            s = get_settings(url)
        except Exception as e:
            print(f"\n  can't reach the hub at {url}: {e}")
            print("  is the bridge running?  →  ./run.sh")
            return 1
        print(f"\n  {_fmt(s)}")
        print("  [a] toggle audio   [v] set volume   [+/-] volume ±10   "
              "[0-100] set volume   [q] quit")
        try:
            cmd = input("  > ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        try:
            if cmd in ("q", "quit", "exit", ""):
                return 0
            elif cmd in ("a", "audio", "toggle"):
                post_settings(url, {"audio_enabled": not s.get("audio_enabled", True)})
            elif cmd == "on":
                post_settings(url, {"audio_enabled": True})
            elif cmd == "off":
                post_settings(url, {"audio_enabled": False})
            elif cmd == "+":
                post_settings(url, {"volume": min(100, int(s.get("volume", 0)) + 10)})
            elif cmd == "-":
                post_settings(url, {"volume": max(0, int(s.get("volume", 0)) - 10)})
            elif cmd in ("v", "volume"):
                val = input("  volume (0-100): ").strip()
                if val.lstrip("+-").isdigit():
                    post_settings(url, {"volume": int(val)})
            elif cmd.isdigit():
                post_settings(url, {"volume": int(cmd)})
            else:
                print("  ?")
        except Exception as e:
            print(f"  update failed: {e}")


def main() -> int:
    p = argparse.ArgumentParser(description="pager-buddy audio settings")
    p.add_argument("--audio", choices=["on", "off"], help="enable/disable alert audio")
    p.add_argument("--volume", type=int, metavar="0-100", help="set alert volume")
    p.add_argument("--show", action="store_true", help="print current settings and exit")
    args = p.parse_args()
    url = settings_url()

    # No flags → drop into the interactive settings session.
    if args.audio is None and args.volume is None and not args.show:
        return interactive(url)

    body: dict = {}
    if args.audio is not None:
        body["audio_enabled"] = (args.audio == "on")
    if args.volume is not None:
        body["volume"] = max(0, min(100, args.volume))
    try:
        s = post_settings(url, body) if body else get_settings(url)
    except Exception as e:
        print(f"can't reach the hub at {url}: {e}  (is the bridge running? ./run.sh)",
              file=sys.stderr)
        return 1
    print(_fmt(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
