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
    if (s.state === "done") return 1;          // Dismiss (Jump removed — device can't focus the Mac)
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
  if (S.view === "idle") {
    if (!D.sessions.length) return;
    S.view = "list"; S.sel = 0; return render();
  }
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
      D.sessions = D.sessions.filter((x) => x.id !== s.id); toast("Dismissed");
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

// ---------- line-art icon kit (TE/OP-1: 1px neon stroke, no fill, inherits color) ----------
function svg(body, w, vb = 24) {
  return `<svg class="ico" viewBox="0 0 ${vb} ${vb}" width="${w}" height="${w}" fill="none" ` +
    `stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${body}</svg>`;
}
const IC = {
  bt:    (w = 9)  => svg(`<path d="M7 8l10 8-5 4V4l5 4L7 16"/>`, w),                          // bluetooth rune
  btoff: (w = 9)  => svg(`<path d="M7 8l10 8-5 4V4l5 4L7 16"/><path d="M4 4l16 16"/>`, w),    // + slash = offline
  bolt:  (w = 8)  => svg(`<path d="M13 2L4 14h6l-1 8 9-12h-6z" fill="currentColor" stroke="none"/>`, w),
  check: (w = 10) => svg(`<path d="M4 13l5 5L20 6"/>`, w),
  warn:  (w = 11) => svg(`<path d="M12 3l10 17H2L12 3z"/><path d="M12 10v4"/><path d="M12 17v.4"/>`, w),
  ask:   (w = 11) => svg(`<rect x="3" y="4" width="18" height="13"/><path d="M3 17v4l5-4"/>`, w),  // speech box
  chev:  (w = 9)  => svg(`<path d="M5 9l7 7 7-7"/>`, w),                                       // SIDE = scroll/next
  back:  (w = 10) => svg(`<path d="M11 6l-5 5 5 5"/><path d="M6 11h13"/>`, w),
  front: (w = 11) => svg(`<rect x="3" y="8" width="18" height="8"/>`, w),                      // the FRONT pill = OK
};

// ---------- renderers ----------
function batteryHTML() {
  const lvl = Math.max(0, Math.min(100, D.battery));
  const chg = D.charging || D.usb;
  const cls = lvl <= 20 ? "b-low" : chg ? "b-chg" : "b-ok"; // ≤20% red wins over charging
  const fw = Math.max(2, Math.round((lvl / 100) * 16));     // proportional fill width (in the 26-wide viewBox)
  const bat =
    `<svg class="ico" viewBox="0 0 26 12" width="19" height="9" fill="none" stroke="currentColor" stroke-width="1.4">` +
      `<rect x="1" y="1.6" width="20" height="8.8"/>` +
      `<rect x="22.4" y="4" width="2.2" height="4" fill="currentColor" stroke="none"/>` +
      `<rect x="2.8" y="3.4" width="${fw}" height="5.2" fill="currentColor" stroke="none"/>` +
    `</svg>`;
  return `<span class="batt ${cls}">` +
    (chg ? `<span class="bolt">${IC.bolt()}</span>` : "") +
    bat + `<span class="batt-pct">${lvl}%</span></span>`;
}
function statusBar(view) {
  const on = D.online !== false;
  const bt = `<span class="bt ${on ? "on" : ""}" title="${on ? "linked" : "offline"}">` +
    `${on ? IC.bt() : IC.btoff()}</span>`;
  const clk = view !== "idle" ? `<span class="clk">${esc(D.clock)}</span>` : ""; // idle owns the big clock
  return `<div class="statusbar"><span class="left">${bt}${clk}</span>${batteryHTML()}</div>`;
}
// footer hints as framed tags — l/r are pre-built tag() HTML (or "")
function tag(icon, label, cls = "") {
  return `<span class="tag ${cls}">${icon || ""}<span>${esc(label)}</span></span>`;
}
function footer(l, r) {
  return `<div class="footer"><span>${l || ""}</span><span>${r || ""}</span></div>`;
}
function dot(state) { return `<span class="dot s-${state}"></span>`; }

// breathing-rings hero: color = status (green all-clear / amber needs-you), `agi` = faster pulse
function rings(need) {
  const cls = need ? "c-waiting agi" : "c-done";
  return `<div class="rings ${cls}"><span></span><span></span><span></span></div>`;
}

function viewIdle() {
  const { total, need } = counts();
  const line1 = `${total} sessions`;
  const line2 = need > 0 ? `${need} need you` : `all clear`;
  return `<div class="content"><div class="idle">` +
    rings(need > 0) +
    `<div class="clock-big">${esc(D.clock)}</div>` +
    `<div class="date">${esc(D.date)}</div>` +
    `<div class="tag summary ${need > 0 ? "need" : ""}">${esc(line1)}<br>${esc(line2)}</div>` +
    `</div></div>` + footer(tag(IC.front(), "open"), tag(IC.chev(), "menu"));
}

