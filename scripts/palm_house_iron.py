"""Ironwork and glass for the palm house, as a Geometry Nodes modifier.

Works on the tagged base surface from palm_house.py: every pane stays a glass
face, and edges become members according to their tags:
- wing ribs (arches): lattice girders, two chords joined by a zigzag web
- every 4th drum/dome meridian: lattice girder from plinth to apex, the
  others light glazing bars
- purlins, rings, other meridians: glazing bars
- seams (wing against drum): heavy box girder
Girder depth runs inward along the surface normal, which the base surface
keeps pointing outward.

Run inside Blender after palm_house.py:
    exec(open(bpy.path.abspath('//scripts/palm_house_iron.py')).read())
"""
import bpy
import math

exec(open(bpy.path.abspath('//scripts/gn_helpers.py')).read())

T = Tree("GN_Palm_House_Iron")
T.input("Geometry", 'NodeSocketGeometry')
T.input("Rib Depth", 'NodeSocketFloat', 0.28, 0.0)
T.input("Dome Rib Depth", 'NodeSocketFloat', 0.40, 0.0)
T.input("Web Panel", 'NodeSocketFloat', 0.30, 0.02)
T.input("Chord Size", 'NodeSocketFloat', 0.07, 0.001)
T.input("Bar Size", 'NodeSocketFloat', 0.045, 0.001)
T.input("Major Every", 'NodeSocketInt', 4, 1, 48)
T.input("Meridians", 'NodeSocketInt', 48, 3, 400)     # must match palm_house.DRUM_SEGMENTS
T.input("Plinth Height", 'NodeSocketFloat', 0.8, 0.0)   # must match palm_house.PLINTH
T.input("Plinth Width", 'NodeSocketFloat', 0.45, 0.05)
T.input("Iron", 'NodeSocketMaterial')
T.input("Glass", 'NodeSocketMaterial')
T.input("Brick", 'NodeSocketMaterial')
T.input("Coping", 'NodeSocketMaterial')
T.input("Door", 'NodeSocketMaterial')
T.input("Cresting Scale", 'NodeSocketFloat', 1.4, 0.1)
T.input("Lantern Scale", 'NodeSocketFloat', 1.5, 0.1)    # palm_house.LANTERN_R = 1.0 x this
T.input("Finial Scale", 'NodeSocketFloat', 1.6, 0.1)
T.output("Geometry")

surface = T.gi("Geometry")
# keep the surface normal on the points so the curves made from edges inherit it
store = T.node('GeometryNodeStoreNamedAttribute', {'Geometry': surface, 'Name': "srf_normal",
                                                   'Value': T.node('GeometryNodeInputNormal').outputs[0]},
               data_type='FLOAT_VECTOR', domain='POINT')
surface_n = store.outputs[0]


def tagged(name):
    n = T.node('GeometryNodeInputNamedAttribute', {'Name': name}, data_type='BOOLEAN')
    return n.outputs['Attribute']


def srf_normal():
    return T.node('GeometryNodeInputNamedAttribute', {'Name': "srf_normal"},
                  data_type='FLOAT_VECTOR').outputs['Attribute']


def curves(selection, smooth=True, length=0.25):
    c = T.node('GeometryNodeMeshToCurve', {'Mesh': surface_n, 'Selection': selection}).outputs[0]
    if smooth:      # the edges are chords of circles: smooth them back into arcs
        c = T.node('GeometryNodeCurveSplineType', {'Curve': c}, spline_type='CATMULL_ROM').outputs[0]
        r = T.node('GeometryNodeResampleCurve', {'Curve': c, 'Length': length})
        T.set_menu(r, 'Mode', 'Length')
        c = r.outputs[0]
    return c


def oriented(c):
    """Profiles follow the surface: curve normal = surface normal."""
    n = T.node('GeometryNodeSetCurveNormal', {'Curve': c, 'Normal': srf_normal()})
    T.set_menu(n, 'Mode', 'Free')
    return n.outputs[0]


def sweep(c, w, h):
    prof = T.node('GeometryNodeCurvePrimitiveQuadrilateral', {'Width': w, 'Height': h}).outputs[0]
    return T.node('GeometryNodeCurveToMesh', {'Curve': oriented(c), 'Profile Curve': prof,
                                              'Fill Caps': True}).outputs[0]


