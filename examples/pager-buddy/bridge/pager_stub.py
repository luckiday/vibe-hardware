#!/usr/bin/env python3
"""pager_stub.py — stands in for the M5StickC S3 pager (the real ESP32 endpoint).

Implements the device side of the pager-buddy status protocol (protocol.yaml):

  POST /v1/snapshot   ← the Mac pushes the latest snapshot; we render it as an
                        ASCII "screen" (simulating the 135×240 display)
  GET  /v1/snapshot   → returns the last snapshot      (for a polling renderer)
  GET  /healthz       → 200 OK

With --ui it ALSO serves the design web mock (examples/pager-buddy/design) so you
can open http://host:port/ and watch live status in the rich UI — same origin,
no CORS hassle. Responses also send `Access-Control-Allow-Origin: *` so a UI
served elsewhere (e.g. python3 -m http.server in design/) can poll too.

This is throwaway scaffolding: it proves the Mac→device status path end-to-end
before any ST7789 C is written. The firmware ui_status component (and the design
mock) consume the exact same JSON.

Run:  python3 pager_stub.py [--port 8787] [--host 0.0.0.0] [--ui [DIR]]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import unicodedata
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WIDTH = 46  # inner width of the faux screen
# Hide sessions idle past this (renderer-side freshness; matches the hook default).
IDLE_TTL = int(os.environ.get("PAGER_BUDDY_IDLE_TTL", "600"))
REFRESH = 5  # seconds — re-render on a timer so stale sessions drop without new pushes

# When --ui is given, static files under this dir are served (set in main()).
UI_DIR = None
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

# state dot colors (ANSI) — mirrors design/styles.css color language
COLORS = {
    "working": "34",   # blue
    "waiting": "33",   # amber
    "asking": "36",    # cyan
    "done": "32",      # green
    "error": "31",     # red
}
STATE_LABEL = {
    "working": "working", "waiting": "needs you",
    "asking": "asks", "done": "done", "error": "error",
}

_latest = {"snapshot": None}


def color(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m"


def dot(state: str) -> str:
    return color(COLORS.get(state, "37"), "●")


def dwidth(text: str) -> int:
    """Display columns — CJK / fullwidth glyphs take two cells in a terminal."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in text)


def trunc(text, width: int) -> str:
    text = str(text)
    if dwidth(text) <= width:
        return text
    out, w = "", 0
    for c in text:
        cw = 2 if unicodedata.east_asian_width(c) in ("W", "F") else 1
        if w + cw > width - 1:
            break
        out, w = out + c, w + cw
    return out + "…"


def line(text: str = "") -> str:
    """One faux-screen row: left border, content padded to WIDTH, right border.

    Padding ignores ANSI color codes so colored dots don't skew alignment.
    """
    visible = _strip_ansi(text)
    pad = max(0, WIDTH - dwidth(visible))
    return f"│ {text}{' ' * pad} │"


