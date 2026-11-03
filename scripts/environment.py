"""Setting for the park: rolling ground, gravel paths, lawn, flower beds, trees.

The gravel mask (a ring round the tower footing plus a straight path, and the
palm house grounds read from palm_house_site.py's mask image) is written once
as node math and built twice: in the ground material, and in the grass
scatter so no grass grows on the gravel or in the flower beds.

Run palm_house_site.py first: it writes the mask image this script samples.

Run inside Blender:
    exec(open(bpy.path.abspath('//scripts/environment.py')).read())
"""
import bpy
import math

exec(open(bpy.path.abspath('//scripts/gn_helpers.py')).read())

# layout, in metres and radians, shared by shader and geometry nodes
RING_R = 7.4          # gravel ring centre radius (footing outer edge is 6.1)
RING_HW = 1.2         # half width of the ring
PATH_ANGLE = -math.pi / 2   # path runs from the tower toward -Y
PATH_HW = 1.2         # half width of the path
FLAT_R = 30.0         # ground is flat within this radius of the tower
# further flat building sites (x, y, radius); keep in step with the structure scripts
FLAT_SITES = [(-110.0, -130.0, 45.0)]   # palm house (scripts/palm_house.py SITE)

# palm house grounds: layout constants and mask image from palm_house_site.py
SITE = {}
exec(open(bpy.path.abspath('//scripts/palm_house_site.py')).read().split(
    "\ngravel, beds, BED_INFO = build_fields()")[0], SITE)
SITE_EDGE_NOISE = 0.25     # formal garden: much crisper lawn edges than round the tower
# the site path's last stretch, east to the tower path, outside the mask image
SITE_PATH_LINK = (SITE['PATH_END'], (0.0, SITE['PATH_END'][1]))


def site_mask_image():
    img = bpy.data.images.get(SITE['MASK_IMAGE'])
    if img is None:
        img = bpy.data.images.load(bpy.path.abspath(SITE['MASK_FILE']))
        img.name = SITE['MASK_IMAGE']
    img.colorspace_settings.is_data = True
    return img


def site_fields(T, pos):
    """Signed distances (m, positive inside) to the site's gravel and beds."""
    p = T.sep(pos)
    uv = T.xyz(T.m('DIVIDE', T.m('SUBTRACT', p[0], SITE['X0']), SITE['X1'] - SITE['X0']),
               T.m('DIVIDE', T.m('SUBTRACT', p[1], SITE['Y0']), SITE['Y1'] - SITE['Y0']), 0.0)
    if T.ng.bl_idname == 'GeometryNodeTree':
        tex = T.node('GeometryNodeImageTexture', {'Image': site_mask_image(), 'Vector': uv},
                     interpolation='Linear', extension='CLIP')
    else:
        tex = T.node('ShaderNodeTexImage', {'Vector': uv}, image=site_mask_image(),
                     interpolation='Linear', extension='CLIP')
    c = T.sep(tex.outputs['Color'])
    return T.m('SUBTRACT', c[0], SITE['SD_OFFSET']), T.m('SUBTRACT', c[1], SITE['SD_OFFSET'])


def capsule_distance(T, pos, a, b):
    """Distance in XY from pos to the segment a-b."""
    p = T.sep(pos)
    ab = (b[0] - a[0], b[1] - a[1])
    px, py = T.m('SUBTRACT', p[0], a[0]), T.m('SUBTRACT', p[1], a[1])
    t = T.m('DIVIDE', T.m('ADD', T.m('MULTIPLY', px, ab[0]), T.m('MULTIPLY', py, ab[1])),
            ab[0] ** 2 + ab[1] ** 2)
    t = T.node('ShaderNodeClamp', {'Value': t}).outputs[0]
    return T.v('LENGTH', T.xyz(T.m('SUBTRACT', px, T.m('MULTIPLY', t, ab[0])),
                               T.m('SUBTRACT', py, T.m('MULTIPLY', t, ab[1])), 0.0))


def bed_mask(T, pos):
    """1 in the palm house flower beds, 0 elsewhere."""
    return T.m('GREATER_THAN', site_fields(T, pos)[1], 0.0)


