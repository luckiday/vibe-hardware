#!/usr/bin/env python3
"""ble_push.py — relay status snapshots from the bridge hub to the pager over BLE.

The firmware link is BLE (the device is a NimBLE peripheral; see
../firmware/components/bridge). This is the Mac-side *central*: it connects to the
pager and WRITES the latest snapshot to the snapshot characteristic whenever it
changes. It reuses the existing hub (pager_stub.py) as the session registry —
hooks still POST there, the web mock still reads there — so this only adds the
BLE delivery leg:

    Claude hook ─POST→ pager_stub.py (hub, /v1/snapshot) ─GET poll→ ble_push.py ─BLE write→ pager

Run:
    pip install bleak                 # one-time
    python3 pager_stub.py             # the hub (hooks POST here)
    python3 ble_push.py               # this relay (scans for "pg-XXXX", connects, pushes)

The device must be flashed with the BLE firmware and advertising. Snapshots
larger than one BLE write are framed into chunks: a 2-byte header [ver=1, flags]
precedes each chunk, flags bit0=START (first), bit1=END (last). Matches
components/bridge/bridge.c.  See protocol.yaml for the wire format + UUIDs.
"""
from __future__ import annotations

import argparse
import asyncio
import functools
import json
import sys
import urllib.request

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    sys.exit("ble_push needs bleak:  pip install bleak")

# UUIDs — must match components/bridge/bridge.c (PB_UUID role byte = last byte).
SERVICE_UUID     = "00010000-7265-6761-702d-796464756200"
SNAPSHOT_UUID    = "00010000-7265-6761-702d-796464756201"  # WRITE  (Mac → device)
RESOLUTION_UUID  = "00010000-7265-6761-702d-796464756202"  # NOTIFY (device → Mac, Level-1)
CONTROL_UUID     = "00010000-7265-6761-702d-796464756203"  # WRITE  (Mac → device, settings)

FRAME_VER   = 1
FLAG_START  = 0x01
FLAG_END    = 0x02
NAME_PREFIX = "pg-"


