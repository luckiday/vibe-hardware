#!/usr/bin/env python3
"""analytics.py — a local SQLite log of Claude Code agent activity, plus reports.

The pager hook (claude_pager_hook.py) calls record_event() once per Claude Code
hook event, appending one row to a small SQLite database (default
~/.pager-buddy/analytics.db). Like the hook itself, every write here is
**best-effort and fails open** — analytics must never block or break the agent.

`report` turns that raw event log into a human summary (and --json so you can pipe
it into your own screen-time tooling):

  * distinct agent sessions per day               ("how many sessions today?")
  * average / median instruction time             (UserPromptSubmit → Stop)
  * tool-call counts, active hours, per-project breakdown
  * a coverage-based "active time" estimate       (screen-time friendly)

Why the hook, not the hub: the hook sees *every* lifecycle event with its real
timestamp, session_id, tool_name and cwd. The hub only ever sees aggregated
snapshots, so it can't tell one instruction from the next.

Usage:
  analytics.py report [--date YYYY-MM-DD] [--days N] [--json] [--db PATH]
  analytics.py prune  [--keep-days N]              # drop rows older than N days

Env:
  PAGER_BUDDY_DB         database path (default ~/.pager-buddy/analytics.db)
  PAGER_BUDDY_ANALYTICS  set to off/none/0 to disable recording entirely
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta

DEFAULT_DB = "~/.pager-buddy/analytics.db"

# One "instruction" = a user turn: from a prompt to the agent going quiet.
TURN_START = "UserPromptSubmit"
TURN_END = {"Stop", "StopFailure"}

# Coverage-based "active time": bucket events into ACTIVE_BIN-second bins; any bin
# with at least one event counts as active, so active_time ≈ active_bins × ACTIVE_BIN.
# 5 min smooths over read/think gaps without inflating a single quick command into
# an hour — a sane proxy to line up against macOS Screen Time.
ACTIVE_BIN = 300


# ── tiny ANSI helpers (respect NO_COLOR / non-tty; same language as `pager`) ──────
_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None
BOLD, DIM = "1", "2"


def _c(code: str, s: str) -> str:
    return f"\033[{code}m{s}\033[0m" if _COLOR else s


# ── database ──────────────────────────────────────────────────────────────────────
def db_path(explicit: str | None = None) -> str:
    return os.path.expanduser(explicit or os.environ.get("PAGER_BUDDY_DB", DEFAULT_DB))


def _connect(path: str) -> sqlite3.Connection:
    """Open (creating the schema if needed). WAL + a busy timeout let concurrent
    one-shot hook processes append without tripping over each other."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=2.0)
    conn.execute("PRAGMA busy_timeout=2000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         REAL    NOT NULL,   -- epoch seconds (fractional)
            day        TEXT    NOT NULL,   -- local 'YYYY-MM-DD' (cheap grouping)
            hour       INTEGER NOT NULL,   -- local hour 0-23 (cheap histogram)
            session_id TEXT,
            event      TEXT,               -- hook_event_name
            tool       TEXT,               -- tool_name (PreToolUse / PermissionRequest)
            project    TEXT,               -- basename(cwd)
            cwd        TEXT,
            agent      TEXT,
            term       TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_day ON events(day)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id)")
    return conn


