# Contributing

This repo is a set of **agent skills** for vibe-coding hardware, plus worked
`examples/`. Two ways to help: improve a skill, or add an example.

## Improve a skill

Each skill is `skills/<name>/`:

```
skills/<name>/
  SKILL.md        # frontmatter (name + description with "use when…") + the method
  references/     # the deep lessons / gotchas (loaded on demand)
  scripts/        # plain bash/python tools (no framework lock-in)
```

- **Living docs.** When a real build teaches you a new gotcha, fix, or better
  practice, fold it back into the skill (`SKILL.md` / `references/` / `scripts/`) and
  commit it *with* the work — don't leave the lesson in a chat log. Compounding the
  experience is the whole point.
- **Keep it general.** Skills teach a reusable method. Illustrate with generic parts
  (a XIAO, an off-the-shelf sensor) — **never commit a proprietary or product-specific
  design**. Worked designs go in `examples/` (which you choose to publish), not in the
  skill.
- **Scripts stay portable.** `bash` + `python3` + the documented CLI (KiCad, build123d
  venv). Gate paths behind env overrides (e.g. `KICAD_CLI`) for non-mac users.

## Language

Hardware people are everywhere, and so are the contributors here. **Non-English text is
welcome** — a pronunciation fixture in code (see `vibe-voice`'s zh/ja/ko preflight
samples), a quoted user-facing string, a log excerpt in an example, a whole translated
doc.

The one convention: English is the **lingua franca of the shared docs**, so anyone can
get oriented. A translation lives *beside* its English original with a language suffix —
`README.zh.md`, `docs/getting-started.ja.md` — rather than replacing it. CI fails only on
a translation whose English original is missing; a normal doc that reads as mostly
non-English gets a nudge to become a `*.<lang>.md`, not an error.

Write in the English you have. A clear idea in imperfect English beats a missing one, and
we would much rather fix your grammar than lose your gotcha.

## Add an example

`examples/<name>/` is a complete small build that exercises one or more skills. Give it
a `README.md` brief (the spec), the generator sources, and a note on what each skill
produced. Point the relevant skill's "worked reference" at it.

## Scope

Small embedded products: a module-carrier PCB + a 3D-printed/moulded shell + firmware
that runs on it. If a skill needs a heavyweight EDA/CAD GUI to use, it's not done — the
goal is *generate by script, review in the browser*.
