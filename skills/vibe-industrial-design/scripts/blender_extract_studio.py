# Extract the STUDIO out of a hand-tuned project so it survives every model regeneration.
#
#   Blender --background --python blender_extract_studio.py -- <tuned.blend> [studio.blend]
#
# Keeps "everything except the device": world (HDRI), walls, lights, camera, render + view
# settings, UI layout — plus a material OVERRIDE TABLE: for every device part whose slot
# carries a non-glTF material (anything not named Material_N), record
# {object name → [material name per slot]} into a text block `studio-overrides.json` and
# keep those materials (fake user). blender_render.py / blender_shots.py re-attach them by
# object name after the next import. Then the device is deleted, orphans purged, everything
# packed, and studio.blend is saved compressed (machine-independent).
import json
import os
import sys

import bpy

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
SRC = os.path.abspath(argv[0]) if argv else os.path.abspath('out/render.blend')
DST = os.path.abspath(argv[1]) if len(argv) > 1 else os.environ.get('ID_STUDIO', os.path.abspath('studio.blend'))
ROOT_NAME = 'device-root'

bpy.ops.wm.open_mainfile(filepath=SRC)

root = bpy.data.objects.get(ROOT_NAME)
assert root, f'no {ROOT_NAME} — was this project made by blender_render.py?'
device_objs, stack = [], [root]
while stack:
    cur = stack.pop()
    for c in cur.children:
        device_objs.append(c)
        stack.append(c)

overrides, keep = {}, set()
for o in device_objs:
    if o.type != 'MESH':
        continue
    names = [s.material.name if s.material else None for s in o.material_slots]
    tuned = [n for n in names if n and not n.startswith('Material_')]
    if tuned:
        overrides[o.name] = names
        keep.update(tuned)
for n in keep:
    bpy.data.materials[n].use_fake_user = True

txt = bpy.data.texts.get('studio-overrides.json') or bpy.data.texts.new('studio-overrides.json')
txt.clear()
txt.write(json.dumps(overrides, ensure_ascii=False, indent=1))
print('override table:', json.dumps(overrides, ensure_ascii=False))

for o in device_objs:
    bpy.data.objects.remove(o, do_unlink=True)
bpy.data.objects.remove(root, do_unlink=True)
for _ in range(3):
    bpy.ops.outliner.orphans_purge(do_recursive=True)

bpy.ops.file.pack_all()
bpy.ops.wm.save_as_mainfile(filepath=DST, compress=True)
print('studio ->', DST, f'({os.path.getsize(DST) / 1e6:.1f} MB)')