def rod(c, r):
    prof = T.node('GeometryNodeCurvePrimitiveCircle', {'Resolution': 6, 'Radius': r}).outputs['Curve']
    return T.node('GeometryNodeCurveToMesh', {'Curve': c, 'Profile Curve': prof}).outputs[0]


def inward(c, depth, factor=None):
    off = T.v('SCALE', srf_normal(), scale=T.m('MULTIPLY', depth, -1.0 if factor is None else factor))
    return T.node('GeometryNodeSetPosition', {'Geometry': c, 'Offset': off}).outputs[0]


def girder(c, depth):
    chord = T.gi("Chord Size")
    outer = sweep(c, chord, T.m('MULTIPLY', chord, 0.6))
    inner = sweep(inward(c, depth), chord, T.m('MULTIPLY', chord, 0.6))
    # web: zigzag between the chords, one apex every half panel
    r = T.node('GeometryNodeResampleCurve', {'Curve': c, 'Length': T.m('MULTIPLY', T.gi("Web Panel"), 0.5)})
    T.set_menu(r, 'Mode', 'Length')
    k = T.node('GeometryNodeSplineParameter').outputs['Index']
    zig = T.m('MODULO', k, 2.0)
    web = T.node('GeometryNodeSetPosition', {'Geometry': r.outputs[0], 'Offset': T.v(
        'SCALE', srf_normal(), scale=T.m('MULTIPLY', zig, T.m('MULTIPLY', depth, -0.97)))}).outputs[0]
    web = rod(web, T.m('MULTIPLY', chord, 0.22))
    return T.join(outer, inner, web)


def is_major_meridian():
    """True on every Major Every-th meridian (by angle round the dome axis)."""
    p = T.sep(T.node('GeometryNodeInputPosition').outputs[0])
    ang = T.m('ARCTAN2', p[1], p[0])
    step = T.m('DIVIDE', 2 * math.pi, T.m('DIVIDE', T.gi("Meridians"), T.gi("Major Every")))
    k = T.m('DIVIDE', ang, step)
    frac = T.m('ABSOLUTE', T.m('SUBTRACT', k, T.m('ROUND', k)))
    near_axis = T.m('LESS_THAN', T.v('LENGTH', T.xyz(p[0], p[1], 0.0)), 0.3)   # apex: any
    return T.m('MAXIMUM', T.m('LESS_THAN', frac, 0.02), near_axis)


bar = T.gi("Bar Size")
members = []
# wing arches
members.append(girder(curves(tagged("rib")), T.gi("Rib Depth")))
# purlins and rings
members.append(sweep(curves(tagged("purlin")), bar, bar))
members.append(sweep(curves(tagged("ring")), bar, T.m('MULTIPLY', bar, 1.4)))
# drum and dome meridians: majors as girders, the rest as bars
mer = curves(tagged("meridian"))
sep = T.node('GeometryNodeSeparateGeometry', {'Geometry': mer, 'Selection': is_major_meridian()},
             domain='CURVE')
members.append(girder(sep.outputs['Selection'], T.gi("Dome Rib Depth")))
members.append(sweep(sep.outputs['Inverted'], bar, T.m('MULTIPLY', bar, 1.4)))
# seams where the wings meet the drum: box girder
members.append(sweep(curves(tagged("seam")), T.m('MULTIPLY', bar, 5.0), T.m('MULTIPLY', bar, 5.0)))
# gable and porch walls: mullions and transoms, a little heavier than glazing bars
members.append(sweep(curves(tagged("mullion"), smooth=False), T.m('MULTIPLY', bar, 1.6), T.m('MULTIPLY', bar, 1.6)))
members.append(sweep(curves(tagged("transom"), smooth=False), T.m('MULTIPLY', bar, 1.6), T.m('MULTIPLY', bar, 1.6)))


def lowered(c, dz):
    return T.node('GeometryNodeSetPosition', {'Geometry': c, 'Offset': T.xyz(0.0, 0.0, dz)}).outputs[0]


