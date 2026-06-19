// app.js — StickC S3 display mock: state machine + 2-button handling + renderers.
// Buttons: SIDE = cycle highlight (wraps). FRONT short = OK/confirm. FRONT long = back.

const D = window.PAGER;
const el = (id) => document.getElementById(id);
const esc = (s) =>
  String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const S = { view: "idle", sel: 0, openId: null };
let playTimer = null;

const STATE_LABEL = {
  working: "working", waiting: "needs you", asking: "asks", done: "done", error: "error",
};

function counts() {
  const total = D.sessions.length;
  const need = D.sessions.filter((s) => s.state === "waiting" || s.state === "asking").length;
  return { total, need };
}
function openSession(id) {
  const s = D.sessions.find((x) => x.id === id);
  if (!s) return;
  S.openId = id;
  S.view = "session";
  S.sel = s.state === "waiting" ? 1 : 0; // default-highlight Allow on a permission
  render();
}

// focusable item count for the current screen
function itemCount() {
  if (S.view === "list") return D.sessions.length;
  if (S.view === "session") {
    const s = cur();
    if (!s) return 0;
    if (s.state === "waiting") return 2;       // Deny | Allow
    if (s.state === "asking") return s.ask.opts.length;
    if (s.state === "done") return 2;          // Jump | Dismiss
  }
  return 0;
}
const cur = () => D.sessions.find((x) => x.id === S.openId);

// ---------- button actions ----------
function onScroll() {
  const n = itemCount();
  if (n) S.sel = (S.sel + 1) % n;
  render();
}
function onOk() {
  if (S.view === "idle") { S.view = "list"; S.sel = 0; return render(); }
  if (S.view === "list") {
    if (!D.sessions.length) return;
    return openSession(D.sessions[S.sel].id);
  }
  if (S.view === "session") {
    const s = cur();
    if (!s) { S.view = "list"; return render(); }
    if (s.state === "waiting") {
      const allow = S.sel === 1;
      toast(allow ? "✓ Allowed · " + s.approve.tool : "✕ Denied");
      s.state = "working";
    } else if (s.state === "asking") {
      toast("→ " + s.ask.opts[S.sel]);
      s.state = "working";
    } else if (s.state === "done") {
      if (S.sel === 0) toast("⤴ Jumped to " + s.term);
      else { D.sessions = D.sessions.filter((x) => x.id !== s.id); toast("Dismissed"); }
    }
    backToList();
  }
}
function onBack() {
  if (S.view === "session") backToList();
  else if (S.view === "list") { S.view = "idle"; S.sel = 0; render(); }
  else render();
}
function backToList() {
  S.openId = null;
  if (!D.sessions.length) { S.view = "idle"; S.sel = 0; }
  else { S.view = "list"; S.sel = Math.min(S.sel, D.sessions.length - 1); }
  render();
}

// ---------- renderers ----------
function batteryHTML() {
  const lvl = Math.max(0, Math.min(100, D.battery));
  const chg = D.charging || D.usb;
  const cls = lvl <= 20 ? "b-low" : chg ? "b-chg" : "b-ok"; // ≤20% red wins over charging
  return `<span class="batt ${cls}">` +
    (chg ? `<span class="bolt">⚡</span>` : "") +
    `<span class="batt-icon"><span class="batt-fill" style="width:${Math.max(12, lvl)}%"></span></span>` +
    `<span class="batt-pct">${lvl}%</span></span>`;
}
function statusBar() {
  return `<div class="statusbar"><span>${esc(D.clock)}</span>${batteryHTML()}</div>`;
}
function footer(l, r) {
  return `<div class="footer"><span>${l || ""}</span><span>${r || ""}</span></div>`;
}
function dot(state) { return `<span class="dot s-${state}"></span>`; }

