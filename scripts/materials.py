"""Procedural materials for the engineering series (pristine finish).

Nodes are found by type, never by name, so the script works on any UI
language. Texture coordinates come from the object, since geometry built in
Geometry Nodes carries no UV map.

Run inside Blender:
    exec(open(bpy.path.abspath('//scripts/materials.py')).read())
"""
import bpy


def new_material(name):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    out.location, bsdf.location = (400, 0), (100, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    return mat, nt, bsdf


def coords(nt):
    tc = nt.nodes.new('ShaderNodeTexCoord')
    tc.location = (-1000, 0)
    return tc.outputs['Object']


def noise(nt, vec, scale, detail=4.0, rough=0.5):
    n = nt.nodes.new('ShaderNodeTexNoise')
    n.inputs['Scale'].default_value = scale
    n.inputs['Detail'].default_value = detail
    n.inputs['Roughness'].default_value = rough
    nt.links.new(vec, n.inputs['Vector'])
    return n.outputs['Fac']


def ramp(nt, fac, stops):
    """stops: list of (position, (r, g, b))."""
    r = nt.nodes.new('ShaderNodeValToRGB')
    els = r.color_ramp.elements
    while len(els) > len(stops):
        els.remove(els[-1])
    while len(els) < len(stops):
        els.new(0.5)
    for el, (pos, rgb) in zip(els, stops):
        el.position = pos
        el.color = (*rgb, 1.0)
    nt.links.new(fac, r.inputs['Fac'])
    return r.outputs['Color']


def map_range(nt, fac, lo, hi):
    m = nt.nodes.new('ShaderNodeMapRange')
    m.inputs['To Min'].default_value = lo
    m.inputs['To Max'].default_value = hi
    nt.links.new(fac, m.inputs['Value'])
    return m.outputs['Result']


def bump(nt, height, strength, distance=0.01):
    b = nt.nodes.new('ShaderNodeBump')
    b.inputs['Strength'].default_value = strength
    b.inputs['Distance'].default_value = distance
    nt.links.new(height, b.inputs['Height'])
    return b.outputs['Normal']


def painted_iron(name, dark, light, rough=(0.32, 0.42), coat=0.15):
    """Fresh oil paint on iron: dielectric, faint brush mottling, light coat."""
    mat, nt, bsdf = new_material(name)
    co = coords(nt)
    mottle = noise(nt, co, 6.0, detail=6.0)
    nt.links.new(ramp(nt, mottle, [(0.35, dark), (0.65, light)]), bsdf.inputs['Base Color'])
    nt.links.new(map_range(nt, noise(nt, co, 25.0), *rough), bsdf.inputs['Roughness'])
    bsdf.inputs['Metallic'].default_value = 0.0
    bsdf.inputs['Coat Weight'].default_value = coat
    bsdf.inputs['Coat Roughness'].default_value = 0.25
    nt.links.new(bump(nt, noise(nt, co, 180.0, detail=2.0), 0.04), bsdf.inputs['Normal'])
    return mat


def limestone(name):
    """Pale dressed limestone with soft colour variation and tooling bump."""
    mat, nt, bsdf = new_material(name)
    co = coords(nt)
    vor = nt.nodes.new('ShaderNodeTexVoronoi')
    vor.inputs['Scale'].default_value = 3.0
    nt.links.new(co, vor.inputs['Vector'])
    big = noise(nt, co, 1.5, detail=3.0)
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'FLOAT'
    mix.inputs['Factor'].default_value = 0.5
    nt.links.new(big, mix.inputs['A'])
    nt.links.new(vor.outputs['Distance'], mix.inputs['B'])
    col = ramp(nt, mix.outputs['Result'], [(0.2, (0.30, 0.27, 0.21)),
                                           (0.5, (0.40, 0.37, 0.30)),
                                           (0.8, (0.46, 0.43, 0.36))])
    nt.links.new(col, bsdf.inputs['Base Color'])
    bsdf.inputs['Roughness'].default_value = 0.85
    fine = noise(nt, co, 60.0, detail=8.0, rough=0.7)
    nt.links.new(bump(nt, fine, 0.25), bsdf.inputs['Normal'])
    return mat


def oak(name):
    """Oiled oak planks: brick texture for boards, wave texture for grain.

    Colour values are linear, as Blender stores them (sRGB looks lighter).
    """
    mat, nt, bsdf = new_material(name)
    co = coords(nt)
    wave = nt.nodes.new('ShaderNodeTexWave')
    wave.wave_type = 'BANDS'
    wave.bands_direction = 'X'
    wave.inputs['Scale'].default_value = 6.0
    wave.inputs['Distortion'].default_value = 8.0
    wave.inputs['Detail'].default_value = 4.0
    nt.links.new(co, wave.inputs['Vector'])
    grain = ramp(nt, wave.outputs['Fac'], [(0.3, (0.075, 0.040, 0.018)),
                                           (0.7, (0.14, 0.080, 0.036))])
    planks = nt.nodes.new('ShaderNodeTexBrick')
    planks.offset = 0.37
    planks.inputs['Scale'].default_value = 1.0
    planks.inputs['Brick Width'].default_value = 2.4
    planks.inputs['Row Height'].default_value = 0.14
    planks.inputs['Mortar Size'].default_value = 0.006
    planks.inputs['Mortar'].default_value = (0.012, 0.008, 0.005, 1.0)
    planks.inputs['Color2'].default_value = (0.11, 0.06, 0.028, 1.0)
    nt.links.new(co, planks.inputs['Vector'])
    nt.links.new(grain, planks.inputs['Color1'])
    nt.links.new(planks.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(bump(nt, planks.outputs['Fac'], 0.3, 0.005), bsdf.inputs['Normal'])
    bsdf.inputs['Roughness'].default_value = 0.6
    return mat


MATERIALS = {
    # Eiffel's 1889 "Venetian red", freshly applied
    "Iron": painted_iron("M_Iron_VenetianRed",
                         dark=(0.15, 0.032, 0.020), light=(0.175, 0.040, 0.025)),
    "Tank Iron": painted_iron("M_Iron_RedOxide_Dark",
                              dark=(0.060, 0.014, 0.010), light=(0.068, 0.017, 0.012),
                              rough=(0.38, 0.5)),
    "Stone": limestone("M_Limestone"),
    "Timber": oak("M_Oak_Deck"),
}

# plug them into the tower's modifier
obj = bpy.data.objects.get("Shukhov_Lattice")
if obj is not None:
    mod = obj.modifiers["Shukhov_Lattice"]
    ins = mod.properties.inputs
    for item in mod.node_group.interface.items_tree:
        if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.name in MATERIALS:
            getattr(ins, item.identifier).value = MATERIALS[item.name]
    obj.update_tag()   # writing modifier inputs does not trigger re-evaluation
