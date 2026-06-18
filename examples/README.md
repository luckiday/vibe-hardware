# Examples

End-to-end builds that exercise the [skills](../skills/). Each is a small, real product
you can reproduce: a brief (the spec), the generator sources, and a note on what each
skill produced.

| Example | Skills used | What it is |
|---|---|---|
| [**pager-buddy**](pager-buddy/) | firmware · pcb · cad | an ESP32 desk "pager" that signals **Claude Code session status / notifications** *(brief — being filled in)* |

## Add your own

```
examples/<name>/
  README.md      # the brief: what it does, the shared fit numbers, per-skill output
  firmware/      # vibe-firmware sources
  pcb/           # vibe-pcb project (gen_sch.py / gen_pcb.py …)
  cad/           # vibe-cad model (one parametric .py + build_all.py)
```

Keep examples **generic and publishable** — illustrate the method, don't ship a
proprietary product design. Point the relevant skill's "worked reference" at your
example so the next person has a filled-in template.