function viewIdle() {
  const { total, need } = counts();
  const face = need > 0 ? "•_•" : "•‿•";
  const faceC = need > 0 ? "c-waiting" : "c-done";
  const sum = need > 0
    ? `${total} sessions · <b class="need">${need} need you</b>`
    : `${total} sessions · all clear`;
  return `<div class="content"><div class="idle">` +
    `<div class="face ${faceC}">${face}</div>` +
    `<div class="clock-big">${esc(D.clock)}</div>` +
    `<div class="date">${esc(D.date)}</div>` +
    `<div class="summary">${sum}</div>` +
    `</div></div>` + footer("— open", "▼ menu");
}

function viewList() {
  const rows = D.sessions.map((s, i) => {
    const sel = i === S.sel ? " sel" : "";
    return `<div class="row${sel}">` +
      `<div class="l1">${dot(s.state)}<span class="name">${esc(s.name)}</span>` +
      `<span class="age">${esc(s.age)}</span></div>` +
      `<div class="l2"><span class="chip">${esc(s.agent)}</span>` +
      `<span class="chip">${esc(s.term)}</span>` +
      `<span class="c-${s.state}" style="font-size:7px">${STATE_LABEL[s.state]}</span></div>` +
      `</div>`;
  }).join("");
  return `<div class="content">${rows}</div>` + footer("— open", "▼ next");
}

function viewSession() {
  const s = cur();
  if (!s) return viewList();
  if (s.state === "waiting") return scrApprove(s);
  if (s.state === "asking") return scrAsk(s);
  if (s.state === "done") return scrDone(s);
  return scrWorking(s);
}

function scrWorking(s) {
  const acts = s.activity.map((a) =>
    `<div class="act"><span class="tool">${esc(a.tool)}(</span>${esc(a.detail)}<span class="tool">)</span>` +
    (a.sub ? `<div class="sub">└ ${esc(a.sub)}</div>` : "") + `</div>`).join("");
  return `<div class="content"><div class="head">${dot("working")}<b>${esc(s.name)}</b></div>` +
    acts + `<div class="act spin" style="margin-top:4px">▌ working…</div></div>` +
    footer("— back", "");
}

function scrApprove(s) {
  const a = s.approve;
  const deny = `<div class="choice danger${S.sel === 0 ? " sel" : ""}">Deny</div>`;
  const allow = `<div class="choice${S.sel === 1 ? " sel" : ""}">Allow</div>`;
  const delta = (a.add ? "+" + a.add : "") + (a.del ? " -" + a.del : "");
  return `<div class="content"><div class="head c-waiting">⚠ Permission</div>` +
    `<div class="big">${esc(a.tool)}</div>` +
    `<div class="path">${esc(a.file)}</div>` +
    (delta ? `<div class="delta">${delta} change</div>` : "") +
    `<div class="choices">${deny}${allow}</div></div>` +
    footer("— confirm", "▼ switch");
}

function scrAsk(s) {
  const opts = s.ask.opts.map((o, i) =>
    `<div class="opt${i === S.sel ? " sel" : ""}"><span class="k">${i + 1}</span>${esc(o)}</div>`).join("");
  return `<div class="content"><div class="head c-asking">▣ ${esc(s.agent)} asks</div>` +
    `<div class="q">${esc(s.ask.q)}</div>${opts}</div>` +
    footer("— select", "▼ next");
}

function scrDone(s) {
  const d = s.done;
  const jump = `<div class="choice${S.sel === 0 ? " sel" : ""}">⤴ Jump</div>`;
  const dis = `<div class="choice${S.sel === 1 ? " sel" : ""}">Dismiss</div>`;
  return `<div class="content"><div class="head c-done">✓ ${esc(s.name)}</div>` +
    `<div class="q">${esc(d.summary)}</div>` +
    `<div class="delta">${d.files} files · ${esc(d.tests)}</div>` +
    `<div class="choices">${jump}${dis}</div></div>` +
    footer("— Jump", "▼ switch");
}

function render() {
  let body;
  if (S.view === "idle") body = viewIdle();
  else if (S.view === "list") body = viewList();
  else body = viewSession();
  el("screen").innerHTML = statusBar() + body + (toastHTML || "");
}