# brick plinth under every sill, with a stone coping on top
sills = curves(tagged("sill"), length=0.5)
ph = T.gi("Plinth Height")
plinth = sweep(lowered(sills, T.m('MULTIPLY', ph, -0.5)), T.gi("Plinth Width"), ph)
plinth = T.node('GeometryNodeSetMaterial', {'Geometry': plinth, 'Material': T.gi("Brick")}).outputs[0]
coping = sweep(lowered(sills, 0.03), T.m('ADD', T.gi("Plinth Width"), 0.1), 0.06)
coping = T.node('GeometryNodeSetMaterial', {'Geometry': coping, 'Material': T.gi("Coping")}).outputs[0]

iron = T.join(*members)
iron = T.node('GeometryNodeSetShadeSmooth', {'Mesh': iron, 'Shade Smooth': False}).outputs[0]
iron = T.node('GeometryNodeSetMaterial', {'Geometry': iron, 'Material': T.gi("Iron")}).outputs[0]
# --- Art Nouveau ornament: prototypes from palm_house_ornament.py -------------------------
def proto(name):
    n = T.node('GeometryNodeObjectInfo', {'As Instance': True}, transform_space='ORIGINAL')
    n.inputs['Object'].default_value = bpy.data.objects[name]
    return n.outputs['Geometry']


def facing(vec):
    """Rotation turning the prototype's X axis toward vec, about Z."""
    return T.node('FunctionNodeAlignRotationToVector', {'Vector': vec},
                  axis='X', pivot_axis='Z').outputs[0]


# cresting along the ridges and the drum cornice
ctp = T.node('GeometryNodeCurveToPoints', {'Curve': curves(tagged("ridge"), length=0.1),
                                          'Length': T.m('MULTIPLY', T.gi("Cresting Scale"), 0.45)},
               mode='LENGTH')                               # the motif is 0.45 m wide at scale 1
cresting = T.node('GeometryNodeInstanceOnPoints', {'Points': ctp.outputs['Points'],
                                                   'Instance': proto("Proto_Cresting"),
                                                   'Rotation': facing(ctp.outputs['Tangent']),
                                                   'Scale': T.gi("Cresting Scale")}).outputs[0]

orn = T.node('GeometryNodeInputNamedAttribute', {'Name': "orn"}, data_type='INT').outputs['Attribute']


def orn_points(kind):
    sel = T.node('FunctionNodeCompare', {'A': orn, 'B': float(kind)}, data_type='FLOAT',
                 operation='EQUAL').outputs[0]
    return T.node('GeometryNodeMeshToPoints', {'Mesh': surface, 'Selection': sel}).outputs[0]


orn_dir = T.node('GeometryNodeInputNamedAttribute', {'Name': "orn_dir"},
                 data_type='FLOAT_VECTOR').outputs['Attribute']
finials = T.node('GeometryNodeInstanceOnPoints', {'Points': orn_points(1),
                                                  'Instance': proto("Proto_Finial"),
                                                  'Scale': T.gi("Finial Scale")}).outputs[0]
lantern = T.node('GeometryNodeInstanceOnPoints', {'Points': orn_points(2),
                                                  'Instance': proto("Proto_Lantern"),
                                                  'Scale': T.gi("Lantern Scale")}).outputs[0]
consoles = T.node('GeometryNodeInstanceOnPoints', {'Points': orn_points(3),
                                                   'Instance': proto("Proto_Console"),
                                                   'Rotation': facing(orn_dir)}).outputs[0]
ornament = T.join(cresting, finials, lantern, consoles)

part = T.node('GeometryNodeInputNamedAttribute', {'Name': "part"}, data_type='INT').outputs['Attribute']
is_door = T.node('FunctionNodeCompare', {'A': part, 'B': 3.0}, data_type='FLOAT', operation='EQUAL').outputs[0]
panes = T.node('GeometryNodeSetMaterial', {'Geometry': surface, 'Material': T.gi("Glass")}).outputs[0]
panes = T.node('GeometryNodeSetMaterial', {'Geometry': panes, 'Selection': is_door,
                                           'Material': T.gi("Door")}).outputs[0]
T.set_output("Geometry", T.join(panes, iron, plinth, coping, ornament))


