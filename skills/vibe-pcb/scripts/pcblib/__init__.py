"""pcblib — relational PCB layout for script-generated KiCad boards.

The bridge between language and geometry: a generator names RELATIONS
("beside", "at the contract's USB port", "on the IC's supply pad") and
CONTRACTS (constraints.yaml, pinmap.yaml, parts.yaml); this library computes
the coordinates. See skills/vibe-pcb/SKILL.md for the method and
examples/voice-buddy/pcb/ for the worked generator.

Import split: `contract` is stdlib-only (usable anywhere); `layout`/`gates`/
`route` need pcbnew, `sch` is stdlib-only again. Importing the package pulls
the stdlib parts eagerly and the pcbnew parts lazily, so gen_sch.py can run
under plain python while gen_pcb.py runs under KiCad's python.
"""

from .contract import (load_yaml, load_constraints, load_pinmap, load_parts,
                       Constraints, Pinmap, Parts, PartSpec)
from .sch import Sheet

__all__ = [
    # contracts
    "load_yaml", "load_constraints", "load_pinmap", "load_parts",
    "Constraints", "Pinmap", "Parts", "PartSpec",
    # schematic
    "Sheet",
    # layout (lazy — needs pcbnew)
    "Board", "Part", "Cluster", "place", "beside", "align_pads", "row",
    "at_edge", "apply_move_env",
    # gates (lazy — needs pcbnew)
    "courtyard_overlaps", "cluster_overlaps", "keepout_violations", "hpwl",
    "scorecard", "export_placement", "draw_cluster_boxes",
    # route (lazy — needs pcbnew)
    "path", "wire", "via", "fanout_decoupling", "gnd_pours", "apply_ses",
]

_LAZY = {
    "layout": ["Board", "Part", "Cluster", "place", "beside", "align_pads",
               "row", "at_edge", "apply_move_env"],
    "gates": ["courtyard_overlaps", "cluster_overlaps", "keepout_violations",
              "hpwl", "scorecard", "export_placement", "draw_cluster_boxes"],
    "route": ["path", "wire", "via", "fanout_decoupling", "gnd_pours",
              "apply_ses"],
}


def __getattr__(name):
    for mod, names in _LAZY.items():
        if name in names:
            import importlib
            m = importlib.import_module(f".{mod}", __name__)
            return getattr(m, name)
    raise AttributeError(name)
