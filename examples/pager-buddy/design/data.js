// data.js — sample sessions + the demo scenario for the StickC S3 display mock.
// Plain global (no modules) so index.html opens over file:// as well as a local server.
//
// Session.state drives the color + which action screen opens:
//   working | waiting (needs approval) | asking | done | error
// Mirrors the firmware's future ui_status verbs (see README.md).

window.PAGER = {
  clock: "10:20",
  date: "Fri Jun 19",
  battery: 78,
  charging: false, // charging / on USB → battery fill turns blue (≤20% stays red)
  usb: false,
  online: true,    // BLE link to the Mac bridge (drives the status-bar Bluetooth glyph; toggle with `b`)

  sessions: [
    {
      id: "fix-auth-bug",
      name: "fix auth bug",
      agent: "Claude",
      term: "iTerm",
      age: "27m",
      state: "working",
      task: "fix the auth bug in middleware",
      activity: [
        { tool: "Edit", detail: "src/auth/middleware.ts", sub: "Running…" },
      ],
      // shown when state === "waiting" — status + selection, no code/diff
      approve: { tool: "Edit", file: "src/auth/middleware.ts", add: 3, del: 1 },
      // shown when state === "asking"
      ask: {
        q: "Which deployment target?",
        opts: ["Production", "Staging", "Local only"],
      },
      // shown when state === "done"
      done: { summary: "Fixed the auth bug.", files: 3, tests: "8 passed" },
    },
    {
      id: "backend-server",
      name: "backend server",
      agent: "Codex",
      term: "Terminal",
      age: "1h",
      state: "working",
      task: "build the users endpoint",
      activity: [
        { tool: "Write", detail: "src/routes/users.ts", sub: "New file (47 lines)" },
      ],
    },
    {
      id: "optimize-queries",
      name: "optimize queries",
      agent: "Gemini",
      term: "Ghostty",
      age: "5h",
      state: "working",
      task: "speed up the slow queries",
      activity: [
        { tool: "Analyzing", detail: "the slow queries." },
        { tool: "Read", detail: "schema.prisma", sub: "1.2 KB" },
        { tool: "Edit", detail: "src/db/client.ts", sub: "Updated (+6 -2)" },
      ],
    },
  ],

  // The demo scenario: drive `fix-auth-bug` through the full flow. Each step sets the
  // session state; `page:true` fires a screen flash (stands in for the buzz/page).
  scenario: {
    target: "fix-auth-bug",
    steps: [
      { state: "working", ms: 1400 },
      { state: "waiting", ms: 2200, page: true }, // needs approval
      { state: "working", ms: 1400 },             // (auto-allowed)
      { state: "asking", ms: 2200, page: true },  // asks a question
      { state: "working", ms: 1400 },             // (auto-answered)
      { state: "done", ms: 2600, page: true },    // finished
    ],
  },
};
