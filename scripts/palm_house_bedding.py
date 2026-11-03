"""Carpet bedding in the palm house flower beds, as Geometry Nodes instances.

Victorian scheme, read from the bed field of palm_house_site.py's mask:
- a band EDGE_W wide along every bed edge: white alyssum
- inside: red zonal geraniums
- round bed only: a disc of yellow calceolaria round a fan palm in a tub
  (the fan palm prototype from palm_house_planting.py)

The plants are small procedural clumps built in the node tree; at the camera
distance they are a few pixels across, so only the mound of leaves and the
spots of flower colour matter.

Run inside Blender after palm_house_site.py and environment.py:
    exec(open(bpy.path.abspath('//scripts/palm_house_bedding.py')).read())
"""
import bpy

ENV = {}
exec(open(bpy.path.abspath('//scripts/environment.py')).read().split(
    "\nground, gmod = ensure_object(")[0], ENV)       # definitions only
exec(open(bpy.path.abspath('//scripts/gn_helpers.py')).read())
SITE = ENV['SITE']
site_fields = ENV['site_fields']

EDGE_W = 0.35           # alyssum band
CENTRE_R = 1.4          # calceolaria disc in the round bed
SPACING = 0.20          # minimum distance between plants
# rectangle holding every bed (world XY), for the planting grid
BEDS_MIN, BEDS_MAX = (-124.0, -121.0), (-96.0, -94.0)


def rnd(T, lo, hi, seed, kind='FLOAT'):
    n = T.node('FunctionNodeRandomValue', data_type=kind)
    T.feed(sock(n.inputs, 'Min'), lo)
    T.feed(sock(n.inputs, 'Max'), hi)
    T.feed(sock(n.inputs, 'Seed'), seed)
    return sock(n.outputs, 'Value')


def rot(T, x, y, z):
    return T.node('FunctionNodeEulerToRotation', {'Euler': T.xyz(x, y, z)}).outputs[0]


def mound(T, count, radius, height, piece, seed, tilt=0.6, scale=(0.7, 1.3)):
    """`count` copies of `piece` scattered over a low dome, realized."""
    pts = T.node('GeometryNodePoints', {'Count': count}).outputs[0]
    a = rnd(T, 0.0, 6.283, seed)
    r = T.m('SQRT', rnd(T, 0.0, 1.0, seed + 1))
    z = T.m('MULTIPLY', T.m('SUBTRACT', 1.0, T.m('MULTIPLY', r, r)), height)
    pos = T.xyz(T.m('MULTIPLY', T.m('COSINE', a), T.m('MULTIPLY', r, radius)),
                T.m('MULTIPLY', T.m('SINE', a), T.m('MULTIPLY', r, radius)), z)
    pts = T.node('GeometryNodeSetPosition', {'Geometry': pts, 'Position': pos}).outputs[0]
    s = rnd(T, scale[0], scale[1], seed + 2)
    geo = T.node('GeometryNodeInstanceOnPoints', {
        'Points': pts, 'Instance': piece,
        'Rotation': rot(T, rnd(T, -tilt, tilt, seed + 3), rnd(T, -tilt, tilt, seed + 4),
                        rnd(T, 0.0, 6.283, seed + 5)),
        'Scale': T.xyz(s, s, s)}).outputs[0]
    return T.node('GeometryNodeRealizeInstances', {'Geometry': geo}).outputs[0]


def with_mat(T, geo, name):
    return T.node('GeometryNodeSetMaterial', {'Geometry': geo, 'Material': T.gi(name)}).outputs[0]


def leaf_disc(T, r):
    return T.node('GeometryNodeMeshCircle', {'Vertices': 8, 'Radius': r},
                  fill_type='TRIANGLE_FAN').outputs['Mesh']


def blob(T, r):
    return T.node('GeometryNodeMeshIcoSphere', {'Radius': r, 'Subdivisions': 1}).outputs['Mesh']


def geranium(T):
    """Mound of round leaves, about 0.3 m, with red flower heads above."""
    leaves = with_mat(T, mound(T, 32, 0.17, 0.16, leaf_disc(T, 0.05), 101), "Leaf")
    heads = mound(T, 9, 0.14, 0.08, blob(T, 0.038), 111, tilt=0.2)
    heads = T.node('GeometryNodeTransform', {'Geometry': heads, 'Translation': (0.0, 0.0, 0.19)}).outputs[0]
    return T.join(leaves, with_mat(T, heads, "Geranium"))


def alyssum(T):
    """Low white cushion, about 0.12 m."""
    cushion = with_mat(T, mound(T, 16, 0.14, 0.05, leaf_disc(T, 0.04), 201), "Leaf")
    flowers = mound(T, 36, 0.15, 0.07, blob(T, 0.026), 211, tilt=0.1)
    flowers = T.node('GeometryNodeTransform', {'Geometry': flowers, 'Translation': (0.0, 0.0, 0.03)}).outputs[0]
    return T.join(cushion, with_mat(T, flowers, "Alyssum"))


def calceolaria(T):
    """Bushy, about 0.35 m, covered in small yellow pouches."""
    leaves = with_mat(T, mound(T, 26, 0.16, 0.2, leaf_disc(T, 0.045), 301), "Leaf")
    flowers = mound(T, 28, 0.16, 0.12, blob(T, 0.024), 311, tilt=0.1)
    flowers = T.node('GeometryNodeTransform', {'Geometry': flowers, 'Translation': (0.0, 0.0, 0.17)}).outputs[0]
    return T.join(leaves, with_mat(T, flowers, "Calceolaria"))


