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


# ---------------------------------------------------------------- light bar (purpose-built material)
# The GLB's light bar is "black base + white emissive ×8". Fine for a rasteriser; in
# Cycles it is a faintly glowing plastic strip: a few cm² at strength 8 neither beats
# the studio HDRI (so it doesn't read as a lamp) nor lights the wall below (too weak).
# The two wants contradict physically — wall-lighting strength is in the hundreds, and
# at that level the bar itself is a white smear with no edge.
#
# Product-shot trick: split what the CAMERA sees from what LIGHTS THE SCENE
# (Light Path → Is Camera Ray). Camera rays get STRENGTH_CAM (warm, a touch
# over-exposed, edge still visible); bounce rays get STRENGTH_LIGHT (a real pool of
# light on the wall — Cycles importance-samples mesh lights, no fake area light).
# Unlit = `lit` → 0; the base is milky PMMA with a coat, so nothing to swap.
# All knobs are Value nodes: scripts and hand tuning both just set them.
LIGHTBAR_MAT = 'lightbar-tuned'
LIGHTBAR_COLOR = (1.0, 0.86, 0.62)     # ~2700 K warm white; pure white makes the body look cold
STRENGTH_CAM = 7.0
STRENGTH_LIGHT = 160.0


def lightbar_material(color=LIGHTBAR_COLOR, cam=STRENGTH_CAM, light=STRENGTH_LIGHT):
    m = bpy.data.materials.get(LIGHTBAR_MAT)
    if m:
        return m
    m = bpy.data.materials.new(LIGHTBAR_MAT)
    m.use_nodes = True
    nt = m.node_tree
    nodes, links = nt.nodes, nt.links
    for n in list(nodes):
        nodes.remove(n)
    out = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    lp = nodes.new('ShaderNodeLightPath')
    v_cam = nodes.new('ShaderNodeValue'); v_cam.name = v_cam.label = 'strength_cam'
    v_light = nodes.new('ShaderNodeValue'); v_light.name = v_light.label = 'strength_light'
    v_lit = nodes.new('ShaderNodeValue'); v_lit.name = v_lit.label = 'lit'
    v_cam.outputs[0].default_value = cam
    v_light.outputs[0].default_value = light
    v_lit.outputs[0].default_value = 1.0
    mix = nodes.new('ShaderNodeMix'); mix.data_type = 'FLOAT'; mix.name = 'cam-vs-light'
    mul = nodes.new('ShaderNodeMath'); mul.operation = 'MULTIPLY'; mul.name = 'lit-gate'
    links.new(lp.outputs['Is Camera Ray'], mix.inputs['Factor'])
    links.new(v_light.outputs[0], mix.inputs[2])   # factor 0 → bounce rays
    links.new(v_cam.outputs[0], mix.inputs[3])     # factor 1 → camera rays
    links.new(mix.outputs[0], mul.inputs[0])
    links.new(v_lit.outputs[0], mul.inputs[1])
    links.new(mul.outputs[0], bsdf.inputs['Emission Strength'])
    bsdf.inputs['Emission Color'].default_value = (*color, 1.0)
    bsdf.inputs['Base Color'].default_value = (0.90, 0.88, 0.84, 1.0)   # milky PMMA diffuser
    bsdf.inputs['Roughness'].default_value = 0.45
    bsdf.inputs['Coat Weight'].default_value = 0.6                        # acrylic sheen
    bsdf.inputs['Coat Roughness'].default_value = 0.15
    links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    for i, n in enumerate((lp, v_cam, v_light, v_lit, mix, mul, bsdf, out)):
        n.location = (i * 220 - 800, 0)
    return m


def apply_lightbar(imported, name_prefix='lightbar'):
    """Replace every device material named `lightbar*` (the GLB's bottom light) with
    the tuned material. Run AFTER apply_overrides: the code version always wins, even
    if a hand-tuned studio recorded an override for the bar."""
    m = lightbar_material()
    n = 0
    for o in imported:
        if o.type != 'MESH':
            continue
        for s in o.material_slots:
            if s.material and s.material.name.startswith(name_prefix) and s.material is not m:
                s.material = m
                n += 1
    print(f'[lightbar] {n} slot(s) -> {LIGHTBAR_MAT} (cam {STRENGTH_CAM} / light {STRENGTH_LIGHT})')
    return m


