# Headless Blender render: GLB → (studio.blend | programmatic studio) → Cycles.
#
#   Blender --background --python blender_render.py -- <in.glb> [out.png] [samples] [studio.blend]
#   samples 0 = save the .blend project only (no render). Defaults: out/render.png, 128,
#   ./studio.blend (also via env ID_STUDIO). The project is saved next to out.png as
#   <out>.blend with textures packed — open it, tune, F12.
#
# Studio comes from one of two places, chosen automatically:
#   1. studio.blend exists (hand-tuned, produced by blender_extract_studio.py): open it,
#      place the new device only, re-attach hand-tuned materials from its override table.
#      Model changes; lighting and material design are reused.
#   2. otherwise a programmatic fallback (wall + key/fill softboxes + camera + settings).
#
# Facts that bit us:
# - three.js exports millimetres, glTF means metres → scale 0.001 or the device is 170 m wide.
# - The importer converts y-up → z-up; the FRONT faces −Y. Wall on +Y, camera on −Y.
# - Emissives (with KHR_materials_emissive_strength) import as real light sources.
# - Product shots: view transform Khronos PBR Neutral, not AgX (AgX turns safety orange salmon).
import os
import sys
from math import radians

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blender_scenelib as lib  # noqa: E402

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
GLB = os.path.abspath(argv[0]) if argv else os.path.abspath('out/device.glb')
OUT = os.path.abspath(argv[1]) if len(argv) > 1 else os.path.abspath('out/render.png')
SAMPLES = int(argv[2]) if len(argv) > 2 else 128
STUDIO = os.path.abspath(argv[3]) if len(argv) > 3 else os.environ.get('ID_STUDIO', os.path.abspath('studio.blend'))
DEVICE_DEPTH_M = float(os.environ.get('ID_DEVICE_DEPTH_MM', '12')) / 1000.0


def build_programmatic_studio(scene):
    def link(o):
        scene.collection.objects.link(o)
        return o

    import bmesh
    wall_mesh = bpy.data.meshes.new('wall')
    wall = link(bpy.data.objects.new('wall', wall_mesh))
    bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=1, y_segments=1, size=1.2)
    bm.to_mesh(wall_mesh)
    bm.free()
    wall.rotation_euler = (radians(90), 0, 0)      # normal → −Y, facing the camera
    wall.location = (0, DEVICE_DEPTH_M / 2 + 0.0015, 0)
    m = bpy.data.materials.new('wall')
    m.use_nodes = True
    b = m.node_tree.nodes['Principled BSDF']
    b.inputs['Base Color'].default_value = (0.855, 0.83, 0.80, 1)
    b.inputs['Roughness'].default_value = 0.95
    wall_mesh.materials.append(m)

    def area(name, loc, rot, size, power, color=(1, 0.98, 0.95)):
        d = bpy.data.lights.new(name, 'AREA')
        d.shape, d.size, d.energy, d.color = 'SQUARE', size, power, color
        o = link(bpy.data.objects.new(name, d))
        o.location, o.rotation_euler = loc, rot
        return o

    area('key', (0.5, -0.8, 0.55), (radians(35), radians(25), 0), 1.2, 80)
    area('fill', (-0.55, -0.7, 0.1), (radians(8), radians(-35), 0), 0.9, 26)

    world = bpy.data.worlds.new('world')
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes['Background']
    bg.inputs['Color'].default_value = (0.82, 0.80, 0.78, 1)
    bg.inputs['Strength'].default_value = 0.22

    cam_data = bpy.data.cameras.new('cam')
    cam_data.lens = 85
    cam = link(bpy.data.objects.new('cam', cam_data))
    cam.location = (-0.012, -0.72, 0.01)
    target = link(bpy.data.objects.new('cam-target', None))
    tc = cam.constraints.new('TRACK_TO')
    tc.target, tc.track_axis, tc.up_axis = target, 'TRACK_NEGATIVE_Z', 'UP_Y'
    scene.camera = cam

    scene.render.engine = 'CYCLES'
    try:
        scene.view_settings.view_transform = 'Khronos PBR Neutral'
    except TypeError:
        scene.view_settings.view_transform = 'Standard'
    scene.view_settings.exposure = -0.15
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1280


if os.path.exists(STUDIO):
    bpy.ops.wm.open_mainfile(filepath=STUDIO)
    scene = bpy.context.scene
    _, imported = lib.import_device(scene, GLB)
    lib.apply_overrides(imported)
    print('studio: hand-tuned', STUDIO)
else:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    lib.import_device(scene, GLB)
    build_programmatic_studio(scene)
    print('studio: programmatic fallback (no studio.blend)')

scene.cycles.samples = SAMPLES if SAMPLES > 0 else 128
scene.render.filepath = OUT
scene.render.image_settings.file_format = 'PNG'

os.makedirs(os.path.dirname(OUT), exist_ok=True)
BLEND = os.path.splitext(OUT)[0] + '.blend'
bpy.ops.file.pack_all()      # glTF textures live in memory; unpacked .blend opens magenta
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print('blend ->', BLEND)
if SAMPLES > 0:
    bpy.ops.render.render(write_still=True)
    print('rendered ->', OUT)