def build_bedding_tree():
    T = Tree("GN_Palm_House_Bedding")
    T.input("Spacing", 'NodeSocketFloat', SPACING, 0.05)
    T.input("Palm", 'NodeSocketObject')
    T.input("Palm Height", 'NodeSocketFloat', 3.2, 0.1)
    for m in ("Leaf", "Geranium", "Alyssum", "Calceolaria", "Tub"):
        T.input(m, 'NodeSocketMaterial')
    T.output("Geometry")

    kinds = T.instances([geranium(T), alyssum(T), calceolaria(T)])

    size = (BEDS_MAX[0] - BEDS_MIN[0], BEDS_MAX[1] - BEDS_MIN[1])
    centre = ((BEDS_MAX[0] + BEDS_MIN[0]) / 2, (BEDS_MAX[1] + BEDS_MIN[1]) / 2, 0.0)
    grid = T.node('GeometryNodeMeshGrid', {'Size X': size[0], 'Size Y': size[1],
                                           'Vertices X': 2, 'Vertices Y': 2}).outputs['Mesh']
    grid = T.node('GeometryNodeTransform', {'Geometry': grid, 'Translation': centre}).outputs[0]
    pts = T.node('GeometryNodeDistributePointsOnFaces', {
        'Mesh': grid, 'Distance Min': T.gi("Spacing"),
        'Density Max': T.m('DIVIDE', 1.6, T.m('MULTIPLY', T.gi("Spacing"), T.gi("Spacing"))),
        'Seed': 5}, distribute_method='POISSON').outputs['Points']

    pos = T.node('GeometryNodeInputPosition').outputs[0]
    bed = site_fields(T, pos)[1]
    pts = T.node('GeometryNodeDeleteGeometry', {'Geometry': pts,
                                                'Selection': T.m('LESS_THAN', bed, 0.06)},
                 domain='POINT').outputs[0]
    # 0 geranium, 1 alyssum on the edge band, 2 calceolaria in the round bed's centre
    p = T.sep(pos)
    dc = T.v('LENGTH', T.xyz(T.m('SUBTRACT', p[0], SITE['BED_C'][0]),
                             T.m('SUBTRACT', p[1], SITE['BED_C'][1]), 0.0))
    edge = T.m('LESS_THAN', bed, EDGE_W)
    centre_disc = T.m('LESS_THAN', dc, CENTRE_R)
    kind = T.m('MAXIMUM', edge, T.m('MULTIPLY', centre_disc, 2.0))
    # clear the palm's tub
    pts = T.node('GeometryNodeDeleteGeometry', {'Geometry': pts,
                                                'Selection': T.m('LESS_THAN', dc, 0.55)},
                 domain='POINT').outputs[0]
    s = rnd(T, 0.85, 1.15, 13)
    plants = T.node('GeometryNodeInstanceOnPoints', {
        'Points': pts, 'Instance': kinds, 'Pick Instance': True, 'Instance Index': kind,
        'Rotation': rot(T, 0.0, 0.0, rnd(T, 0.0, 6.283, 14)),
        'Scale': T.xyz(s, s, s)}).outputs[0]

    # fan palm in a tub at the centre of the round bed
    tub = T.node('GeometryNodeMeshCylinder', {'Vertices': 24, 'Radius': 0.42, 'Depth': 0.5}).outputs['Mesh']
    tub = T.node('GeometryNodeTransform', {'Geometry': tub,
                                           'Translation': (*SITE['BED_C'], 0.25)}).outputs[0]
    tub = with_mat(T, tub, "Tub")
    palm = T.node('GeometryNodeObjectInfo', {'Object': T.gi("Palm"), 'As Instance': True},
                  transform_space='ORIGINAL').outputs['Geometry']
    ps = T.m('DIVIDE', T.gi("Palm Height"), 4.0)      # prototype is about 4 m tall
    palm = T.node('GeometryNodeTransform', {'Geometry': palm, 'Translation': (*SITE['BED_C'], 0.45),
                                            'Rotation': (0.0, 0.0, 0.6),
                                            'Scale': T.xyz(ps, ps, ps)}).outputs[0]
    T.set_output("Geometry", T.join(plants, tub, palm))
    return T.ng


def material(name, color, rough=0.6):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    b = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = rough
    return mat


obj, mod = ENV['ensure_object']("Palm_House_Bedding", "Palm_House", build_bedding_tree(), "Bedding")
set_in = ENV['set_input']
set_in(mod, "Palm", bpy.data.objects["Proto_Plant_FanPalm"])
set_in(mod, "Leaf", material("M_Bedding_Leaf", (0.025, 0.060, 0.014), 0.55))
set_in(mod, "Geranium", material("M_Geranium_Flower", (0.62, 0.012, 0.010), 0.5))
set_in(mod, "Alyssum", material("M_Alyssum_Flower", (0.72, 0.72, 0.66), 0.7))
set_in(mod, "Calceolaria", material("M_Calceolaria_Flower", (0.80, 0.42, 0.01), 0.5))
set_in(mod, "Tub", material("M_Tub_Painted", (0.02, 0.06, 0.035), 0.45))
