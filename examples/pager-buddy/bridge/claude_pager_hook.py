#!/usr/bin/env python3
"""claude_pager_hook.py — Level-0 Claude Code → pager-buddy bridge (hook command).

Claude Code runs this once per hook event, piping the event payload as JSON to
stdin. We map the event into the pager-buddy status protocol (see protocol.yaml),
update a small file-backed session registry — so a per-event process can still
emit a *full* snapshot — and HTTP POST that snapshot to the device.

Design rules (mirrors open-vibe-island):
  * FAIL OPEN — any error exits 0 silently, so a down/slow device never blocks
    or alters Claude. Nothing is ever written to stdout (Claude parses hook
    stdout); diagnostics go to stderr only when PAGER_BUDDY_DEBUG is set.

Env:
  PAGER_BUDDY_URL    device endpoint   (default http://127.0.0.1:8787/v1/snapshot)
  PAGER_BUDDY_STATE  registry path     (default ~/.pager-buddy/state.json)
  PAGER_BUDDY_DEBUG  if set, log to stderr

Usage:
  claude_pager_hook.py --source claude     # normal: read one hook event from stdin
  claude_pager_hook.py --demo              # feed a scripted scenario (no Claude needed)
"""
from __future__ import annotations

import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from urllib import request as urlrequest

DEFAULT_URL = "http://127.0.0.1:8787/v1/snapshot"
DEFAULT_STATE = "~/.pager-buddy/state.json"
MAX_ACTIVITY = 3            # tool steps kept per session
STALE_AGE = 86_400         # drop sessions untouched for >24h
POST_TIMEOUT = 1.5         # seconds — keep small; we fail open


# ── logging (stderr only, opt-in) ──────────────────────────────────────────────
def debug(msg: str) -> None:
    if os.environ.get("PAGER_BUDDY_DEBUG"):
        sys.stderr.write(f"[pager-hook] {msg}\n")


# ── text/field helpers ─────────────────────────────────────────────────────────
def clip(value, limit: int = 80):
    if not value:
        return value
    collapsed = " ".join(str(value).split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 1] + "…"


def prettify(name: str) -> str:
    return name.replace("-", " ").replace("_", " ").strip() or name


def humanize_age(start: float, ref: float) -> str:
    secs = max(0, int(ref - start))
    if secs < 60:
        return f"{secs}s"
    mins = secs // 60
    if mins < 60:
        return f"{mins}m"
    hours = mins // 60
    if hours < 24:
        return f"{hours}h"
    return f"{hours // 24}d"


def extract_path(tool_input):
    if isinstance(tool_input, dict):
        for key in ("file_path", "path", "notebook_path", "target_file", "working_directory"):
            value = tool_input.get(key)
            if isinstance(value, str) and value:
                return value
    return None


def tool_detail(tool_input):
    if isinstance(tool_input, dict):
        for key in ("command", "file_path", "pattern", "query", "prompt", "description", "skill", "url"):
            value = tool_input.get(key)
            if isinstance(value, str) and value:
                return clip(value)
    if isinstance(tool_input, str):
        return clip(tool_input)
    return None