def record_event(payload: dict, now: float | None = None, path: str | None = None) -> bool:
    """Append one hook event. Best-effort: any failure returns False without raising,
    so the agent is never affected. Disable with PAGER_BUDDY_ANALYTICS=off."""
    if os.environ.get("PAGER_BUDDY_ANALYTICS", "").strip().lower() in ("off", "none", "0"):
        return False
    now = time.time() if now is None else now
    try:
        local = datetime.fromtimestamp(now)
        cwd = payload.get("cwd") or ""
        project = os.path.basename(cwd.rstrip("/")) or None
        conn = _connect(db_path(path))
        try:
            conn.execute(
                "INSERT INTO events "
                "(ts, day, hour, session_id, event, tool, project, cwd, agent, term) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    now,
                    local.strftime("%Y-%m-%d"),
                    local.hour,
                    payload.get("session_id"),
                    payload.get("hook_event_name"),
                    payload.get("tool_name"),
                    project,
                    cwd or None,
                    payload.get("agent") or "Claude",
                    payload.get("terminal_app"),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        return True
    except Exception:
        return False  # fail open — analytics is never worth breaking the agent for


def db_stats(db: str | None = None) -> tuple[int, int, str | None]:
    """(total events, distinct days, last day) — for `pager doctor`."""
    path = db_path(db)
    if not os.path.exists(path):
        return 0, 0, None
    try:
        conn = _connect(path)
        try:
            row = conn.execute(
                "SELECT COUNT(*), COUNT(DISTINCT day), MAX(day) FROM events"
            ).fetchone()
            return int(row[0] or 0), int(row[1] or 0), row[2]
        finally:
            conn.close()
    except Exception:
        return 0, 0, None


def prune(keep_days: int, db: str | None = None) -> int:
    cutoff = (date.today() - timedelta(days=max(0, keep_days))).strftime("%Y-%m-%d")
    conn = _connect(db_path(db))
    try:
        cur = conn.execute("DELETE FROM events WHERE day < ?", (cutoff,))
        conn.commit()
        conn.execute("VACUUM")
        return cur.rowcount
    finally:
        conn.close()


# ── compute ─────────────────────────────────────────────────────────────────────
def _turns(rows):
    """Yield (session_id, start_ts, end_ts, start_day) per completed instruction.

    `rows` must be ordered by session_id, ts. A turn opens on UserPromptSubmit and
    closes on the next Stop in the same session; a second prompt before any Stop
    replaces the open start (the user interrupted), so we never measure across it."""
    open_start: dict = {}
    for ts, day, hour, sid, event, tool, project in rows:
        if event == TURN_START:
            open_start[sid] = (ts, day)
        elif event in TURN_END and sid in open_start:
            start_ts, start_day = open_start.pop(sid)
            yield sid, start_ts, ts, start_day


def _median(xs: list[float]) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def compute(conn: sqlite3.Connection, days: list[str]) -> dict:
    placeholders = ",".join("?" for _ in days)
    rows = conn.execute(
        f"SELECT ts, day, hour, session_id, event, tool, project FROM events "
        f"WHERE day IN ({placeholders}) ORDER BY session_id, ts",
        days,
    ).fetchall()

    durations = [e - s for _, s, e, _ in _turns(rows) if e >= s]

    sessions: set = set()
    prompts = 0
    tools: Counter = Counter()
    hours: Counter = Counter()          # 所有事件 / 小时 (活跃直方图)
    prompt_hours: Counter = Counter()   # 仅 prompt / 小时
    active: set = set()
    first_ts = last_ts = None
    per_day: dict = defaultdict(
        lambda: {"sessions": set(), "prompts": 0, "events": 0, "active": set()}
    )
    projects: dict = defaultdict(
        lambda: {"sessions": set(), "prompts": 0, "active": set()}
    )

    for ts, day, hour, sid, event, tool, project in rows:
        bin_ = int(ts // ACTIVE_BIN)
        active.add(bin_)
        hours[hour] += 1
        per_day[day]["events"] += 1
        per_day[day]["active"].add(bin_)
        if sid:
            sessions.add(sid)
            per_day[day]["sessions"].add(sid)
        if project:
            projects[project]["active"].add(bin_)
            if sid:
                projects[project]["sessions"].add(sid)
        if event == TURN_START:
            prompts += 1
            prompt_hours[hour] += 1
            per_day[day]["prompts"] += 1
            if project:
                projects[project]["prompts"] += 1
        if event == "PreToolUse" and tool:
            tools[tool] += 1
        first_ts = ts if first_ts is None else min(first_ts, ts)
        last_ts = ts if last_ts is None else max(last_ts, ts)

    return {
        "events": len(rows),
        "sessions": len(sessions),
        "prompts": prompts,
        "turns": {
            "count": len(durations),
            "avg": (sum(durations) / len(durations)) if durations else 0.0,
            "median": _median(durations),
            "total": sum(durations),
        },
        "tools": dict(tools.most_common()),
        "tool_calls": sum(tools.values()),
        "hours": {h: hours.get(h, 0) for h in range(24)},
        "prompt_hours": {h: prompt_hours.get(h, 0) for h in range(24)},
        "active_seconds": len(active) * ACTIVE_BIN,
        "first_ts": first_ts,
        "last_ts": last_ts,
        "per_day": {
            d: {
                "sessions": len(v["sessions"]),
                "prompts": v["prompts"],
                "events": v["events"],
                "active_seconds": len(v["active"]) * ACTIVE_BIN,
            }
            for d, v in sorted(per_day.items())
        },
        "projects": {
            p: {
                "sessions": len(v["sessions"]),
                "prompts": v["prompts"],
                "active_seconds": len(v["active"]) * ACTIVE_BIN,
            }
            for p, v in projects.items()
        },
    }


def resolve_days(date_str: str | None, n: int | None) -> list[str]:
    """A list of 'YYYY-MM-DD', oldest→newest, ending at --date (default today)."""
    anchor = (
        datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    )
    n = max(1, n or 1)
    return [(anchor - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(n - 1, -1, -1)]


def build_report(days: list[str], db: str | None = None) -> dict:
    path = db_path(db)
    conn = _connect(path)
    try:
        rep = compute(conn, days)
    finally:
        conn.close()
    rep["days"] = days
    rep["db"] = path
    return rep


# ── render ─────────────────────────────────────────────────────────────────────
def fmt_dur(seconds: float) -> str:
    s = int(round(seconds))
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m {s % 60:02d}s"
    return f"{s // 3600}h {(s % 3600) // 60:02d}m"


def fmt_span(seconds: float) -> str:
    s = int(round(seconds))
    if s < 3600:
        return f"{s // 60}m"
    return f"{s // 3600}h {(s % 3600) // 60:02d}m"


_BLOCKS = "▏▎▍▌▋▊▉█"  # 1/8 … 8/8


def bar(value: float, peak: float, width: int) -> str:
    if peak <= 0 or value <= 0:
        return ""
    units = (value / peak) * width
    full = int(units)
    s = "█" * full
    frac = units - full
    if frac > 0 and full < width:
        s += _BLOCKS[min(7, int(frac * 8))]
    return s or "▏"  # always show a sliver for any nonzero value


def _clock(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def _day_long(d: str) -> str:
    return datetime.strptime(d, "%Y-%m-%d").strftime("%a %b %-d %Y")


def _day_short(d: str) -> str:
    return datetime.strptime(d, "%Y-%m-%d").strftime("%a %m-%d")


def render_json(rep: dict) -> str:
    return json.dumps(rep, indent=2, sort_keys=True)


def render_text(rep: dict) -> str:
    days = rep["days"]
    out: list[str] = []
    if len(days) == 1:
        out.append(_c(BOLD, f"pager-buddy · report · {_day_long(days[0])}"))
    else:
        out.append(
            _c(BOLD, f"pager-buddy · report · {days[0]} → {days[-1]}  ({len(days)} days)")
        )
    out.append("")

    if rep["events"] == 0:
        out.append(_c(DIM, "  no agent activity recorded for this period."))
        out.append(_c(DIM, "  (are the hooks installed?  pager hooks status)"))
        return "\n".join(out)

    t = rep["turns"]
    span = ""
    if rep["first_ts"] and rep["last_ts"]:
        span = _c(DIM, f"   {_clock(rep['first_ts'])} → {_clock(rep['last_ts'])}")

    out.append(f"  sessions      {_c(BOLD, str(rep['sessions']))} distinct")
    if t["count"]:
        out.append(
            f"  instructions  {_c(BOLD, str(rep['prompts']))} prompts  ·  "
            f"avg {fmt_dur(t['avg'])} · median {fmt_dur(t['median'])}  "
            + _c(DIM, f"({t['count']} completed)")
        )
    else:
        out.append(f"  instructions  {_c(BOLD, str(rep['prompts']))} prompts")
    top = list(rep["tools"].items())[:8]
    tools_str = " · ".join(f"{k} {v}" for k, v in top)
    out.append(
        f"  tool calls    {_c(BOLD, str(rep['tool_calls']))}  "
        + (_c(DIM, f"({tools_str})") if tools_str else "")
    )
    out.append(f"  active time   ≈{fmt_span(rep['active_seconds'])}{span}")
    out.append("")

    if len(days) > 1:
        out.append(_c(DIM, "  by day"))
        peak = max((d["active_seconds"] for d in rep["per_day"].values()), default=0)
        for d in days:
            dd = rep["per_day"].get(
                d, {"sessions": 0, "prompts": 0, "active_seconds": 0}
            )
            b = bar(dd["active_seconds"], peak, 10)
            out.append(
                f"    {_day_short(d)}  {b:<10}  "
                f"{dd['sessions']} sess · {dd['prompts']} prompts · ≈{fmt_span(dd['active_seconds'])}"
            )
        out.append("")

    hrs = rep["hours"]
    active_hours = [h for h in range(24) if hrs[h] > 0]
    if active_hours:
        lo, hi = active_hours[0], active_hours[-1]
        peak = max(hrs.values())
        out.append(_c(DIM, "  by hour  (events)"))
        for h in range(lo, hi + 1):
            v = hrs[h]
            out.append(f"    {h:02d}  {bar(v, peak, 16):<16} {v}")
        out.append("")

    if rep["projects"]:
        out.append(_c(DIM, "  by project"))
        items = sorted(
            rep["projects"].items(), key=lambda kv: kv[1]["active_seconds"], reverse=True
        )[:6]
        width = max((len(p) for p, _ in items), default=0)
        for p, v in items:
            out.append(
                f"    {p:<{width}}  "
                f"{v['sessions']} sess · {v['prompts']} prompts · ≈{fmt_span(v['active_seconds'])}"
            )

    return "\n".join(out).rstrip()


# ── CLI ────────────────────────────────────────────────────────────────────────
def main() -> int:
    p = argparse.ArgumentParser(
        prog="analytics.py",
        description="local SQLite log of Claude Code agent activity + reports",
    )
    sub = p.add_subparsers(dest="cmd", required=True, metavar="<command>")

    r = sub.add_parser("report", help="summarize a day (or a range with --days)")
    r.add_argument("--date", help="anchor date YYYY-MM-DD (default today)")
    r.add_argument("--days", type=int, default=1, help="how many days back through --date")
    r.add_argument("--json", action="store_true", help="machine-readable output")
    r.add_argument("--db", help=f"database path (default {DEFAULT_DB})")

    pr = sub.add_parser("prune", help="drop rows older than --keep-days")
    pr.add_argument("--keep-days", type=int, default=90)
    pr.add_argument("--db")

    args = p.parse_args()
    if args.cmd == "report":
        rep = build_report(resolve_days(args.date, args.days), db=args.db)
        print(render_json(rep) if args.json else render_text(rep))
        return 0
    if args.cmd == "prune":
        n = prune(args.keep_days, db=args.db)
        print(f"pruned {n} row(s) older than {args.keep_days} days")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