function viewList() {
  if (!D.sessions.length) {
    return `<div class="content"><div class="idle">` +
      rings(false) +
      `<div class="tag summary">no active tasks</div>` +
      `</div></div>` + footer("", tag(IC.back(), "back"));
  }
  const rows = D.sessions.map((s, i) => {
    const sel = i === S.sel ? " sel" : "";
    const accent = i === S.sel ? ` style="color:var(--${s.state})"` : ""; // selected row's edge bar = state color
    return `<div class="row${sel}"${accent}>` +
      `<div class="l1">${dot(s.state)}<span class="name">${esc(s.name)}</span>` +
      `<span class="age">${esc(s.age)}</span></div>` +
      `<div class="l2"><span class="chip">${esc(s.agent)}</span>` +
      `<span class="lstate c-${s.state}">${STATE_LABEL[s.state]}</span></div>` +  // term shown on the session screen
      `</div>`;
  }).join("");
  return `<div class="content">${rows}</div>` + footer(tag(IC.front(), "open"), tag(IC.chev(), "next"));
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
  const sub = s.task ? `<div class="subtitle">${esc(s.task)}</div>` : "";
  return `<div class="content"><div class="head">${dot("working")}<b class="c-working">${esc(s.name)}</b></div>` +
    sub + acts +
    `<div class="act run"><span class="bars"><i></i><i></i><i></i><i></i></span>working</div></div>` +
    footer(tag(IC.back(), "back"), "");
}

function scrApprove(s) {
  const a = s.approve;
  const deny = `<div class="choice danger${S.sel === 0 ? " sel" : ""}">Deny</div>`;
  const allow = `<div class="choice${S.sel === 1 ? " sel" : ""}">Allow</div>`;
  const delta = (a.add ? "+" + a.add : "") + (a.del ? " -" + a.del : "");
  return `<div class="content"><div class="head c-waiting">${IC.warn()}<span class="tag c-waiting">permission</span></div>` +
    `<div class="big">${esc(a.tool)}</div>` +
    `<div class="path">${esc(a.file)}</div>` +
    (delta ? `<div class="delta">${delta} change</div>` : "") +
    `<div class="choices">${deny}${allow}</div></div>` +
    footer(tag(IC.front(), "confirm"), tag(IC.chev(), "switch"));
}

function scrAsk(s) {
  const opts = s.ask.opts.map((o, i) =>
    `<div class="opt${i === S.sel ? " sel" : ""}"><span class="k">${i + 1}</span><span>${esc(o)}</span></div>`).join("");
  return `<div class="content"><div class="head c-asking">${IC.ask()}<span class="tag c-asking">${esc(s.agent)} asks</span></div>` +
    `<div class="q">${esc(s.ask.q)}</div>${opts}</div>` +
    footer(tag(IC.front(), "select"), tag(IC.chev(), "next"));
}

function scrDone(s) {
  const d = s.done;
  const dis = `<div class="choice sel">Dismiss</div>`;   // Jump removed — the device can't focus the Mac
  const meta = [];                        // files/tests are optional on the wire
  if (d.files != null) meta.push(`${d.files} files`);
  if (d.tests) meta.push(esc(d.tests));
  return `<div class="content"><div class="head c-done">${IC.check()}<b class="c-done">${esc(s.name)}</b></div>` +
    `<div class="q">${esc(d.summary)}</div>` +
    (meta.length ? `<div class="delta">${meta.join(" · ")}</div>` : "") +
    `<div class="choices">${dis}</div></div>` +
    footer(tag(IC.front(), "dismiss"), "");
}

function render() {
  let body;
  if (S.view === "idle") body = viewIdle();
  else if (S.view === "list") body = viewList();
  else body = viewSession();
  el("screen").innerHTML = statusBar(S.view) + body + (toastHTML || "");
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
    else if (e.key === "b") { D.online = !D.online; render(); }   // toggle the status-bar Bluetooth glyph
  });

  // deep-link for demos / sharing: ?view=list  |  ?id=<session>[&state=waiting|asking|done]
  const p = new URLSearchParams(location.search);
  if (p.get("zoom")) setZoom(p.get("zoom"));
  if (p.get("batt")) D.battery = parseInt(p.get("batt"), 10);
  if (p.get("chg") === "1") { D.charging = true; el("pChg").classList.add("on"); }
  if (p.get("online") === "0") D.online = false;   // ?online=0 → show the offline Bluetooth glyph
  const id = p.get("id"), st = p.get("state"), view = p.get("view");
  if (id) {
    const s = D.sessions.find((x) => x.id === id);
    if (s) { if (st) s.state = st; return openSession(id); }
  }
  if (view) { S.view = view; }
  render();
});