def gravel_mask(T, pos, edge_noise=0.7):
    """1 on gravel, 0 on lawn, with a ragged edge. pos: position socket."""
    p = T.sep(pos)
    n = T.node('ShaderNodeTexNoise', {'Vector': pos, 'Scale': 1.5, 'Detail': 3.0})
    wobble = T.m('MULTIPLY', T.m('SUBTRACT', n.outputs[0], 0.5), edge_noise)
    d = T.v('LENGTH', T.xyz(p[0], p[1], 0.0))
    ring = T.m('LESS_THAN', T.m('ADD', T.m('ABSOLUTE', T.m('SUBTRACT', d, RING_R)), wobble), RING_HW)
    c, s = math.cos(PATH_ANGLE), math.sin(PATH_ANGLE)
    along = T.m('ADD', T.m('MULTIPLY', p[0], c), T.m('MULTIPLY', p[1], s))
    across = T.m('ABSOLUTE', T.m('ADD', T.m('MULTIPLY', p[0], -s), T.m('MULTIPLY', p[1], c)))
    path = T.m('MULTIPLY', T.m('GREATER_THAN', along, RING_R),
               T.m('LESS_THAN', T.m('ADD', across, wobble), PATH_HW))
    link = T.m('LESS_THAN', T.m('ADD', capsule_distance(T, pos, *SITE_PATH_LINK), wobble),
               SITE['PATH_HW'])
    site_wobble = T.m('MULTIPLY', T.m('SUBTRACT', n.outputs[0], 0.5), SITE_EDGE_NOISE)
    site = T.m('GREATER_THAN', T.m('ADD', site_fields(T, pos)[0], site_wobble), 0.0)
    return T.m('MAXIMUM', T.m('MAXIMUM', ring, path), T.m('MAXIMUM', link, site))


# --- ground geometry ------------------------------------------------------------
def build_ground_tree():
    T = Tree("GN_Ground")
    T.input("Size", 'NodeSocketFloat', 800.0, 10.0)
    T.input("Vertices", 'NodeSocketInt', 401, 2, 4000)
    T.input("Hill Height", 'NodeSocketFloat', 2.5, 0.0)
    T.input("Hill Scale", 'NodeSocketFloat', 0.006, 0.0)
    T.input("Ground", 'NodeSocketMaterial')
    T.output("Geometry")
    grid = T.node('GeometryNodeMeshGrid', {'Size X': T.gi("Size"), 'Size Y': T.gi("Size"),
                                           'Vertices X': T.gi("Vertices"),
                                           'Vertices Y': T.gi("Vertices")})
    pos = T.node('GeometryNodeInputPosition').outputs[0]
    p = T.sep(pos)
    d = T.v('LENGTH', T.xyz(p[0], p[1], 0.0))
    hills = T.node('ShaderNodeTexNoise', {'Vector': pos, 'Scale': T.gi("Hill Scale"),
                                          'Detail': 3.0, 'Roughness': 0.45})
    rise = T.node('ShaderNodeMapRange', {'Value': d, 'From Min': FLAT_R,
                                         'From Max': FLAT_R + 80.0},
                  interpolation_type='SMOOTHSTEP').outputs[0]
    for sx, sy, sr in FLAT_SITES:
        ds = T.v('LENGTH', T.xyz(T.m('SUBTRACT', p[0], sx), T.m('SUBTRACT', p[1], sy), 0.0))
        rs = T.node('ShaderNodeMapRange', {'Value': ds, 'From Min': sr, 'From Max': sr + 60.0},
                    interpolation_type='SMOOTHSTEP').outputs[0]
        rise = T.m('MINIMUM', rise, rs)
    z = T.m('MULTIPLY', T.m('MULTIPLY', T.m('SUBTRACT', hills.outputs[0], 0.5),
                                   T.m('MULTIPLY', T.gi("Hill Height"), 2.0)), rise)
    sp = T.node('GeometryNodeSetPosition', {'Geometry': grid.outputs['Mesh'],
                                            'Offset': T.xyz(0.0, 0.0, z)})
    sm = T.node('GeometryNodeSetShadeSmooth', {'Mesh': sp.outputs[0], 'Shade Smooth': True})
    mat = T.node('GeometryNodeSetMaterial', {'Geometry': sm.outputs[0],
                                             'Material': T.gi("Ground")})
    T.set_output("Geometry", mat.outputs[0])
    return T.ng


