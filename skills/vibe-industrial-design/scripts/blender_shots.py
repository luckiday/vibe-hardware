# Multi-angle shot set from the hand-tuned studio: one run, all cameras, text added later.
#
#   Blender --background --python blender_shots.py -- <in.glb> [samples] [shot names…]
#   env: ID_STUDIO (default ./studio.blend), ID_SHOTS_DIR (default out/shots),
#        ID_LIGHT_PREFIX (material-name prefix of the light bar to toggle; default 'lightbar')
#
# Camera moves, wall doesn't; faces you can't put a camera behind (back/top/bottom of a
# wall-mounted device) are shown by ROTATING THE DEVICE. Lit/unlit toggles only the
# materials whose name starts with ID_LIGHT_PREFIX — front indicator dots stay lit.
import os
import sys
from math import radians

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_scenelib as lib  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
GLB = os.path.abspath(argv[0]) if argv else os.path.abspath('out/device.glb')
SAMPLES = int(argv[1]) if len(argv) > 1 else 128
ONLY = set(argv[2:])
STUDIO = os.environ.get('ID_STUDIO', os.path.abspath('studio.blend'))
OUTDIR = os.environ.get('ID_SHOTS_DIR', os.path.abspath('out/shots'))
LIGHT_PREFIX = os.environ.get('ID_LIGHT_PREFIX', 'lightbar')
os.makedirs(OUTDIR, exist_ok=True)

assert os.path.exists(STUDIO), f'missing {STUDIO} — run blender_extract_studio.py first'
bpy.ops.wm.open_mainfile(filepath=STUDIO)
scene = bpy.context.scene
device, imported = lib.import_device(scene, GLB)
lib.apply_overrides(imported)
emissives = lib.emissive_materials(imported, name_prefix=LIGHT_PREFIX)

cam = scene.camera
scene.cycles.samples = SAMPLES
scene.render.image_settings.file_format = 'PNG'

# rot = device pose (deg XYZ), cam = camera position (m), lens (mm), res, lit.
# Device front faces −Y (see blender_render.py). Tune the numbers to your product size.
SHOTS = {
    'front':      dict(rot=(0, 0, 0),    cam=(-0.012, -0.72, 0.01),  lens=85, res=(1920, 1280), lit=True),
    'hero':       dict(rot=(0, 0, 0),    cam=(-0.34, -0.58, -0.12),  lens=70, res=(1920, 1280), lit=True),
    'side':       dict(rot=(0, 0, 0),    cam=(0.60, -0.22, 0.02),    lens=85, res=(1440, 1280), lit=True),
    'back':       dict(rot=(0, 0, 180),  cam=(0.012, -0.72, 0.01),   lens=85, res=(1920, 1280), lit=False),
    'top':        dict(rot=(90, 0, 0),   cam=(0, -0.62, 0.0),        lens=85, res=(1920, 900),  lit=True),
    'bottom-off': dict(rot=(-90, 0, 0),  cam=(0, -0.62, 0.0),        lens=85, res=(1920, 900),  lit=False),
    'bottom-on':  dict(rot=(-90, 0, 0),  cam=(0, -0.62, 0.0),        lens=85, res=(1920, 900),  lit=True),
}

for name, s in SHOTS.items():
    if ONLY and name not in ONLY:
        continue
    device.rotation_euler = tuple(radians(v) for v in s['rot'])
    cam.location = s['cam']
    cam.data.lens = s['lens']
    scene.render.resolution_x, scene.render.resolution_y = s['res']
    lib.set_emissive(emissives, s['lit'])
    scene.render.filepath = os.path.join(OUTDIR, f'{name}.png')
    bpy.ops.render.render(write_still=True)
    print('shot ->', scene.render.filepath)
print('done:', OUTDIR)