// ---------- toast + flash ----------
let toastHTML = "";
let toastTimer = null;
function toast(msg) {
  toastHTML = `<div class="toast">${esc(msg)}</div>`;
  render();
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastHTML = ""; render(); }, 1600);
}
function flash() {
  const scr = el("screen");
  scr.classList.remove("flash");
  void scr.offsetWidth; // restart animation
  scr.classList.add("flash");
  setTimeout(() => scr.classList.remove("flash"), 1500);
}

// ---------- demo scenario ----------
function stopPlay() { if (playTimer) { clearTimeout(playTimer); playTimer = null; } }
function play() {
  stopPlay();
  const sc = D.scenario;
  const t = D.sessions.find((x) => x.id === sc.target);
  if (!t) return;
  let i = 0;
  S.view = "list"; render();
  (function step() {
    if (i >= sc.steps.length) return;
    const st = sc.steps[i++];
    t.state = st.state;
    if (st.page) { openSession(t.id); flash(); }
    else { if (S.openId === t.id) { S.view = "list"; } render(); }
    playTimer = setTimeout(step, st.ms);
  })();
}

// ---------- input wiring (front long-press = back) ----------
function wireFront(btn) {
  let down = 0, held = false, timer = null;
  const start = () => {
    down = Date.now(); held = false;
    timer = setTimeout(() => { held = true; onBack(); }, 500);
  };
  const end = () => {
    clearTimeout(timer);
    if (!held && down) onOk();
    down = 0;
  };
  btn.addEventListener("mousedown", start);
  btn.addEventListener("mouseup", end);
  btn.addEventListener("mouseleave", () => { clearTimeout(timer); down = 0; });
  btn.addEventListener("touchstart", (e) => { e.preventDefault(); start(); }, { passive: false });
  btn.addEventListener("touchend", (e) => { e.preventDefault(); end(); }, { passive: false });
}

window.addEventListener("DOMContentLoaded", () => {
  wireFront(el("btnFront"));
  el("btnSide").addEventListener("click", () => { stopPlay(); onScroll(); });
  el("cScroll").addEventListener("click", () => { stopPlay(); onScroll(); });
  el("cOk").addEventListener("click", () => { stopPlay(); onOk(); });
  el("cBack").addEventListener("click", () => { stopPlay(); onBack(); });
  el("cPlay").addEventListener("click", play);

  const zoomBtns = document.querySelectorAll(".zoom button");
  const setZoom = (z) => {
    document.documentElement.style.setProperty("--scale", z);
    zoomBtns.forEach((x) => x.classList.toggle("on", x.dataset.z === String(z)));
  };
  zoomBtns.forEach((b) => b.addEventListener("click", () => setZoom(b.dataset.z)));

  const pChg = el("pChg");
  pChg.addEventListener("click", () => { D.charging = !D.charging; pChg.classList.toggle("on", D.charging); render(); });
  el("pLow").addEventListener("click", () => { D.battery = 15; render(); });
  el("pFull").addEventListener("click", () => { D.battery = 94; D.charging = false; pChg.classList.remove("on"); render(); });

  document.addEventListener("keydown", (e) => {
    if (["ArrowDown", "ArrowRight", "j"].includes(e.key)) { stopPlay(); onScroll(); e.preventDefault(); }
    else if (e.key === "Enter" || e.key === " ") { stopPlay(); onOk(); e.preventDefault(); }
    else if (e.key === "Backspace" || e.key === "Escape") { stopPlay(); onBack(); e.preventDefault(); }
    else if (e.key === "p") { play(); }
  });

  // deep-link for demos / sharing: ?view=list  |  ?id=<session>[&state=waiting|asking|done]
  const p = new URLSearchParams(location.search);
  if (p.get("zoom")) setZoom(p.get("zoom"));
  if (p.get("batt")) D.battery = parseInt(p.get("batt"), 10);
  if (p.get("chg") === "1") { D.charging = true; el("pChg").classList.add("on"); }
  const id = p.get("id"), st = p.get("state"), view = p.get("view");
  if (id) {
    const s = D.sessions.find((x) => x.id === id);
    if (s) { if (st) s.state = st; return openSession(id); }
  }
  if (view) { S.view = view; }
  render();
});