# --- ground material --------------------------------------------------------------
def build_ground_material():
    name = "M_Ground_Lawn_Gravel"
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    S = Tree.wrap(nt)
    out = S.node('ShaderNodeOutputMaterial')
    pos = S.node('ShaderNodeTexCoord').outputs['Object']

    # lawn: patchy green, faint yellowing, fine blade bump
    patches = S.node('ShaderNodeTexNoise', {'Vector': pos, 'Scale': 0.08, 'Detail': 4.0}).outputs[0]
    fine = S.node('ShaderNodeTexNoise', {'Vector': pos, 'Scale': 3.0, 'Detail': 6.0}).outputs[0]
    lawn_ramp = S.node('ShaderNodeValToRGB')
    els = lawn_ramp.color_ramp.elements
    els[0].position, els[0].color = 0.35, (0.030, 0.055, 0.012, 1)
    els[1].position, els[1].color = 0.70, (0.070, 0.090, 0.022, 1)
    S.link(S.m('ADD', S.m('MULTIPLY', patches, 0.7), S.m('MULTIPLY', fine, 0.3)),
           lawn_ramp.inputs['Fac'])
    blades = S.node('ShaderNodeTexNoise', {'Vector': pos, 'Scale': 220.0, 'Detail': 2.0}).outputs[0]
    lawn_bump = S.node('ShaderNodeBump', {'Strength': 0.5, 'Distance': 0.01, 'Height': blades})
    lawn = S.node('ShaderNodeBsdfPrincipled', {'Base Color': lawn_ramp.outputs['Color'],
                                              'Roughness': 0.9,
                                              'Normal': lawn_bump.outputs[0]})

    # gravel: small pale stones
    vor = S.node('ShaderNodeTexVoronoi', {'Vector': pos, 'Scale': 30.0})
    stone_ramp = S.node('ShaderNodeValToRGB')
    els = stone_ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.07, 0.06, 0.048, 1)
    els[1].position, els[1].color = 1.0, (0.22, 0.19, 0.15, 1)
    S.link(vor.outputs['Color'], stone_ramp.inputs['Fac'])
    pebble = S.m('POWER', S.m('SUBTRACT', 1.0, vor.outputs['Distance']), 3.0)
    gravel_bump = S.node('ShaderNodeBump', {'Strength': 0.8, 'Distance': 0.02, 'Height': pebble})
    gravel = S.node('ShaderNodeBsdfPrincipled', {'Base Color': stone_ramp.outputs['Color'],
                                                'Roughness': 0.8,
                                                'Normal': gravel_bump.outputs[0]})

    # bed soil: dark, lumpy, freshly raked
    clods = S.node('ShaderNodeTexNoise', {'Vector': pos, 'Scale': 40.0, 'Detail': 4.0}).outputs[0]
    soil_bump = S.node('ShaderNodeBump', {'Strength': 0.6, 'Distance': 0.02, 'Height': clods})
    soil = S.node('ShaderNodeBsdfPrincipled', {'Base Color': (0.035, 0.022, 0.014, 1.0),
                                              'Roughness': 0.95,
                                              'Normal': soil_bump.outputs[0]})

    mix = S.node('ShaderNodeMixShader', {'Fac': gravel_mask(S, pos)})
    S.link(lawn.outputs[0], mix.inputs[1])
    S.link(gravel.outputs[0], mix.inputs[2])
    bed = S.node('ShaderNodeMixShader', {'Fac': bed_mask(S, pos)})
    S.link(mix.outputs[0], bed.inputs[1])
    S.link(soil.outputs[0], bed.inputs[2])
    S.link(bed.outputs[0], out.inputs['Surface'])
    return mat


def ensure_object(name, collection, group, modname):
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, bpy.data.meshes.new(name + "_Mesh"))
        bpy.data.collections[collection].objects.link(obj)
    mod = obj.modifiers.get(modname) or obj.modifiers.new(modname, 'NODES')
    mod.node_group = group
    reset_modifier_inputs(mod)
    return obj, mod


def set_input(mod, name, value):
    for item in mod.node_group.interface.items_tree:
        if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.name == name:
            getattr(mod.properties.inputs, item.identifier).value = value
    mod.id_data.update_tag()


ground, gmod = ensure_object("Ground", "Environment", build_ground_tree(), "Ground_Terrain")
set_input(gmod, "Ground", build_ground_material())


# --- shared bits for scatter trees ------------------------------------------------
def rand(T, lo, hi, seed, kind='FLOAT', ident=None):
    n = T.node('FunctionNodeRandomValue', data_type=kind)
    T.feed(sock(n.inputs, 'Min'), lo)
    T.feed(sock(n.inputs, 'Max'), hi)
    T.feed(sock(n.inputs, 'Seed'), seed)
    if ident is not None:
        T.feed(sock(n.inputs, 'ID'), ident)
    return sock(n.outputs, 'Value')


def euler(T, x, y, z):
    return T.node('FunctionNodeEulerToRotation', {'Euler': T.xyz(x, y, z)}).outputs[0]


def ground_surface(T):
    info = T.node('GeometryNodeObjectInfo', {'Object': T.gi("Ground Object")},
                  transform_space='RELATIVE')
    return info.outputs['Geometry']


def radial_distance(T):
    p = T.sep(T.node('GeometryNodeInputPosition').outputs[0])
    return T.v('LENGTH', T.xyz(p[0], p[1], 0.0))


def viewport_factor(T, factor):
    """1 for final renders, `factor` in the viewport."""
    is_vp = T.node('GeometryNodeIsViewport').outputs[0]
    sw = T.node('GeometryNodeSwitch', input_type='FLOAT')
    T.link(is_vp, sw.inputs['Switch'])
    T.feed(sw.inputs['False'], 1.0)
    T.feed(sw.inputs['True'], factor)
    return sw.outputs[0]