def infer_terminal(env):
    """Best-effort terminal/IDE name from the hook's environment.

    Claude Code's hook payload has no terminal field, so we read the env the hook
    inherits. TERM_PROGRAM is the authoritative signal (each terminal sets it when
    it spawns the shell); per-app vars are fallbacks only. Simplified port of
    open-vibe-island's inferTerminalApp.
    """
    # multiplexers expose their own context; detect before the host terminal
    if env.get("CMUX_WORKSPACE_ID") or env.get("CMUX_SOCKET_PATH"):
        return "cmux"
    if env.get("ZELLIJ"):
        return "Zellij"
    if env.get("TMUX"):
        return "tmux"

    tp = (env.get("TERM_PROGRAM") or "").lower()
    if tp:
        if tp == "apple_terminal":
            return "Terminal"
        if "iterm" in tp:
            return "iTerm"
        if "warp" in tp:
            return "Warp"
        if "ghostty" in tp:
            return "Ghostty"
        if tp == "wezterm":
            return "WezTerm"
        if tp == "tabby":
            return "Tabby"
        if tp == "vscode":
            return "Cursor" if env.get("CURSOR_TRACE_ID") else "VS Code"
        if tp == "vscode-insiders":
            return "VS Code Insiders"
        if tp == "windsurf":
            return "Windsurf"

    # Claude Code running as an editor extension: the extension host has no shell,
    # so TERM_PROGRAM is unset. Use Claude's own entrypoint + the macOS app bundle.
    if "vscode" in (env.get("CLAUDE_CODE_ENTRYPOINT") or "").lower():
        bundle = (env.get("__CFBundleIdentifier") or "").lower()
        if "cursor" in bundle or env.get("CURSOR_TRACE_ID"):
            return "Cursor"
        if "windsurf" in bundle:
            return "Windsurf"
        if "insiders" in bundle:
            return "VS Code Insiders"
        if "vscodium" in bundle:
            return "VSCodium"
        return "VS Code"

    # fallbacks (vulnerable to GUI env inheritance; only when TERM_PROGRAM is empty)
    if env.get("ITERM_SESSION_ID") or env.get("LC_TERMINAL") == "iTerm2":
        return "iTerm"
    if env.get("WARP_IS_LOCAL_SHELL_SESSION"):
        return "Warp"
    if env.get("GHOSTTY_RESOURCES_DIR"):
        return "Ghostty"
    if env.get("KITTY_WINDOW_ID"):
        return "kitty"
    if env.get("ALACRITTY_SOCKET") or env.get("ALACRITTY_WINDOW_ID"):
        return "Alacritty"
    if "jetbrains" in (env.get("TERMINAL_EMULATOR") or "").lower():
        return "JetBrains"
    return None


def extract_question(tool_input):
    if not isinstance(tool_input, dict):
        return None
    questions = tool_input.get("questions")
    if not isinstance(questions, list) or not questions:
        return None
    first = questions[0]
    if not isinstance(first, dict):
        return None
    q = first.get("question")
    opts = [
        o["label"]
        for o in (first.get("options") or [])
        if isinstance(o, dict) and o.get("label")
    ]
    if not q or not opts:
        return None
    return {"q": clip(q, 60), "opts": opts}


# ── registry (file-backed, locked) ──────────────────────────────────────────────
@contextmanager
def locked(state_path: str):
    """Serialize concurrent hook processes around the registry file."""
    os.makedirs(os.path.dirname(state_path), exist_ok=True)
    lock_path = state_path + ".lock"
    handle = open(lock_path, "w")
    try:
        try:
            import fcntl  # POSIX only; this bridge targets macOS/Linux
            fcntl.flock(handle, fcntl.LOCK_EX)
        except Exception as exc:  # noqa: BLE001 — best effort; never block the agent
            debug(f"lock unavailable, proceeding unlocked: {exc}")
        yield
    finally:
        handle.close()


def load_registry(state_path: str) -> dict:
    try:
        with open(state_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("sessions"), dict):
            return data
    except FileNotFoundError:
        pass
    except Exception as exc:  # noqa: BLE001 — corrupt file shouldn't wedge the hook
        debug(f"registry reset ({exc})")
    return {"sessions": {}}


def save_registry(state_path: str, registry: dict) -> None:
    tmp = state_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(registry, fh)
    os.replace(tmp, state_path)


# ── event → session-state mapping (see protocol.yaml event_mapping) ──────────────
def _clear_actions(session: dict, keep_done: bool = False) -> None:
    session.pop("approve", None)
    session.pop("ask", None)
    if not keep_done:
        session.pop("done", None)


def _push_activity(session: dict, tool, detail) -> None:
    if not tool:
        return
    activity = session.setdefault("activity", [])
    activity.append({"tool": tool, "detail": detail or ""})
    del activity[:-MAX_ACTIVITY]


