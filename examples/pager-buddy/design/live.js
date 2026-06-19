// live.js — Level-0 live feed. Polls the bridge snapshot endpoint and drives the
// SAME renderers/state-machine in app.js with real Claude Code status. Opt-in:
// the mock is offline (demo data) by default; click "Connect" or pass ?live=1.
//
// The wire format (../bridge/protocol.yaml) was defined so a snapshot's `session`
// objects are field-for-field what app.js already renders — so this layer just
// swaps the data behind `D` and re-renders. It reads app.js globals (D, S,
// render, openSession, flash, stopPlay, el) — load this AFTER app.js.
//
// Override the endpoint with ?bridge=<url>. Default assumes pager_stub.py / the
// bridge on the same host:port the page was served from, else 127.0.0.1:8787.

(function () {
  const params = new URLSearchParams(location.search);
  const sameOrigin = location.origin && location.origin.startsWith("http")
    ? location.origin + "/v1/snapshot"
    : "http://127.0.0.1:8787/v1/snapshot";
  const BRIDGE_URL = params.get("bridge") || sameOrigin;
  const INTERVAL = 1000;

  const L = { timer: null, everConnected: false, prevActionable: new Set() };

  function setStatus(text, on) {
    const node = el("liveStatus");
    if (node) { node.textContent = text; node.className = "live-status " + (on ? "on" : "off"); }
    const btn = el("cLive");
    if (btn) btn.textContent = L.timer ? "■ Disconnect" : "● Connect";
  }

  function actionableIds() {
    return new Set(
      D.sessions.filter((s) => s.state === "waiting" || s.state === "asking").map((s) => s.id)
    );
  }

  function applySnapshot(snap) {
    if (!snap || !Array.isArray(snap.sessions)) return;
    if (snap.clock) D.clock = snap.clock;
    if (snap.date) D.date = snap.date;
    D.sessions = snap.sessions.map((s) => ({
      id: s.id, name: s.name, agent: s.agent, term: s.term, age: s.age,
      state: s.state, task: s.task || "",
      activity: Array.isArray(s.activity) ? s.activity : [],
      approve: s.approve, ask: s.ask, done: s.done,
    }));

    // keep navigation coherent against the new data
    if (S.view === "session" && !D.sessions.some((x) => x.id === S.openId)) {
      S.openId = null;
      S.view = D.sessions.length ? "list" : "idle";
    }
    if (S.view === "list") S.sel = Math.min(S.sel, Math.max(0, D.sessions.length - 1));

    // a NEW thing needs you → page (flash, stands in for the buzz). Auto-open it
    // only from idle, so a live update never yanks the user mid-browse.
    const now = actionableIds();
    let fresh = null;
    now.forEach((id) => { if (!L.prevActionable.has(id)) fresh = id; });
    L.prevActionable = now;
    if (fresh) {
      flash();
      if (S.view === "idle") return openSession(fresh); // openSession() renders
    }
    render();
  }

  async function tick() {
    try {
      const res = await fetch(BRIDGE_URL, { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const snap = await res.json();
      L.everConnected = true;
      stopPlay(); // live data owns the screen
      applySnapshot(snap);
      setStatus("live · " + D.sessions.length + " session" + (D.sessions.length === 1 ? "" : "s"), true);
    } catch (e) {
      setStatus(L.everConnected ? "reconnecting…" : "offline · bridge not found", false);
    }
  }

  function connect() {
    if (L.timer) return;
    setStatus("connecting…", false);
    tick();
    L.timer = setInterval(tick, INTERVAL);
    const btn = el("cLive");
    if (btn) btn.textContent = "■ Disconnect";
  }

  function disconnect() {
    if (L.timer) { clearInterval(L.timer); L.timer = null; }
    L.prevActionable = new Set();
    setStatus("offline · demo data", false);
  }

  window.addEventListener("DOMContentLoaded", () => {
    const btn = el("cLive");
    if (btn) btn.addEventListener("click", () => (L.timer ? disconnect() : connect()));
    setStatus("offline · demo data", false);
    if (params.get("live") === "1" || params.get("bridge")) connect();
  });
})();