# --- lawn grass ------------------------------------------------------------------------
def build_grass_tree():
    T = Tree("GN_Lawn_Grass")
    T.input("Ground Object", 'NodeSocketObject')
    T.input("Center", 'NodeSocketVector', (4.0, -38.0, 0.0))
    T.input("Radius", 'NodeSocketFloat', 56.0, 1.0)
    T.input("Clumps per m2", 'NodeSocketFloat', 60.0, 0.0)
    T.input("Viewport Fraction", 'NodeSocketFloat', 0.08, 0.0, 1.0)
    T.input("Blade Height", 'NodeSocketFloat', 0.09, 0.005)
    T.input("Grass", 'NodeSocketMaterial')
    T.output("Geometry")

    # one blade: tapered, bent ribbon 1 m tall (scaled per instance)
    blade = T.node('GeometryNodeCurvePrimitiveLine', {'End': (0.0, 0.0, 1.0)}).outputs[0]
    blade = T.node('GeometryNodeResampleCurve', {'Curve': blade, 'Count': 5}).outputs[0]
    f = T.node('GeometryNodeSplineParameter').outputs['Factor']
    blade = T.node('GeometryNodeSetPosition', {'Geometry': blade, 'Offset': T.xyz(
        T.m('MULTIPLY', T.m('POWER', f, 2.0), 0.35), 0.0, 0.0)}).outputs[0]
    blade = T.node('GeometryNodeSetCurveRadius', {'Curve': blade,
                                                  'Radius': T.m('SUBTRACT', 1.0, T.m('MULTIPLY', f, 0.9))}).outputs[0]
    width = T.node('GeometryNodeCurvePrimitiveLine', {'Start': (-0.04, 0.0, 0.0),
                                                      'End': (0.04, 0.0, 0.0)}).outputs[0]
    blade = T.node('GeometryNodeCurveToMesh', {'Curve': blade, 'Profile Curve': width}).outputs[0]

    # clump: 12 blades with random lean, turn and height
    pts = T.node('GeometryNodePoints', {'Count': 12,
                                        'Position': rand(T, (-0.04, -0.04, 0.0), (0.04, 0.04, 0.0), 1, 'FLOAT_VECTOR')}).outputs[0]
    rot = euler(T, rand(T, -0.35, 0.35, 2), rand(T, -0.35, 0.35, 3), rand(T, 0.0, 6.283, 4))
    h = T.m('MULTIPLY', T.gi("Blade Height"), rand(T, 0.6, 1.4, 5))
    clump = T.node('GeometryNodeInstanceOnPoints', {'Points': pts, 'Instance': blade,
                                                    'Rotation': rot,
                                                    'Scale': T.xyz(h, h, h)}).outputs[0]
    clump = T.node('GeometryNodeRealizeInstances', {'Geometry': clump}).outputs[0]
    clump = T.node('GeometryNodeSetMaterial', {'Geometry': clump, 'Material': T.gi("Grass")}).outputs[0]

    # scatter on the lawn near the tower, never on gravel
    pos = T.node('GeometryNodeInputPosition').outputs[0]
    on_lawn = T.m('LESS_THAN', T.m('MAXIMUM', gravel_mask(T, pos), bed_mask(T, pos)), 0.5)
    # covers both the camera foreground and the tower base; thins out at the edge
    off = T.sep(T.v('SUBTRACT', pos, T.gi("Center")))
    dist = T.v('LENGTH', T.xyz(off[0], off[1], 0.0))
    fade = T.node('ShaderNodeMapRange', {'Value': dist, 'From Min': T.gi("Radius"),
                                         'From Max': T.m('MULTIPLY', T.gi("Radius"), 0.75)},
                  interpolation_type='SMOOTHSTEP').outputs[0]
    dens = T.m('MULTIPLY', T.m('MULTIPLY', T.gi("Clumps per m2"), fade),
               viewport_factor(T, T.gi("Viewport Fraction")))
    pts = T.node('GeometryNodeDistributePointsOnFaces', {'Mesh': ground_surface(T),
                                                         'Density': dens,
                                                         'Seed': 7}).outputs['Points']
    # the mask is tested per point: the ground's 2 m faces are too coarse for it
    pts = T.node('GeometryNodeDeleteGeometry', {'Geometry': pts,
                                                'Selection': T.m('LESS_THAN', on_lawn, 0.5)},
                 domain='POINT').outputs[0]
    s = rand(T, 0.7, 1.3, 8)
    inst = T.node('GeometryNodeInstanceOnPoints', {'Points': pts, 'Instance': clump,
                                                   'Rotation': euler(T, 0.0, 0.0, rand(T, 0.0, 6.283, 9)),
                                                   'Scale': T.xyz(s, s, s)}).outputs[0]
    T.set_output("Geometry", inst)
    return T.ng


