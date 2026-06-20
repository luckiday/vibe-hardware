#!/usr/bin/env python3
"""install_hooks.py — register (or remove) the pager-buddy Level-0 hook in
Claude Code's settings.json.

  install     merge our hook command into hooks[event] for every tracked event,
              tagged so it is idempotent and cleanly removable. Backs up once.
  uninstall   remove every pager-buddy hook (command contains the marker below)
  status      show which events currently carry our hook

Targets ~/.claude/settings.json by default. Use --settings to target another
file (e.g. a project's .claude/settings.json). Use --url to bake the device
endpoint into the command (default http://127.0.0.1:8787/v1/snapshot).

This edits your LIVE Claude Code config. It prints what it changes and NEVER
removes hooks it did not add. Re-running `install` is safe (replaces ours).

Usage:
  python3 install_hooks.py install [--url URL] [--settings PATH]
  python3 install_hooks.py uninstall [--settings PATH]
  python3 install_hooks.py status [--settings PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import shlex
import sys

# Marker that uniquely identifies our hooks (so uninstall is surgical).
MARKER = "claude_pager_hook.py"
DEFAULT_URL = "http://127.0.0.1:8787/v1/snapshot"
DEFAULT_SETTINGS = "~/.claude/settings.json"

# Events we register. Those needing a tool matcher use "*".
EVENTS = [
    "SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse",
    "PermissionRequest", "Notification", "Stop", "StopFailure", "PostToolUseFailure",
]
MATCHER_EVENTS = {"PreToolUse", "PermissionRequest", "Notification", "PostToolUseFailure"}

HOOK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "claude_pager_hook.py")


def hook_python() -> str:
    """A stable interpreter for the hook. Prefer the system python over whatever
    ran the installer (which may be a transient venv, e.g. ESP-IDF's). The hook
    is stdlib-only, so any python3 works."""
    for candidate in ("/usr/bin/python3", "/opt/homebrew/bin/python3", "/usr/local/bin/python3"):
        if os.path.exists(candidate):
            return candidate
    return sys.executable or "python3"


def hook_command(url: str, gate: str | None = None) -> str:
    env = f"PAGER_BUDDY_URL={shlex.quote(url)} "
    if gate is not None:   # bake the two-way approval gate scope into the command
        env += f"PAGER_BUDDY_GATE={shlex.quote(gate)} "
    return (
        f"{env}{shlex.quote(hook_python())} {shlex.quote(HOOK_PATH)} --source claude"
    )


def load_settings(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as exc:
        print(f"✗ {path} is not valid JSON ({exc}); refusing to touch it.")
        raise SystemExit(1)


def write_settings(path: str, data: dict, backup: bool) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if backup and os.path.isfile(path):
        bak = path + ".bak"
        with open(path, "r", encoding="utf-8") as src, open(bak, "w", encoding="utf-8") as dst:
            dst.write(src.read())
        print(f"  backed up existing settings → {bak}")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")


def is_ours(hook: dict) -> bool:
    return isinstance(hook, dict) and MARKER in str(hook.get("command", ""))


def strip_ours(groups):
    """Remove our hooks from a list of hook-groups; drop emptied groups."""
    cleaned = []
    for group in groups or []:
        if not isinstance(group, dict):
            cleaned.append(group)
            continue
        kept = [h for h in group.get("hooks", []) if not is_ours(h)]
        if kept:
            new_group = dict(group)
            new_group["hooks"] = kept
            cleaned.append(new_group)
    return cleaned


def cmd_install(path: str, url: str, gate: str | None = None) -> int:
    if not os.path.isfile(HOOK_PATH):
        print(f"✗ hook script not found next to installer: {HOOK_PATH}")
        return 1

    settings = load_settings(path)
    hooks = settings.setdefault("hooks", {})
    command = hook_command(url, gate)

    for event in EVENTS:
        groups = strip_ours(hooks.get(event, []))
        group = {"hooks": [{"type": "command", "command": command}]}
        if event in MATCHER_EVENTS:
            group = {"matcher": "*", **group}
        groups.append(group)
        hooks[event] = groups

    write_settings(path, settings, backup=True)
    print(f"✓ installed pager-buddy hooks into {path}")
    print(f"  events : {', '.join(EVENTS)}")
    print(f"  command: {command}")
    print("  → start pager_stub.py (or your device) at the URL above, then use Claude.")
    print("  → restart Claude Code so it reloads settings.json.")
    return 0


def cmd_uninstall(path: str) -> int:
    settings = load_settings(path)
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        print("· no hooks block; nothing to remove.")
        return 0

    removed = 0
    for event in list(hooks.keys()):
        before = sum(len(g.get("hooks", [])) for g in hooks[event] if isinstance(g, dict))
        cleaned = strip_ours(hooks[event])
        after = sum(len(g.get("hooks", [])) for g in cleaned if isinstance(g, dict))
        removed += before - after
        if cleaned:
            hooks[event] = cleaned
        else:
            del hooks[event]

    if not hooks:
        settings.pop("hooks", None)

    write_settings(path, settings, backup=True)
    print(f"✓ removed {removed} pager-buddy hook(s) from {path}")
    return 0


def cmd_status(path: str) -> int:
    settings = load_settings(path)
    hooks = settings.get("hooks", {}) if isinstance(settings.get("hooks"), dict) else {}
    found = [
        event for event, groups in hooks.items()
        if any(is_ours(h) for g in groups if isinstance(g, dict) for h in g.get("hooks", []))
    ]
    print(f"settings: {path}")
    if found:
        print(f"✓ pager-buddy hooks present on: {', '.join(sorted(found))}")
    else:
        print("· no pager-buddy hooks installed")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="pager-buddy Claude Code hook installer")
    parser.add_argument("action", choices=["install", "uninstall", "status"])
    parser.add_argument("--url", default=DEFAULT_URL, help="device endpoint baked into the hook command")
    parser.add_argument("--settings", default=DEFAULT_SETTINGS, help="path to settings.json")
    parser.add_argument("--gate", default=None,
                        help="two-way approval gate scope baked as PAGER_BUDDY_GATE "
                             "(e.g. 'Bash' or 'Bash,Edit,Write'; '' or 'off' to disable). "
                             "Omit to use the hook default (Bash,Edit,Write,MultiEdit,NotebookEdit).")
    args = parser.parse_args()

    path = os.path.expanduser(args.settings)
    if args.action == "install":
        return cmd_install(path, args.url, args.gate)
    if args.action == "uninstall":
        return cmd_uninstall(path)
    return cmd_status(path)


if __name__ == "__main__":
    raise SystemExit(main())