def fetch_json(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return json.loads(r.read())
    except Exception:
        return None


def fetch_snapshot(hub_url: str) -> dict | None:
    return fetch_json(hub_url)


def content_key(snap: dict) -> str:
    """A stable key over the MEANINGFUL fields, ignoring the volatile time fields
    the hub re-stamps every serve (top-level ts/clock/date + each session's derived
    age). The device anchors its own clock on `ts` and re-ages locally, so we only
    push on real changes (state / sessions / activity) — not once per second."""
    meaningful = {k: v for k, v in snap.items() if k not in ("ts", "clock", "date")}
    meaningful["sessions"] = [
        {k: v for k, v in s.items() if k != "age"} for s in snap.get("sessions", [])
    ]
    return json.dumps(meaningful, sort_keys=True, separators=(",", ":"))


def frame_chunks(payload: bytes, chunk: int) -> list[bytes]:
    """Split payload into [ver, flags]+data chunks with START on the first, END on the last."""
    if not payload:
        return []
    parts = [payload[i:i + chunk] for i in range(0, len(payload), chunk)]
    out = []
    for i, part in enumerate(parts):
        flags = (FLAG_START if i == 0 else 0) | (FLAG_END if i == len(parts) - 1 else 0)
        out.append(bytes([FRAME_VER, flags]) + part)
    return out


async def find_device(adapter: str | None):
    print("[ble] scanning for the pager…")
    while True:
        # Match on the SERVICE UUID (robust) — the GAP name can be stale: macOS caches
        # it, so a unit that once ran other firmware may still report e.g. "VS-XXXX".
        found = await BleakScanner.discover(timeout=5.0, adapter=adapter, return_adv=True)
        for dev, adv in found.values():
            uuids = [u.lower() for u in (adv.service_uuids or [])]
            name = dev.name or (adv.local_name if adv else None) or ""
            if SERVICE_UUID in uuids or name.startswith(NAME_PREFIX):
                print(f"[ble] found {name or '?'} ({dev.address})")
                return dev
        print("[ble] none yet, retrying…")


def _post_resolution(res_url: str, res: dict) -> dict:
    req = urllib.request.Request(
        res_url, data=json.dumps(res).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=2) as r:
        return json.loads(r.read())


async def forward_resolution(hub_url: str, _sender, data: bytearray):
    """Forward a device resolution (the user's on-device selection) to the hub.

    Registered with bleak as an async (coroutine) callback so bleak awaits it — a
    plain function returning a coroutine would be left un-awaited (bleak 3.x only
    awaits `iscoroutinefunction` callbacks). The blocking HTTP POST is offloaded to
    a thread so it doesn't stall the BLE loop (which is also pushing snapshots)."""
    try:
        res = json.loads(bytes(data))
    except (json.JSONDecodeError, UnicodeDecodeError):
        print(f"[ble] ← resolution {bytes(data)!r}")
        return
    print(f"[ble] ← resolution {res}")
    res_url = hub_url.replace("/v1/snapshot", "/v1/resolution")
    try:
        reply = await asyncio.to_thread(_post_resolution, res_url, res)
        print(f"[ble] → hub /v1/resolution {reply}")
    except Exception as e:
        print(f"[ble] hub forward failed ({e})")


async def run(args: argparse.Namespace) -> int:
    settings_url = args.hub.replace("/v1/snapshot", "/v1/settings")
    while True:  # reconnect loop
        dev = await find_device(args.adapter)
        try:
            async with BleakClient(dev, adapter=args.adapter) as client:
                # ATT write payload = MTU − 3; reserve 2 for our frame header.
                mtu = getattr(client, "mtu_size", 23) or 23
                chunk = max(20, mtu - 3 - 2)
                print(f"[ble] connected (MTU {mtu}, chunk {chunk}B). pushing snapshots…")
                try:
                    # functools.partial of an async fn stays a coroutine function, so
                    # bleak awaits it (a lambda would not be — see forward_resolution).
                    await client.start_notify(
                        RESOLUTION_UUID, functools.partial(forward_resolution, args.hub))
                except Exception:
                    pass  # resolution is Level-1; ok if absent

                # Both keys reset per connection → snapshot + settings re-push on reconnect.
                last_key = None
                last_settings_key = None
                while client.is_connected:
                    snap = fetch_snapshot(args.hub)
                    if snap is not None:
                        key = content_key(snap)
                        if key != last_key:
                            # send the full (time-fresh) snapshot, not just the key
                            body = json.dumps(snap, separators=(",", ":")).encode()
                            for fr in frame_chunks(body, chunk):
                                await client.write_gatt_char(SNAPSHOT_UUID, fr, response=False)
                            n = len(snap.get("sessions", []))
                            print(f"[ble] → snapshot ({len(body)}B, {n} session(s))")
                            last_key = key

                    # Audio settings → the control characteristic (compact {audio,vol}).
                    st = fetch_json(settings_url)
                    if st is not None:
                        skey = json.dumps(st, sort_keys=True, separators=(",", ":"))
                        if skey != last_settings_key:
                            payload = json.dumps(
                                {"audio": 1 if st.get("audio_enabled", True) else 0,
                                 "vol": int(st.get("volume", 60))},
                                separators=(",", ":")).encode()
                            try:
                                for fr in frame_chunks(payload, chunk):
                                    await client.write_gatt_char(CONTROL_UUID, fr, response=False)
                                print(f"[ble] → settings {payload.decode()}")
                                last_settings_key = skey
                            except Exception as e:
                                # control char may be absent on older firmware — don't
                                # let it kill the snapshot path; retry next loop.
                                print(f"[ble] settings write skipped ({e})")
                    await asyncio.sleep(args.interval)
        except Exception as e:
            print(f"[ble] disconnected ({e}); rescanning…")
        await asyncio.sleep(1.0)


def main() -> int:
    p = argparse.ArgumentParser(description="relay snapshots to the pager over BLE")
    p.add_argument("--hub", default="http://127.0.0.1:8787/v1/snapshot",
                   help="bridge hub snapshot endpoint to poll (default: local pager_stub.py)")
    p.add_argument("--interval", type=float, default=1.0, help="hub poll seconds (default 1.0)")
    p.add_argument("--adapter", default=None, help="BLE adapter (Linux hciX; ignored on macOS)")
    args = p.parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\n[ble] stopped")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