def build_grass_material():
    name = "M_Grass_Blades"
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    S = Tree.wrap(nt)
    out = S.node('ShaderNodeOutputMaterial')
    pos = S.node('ShaderNodeNewGeometry').outputs['Position']
    patches = S.node('ShaderNodeTexNoise', {'Vector': pos, 'Scale': 0.08, 'Detail': 4.0}).outputs[0]
    ramp = S.node('ShaderNodeValToRGB')
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.35, (0.035, 0.065, 0.014, 1)
    els[1].position, els[1].color = 0.70, (0.080, 0.100, 0.025, 1)
    S.link(patches, ramp.inputs['Fac'])
    leaf = S.node('ShaderNodeBsdfPrincipled', {'Base Color': ramp.outputs['Color'],
                                              'Roughness': 0.55})
    back = S.node('ShaderNodeBsdfTranslucent', {'Color': ramp.outputs['Color']})
    mix = S.node('ShaderNodeMixShader', {'Fac': 0.3})
    S.link(leaf.outputs[0], mix.inputs[1])
    S.link(back.outputs[0], mix.inputs[2])
    S.link(mix.outputs[0], out.inputs['Surface'])
    return mat


# --- tree belt: lindens, birches, spruces -------------------------------------------
def leaf_cards(T, surface, density, size, seed, mat, push=0.15):
    """Cover a surface with small randomly turned quads standing in for leaves."""
    card = T.node('GeometryNodeMeshGrid', {'Size X': size, 'Size Y': size,
                                           'Vertices X': 2, 'Vertices Y': 2}).outputs['Mesh']
    dist = T.node('GeometryNodeDistributePointsOnFaces', {'Mesh': surface, 'Density': density,
                                                          'Seed': seed})
    pts = dist.outputs['Points']
    nrm = dist.outputs['Normal']
    pts = T.node('GeometryNodeSetPosition', {'Geometry': pts, 'Offset': T.v(
        'SCALE', nrm, scale=rand(T, -push, push, seed + 2))}).outputs[0]
    rot = euler(T, rand(T, 0.0, 6.283, seed + 3), rand(T, 0.0, 6.283, seed + 4),
                rand(T, 0.0, 6.283, seed + 5))
    s = rand(T, 0.7, 1.3, seed + 6)
    geo = T.node('GeometryNodeInstanceOnPoints', {'Points': pts, 'Instance': card,
                                                  'Rotation': rot, 'Scale': T.xyz(s, s, s)}).outputs[0]
    geo = T.node('GeometryNodeRealizeInstances', {'Geometry': geo}).outputs[0]
    return T.node('GeometryNodeSetMaterial', {'Geometry': geo, 'Material': T.gi(mat)}).outputs[0]


def crown(T, count, lo, hi, size, squash, seed, mat, lump_scale=1.2, lump=1.0,
          leaves_per_m2=9.0, leaf=0.35):
    """Lumpy crown: noise-displaced blobs inside a box lo..hi as a dark core,
    covered in leaf cards. (Blobs in an ellipsoid gave rounder crowns, but the
    looser, irregular outline of the box version reads better: render v03.)

    The blobs are stacked one per height band, so each overlaps the one below
    (fully random heights left gaps on the tall birch crowns, and their tops
    floated), and drawn in toward the trunk near the top.
    """
    blob = T.node('GeometryNodeMeshIcoSphere', {'Radius': 1.0, 'Subdivisions': 2}).outputs['Mesh']
    i = T.node('GeometryNodeInputIndex').outputs[0]
    f = T.m('DIVIDE', T.m('ADD', i, rand(T, 0.0, 1.0, seed + 7)), count)    # 0 bottom .. 1 top
    taper = T.m('SUBTRACT', 1.0, T.m('MULTIPLY', T.m('MULTIPLY', f, f), 0.6))
    pos = T.xyz(T.m('MULTIPLY', rand(T, lo[0], hi[0], seed + 8), taper),
                T.m('MULTIPLY', rand(T, lo[1], hi[1], seed + 9), taper),
                T.m('ADD', lo[2], T.m('MULTIPLY', f, hi[2] - lo[2])))
    pts = T.node('GeometryNodePoints', {'Count': count, 'Position': pos}).outputs[0]
    s = rand(T, size[0], size[1], seed + 1)
    geo = T.node('GeometryNodeInstanceOnPoints', {'Points': pts, 'Instance': blob,
                                                  'Scale': T.xyz(s, s, T.m('MULTIPLY', s, squash))}).outputs[0]
    geo = T.node('GeometryNodeRealizeInstances', {'Geometry': geo}).outputs[0]
    pos = T.node('GeometryNodeInputPosition').outputs[0]
    n = T.node('ShaderNodeTexNoise', {'Vector': pos, 'Scale': lump_scale, 'Detail': 6.0,
                                      'Roughness': 0.65}).outputs[0]
    nrm = T.node('GeometryNodeInputNormal').outputs[0]
    core = T.node('GeometryNodeSetPosition', {'Geometry': geo, 'Offset': T.v(
        'SCALE', nrm, scale=T.m('MULTIPLY', T.m('SUBTRACT', n, 0.5), 2.0 * lump))}).outputs[0]
    core = T.node('GeometryNodeSetShadeSmooth', {'Mesh': core, 'Shade Smooth': True}).outputs[0]
    cards = leaf_cards(T, core, leaves_per_m2, leaf, seed + 10, mat)
    core = T.node('GeometryNodeSetMaterial', {'Geometry': core, 'Material': T.gi("Crown Core")}).outputs[0]
    return T.join(core, cards)


