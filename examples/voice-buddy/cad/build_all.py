"""Export the voice-buddy enclosure: STEP + STL for the printed parts, plus the
fit / exploded assemblies, each with the hidden GLB sidecar the CAD Viewer needs.

    cd examples/voice-buddy/cad && /path/to/.venv/bin/python build_all.py

Outputs land in models/ (regenerated, never committed — repo .gitignore keeps
*.stl / .*.glb out; don't commit the STEPs either, they rebuild from source).
"""

from pathlib import Path

from build123d import export_gltf, export_step, export_stl

import voicebuddy_case as m

HERE = Path(__file__).resolve().parent
OUT = HERE / "models"
OUT.mkdir(exist_ok=True)


def export(part, name: str, stl: bool):
    """STEP (+ optional STL) + the viewer's hidden .<name>.step.glb sidecar."""
    export_step(part, str(OUT / f"{name}.step"))
    export_gltf(part, str(OUT / f".{name}.step.glb"), binary=True)
    if stl:
        export_stl(part, str(OUT / f"{name}.stl"))
    print(f"  {name}.step" + (" + .stl" if stl else "") + " (+ GLB sidecar)")


if __name__ == "__main__":
    print("exporting to", OUT)
    export(m.build_shell_front(), "shell_front", stl=True)   # printed part 1
    export(m.build_cover_rear(), "cover_rear", stl=True)     # printed part 2
    export(m.build_plunger(), "plunger", stl=True)           # printed part 3 (x3)
    export(m.build_fit(), "voicebuddy_fit", stl=False)       # review assemblies
    export(m.build_exploded(), "voicebuddy_exploded", stl=False)

    print(f"grille: {len(m._grille_pts())} x d{m.GRILLE_HOLE_D} holes, "
          f"open ratio {m.grille_ratio():.3f} (contract min {m.GRILLE_MIN})")
    vol = m.cavity_volume_cm3()
    assert vol >= m.CAVITY_MIN_CM3, f"rear cavity {vol:.1f} cm3 < {m.CAVITY_MIN_CM3}"
    print(f"rear cavity air volume: {vol:.1f} cm3 (>= {m.CAVITY_MIN_CM3} heuristic)")
    print("done")