def apply_event(registry: dict, payload: dict, now: float) -> None:
    event = payload.get("hook_event_name") or ""
    sid = payload.get("session_id") or "unknown"
    sessions = registry.setdefault("sessions", {})

    if event == "SessionEnd":
        sessions.pop(sid, None)
        return

    session = sessions.get(sid)
    cwd = payload.get("cwd") or ""
    if session is None:
        session = {
            "id": sid,
            "name": prettify(os.path.basename(cwd.rstrip("/"))) or "session",
            "agent": "Claude",
            "term": payload.get("terminal_app") or "—",
            "state": "working",
            "task": "",
            "activity": [],
            "started_at": now,
        }
        sessions[sid] = session

    session["updated_at"] = now
    if payload.get("terminal_app"):
        session["term"] = payload["terminal_app"]

    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")

    if event == "SessionStart":
        session["state"] = "working"
    elif event == "UserPromptSubmit":
        session["state"] = "working"
        session["task"] = clip(payload.get("prompt")) or session["task"]
        _clear_actions(session)
    elif event == "PreToolUse":
        if tool == "AskUserQuestion":
            ask = extract_question(tool_input)
            if ask:
                session["state"] = "asking"
                session["ask"] = ask
        else:
            session["state"] = "working"
            _clear_actions(session)
            _push_activity(session, tool, tool_detail(tool_input))
    elif event == "PermissionRequest":
        if tool == "AskUserQuestion":
            ask = extract_question(tool_input)
            if ask:
                session["state"] = "asking"
                session["ask"] = ask
        else:
            session["state"] = "waiting"
            session["approve"] = {
                "tool": tool or "tool",
                "file": extract_path(tool_input) or clip(tool_detail(tool_input)) or cwd,
            }
    elif event == "Notification":
        message = payload.get("message") or payload.get("title")
        if message:
            session["task"] = clip(message)
    elif event in ("PostToolUseFailure", "StopFailure"):
        session["state"] = "error"
        session["task"] = clip(payload.get("error") or payload.get("message")) or session["task"]
    elif event == "Stop":
        session["state"] = "done"
        summary = clip(payload.get("last_assistant_message")) or session.get("task") or "Done."
        session["done"] = {"summary": summary}
        _clear_actions(session, keep_done=True)


# ── snapshot ─────────────────────────────────────────────────────────────────
def build_snapshot(registry: dict, now: float) -> dict:
    rows = []
    for session in registry.get("sessions", {}).values():
        touched = session.get("updated_at", session.get("started_at", now))
        if now - touched > STALE_AGE:
            continue
        out = {
            "id": session["id"],
            "name": session["name"],
            "agent": session.get("agent", "Claude"),
            "term": session.get("term", "—"),
            "age": humanize_age(session.get("started_at", now), now),
            "state": session.get("state", "working"),
            "task": session.get("task", ""),
            "activity": session.get("activity", []),
        }
        for key in ("approve", "ask", "done"):
            if key in session:
                out[key] = session[key]
        rows.append((touched, out))

    rows.sort(key=lambda item: item[0], reverse=True)
    moment = datetime.now()
    return {
        "v": 1,
        "type": "snapshot",
        "ts": round(now, 3),
        "clock": moment.strftime("%H:%M"),
        "date": moment.strftime("%a %b %-d"),
        "sessions": [row for _, row in rows],
    }


