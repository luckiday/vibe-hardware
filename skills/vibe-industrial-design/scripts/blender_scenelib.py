"""Shared by blender_render.py / blender_shots.py: import the GLB, re-attach the
hand-tuned materials from the studio's override table, toggle emissives.

Run inside Blender (`Blender --background --python …`); `bpy` only.
"""
import json
import bpy


def import_device(scene, glb, root_name='device-root', scale=0.001):
    """Import a GLB, parent it under an empty, scale (three.js mm → Blender m).
    Returns (root, imported_objects)."""
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=glb)
    imported = [o for o in bpy.data.objects if o not in before]
    root = bpy.data.objects.new(root_name, None)
    scene.collection.objects.link(root)
    for o in imported:
        if o.parent is None:
            o.parent = root
    root.scale = (scale, scale, scale)
    return root, imported


def apply_overrides(imported, text_name='studio-overrides.json'):
    """Re-attach hand-tuned materials recorded by blender_extract_studio.py.
    Matched by OBJECT NAME (stable — the exporter sets it). A renamed/removed part
    or a missing material prints an [override] line; nothing is dropped silently."""
    txt = bpy.data.texts.get(text_name)
    if not txt:
        return
    table = json.loads(txt.as_string() or '{}')
    objs = {o.name: o for o in imported}
    for name, slots in table.items():
        o = objs.get(name)
        if o is None:
            print(f'[override] object {name} not in this GLB (renamed/removed?) — skipped')
            continue
        for i, mat_name in enumerate(slots):
            if mat_name is None or mat_name.startswith('Material_'):
                continue  # None / glTF-native: keep the imported one
            mat = bpy.data.materials.get(mat_name)
            if mat is None:
                print(f'[override] material {mat_name} not in studio.blend — skipped')
                continue
            if i < len(o.material_slots):
                o.material_slots[i].material = mat
                print(f'[override] {name}[{i}] <- {mat_name}')


def emissive_materials(imported, name_prefix=None):
    """Materials that REALLY emit. Test strength × colour: Principled's Emission
    Strength defaults to 1.0 (with black colour) — "strength > 0" flags everything
    and set_emissive would paint the whole device black. `name_prefix` restricts to
    named materials (e.g. 'lightbar') so 'lights off' leaves front indicator dots alone."""
    mats = {}
    for o in imported:
        if o.type != 'MESH':
            continue
        for s in o.material_slots:
            m = s.material
            if not (m and m.node_tree):
                continue
            if name_prefix and not m.name.startswith(name_prefix):
                continue
            for n in m.node_tree.nodes:
                if n.type == 'BSDF_PRINCIPLED':
                    stg = n.inputs.get('Emission Strength')
                    col = n.inputs.get('Emission Color')
                    if stg and col and stg.default_value > 0.5 and max(col.default_value[:3]) > 0.05:
                        mats[m.name] = (n, stg.default_value)
    return mats


def set_emissive(mats, on, opal=(0.87, 0.85, 0.81, 1.0)):
    """Lit / unlit. Emissive parts export with a BLACK base (all the light is in the
    emission) — zeroing strength alone leaves a black plastic bar; swap the base to a
    milky diffuser colour when off."""
    for node, original in mats.values():
        node.inputs['Emission Strength'].default_value = original if on else 0.0
        node.inputs['Base Color'].default_value = (0, 0, 0, 1) if on else opal
        node.inputs['Roughness'].default_value = 0.4
