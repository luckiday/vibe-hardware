#!/usr/bin/env bash
# smoke.sh — no-hardware sanity for the `pager` CLI. Does NOT load a real LaunchAgent
# or touch Bluetooth: it exercises shell-script syntax, argparse wiring, the status
# block, the plist round-trip (sandboxed), and status against a throwaway hub. Safe
# to run anytime — nothing here mutates your real LaunchAgents / hooks / running bridge.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
PORT="${PAGER_BUDDY_SMOKE_PORT:-8799}"
fail() { echo "✗ $1" >&2; exit 1; }

echo "• syntax"
python3 -c "import ast; ast.parse(open('pager').read())" || fail "pager parse"
python3 -c "import ast; ast.parse(open('analytics.py').read())" || fail "analytics parse"
for f in run.sh service.sh install.sh lib.sh smoke.sh; do bash -n "$f" || fail "$f"; done

echo "• argparse wiring (every subcommand --help exits 0)"
./pager --help >/dev/null || fail "pager --help"
for c in up down status logs run install uninstall boot hooks audio doctor top report completion; do
  ./pager "$c" --help >/dev/null || fail "pager $c --help"
done

echo "• shell completion emits a usable script"
./pager completion bash | grep -q "complete -F _pager pager" || fail "bash completion"
./pager completion zsh  | grep -q "compdef _pager pager"     || fail "zsh completion"

echo "• status (nothing running → all rows, no error)"
./pager status --port "$PORT" >/dev/null || fail "pager status"

echo "• plist round-trip (sandboxed — no real LaunchAgent)"
python3 - "$PORT" <<'PY' || fail "plist round-trip"
import importlib.util, importlib.machinery, plistlib, sys, tempfile
from pathlib import Path
# the CLI file is `pager` (no .py), so give importlib an explicit source loader
loader = importlib.machinery.SourceFileLoader("pagercli", "pager")
spec = importlib.util.spec_from_loader("pagercli", loader)
m = importlib.util.module_from_spec(spec); loader.exec_module(m)
tmp = Path(tempfile.mkdtemp())
m.PLIST = tmp / "agent.plist"; m.LOG = tmp / "agent.log"   # sandbox the paths
port = int(sys.argv[1])
m.write_plist(port, True)
d = plistlib.load(open(m.PLIST, "rb"))
assert d["RunAtLoad"] is True, d
assert d["KeepAlive"] == {"SuccessfulExit": False}, d
assert any("run.sh" in a for a in d["ProgramArguments"]), d
assert d["EnvironmentVariables"]["PAGER_BUDDY_PORT"] == str(port), d
assert m.boot_enabled() is True and m.plist_port() == port
m.write_plist(port, False)
assert m.boot_enabled() is False
print("  ok: RunAtLoad / KeepAlive / port / run.sh all correct")
PY

echo "• analytics: record + report round-trip (temp DB, no real data touched)"
python3 - <<'PY' || fail "analytics round-trip"
import analytics as a
import tempfile, time, datetime
from pathlib import Path
db = str(Path(tempfile.mkdtemp()) / "a.db")
now = time.time()
proj = "/Users/dev/demo-proj"
a.record_event({"hook_event_name":"UserPromptSubmit","session_id":"s1","cwd":proj}, now=now,   path=db)
a.record_event({"hook_event_name":"PreToolUse","tool_name":"Bash","session_id":"s1","cwd":proj}, now=now+1, path=db)
a.record_event({"hook_event_name":"PreToolUse","tool_name":"Edit","session_id":"s1","cwd":proj}, now=now+2, path=db)
a.record_event({"hook_event_name":"Stop","session_id":"s1","cwd":proj}, now=now+8, path=db)
a.record_event({"hook_event_name":"UserPromptSubmit","session_id":"s2","cwd":proj}, now=now+9, path=db)
days = [datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d")]
rep = a.build_report(days, db=db)
assert rep["sessions"] == 2, rep
assert rep["prompts"] == 2, rep
assert rep["turns"]["count"] == 1, rep            # one completed prompt→Stop
assert 7.5 <= rep["turns"]["avg"] <= 8.5, rep     # ~8s
assert rep["tool_calls"] == 2, rep
assert "report" in a.render_text(rep)
import json; json.loads(a.render_json(rep))        # --json is valid JSON
cnt, ndays, last = a.db_stats(db=db)
assert cnt == 5 and ndays == 1, (cnt, ndays, last)
print("  ok: 2 sessions · 2 instructions · 1 turn ~8s · 2 tool calls")
PY

echo "• status against a live hub"
python3 pager_stub.py --port "$PORT" >/tmp/pager_smoke_hub.log 2>&1 &
HUB=$!; trap 'kill $HUB 2>/dev/null || true' EXIT
for _ in $(seq 1 25); do
  curl -s -m1 "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1 && break; sleep 0.2
done
./pager status --port "$PORT" | grep -q running || fail "status did not see the hub"
echo "  ok: hub row shows running"

echo "✓ smoke passed"