def trunk(T, height, r0, r1, mat):
    g = T.node('GeometryNodeMeshCone', {'Vertices': 10, 'Radius Bottom': r0,
                                        'Radius Top': r1, 'Depth': height}).outputs['Mesh']
    return T.node('GeometryNodeSetMaterial', {'Geometry': g, 'Material': T.gi(mat)}).outputs[0]


def linden(T):
    """Broad, rounded crown on a short trunk, about 15 m."""
    return T.join(trunk(T, 6.0, 0.45, 0.2, "Bark"),
                  crown(T, 26, (-3.8, -3.8, 4.0), (3.8, 3.8, 12.0), (1.4, 2.4), 0.85, 21, "Foliage"))


def birch(T):
    """Tall, airy crown on a white trunk, about 18 m."""
    return T.join(trunk(T, 14.0, 0.22, 0.08, "Birch Bark"),
                  crown(T, 18, (-2.2, -2.2, 5.0), (2.2, 2.2, 17.0), (0.9, 1.6), 1.4, 31,
                        "Birch Foliage", lump_scale=2.0, lump=0.6, leaves_per_m2=7.0, leaf=0.3))


def spruce(T):
    """Dark narrow cone of overlapping drooping tiers, about 20 m."""
    tiers = 14
    pts = T.node('GeometryNodePoints', {'Count': tiers}).outputs[0]
    i = T.node('GeometryNodeInputIndex').outputs[0]
    f = T.m('DIVIDE', i, tiers - 1)                      # 0 bottom .. 1 top
    pts = T.node('GeometryNodeSetPosition', {'Geometry': pts, 'Position': T.xyz(
        0.0, 0.0, T.m('ADD', 1.8, T.m('MULTIPLY', f, 15.5)))}).outputs[0]
    cone = T.node('GeometryNodeMeshCone', {'Vertices': 16, 'Side Segments': 2,
                                           'Radius Bottom': 1.0, 'Radius Top': 0.15,
                                           'Depth': 2.6}).outputs['Mesh']
    r = T.m('MULTIPLY', T.m('SUBTRACT', 1.0, T.m('MULTIPLY', f, 0.88)), 3.0)
    turn = euler(T, rand(T, -0.08, 0.08, 41), rand(T, -0.08, 0.08, 42), rand(T, 0.0, 6.283, 43))
    geo = T.node('GeometryNodeInstanceOnPoints', {'Points': pts, 'Instance': cone,
                                                  'Rotation': turn,
                                                  'Scale': T.xyz(r, r, 1.0)}).outputs[0]
    geo = T.node('GeometryNodeRealizeInstances', {'Geometry': geo}).outputs[0]
    pos = T.node('GeometryNodeInputPosition').outputs[0]
    n = T.node('ShaderNodeTexNoise', {'Vector': pos, 'Scale': 1.5, 'Detail': 5.0}).outputs[0]
    p = T.sep(pos)
    core = T.node('GeometryNodeSetPosition', {'Geometry': geo, 'Offset': T.v(
        'SCALE', T.xyz(p[0], p[1], 0.0), scale=T.m('MULTIPLY', T.m('SUBTRACT', n, 0.5), 0.7))}).outputs[0]
    core = T.node('GeometryNodeSetShadeSmooth', {'Mesh': core, 'Shade Smooth': True}).outputs[0]
    needles = leaf_cards(T, core, 7.0, 0.3, 51, "Spruce", push=0.12)
    core = T.node('GeometryNodeSetMaterial', {'Geometry': core, 'Material': T.gi("Crown Core")}).outputs[0]
    return T.join(trunk(T, 3.0, 0.35, 0.25, "Bark"), core, needles)