def set_lightbar(on, cam=None, light=None):
    """Lit/unlit + optional strength overrides for the tuned bar (no-op if absent)."""
    m = bpy.data.materials.get(LIGHTBAR_MAT)
    if not m:
        return
    nodes = m.node_tree.nodes
    nodes['lit'].outputs[0].default_value = 1.0 if on else 0.0
    if cam is not None:
        nodes['strength_cam'].outputs[0].default_value = cam
    if light is not None:
        nodes['strength_light'].outputs[0].default_value = light


# ---------------------------------------------------------------- ambient level
def set_ambient(scene, factor, _cache={}):
    """Scale the whole studio (World background strength + every lamp) to `factor`,
    for "dim room, bar switched on" comparison shots. Baseline is captured on the
    first call, so it can be set repeatedly and returned to 1.0."""
    key = id(scene)
    if key not in _cache:
        base = {}
        w = scene.world
        if w and w.node_tree:
            for n in w.node_tree.nodes:
                if n.type == 'BACKGROUND':
                    base[('w', n.name)] = n.inputs['Strength'].default_value
        for o in scene.objects:
            if o.type == 'LIGHT':
                base[('l', o.name)] = o.data.energy
        _cache[key] = base
    w = scene.world
    for (kind, name), v in _cache[key].items():
        if kind == 'w' and w and w.node_tree:
            w.node_tree.nodes[name].inputs['Strength'].default_value = v * factor
        elif kind == 'l':
            o = scene.objects.get(name)
            if o:
                o.data.energy = v * factor


# ---------------------------------------------------------------- post: bloom
# A path tracer computes where light GOES (the pool on the wall is real transport);
# it never paints the halo a lens/sensor puts around a bright source. That is post:
# the compositor Glare node in Bloom mode. Threshold 1.0 = only pixels brighter than
# white bloom (the bar at camera strength 7, lit dots) — paint highlights mostly don't.
# Blender 5.x facts: Glare's type/quality/params are node INPUT SOCKETS (menu values
# are the display names, 'Bloom' not 'BLOOM'); the tree hangs off
# scene.compositing_node_group; the output is a NodeGroupOutput whose Image socket
# must be declared on the tree interface first (CompositorNodeComposite is gone).
def enable_bloom(scene, threshold=1.0, size=0.7, strength=0.6, smoothness=0.1):
    nt = scene.compositing_node_group
    if nt is None:
        nt = bpy.data.node_groups.new('studio-comp', 'CompositorNodeTree')
        scene.compositing_node_group = nt
    nodes, links = nt.nodes, nt.links
    if 'bloom' in nodes:
        g = nodes['bloom']
    else:
        rl = next((n for n in nodes if n.type == 'R_LAYERS'), None) or nodes.new('CompositorNodeRLayers')
        out = next((n for n in nodes if n.type in ('COMPOSITE', 'GROUP_OUTPUT')), None)
        if out is None:
            out = nodes.new('NodeGroupOutput')
        if 'Image' not in [i.name for i in out.inputs]:
            nt.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
        g = nodes.new('CompositorNodeGlare')
        g.name = g.label = 'bloom'
        g.inputs['Type'].default_value = 'Bloom'
        g.inputs['Quality'].default_value = 'High'
        for l in list(links):
            if l.to_node is out and l.to_socket.name == 'Image':
                links.remove(l)
        links.new(rl.outputs['Image'], g.inputs['Image'])
        links.new(g.outputs['Image'], out.inputs['Image'])
        rl.location, g.location, out.location = (-400, 0), (0, 0), (300, 0)
    g.inputs['Threshold'].default_value = threshold
    g.inputs['Smoothness'].default_value = smoothness
    g.inputs['Size'].default_value = size
    g.inputs['Strength'].default_value = strength
    g.mute = False
    scene.render.use_compositing = True
    return g


def set_bloom(scene, on):
    nt = scene.compositing_node_group
    if nt and 'bloom' in nt.nodes:
        nt.nodes['bloom'].mute = not on
