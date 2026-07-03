# Examples

End-to-end builds that exercise the [skills](../skills/). Each is a small, real product
you can reproduce: a brief (the spec), the generator sources, and a note on what each
skill produced.

| Example | Skills used | What it is |
|---|---|---|
| [**voice-buddy**](voice-buddy/) | plm · pcb · cad · firmware | a xiaozhi-style **AI speaker** (ESP32-S3 + ES8311/ES7210 + OLED) — the end-to-end reference: generated board (DRC 0/0), printed enclosure (fit 0 mm³), xiaozhi firmware port |
| [**pager-buddy**](pager-buddy/) | plm · firmware · pcb · cad | a desk "pager" that signals **Claude Code session status / notifications** — firmware + Mac bridge working on an M5StickC S3; custom pcb/cad still stubs |

## Add your own

```
examples/<name>/
  README.md      # the brief: what it does, the shared fit numbers, per-skill output
  product.yaml   # the vibe-plm manifest: identity + revision + interface contracts
  firmware/      # vibe-firmware sources       (consumes pcb/pinmap.yaml)
  pcb/           # vibe-pcb project (gen_sch.py / gen_pcb.py …) + pinmap.yaml
  cad/           # vibe-cad model (one parametric .py + build_all.py) + constraints.yaml
```

Validate the manifest + contracts with
`python3 ../../skills/vibe-plm/scripts/plm_check.py product.yaml`.

Keep examples **generic and publishable** — illustrate the method, don't ship a
proprietary product design. Point the relevant skill's "worked reference" at your
example so the next person has a filled-in template.