def build_trees_tree():
    T = Tree("GN_Tree_Belt")
    T.input("Ground Object", 'NodeSocketObject')
    T.input("Inner Radius", 'NodeSocketFloat', 85.0, 0.0)
    T.input("Outer Radius", 'NodeSocketFloat', 320.0, 0.0)
    T.input("Center", 'NodeSocketVector', (0.0, 0.0, 0.0))
    # no trees where dot(position - Center, Open Direction) > Open Offset
    T.input("Open Direction", 'NodeSocketVector', (0.0, -1.0, 0.0))
    T.input("Open Offset", 'NodeSocketFloat', 25.0)
    T.input("Grove Trees per ha", 'NodeSocketFloat', 160.0, 0.0)
    T.input("Lone Trees per ha", 'NodeSocketFloat', 4.0, 0.0)
    T.input("Points Object", 'NodeSocketObject')   # optional: a tree at each of its vertices too
    for m in ("Bark", "Foliage", "Birch Bark", "Birch Foliage", "Spruce", "Crown Core"):
        T.input(m, 'NodeSocketMaterial')
    T.output("Geometry")

    # index 0 spruce, 1 birch, 2 linden (the mix of the treeline as approved in render v03)
    kinds = T.instances([spruce(T), birch(T), linden(T)])

    pos = T.node('GeometryNodeInputPosition').outputs[0]
    rel = T.v('SUBTRACT', pos, T.gi("Center"))
    r = T.sep(rel)
    d = T.v('LENGTH', T.xyz(r[0], r[1], 0.0))
    # a ring round the centre, open on the camera side
    ring = T.m('MULTIPLY', T.m('GREATER_THAN', d, T.gi("Inner Radius")),
               T.m('LESS_THAN', d, T.gi("Outer Radius")))
    ahead = T.v('DOT_PRODUCT', rel, T.v('NORMALIZE', T.gi("Open Direction")))
    ring = T.m('MULTIPLY', ring, T.m('LESS_THAN', ahead, T.gi("Open Offset")))
    groves = T.node('ShaderNodeTexNoise', {'Vector': pos, 'Scale': 0.015, 'Detail': 2.0}).outputs[0]
    in_grove = T.m('GREATER_THAN', groves, 0.52)
    # dense groves plus the odd lone tree in the meadow between them
    dens = T.m('DIVIDE', T.m('ADD', T.m('MULTIPLY', in_grove, T.gi("Grove Trees per ha")),
                             T.gi("Lone Trees per ha")), 10000.0)
    pts = T.node('GeometryNodeDistributePointsOnFaces', {'Mesh': ground_surface(T),
                                                         'Density': T.m('MULTIPLY', dens, ring),
                                                         'Seed': 3}).outputs['Points']
    spots = T.node('GeometryNodeObjectInfo', {'Object': T.gi("Points Object")},
                   transform_space='RELATIVE').outputs['Geometry']
    spots = T.node('GeometryNodeMeshToPoints', {'Mesh': spots}).outputs[0]
    pts = T.join(pts, spots)      # placed spots after the scattered ones, so their indices stay
    # 55 % spruces, 30 % birches, 15 % lindens
    r = rand(T, 0.0, 1.0, 15)
    kind = T.m('ADD', T.m('GREATER_THAN', r, 0.55), T.m('GREATER_THAN', r, 0.85))
    s = rand(T, 0.7, 1.3, 13)
    sxy = T.m('MULTIPLY', s, rand(T, 0.85, 1.15, 16))
    sz = T.m('MULTIPLY', s, rand(T, 0.85, 1.25, 17))
    inst = T.node('GeometryNodeInstanceOnPoints', {'Points': pts,
                                                   'Instance': kinds,
                                                   'Pick Instance': True,
                                                   'Instance Index': kind,
                                                   'Rotation': euler(T, 0.0, 0.0, rand(T, 0.0, 6.283, 14)),
                                                   'Scale': T.xyz(sxy, sxy, sz)}).outputs[0]
    T.set_output("Geometry", inst)
    return T.ng


def simple_material(name, color, rough=0.8, translucent=0.0, noise_scale=None, color2=None):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    S = Tree.wrap(nt)
    out = S.node('ShaderNodeOutputMaterial')
    col = (*color, 1.0)
    bsdf = S.node('ShaderNodeBsdfPrincipled', {'Roughness': rough})
    if noise_scale:
        pos = S.node('ShaderNodeNewGeometry').outputs['Position']
        n = S.node('ShaderNodeTexNoise', {'Vector': pos, 'Scale': noise_scale, 'Detail': 5.0}).outputs[0]
        ramp = S.node('ShaderNodeValToRGB')
        els = ramp.color_ramp.elements
        els[0].position, els[0].color = 0.35, col
        els[1].position, els[1].color = 0.70, (*color2, 1.0)
        S.link(n, ramp.inputs['Fac'])
        col = ramp.outputs['Color']
    S.feed(bsdf.inputs['Base Color'], col)
    shader = bsdf.outputs[0]
    if translucent:
        back = S.node('ShaderNodeBsdfTranslucent')
        S.feed(back.inputs['Color'], col)
        mix = S.node('ShaderNodeMixShader', {'Fac': translucent})
        S.link(shader, mix.inputs[1])
        S.link(back.outputs[0], mix.inputs[2])
        shader = mix.outputs[0]
    S.link(shader, out.inputs['Surface'])
    return mat


grass_tree, grass_mat = build_grass_tree(), build_grass_material()
grass, grmod = ensure_object("Lawn_Grass", "Environment", grass_tree, "Grass_Scatter")
set_input(grmod, "Ground Object", ground)
set_input(grmod, "Grass", grass_mat)
# second patch: the palm house foreground, from CAM_PalmHouse to the terrace
ph_grass, phgmod = ensure_object("Lawn_Grass_PalmHouse", "Environment", grass_tree, "Grass_Scatter")
set_input(phgmod, "Ground Object", ground)
set_input(phgmod, "Grass", grass_mat)
set_input(phgmod, "Center", (-99.0, -95.0, 0.0))
set_input(phgmod, "Radius", 36.0)

