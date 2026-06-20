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
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime
from urllib import request as urlrequest
from urllib.parse import quote

DEFAULT_URL = "http://127.0.0.1:8787/v1/snapshot"
DEFAULT_STATE = "~/.pager-buddy/state.json"
MAX_ACTIVITY = 3            # tool steps kept per session
# Sessions go stale by inactivity, not by SessionEnd (which is unreliable — a
# closed/crashed/idle CLI often never fires it). Drop sessions idle past this.
IDLE_TTL = int(os.environ.get("PAGER_BUDDY_IDLE_TTL", "600"))  # seconds (default 10 min)
POST_TIMEOUT = 1.5         # seconds — keep small; we fail open

# ── two-way approval gate (device answers permission prompts) ────────────────────
# For tools in the gate set, a PreToolUse hook BLOCKS: it shows an approval prompt on
# the pager, waits for the user to press Allow/Deny there, and returns that decision to
# Claude Code (permissionDecision allow|deny) — so the device drives the VS Code session.
# Set PAGER_BUDDY_GATE="" (or "off"/"none") to disable; it then behaves push-only.
# Only active in "default" permission mode — bypassPermissions/acceptEdits/plan never
# prompt, so the gate stays out of the way there (no spurious Allow on the device).
# A blocking hook must finish under Claude's hook timeout (~60 s), so keep GATE_TIMEOUT
# below that; on timeout we stay silent and Claude falls back to its own prompt.
def _gate_tools() -> set:
    raw = os.environ.get("PAGER_BUDDY_GATE", "Bash,Edit,Write,MultiEdit,NotebookEdit")
    if raw.strip().lower() in ("", "off", "none", "0"):
        return set()
    return {t.strip() for t in raw.split(",") if t.strip()}

GATE_TOOLS = _gate_tools()
GATE_TIMEOUT = float(os.environ.get("PAGER_BUDDY_GATE_TIMEOUT", "30"))  # seconds to wait for a press
GATE_POLL = 0.4            # seconds between hub polls while waiting


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


def summarize(text, limit: int = 90):
    """A clean one-line title/summary from a prompt or assistant message.

    The tiny screen can't show markdown: pick the first meaningful line (skipping
    code fences, preferring prose over a heading), strip inline markdown, and cap
    at a sentence boundary. Turns a run-on 'Fixed it. Root cause…\\n## Root cause\\n…' blob into
    just its lead line."""
    if not text:
        return None
    first = None
    fallback = None  # a heading, used only if there's no prose line
    for raw_line in str(text).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("```"):
            continue
        is_heading = bool(re.match(r"^#{1,6}\s+", line))
        line = re.sub(r"^\s*(#{1,6}\s+|>\s+|[-*+]\s+|\d+[.)]\s+)", "", line).strip()
        if not line:
            continue
        if is_heading:
            fallback = fallback or line
            continue
        first = line
        break
    if first is None:
        first = fallback or " ".join(str(text).split())

    # strip inline markdown: code, bold/italic/strike, [text](url) -> text
    first = re.sub(r"`+", "", first)
    first = re.sub(r"(\*\*|\*|__|_|~~)", "", first)
    first = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", first)
    first = " ".join(first.split())

    if len(first) <= limit:
        return first
    head = first[:limit]
    last = None
    for m in re.finditer(r"[.!?。！？]", head):
        last = m
    if last and last.end() >= 20:        # cut at the last full sentence that fits
        return head[: last.end()]
    space = head.rfind(" ")              # else break at a word boundary (no-op for CJK)
    if space >= 40:
        return head[:space] + "…"
    return head[: limit - 1] + "…"


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
        session["task"] = summarize(payload.get("prompt")) or session["task"]
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
            session["task"] = summarize(message)
    elif event in ("PostToolUseFailure", "StopFailure"):
        session["state"] = "error"
        session["task"] = clip(payload.get("error") or payload.get("message")) or session["task"]
    elif event == "Stop":
        session["state"] = "done"
        summary = summarize(payload.get("last_assistant_message")) or session.get("task") or "Done."
        session["done"] = {"summary": summary}
        _clear_actions(session, keep_done=True)


