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

FRAME_VER   = 1
FLAG_START  = 0x01
FLAG_END    = 0x02
NAME_PREFIX = "pg-"


def fetch_snapshot(hub_url: str) -> dict | None:
    try:
        with urllib.request.urlopen(hub_url, timeout=2) as r:
            return json.loads(r.read())
    except Exception:
        return None


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
        devs = await BleakScanner.discover(timeout=5.0, adapter=adapter)
        for d in devs:
            uuids = (d.details or {}).get("UUIDs", []) if isinstance(d.details, dict) else []
            if (d.name and d.name.startswith(NAME_PREFIX)) or \
               (SERVICE_UUID in [u.lower() for u in uuids]):
                print(f"[ble] found {d.name or '?'}  ({d.address})")
                return d
        print("[ble] none yet, retrying…")


async def on_resolution(_handle, data: bytearray):
    try:
        print(f"[ble] ← resolution {json.loads(data)}")
    except Exception:
        print(f"[ble] ← resolution {bytes(data)!r}")


async def run(args: argparse.Namespace) -> int:
    while True:  # reconnect loop
        dev = await find_device(args.adapter)
        try:
            async with BleakClient(dev, adapter=args.adapter) as client:
                # ATT write payload = MTU − 3; reserve 2 for our frame header.
                mtu = getattr(client, "mtu_size", 23) or 23
                chunk = max(20, mtu - 3 - 2)
                print(f"[ble] connected (MTU {mtu}, chunk {chunk}B). pushing snapshots…")
                try:
                    await client.start_notify(RESOLUTION_UUID, on_resolution)
                except Exception:
                    pass  # resolution is Level-1; ok if absent

                last_key = None
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