trees_tree = build_trees_tree()
trees, trmod = ensure_object("Tree_Belt", "Environment", trees_tree, "Tree_Scatter")
set_input(trmod, "Ground Object", ground)
set_input(trmod, "Bark", simple_material("M_Bark", (0.035, 0.028, 0.022), 0.9))
set_input(trmod, "Foliage", simple_material("M_Foliage", (0.018, 0.040, 0.010), 0.7, 0.25,
                                            noise_scale=0.3, color2=(0.045, 0.070, 0.018)))
set_input(trmod, "Birch Bark", simple_material("M_Bark_Birch", (0.03, 0.028, 0.025), 0.7,
                                               noise_scale=6.0, color2=(0.55, 0.53, 0.48)))
set_input(trmod, "Birch Foliage", simple_material("M_Foliage_Birch", (0.045, 0.075, 0.015), 0.7, 0.3,
                                                  noise_scale=0.5, color2=(0.09, 0.12, 0.03)))
set_input(trmod, "Crown Core", simple_material("M_Crown_Core", (0.006, 0.012, 0.004), 0.9))
set_input(trmod, "Spruce", simple_material("M_Foliage_Spruce", (0.008, 0.020, 0.012), 0.8, 0.1,
                                           noise_scale=0.8, color2=(0.018, 0.035, 0.020)))

# grove behind the palm house, open toward CAM_PalmHouse
grove, grvmod = ensure_object("Tree_Grove_PalmHouse", "Environment", trees_tree, "Tree_Scatter")
for k in ("Ground Object", "Bark", "Foliage", "Birch Bark", "Birch Foliage", "Crown Core", "Spruce"):
    set_input(grvmod, k, getattr(trmod.properties.inputs, next(
        i.identifier for i in trees_tree.interface.items_tree
        if i.item_type == 'SOCKET' and i.in_out == 'INPUT' and i.name == k)).value)
set_input(grvmod, "Center", (-110.0, -130.0, 0.0))
set_input(grvmod, "Inner Radius", 42.0)
set_input(grvmod, "Outer Radius", 220.0)
set_input(grvmod, "Open Direction", (0.355, 0.935, 0.0))
set_input(grvmod, "Open Offset", 5.0)

# park overview (CAM_Park): trees framing the left of the view at hand-placed spots,
# and groves closing the horizon from 250 m ahead of the camera to the edge of the ground
PARK_EYE, PARK_AIM = (-210.0, -65.0), -4.0      # keep in step with shots.py "park"
PARK_TREE_SPOTS = [(38.0, 24.0), (31.0, 48.0), (45.0, 62.0)]   # (azimuth deg, distance m) from the eye


def spot_mesh(name, spots):
    """Vertex-only mesh at the given spots, dropped onto the ground."""
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    me.clear_geometry()
    dg = bpy.context.evaluated_depsgraph_get()
    g = ground.evaluated_get(dg)
    co = []
    for az, d in spots:
        x = PARK_EYE[0] + d * math.cos(math.radians(az))
        y = PARK_EYE[1] + d * math.sin(math.radians(az))
        hit, loc, _, _ = g.ray_cast((x, y, 100.0), (0.0, 0.0, -1.0))
        co.append((x, y, loc.z if hit else 0.0))
    me.from_pydata(co, [], [])
    obj = bpy.data.objects.get(name) or bpy.data.objects.new(name, me)
    if obj.name not in bpy.data.collections["Helpers"].objects:
        bpy.data.collections["Helpers"].objects.link(obj)
    obj.hide_render = True
    return obj


park, pkmod = ensure_object("Tree_Park_Framing", "Environment", trees_tree, "Tree_Scatter")
for k in ("Ground Object", "Bark", "Foliage", "Birch Bark", "Birch Foliage", "Crown Core", "Spruce"):
    set_input(pkmod, k, getattr(trmod.properties.inputs, next(
        i.identifier for i in trees_tree.interface.items_tree
        if i.item_type == 'SOCKET' and i.in_out == 'INPUT' and i.name == k)).value)
aim = math.radians(PARK_AIM)
set_input(pkmod, "Center", (*PARK_EYE, 0.0))
set_input(pkmod, "Inner Radius", 0.0)
set_input(pkmod, "Outer Radius", 900.0)
set_input(pkmod, "Open Direction", (-math.cos(aim), -math.sin(aim), 0.0))   # keeps only trees ahead...
set_input(pkmod, "Open Offset", -250.0)                                     # ...beyond 250 m
set_input(pkmod, "Points Object", spot_mesh("Park_Tree_Spots", PARK_TREE_SPOTS))