# ── snapshot ─────────────────────────────────────────────────────────────────
def build_snapshot(registry: dict, now: float) -> dict:
    rows = []
    for session in registry.get("sessions", {}).values():
        touched = session.get("updated_at", session.get("started_at", now))
        if now - touched > IDLE_TTL:
            continue
        out = {
            "id": session["id"],
            "name": session["name"],
            "agent": session.get("agent", "Claude"),
            "term": session.get("term", "—"),
            "age": humanize_age(touched, now),   # since last update (renderers re-age from ts)
            "ts": round(touched),   # last-update epoch — renderers re-age + prune from this
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


def emit(payload: dict, url: str, state_path: str, override_event: str | None = None) -> bool:
    """Apply one event and push the resulting snapshot. Fails open.

    Returns True iff the snapshot POST succeeded — the gate uses this to bail fast when
    the hub is unreachable (so a globally-installed hook never blocks on a dead hub).
    override_event lets the gate reuse the same mapping to synthesize a state the raw
    event wouldn't produce — e.g. driving a PreToolUse through the PermissionRequest
    branch to render the device's Allow/Deny screen."""
    now = time.time()
    if override_event:
        payload = {**payload, "hook_event_name": override_event}
    try:
        with locked(state_path):
            registry = load_registry(state_path)
            apply_event(registry, payload, now)
            save_registry(state_path, registry)
            snapshot = build_snapshot(registry, now)
    except Exception as exc:  # noqa: BLE001
        debug(f"registry error: {exc}")
        return False
    try:
        post_snapshot(url, snapshot)
        return True
    except Exception as exc:  # noqa: BLE001
        debug(f"post failed (device offline?): {exc}")
        return False


# ── gate: block on a permission prompt until the device answers ──────────────────
def fetch_resolution(res_url: str, sid: str):
    """Return (and consume) the pending device decision for this session, or None."""
    try:
        url = f"{res_url}?session_id={quote(sid)}"
        with urlrequest.urlopen(url, timeout=POST_TIMEOUT) as resp:
            data = json.loads(resp.read())
        return (data or {}).get("resolution")
    except Exception as exc:  # noqa: BLE001 — fail open
        debug(f"resolution fetch failed: {exc}")
        return None


def gated_approval(payload: dict, url: str, state_path: str) -> str | None:
    """Show an Allow/Deny prompt on the pager and block until the user presses one.

    Returns "allow"/"deny" from the device, or None if the device/hub is unreachable
    or nobody answers within GATE_TIMEOUT (caller then lets Claude prompt normally)."""
    sid = payload.get("session_id") or "unknown"
    res_url = url.replace("/v1/snapshot", "/v1/resolution")
    # 1. render the approval screen on the device (waiting + approve{tool,file}). If the
    #    hub is unreachable, bail at once — no prompt can reach the device, so blocking
    #    would just stall Claude. (This is what keeps a globally-installed hook fast when
    #    the bridge isn't running.)
    if not emit(payload, url, state_path, override_event="PermissionRequest"):
        debug("hub unreachable; skipping gate")
        return None
    # 2. clear any stale decision left over from a previous prompt in this session.
    fetch_resolution(res_url, sid)
    # 3. wait for a fresh press.
    deadline = time.time() + GATE_TIMEOUT
    while time.time() < deadline:
        res = fetch_resolution(res_url, sid)
        if res:
            action = str(res.get("action") or "").lower()
            if action in ("allow", "deny"):
                debug(f"device decided: {action}")
                return action
        time.sleep(GATE_POLL)
    debug("gate timed out; falling back to Claude's own prompt")
    return None


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

    # Two-way gate: for a gated tool, block on the device for an Allow/Deny and return
    # it to Claude as a permission decision. Anything else (incl. timeout / device
    # offline) falls through to the normal push so we always fail open.
    #
    # Only gate in "default" permission mode — the one mode where Claude would otherwise
    # prompt the user. In bypassPermissions / acceptEdits / plan it auto-allows or defers
    # and never prompts, so gating there would pop a spurious Allow on the device for a
    # tool that's already been auto-approved. Treat a missing field as "default" (older
    # Claude builds that don't send it still get the gate).
    event = payload.get("hook_event_name") or ""
    tool = payload.get("tool_name") or ""
    mode = payload.get("permission_mode") or "default"
    if event == "PreToolUse" and tool in GATE_TOOLS and mode == "default":
        decision = gated_approval(payload, url, state_path)
        if decision in ("allow", "deny"):
            if decision == "allow":     # let the device's screen return to "running"
                emit(payload, url, state_path)        # normal PreToolUse → working + activity
            sys.stdout.write(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": decision,
                    "permissionDecisionReason": f"pager-buddy: {decision} from device",
                }
            }))
            return 0
        # timeout/offline: the approval screen (if any) stays up; Claude prompts as usual
        return 0

    emit(payload, url, state_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