def _strip_ansi(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        if text[i] == "\033":
            j = text.find("m", i)
            if j != -1:
                i = j + 1
                continue
        out.append(text[i])
        i += 1
    return "".join(out)


def humanize_age(seconds: float) -> str:
    s = max(0, int(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    if s < 86400:
        return f"{s // 3600}h"
    return f"{s // 86400}d"


def live_sessions(snapshot: dict) -> list:
    """Drop sessions idle past IDLE_TTL and re-age the rest on our own clock, so
    closed/idle sessions disappear even when the Mac hasn't pushed an update."""
    if not snapshot:
        return []
    now = time.time()
    out = []
    for s in snapshot.get("sessions", []):
        ts = s.get("ts")
        if ts is not None and now - ts > IDLE_TTL:
            continue
        s = dict(s)
        if ts is not None:
            s["age"] = humanize_age(now - ts)
        out.append(s)
    return out


def render(snapshot: dict) -> str:
    sessions = live_sessions(snapshot)
    need = sum(1 for s in sessions if s.get("state") in ("waiting", "asking"))
    clock = snapshot.get("clock", "--:--") if snapshot else "--:--"

    top = "┌" + "─" * (WIDTH + 2) + "┐"
    bottom = "└" + "─" * (WIDTH + 2) + "┘"
    sep = "├" + "─" * (WIDTH + 2) + "┤"

    rows = [top]
    title = "pager-buddy · stub device"
    rows.append(line(color("2", title)))
    counts = f"{len(sessions)} sessions"
    if need:
        counts += f" · {color('33', str(need) + ' need you')}"
    else:
        counts += " · all clear"
    rows.append(line(f"{clock}   {counts}"))
    rows.append(sep)

    if not sessions:
        rows.append(line(color("2", "(waiting for a snapshot…)")))
    else:
        for s in sessions:
            state = s.get("state", "working")
            name = trunc(s.get("name", "?"), 16).ljust(16)
            age = str(s.get("age", "")).rjust(4)
            chips = trunc(f"{s.get('agent', '?')}·{s.get('term', '?')}", 11).ljust(11)
            label = color(COLORS.get(state, "37"), STATE_LABEL.get(state, state))
            rows.append(line(f"{dot(state)} {name} {age}  {chips} {label}"))

    # detail panel: focus the most-recent actionable session, else top working one
    focus = _focus(sessions)
    if focus:
        rows.append(sep)
        rows.extend(line(r) for r in _detail(focus))

    rows.append(bottom)
    return "\n".join(rows)


def _focus(sessions):
    for state in ("waiting", "asking", "error", "done"):
        for s in sessions:
            if s.get("state") == state:
                return s
    return sessions[0] if sessions else None


def _detail(s) -> list[str]:
    state = s.get("state")
    if state == "waiting":
        a = s.get("approve", {})
        delta = ""
        if a.get("add") or a.get("del"):
            delta = f"  ({'+' + str(a['add']) if a.get('add') else ''}"
            delta += f" -{a['del']}" if a.get("del") else ""
            delta += ")"
        return [
            color("33", "⚠ Permission") + f"   {a.get('tool', '?')}{delta}",
            "  " + trunc(a.get("file", ""), WIDTH - 2),
            "  [ Deny ]   " + color("33", "[ Allow ]"),
        ]
    if state == "asking":
        ask = s.get("ask", {})
        out = [color("36", "▣ Claude asks") + f"   {trunc(ask.get('q', ''), WIDTH - 16)}"]
        for i, opt in enumerate(ask.get("opts", [])[:4], 1):
            out.append(f"  {i}. {trunc(opt, WIDTH - 5)}")
        return out
    if state == "done":
        d = s.get("done", {})
        extra = []
        if d.get("files") is not None or d.get("tests"):
            bits = []
            if d.get("files") is not None:
                bits.append(f"{d['files']} files")
            if d.get("tests"):
                bits.append(str(d["tests"]))
            extra = ["  " + " · ".join(bits)]
        return [
            color("32", "✓ ") + trunc(s.get("name", ""), WIDTH - 4),
            "  " + trunc(d.get("summary", ""), WIDTH - 2),
            *extra,
            "  " + color("32", "[ Jump ]") + "   [ Dismiss ]",
        ]
    if state == "error":
        return [color("31", "✕ error") + "   " + trunc(s.get("task", ""), WIDTH - 12)]
    # working
    out = [trunc(s.get("name", ""), WIDTH)]
    if s.get("task"):
        out.append(color("2", trunc(s["task"], WIDTH)))   # the title: what it's doing
    for act in s.get("activity", [])[-3:]:
        detail = trunc(act.get("detail", ""), WIDTH - 14)
        out.append(f"  {act.get('tool', '?')}( {detail} )")
    out.append(color("34", "▌ working…"))
    return out


def paint(snapshot: dict) -> None:
    sys.stdout.write("\033[2J\033[H")  # clear + home
    sys.stdout.write(render(snapshot) + "\n")
    live = len(live_sessions(snapshot)) if snapshot else 0
    sys.stdout.write(color("2", f"  {datetime.now().strftime('%H:%M:%S')} · {live} live "
                                f"· idle>{IDLE_TTL}s drops off\n"))
    sys.stdout.flush()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # silence default request logging
        pass

    def _send(self, code: int, body: dict):
        payload = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def _serve_static(self, path: str):
        rel = path.split("?", 1)[0]
        if rel in ("", "/"):
            rel = "/index.html"
        safe = os.path.normpath(os.path.join(UI_DIR, rel.lstrip("/")))
        try:
            inside = os.path.commonpath([safe, UI_DIR]) == UI_DIR
        except ValueError:
            inside = False
        if not inside or not os.path.isfile(safe):
            return self._send(404, {"error": "not found"})
        with open(safe, "rb") as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", CONTENT_TYPES.get(os.path.splitext(safe)[1], "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/healthz":
            return self._send(200, {"ok": True})
        if self.path.startswith("/v1/snapshot"):
            snap = _latest["snapshot"]
            if snap:
                # Re-stamp the time fields to NOW on serve: the device has no RTC and
                # anchors its clock + session re-aging on the snapshot's `ts` (see
                # protocol.yaml freshness). A re-served snapshot must carry serve-time,
                # not the stale hook-build time, or the device's clock drifts backward.
                moment = datetime.now()
                snap = {**snap,
                        "ts": round(time.time(), 3),
                        "clock": moment.strftime("%H:%M"),
                        "date": moment.strftime("%a %b %-d"),
                        "sessions": live_sessions(snap)}  # serve only live sessions
            else:
                snap = {"v": 1, "type": "snapshot", "sessions": []}
            return self._send(200, snap)
        if UI_DIR:
            return self._serve_static(self.path)
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/v1/snapshot"):
            return self._send(404, {"error": "not found"})
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b""
        try:
            snapshot = json.loads(raw)
        except Exception:
            return self._send(400, {"error": "invalid json"})
        _latest["snapshot"] = snapshot
        paint(snapshot)
        self._send(200, {"ok": True})


def main() -> int:
    parser = argparse.ArgumentParser(description="pager-buddy stub device")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--ui", nargs="?", const="../design", default=None,
                        help="also serve a static UI dir (default ../design) at /")
    args = parser.parse_args()

    global UI_DIR
    if args.ui is not None:
        UI_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), args.ui))
        if not os.path.isdir(UI_DIR):
            sys.stdout.write(color("31", f"  --ui dir not found: {UI_DIR} (serving data only)\n"))
            UI_DIR = None

    server = ThreadingHTTPServer((args.host, args.port), Handler)

    def _refresh_loop():
        while True:
            time.sleep(REFRESH)
            if _latest["snapshot"]:
                paint(_latest["snapshot"])
    threading.Thread(target=_refresh_loop, daemon=True).start()

    paint(None)
    shown_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    sys.stdout.write(color("2", f"  listening on http://{args.host}:{args.port}  "
                                f"(POST /v1/snapshot · Ctrl-C to stop)\n"))
    if UI_DIR:
        sys.stdout.write(color("36", f"  live UI → open http://{shown_host}:{args.port}/\n"))
    sys.stdout.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        sys.stdout.write("\n[stub] stopped\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