def post_snapshot(url: str, snapshot: dict) -> None:
    body = json.dumps(snapshot).encode("utf-8")
    req = urlrequest.Request(
        url, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urlrequest.urlopen(req, timeout=POST_TIMEOUT) as resp:
        resp.read()


def emit(payload: dict, url: str, state_path: str) -> None:
    """Apply one event and push the resulting snapshot. Fails open."""
    now = time.time()
    try:
        with locked(state_path):
            registry = load_registry(state_path)
            apply_event(registry, payload, now)
            save_registry(state_path, registry)
            snapshot = build_snapshot(registry, now)
    except Exception as exc:  # noqa: BLE001
        debug(f"registry error: {exc}")
        return
    try:
        post_snapshot(url, snapshot)
    except Exception as exc:  # noqa: BLE001
        debug(f"post failed (device offline?): {exc}")


# ── demo: drive the design scenario through the real mapping code ────────────────
def run_demo(url: str, state_path: str) -> int:
    demo_state = state_path + ".demo"
    try:
        os.remove(demo_state)
    except OSError:
        pass

    sys.stderr.write(f"[demo] feeding scripted Claude hook events → {url}\n")
    sys.stderr.write("[demo] (run pager_stub.py in another terminal to watch the screen)\n")

    fix, backend, opt = "s-fix", "s-backend", "s-opt"
    steps = [
        (0.4, {"hook_event_name": "SessionStart", "session_id": fix,
               "cwd": "/Users/dev/fix-auth-bug", "terminal_app": "iTerm"}),
        (0.4, {"hook_event_name": "SessionStart", "session_id": backend,
               "cwd": "/Users/dev/backend-server", "terminal_app": "Terminal"}),
        (0.8, {"hook_event_name": "SessionStart", "session_id": opt,
               "cwd": "/Users/dev/optimize-queries", "terminal_app": "Ghostty"}),
        (1.2, {"hook_event_name": "UserPromptSubmit", "session_id": fix,
               "prompt": "fix the auth bug in middleware"}),
        (1.2, {"hook_event_name": "PreToolUse", "session_id": fix,
               "tool_name": "Edit", "tool_input": {"file_path": "src/auth/middleware.ts"}}),
        (1.2, {"hook_event_name": "UserPromptSubmit", "session_id": backend,
               "prompt": "build the users endpoint"}),
        (1.6, {"hook_event_name": "PreToolUse", "session_id": backend,
               "tool_name": "Write", "tool_input": {"file_path": "src/routes/users.ts"}}),
        (2.2, {"hook_event_name": "PermissionRequest", "session_id": fix,
               "tool_name": "Edit", "tool_input": {"file_path": "src/auth/middleware.ts"}}),
        (1.6, {"hook_event_name": "PreToolUse", "session_id": fix,
               "tool_name": "Bash", "tool_input": {"command": "npm test"}}),
        (2.4, {"hook_event_name": "PreToolUse", "session_id": fix, "tool_name": "AskUserQuestion",
               "tool_input": {"questions": [{"question": "Which deployment target?",
                                             "options": [{"label": "Production"},
                                                         {"label": "Staging"},
                                                         {"label": "Local only"}]}]}}),
        (2.6, {"hook_event_name": "Stop", "session_id": fix,
               "last_assistant_message": "Fixed the auth bug. 3 files changed, tests passing."}),
    ]

    for delay, payload in steps:
        emit(payload, url, demo_state)
        sys.stderr.write(f"[demo] {payload['hook_event_name']:<18} {payload['session_id']}\n")
        time.sleep(delay)

    sys.stderr.write("[demo] done\n")
    try:
        os.remove(demo_state)
        os.remove(demo_state + ".lock")
    except OSError:
        pass
    return 0


# ── entry point ────────────────────────────────────────────────────────────────
def main() -> int:
    args = sys.argv[1:]
    url = os.environ.get("PAGER_BUDDY_URL", DEFAULT_URL)
    state_path = os.path.expanduser(os.environ.get("PAGER_BUDDY_STATE", DEFAULT_STATE))

    if "--demo" in args:
        return run_demo(url, state_path)

    try:
        raw = sys.stdin.buffer.read()
    except Exception as exc:  # noqa: BLE001
        debug(f"stdin read failed: {exc}")
        return 0
    if not raw or not raw.strip():
        return 0
    try:
        payload = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        debug(f"bad json on stdin: {exc}")
        return 0

    # Claude's payload has no terminal field; infer it from the hook's environment.
    if not payload.get("terminal_app"):
        term = infer_terminal(os.environ)
        if term:
            payload["terminal_app"] = term

    emit(payload, url, state_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