# --- materials ----------------------------------------------------------------------
def white_iron():
    mat = bpy.data.materials.get("M_Iron_White") or bpy.data.materials.new("M_Iron_White")
    mat.use_nodes = True
    b = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (0.72, 0.71, 0.66, 1.0)   # linear; a warm off-white
    b.inputs['Roughness'].default_value = 0.38
    b.inputs['Coat Weight'].default_value = 0.15
    return mat


def thin_glass():
    """Single-sided panes: reflection by Fresnel, the rest passes straight through.

    A refractive glass BSDF on one-sided faces would bend light with no exit
    surface; real panes are thin, so treat them as a tinted transparent sheet.
    """
    mat = bpy.data.materials.get("M_Glass_Thin") or bpy.data.materials.new("M_Glass_Thin")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    S = Tree.wrap(nt)
    out = S.node('ShaderNodeOutputMaterial')
    fres = S.node('ShaderNodeFresnel', {'IOR': 1.52}).outputs[0]
    clear = S.node('ShaderNodeBsdfTransparent', {'Color': (0.86, 0.92, 0.88, 1.0)}).outputs[0]
    gloss = S.node('ShaderNodeBsdfGlossy', {'Roughness': 0.02}).outputs[0]
    mix = S.node('ShaderNodeMixShader', {'Fac': fres})
    S.link(clear, mix.inputs[1])
    S.link(gloss, mix.inputs[2])
    S.link(mix.outputs[0], out.inputs['Surface'])
    return mat


def brick():
    """Red brick in stretcher bond with pale mortar (object coordinates)."""
    mat = bpy.data.materials.get("M_Brick_Red") or bpy.data.materials.new("M_Brick_Red")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    S = Tree.wrap(nt)
    out = S.node('ShaderNodeOutputMaterial')
    co = S.node('ShaderNodeTexCoord').outputs['Object']
    # bricks are 0.23 x 0.075 m: lay them along whichever horizontal axis the wall follows
    sep = S.sep(co)
    along = S.m('ADD', sep[0], sep[1])
    vec = S.xyz(along, sep[2], 0.0)
    var = S.node('ShaderNodeTexNoise', {'Vector': co, 'Scale': 8.0, 'Detail': 2.0}).outputs[0]
    b = S.node('ShaderNodeTexBrick', {'Vector': vec, 'Scale': 1.0, 'Brick Width': 0.23,
                                      'Row Height': 0.075, 'Mortar Size': 0.008,
                                      'Mortar': (0.30, 0.28, 0.24, 1.0),
                                      'Color1': (0.20, 0.055, 0.03, 1.0),
                                      'Color2': (0.14, 0.04, 0.025, 1.0)})
    bsdf = S.node('ShaderNodeBsdfPrincipled', {'Base Color': b.outputs['Color'], 'Roughness': 0.85})
    bump = S.node('ShaderNodeBump', {'Height': b.outputs['Fac'], 'Strength': 0.4, 'Distance': 0.01})
    S.link(bump.outputs[0], bsdf.inputs['Normal'])
    S.link(bsdf.outputs[0], out.inputs['Surface'])
    return mat


def door_green():
    mat = bpy.data.materials.get("M_Door_Green") or bpy.data.materials.new("M_Door_Green")
    mat.use_nodes = True
    b = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (0.012, 0.045, 0.025, 1.0)   # deep Brunswick green
    b.inputs['Roughness'].default_value = 0.5
    b.inputs['Coat Weight'].default_value = 0.08   # more coat mirrors the sky and greys the green
    return mat


obj = bpy.data.objects["Palm_House"]
mod = obj.modifiers.get("Palm_House_Iron") or obj.modifiers.new("Palm_House_Iron", 'NODES')
mod.node_group = T.ng
reset_modifier_inputs(mod)
ins = mod.properties.inputs
for item in mod.node_group.interface.items_tree:
    if item.item_type == 'SOCKET' and item.in_out == 'INPUT':
        if item.name == "Iron":
            getattr(ins, item.identifier).value = white_iron()
        elif item.name == "Glass":
            getattr(ins, item.identifier).value = thin_glass()
        elif item.name == "Brick":
            getattr(ins, item.identifier).value = brick()
        elif item.name == "Coping":
            getattr(ins, item.identifier).value = bpy.data.materials["M_Limestone"]
        elif item.name == "Door":
            getattr(ins, item.identifier).value = door_green()
obj.update_tag()
