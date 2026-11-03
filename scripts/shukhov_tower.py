"""Shukhov hyperboloid tower as a live Geometry Nodes generator.

The lattice is a hyperboloid of one sheet built from its two families of
straight rulings. Ruling i of family s joins the base point at angle
theta_i = 2*pi*i/N (radius Rb, z=0) to the top point at angle theta_i + s*phi
(radius Rt, z=H), with phi = K*pi/N so that the top lands on lattice nodes.

At height parameter t a ruling has turned by psi(t) = arg((1-t)Rb + t Rt e^{i phi}).
Rulings of the two families cross where psi = m*pi/N, i.e. at
    t_m = Rb sin(psi) / (Rt sin(phi - psi) + Rb sin(psi)),
on N nodes per level at angles 2*pi*i/N + m*pi/N. Rings and rivets sit there.

Run inside Blender:
    exec(open(bpy.path.abspath('//scripts/shukhov_tower.py')).read())
"""
import bpy
import math

exec(open(bpy.path.abspath('//scripts/gn_helpers.py')).read())

T = Tree("GN_Shukhov_Tower")
T.input("Height", 'NodeSocketFloat', 25.6, 1.0)
T.input("Base Radius", 'NodeSocketFloat', 5.5, 0.1)
T.input("Top Radius", 'NodeSocketFloat', 2.2, 0.1)
T.input("Bars", 'NodeSocketInt', 40, 3, 400)
T.input("Twist Steps", 'NodeSocketInt', 22, 1, 200)
T.input("Ring Step", 'NodeSocketInt', 2, 1, 50)
T.input("Bar Leg", 'NodeSocketFloat', 0.10, 0.005)
T.input("Bar Thickness", 'NodeSocketFloat', 0.012, 0.001)
T.input("Ring Leg", 'NodeSocketFloat', 0.14, 0.005)
T.input("Rivet Radius", 'NodeSocketFloat', 0.03, 0.001)
T.input("Deck Overhang", 'NodeSocketFloat', 1.3, 0.2)
T.input("Tank Height", 'NodeSocketFloat', 3.6, 0.5)
T.input("Footing Height", 'NodeSocketFloat', 0.6, 0.1)
T.input("Iron", 'NodeSocketMaterial')
T.input("Tank Iron", 'NodeSocketMaterial')
T.input("Stone", 'NodeSocketMaterial')
T.input("Timber", 'NodeSocketMaterial')
T.output("Geometry")

H, Rb, Rt = T.gi("Height"), T.gi("Base Radius"), T.gi("Top Radius")
N, K = T.gi("Bars"), T.gi("Twist Steps")

step = T.m('DIVIDE', math.pi, N)          # pi / N
phi = T.m('MULTIPLY', K, step)            # total twist of a ruling
TAU_N = T.m('MULTIPLY', step, 2.0)        # 2 pi / N


def ruling_point(theta, t, sign):
    """Point at parameter t on the ruling starting at angle theta."""
    a_top = T.m('ADD', theta, T.m('MULTIPLY', phi, sign))
    bottom = T.xyz(T.m('MULTIPLY', Rb, T.m('COSINE', theta)),
                   T.m('MULTIPLY', Rb, T.m('SINE', theta)), 0.0)
    top = T.xyz(T.m('MULTIPLY', Rt, T.m('COSINE', a_top)),
                T.m('MULTIPLY', Rt, T.m('SINE', a_top)), H)
    one_minus_t = T.m('SUBTRACT', 1.0, t)
    return T.v('ADD', T.v('SCALE', bottom, scale=one_minus_t),
               T.v('SCALE', top, scale=t))


def level_t(m):
    """Height parameter t_m of node level m."""
    psi = T.m('MULTIPLY', m, step)
    rb_s = T.m('MULTIPLY', Rb, T.m('SINE', psi))
    rt_s = T.m('MULTIPLY', Rt, T.m('SINE', T.m('SUBTRACT', phi, psi)))
    return T.m('DIVIDE', rb_s, T.m('ADD', rt_s, rb_s))


def radial_normal():
    p = T.sep(T.node('GeometryNodeInputPosition').outputs[0])
    return T.v('NORMALIZE', T.xyz(p[0], p[1], 0.0))


def angle_profile(leg, thick):
    """Closed L-shaped profile (angle iron), corner at the origin."""
    circ = T.node('GeometryNodeCurvePrimitiveCircle', {'Resolution': 6})
    sw = T.node('GeometryNodeIndexSwitch', data_type='VECTOR')
    while len(sw.index_switch_items) < 6:
        sw.index_switch_items.new()
    corners = [
        (0.0, 0.0), (leg, 0.0), (leg, thick), (thick, thick), (thick, leg), (0.0, leg)
    ]
    for k, (x, y) in enumerate(corners):
        T.feed(sw.inputs[k + 1], T.xyz(x, y, 0.0))
    T.feed(sw.inputs['Index'], T.node('GeometryNodeInputIndex').outputs[0])
    # centre the L on the curve so both families meet at the node line
    half = T.m('MULTIPLY', leg, -0.5)
    pos = T.v('ADD', sw.outputs[0], T.xyz(half, half, 0.0))
    sp = T.node('GeometryNodeSetPosition', {'Geometry': circ.outputs['Curve'],
                                            'Position': pos})
    return sp.outputs[0]


def sweep(curve, profile):
    nrm = T.node('GeometryNodeSetCurveNormal', {'Curve': curve, 'Normal': radial_normal()})
    T.set_menu(nrm, 'Mode', 'Free')
    mesh = T.node('GeometryNodeCurveToMesh', {'Curve': nrm.outputs[0],
                                              'Profile Curve': profile,
                                              'Fill Caps': True})
    return mesh.outputs[0]


# --- rulings: N straight bars per family -----------------------------------
line = T.node('GeometryNodeCurvePrimitiveLine').outputs[0]
bar_profile = angle_profile(T.gi("Bar Leg"), T.gi("Bar Thickness"))
families = []
for sign in (1.0, -1.0):
    pts = T.node('GeometryNodePoints', {'Count': N}).outputs[0]
    inst = T.node('GeometryNodeInstanceOnPoints', {'Points': pts, 'Instance': line})
    real = T.node('GeometryNodeRealizeInstances', {'Geometry': inst.outputs[0]})
    cop = T.node('GeometryNodeCurveOfPoint')
    theta = T.m('MULTIPLY', cop.outputs['Curve Index'], TAU_N)
    pos = ruling_point(theta, cop.outputs['Index in Curve'], sign)
    sp = T.node('GeometryNodeSetPosition', {'Geometry': real.outputs[0], 'Position': pos})
    families.append(sweep(sp.outputs[0], bar_profile))

# --- rings: horizontal circles at every Ring Step-th node level ------------
n_rings = T.im('ADD', T.im('DIVIDE_FLOOR', K, T.gi("Ring Step")), 1)
rpts = T.node('GeometryNodePoints', {'Count': n_rings}).outputs[0]
idx = T.node('GeometryNodeInputIndex').outputs[0]
m_ring = T.m('MULTIPLY', idx, T.gi("Ring Step"))
t_ring = level_t(m_ring)
rp = T.sep(ruling_point(0.0, t_ring, 1.0))
r_ring = T.v('LENGTH', T.xyz(rp[0], rp[1], 0.0))
rpos = T.node('GeometryNodeSetPosition', {'Geometry': rpts,
                                          'Position': T.xyz(0.0, 0.0, T.m('MULTIPLY', t_ring, H))})
circle = T.node('GeometryNodeCurvePrimitiveCircle', {'Resolution': 160, 'Radius': 1.0}).outputs['Curve']
rinst = T.node('GeometryNodeInstanceOnPoints', {'Points': rpos.outputs[0], 'Instance': circle,
                                                'Scale': r_ring})
rreal = T.node('GeometryNodeRealizeInstances', {'Geometry': rinst.outputs[0]})
ring_profile = angle_profile(T.gi("Ring Leg"), T.gi("Bar Thickness"))
rings = sweep(rreal.outputs[0], ring_profile)

# --- rivets: one bolt head at every crossing --------------------------------
n_levels = T.im('ADD', K, 1)
npts = T.node('GeometryNodePoints', {'Count': T.im('MULTIPLY', N, n_levels)}).outputs[0]
idx2 = T.node('GeometryNodeInputIndex').outputs[0]
i_node = T.im('MODULO', idx2, N)
m_node = T.im('DIVIDE_FLOOR', idx2, N)
theta_node = T.m('ADD', T.m('MULTIPLY', i_node, TAU_N), T.m('MULTIPLY', m_node, step))
# node position = ruling with base angle theta_node - psi evaluated at t_m
t_node = level_t(m_node)
base_angle = T.m('SUBTRACT', theta_node, T.m('MULTIPLY', m_node, step))
npos_vec = ruling_point(base_angle, t_node, 1.0)
npos = T.node('GeometryNodeSetPosition', {'Geometry': npts, 'Position': npos_vec})
rivet = T.node('GeometryNodeMeshCylinder', {'Vertices': 10, 'Radius': T.gi("Rivet Radius"),
                                            'Depth': T.m('MULTIPLY', T.gi("Bar Leg"), 0.9)})
p_sep = T.sep(T.node('GeometryNodeInputPosition').outputs[0])
align = T.node('FunctionNodeAlignRotationToVector', {'Vector': T.xyz(p_sep[0], p_sep[1], 0.0)})
align.axis = 'Z'
vinst = T.node('GeometryNodeInstanceOnPoints', {'Points': npos.outputs[0],
                                                'Instance': rivet.outputs['Mesh'],
                                                'Rotation': align.outputs[0]})
rivets = T.node('GeometryNodeRealizeInstances', {'Geometry': vinst.outputs[0]}).outputs[0]

# --- top and base -----------------------------------------------------------
def move(geo, x=0.0, y=0.0, z=0.0):
    return T.node('GeometryNodeTransform', {'Geometry': geo,
                                            'Translation': T.xyz(x, y, z)}).outputs[0]


def material(geo, name):
    return T.node('GeometryNodeSetMaterial', {'Geometry': geo,
                                              'Material': T.gi(name)}).outputs[0]


def ring_sweep(radius, z, profile, resolution=160):
    c = T.node('GeometryNodeCurvePrimitiveCircle', {'Resolution': resolution,
                                                    'Radius': radius}).outputs['Curve']
    return move(sweep(c, profile), z=z)


def rect(w, h):
    return T.node('GeometryNodeCurvePrimitiveQuadrilateral',
                  {'Width': w, 'Height': h}).outputs[0]


def round_bar(r):
    return T.node('GeometryNodeCurvePrimitiveCircle', {'Resolution': 8,
                                                       'Radius': r}).outputs['Curve']


R_deck = T.m('ADD', Rt, T.gi("Deck Overhang"))
deck_th = 0.12
z_deck = T.m('ADD', H, 0.20)                          # deck top surface
R_tank = T.m('ADD', Rt, 0.25)
h_tank = T.gi("Tank Height")

# ring beam crowning the lattice
ring_beam = ring_sweep(Rt, H, rect(0.22, 0.32))

# deck: timber disc sitting on the ring beam
deck = T.node('GeometryNodeMeshCylinder', {'Vertices': 96, 'Radius': R_deck,
                                           'Depth': deck_th}).outputs['Mesh']
deck = move(deck, z=T.m('SUBTRACT', z_deck, deck_th / 2))
deck_edge = ring_sweep(R_deck, T.m('SUBTRACT', z_deck, 0.06), rect(0.08, 0.20))

# brackets: straight struts from the lattice up to the deck edge
n_br = T.im('DIVIDE_FLOOR', N, 2)
br_drop = 2.2                                          # metres below the top
t_br = T.m('SUBTRACT', 1.0, T.m('DIVIDE', br_drop, H))
rb_sep = T.sep(ruling_point(0.0, t_br, 1.0))
r_br = T.v('LENGTH', T.xyz(rb_sep[0], rb_sep[1], 0.0))
bpts = T.node('GeometryNodePoints', {'Count': n_br}).outputs[0]
binst = T.node('GeometryNodeInstanceOnPoints', {'Points': bpts, 'Instance': line})
breal = T.node('GeometryNodeRealizeInstances', {'Geometry': binst.outputs[0]})
bcop = T.node('GeometryNodeCurveOfPoint')
b_ang = T.m('MULTIPLY', bcop.outputs['Curve Index'], T.m('MULTIPLY', TAU_N, 2.0))
b_t = bcop.outputs['Index in Curve']
b_r = T.m('ADD', T.m('MULTIPLY', r_br, T.m('SUBTRACT', 1.0, b_t)),
          T.m('MULTIPLY', T.m('SUBTRACT', R_deck, 0.15), b_t))
b_z = T.m('ADD', T.m('MULTIPLY', T.m('SUBTRACT', H, br_drop), T.m('SUBTRACT', 1.0, b_t)),
          T.m('MULTIPLY', T.m('SUBTRACT', z_deck, deck_th), b_t))
b_pos = T.xyz(T.m('MULTIPLY', b_r, T.m('COSINE', b_ang)),
              T.m('MULTIPLY', b_r, T.m('SINE', b_ang)), b_z)
bset = T.node('GeometryNodeSetPosition', {'Geometry': breal.outputs[0], 'Position': b_pos})
brackets = sweep(bset.outputs[0], bar_profile)

# railing: posts plus top and middle rails
R_rail = T.m('SUBTRACT', R_deck, 0.10)
n_posts = 48
ppts = T.node('GeometryNodePoints', {'Count': n_posts}).outputs[0]
pidx = T.node('GeometryNodeInputIndex').outputs[0]
p_ang = T.m('MULTIPLY', pidx, 2 * math.pi / n_posts)
ppos = T.node('GeometryNodeSetPosition', {'Geometry': ppts, 'Position': T.xyz(
    T.m('MULTIPLY', R_rail, T.m('COSINE', p_ang)),
    T.m('MULTIPLY', R_rail, T.m('SINE', p_ang)),
    T.m('ADD', z_deck, 0.55))})
post = T.node('GeometryNodeMeshCylinder', {'Vertices': 8, 'Radius': 0.022,
                                           'Depth': 1.1}).outputs['Mesh']
posts = T.node('GeometryNodeRealizeInstances', {'Geometry': T.node(
    'GeometryNodeInstanceOnPoints', {'Points': ppos.outputs[0], 'Instance': post}).outputs[0]}).outputs[0]
rail_top = ring_sweep(R_rail, T.m('ADD', z_deck, 1.1), round_bar(0.03))
rail_mid = ring_sweep(R_rail, T.m('ADD', z_deck, 0.55), round_bar(0.015))

# tank: riveted cylinder with seam bands, conical roof and finial
tank = T.node('GeometryNodeMeshCylinder', {'Vertices': 96, 'Radius': R_tank,
                                           'Depth': h_tank}).outputs['Mesh']
tank = move(tank, z=T.m('ADD', z_deck, T.m('MULTIPLY', h_tank, 0.5)))
bands = []
for f in (0.0, 0.33, 0.66, 1.0):
    zb = T.m('ADD', z_deck, T.m('MULTIPLY', h_tank, f))
    bands.append(ring_sweep(T.m('ADD', R_tank, 0.015), zb, rect(0.05, 0.16), 128))
roof_h = 1.1
roof = T.node('GeometryNodeMeshCone', {'Vertices': 96, 'Radius Bottom': T.m('ADD', R_tank, 0.25),
                                       'Radius Top': 0.12, 'Depth': roof_h}).outputs['Mesh']
z_roof = T.m('ADD', z_deck, h_tank)
roof = move(roof, z=z_roof)            # GN cones have their base at the origin
knob = T.node('GeometryNodeMeshUVSphere', {'Segments': 24, 'Rings': 12, 'Radius': 0.16}).outputs['Mesh']
knob = move(knob, z=T.m('ADD', z_roof, roof_h + 0.12))
spike = T.node('GeometryNodeMeshCone', {'Vertices': 12, 'Radius Bottom': 0.04,
                                        'Radius Top': 0.0, 'Depth': 1.0}).outputs['Mesh']
spike = move(spike, z=T.m('ADD', z_roof, roof_h + 0.2))

# footing: dressed stone ring under the base ring, below z=0
fh = T.gi("Footing Height")
# top face sits under the base ring, which is centred on z=0
z_foot = T.m('SUBTRACT', T.m('MULTIPLY', fh, -0.5), T.m('MULTIPLY', T.gi("Ring Leg"), 0.5))
footing = ring_sweep(Rb, z_foot, rect(1.2, fh), 128)

# --- assemble ---------------------------------------------------------------
iron = T.join(families[0], families[1], rings, rivets, ring_beam, deck_edge,
              brackets, posts, rail_top, rail_mid)
geo = T.join(material(iron, "Iron"),
             material(T.join(tank, *bands, roof, knob, spike), "Tank Iron"),
             material(deck, "Timber"),
             material(footing, "Stone"))
# smooth faces, sharp edges where faces meet at more than 30 degrees
faces = T.node('GeometryNodeSetShadeSmooth', {'Mesh': geo, 'Shade Smooth': True})
faces.domain = 'FACE'
angle = T.node('GeometryNodeInputMeshEdgeAngle').outputs['Unsigned Angle']
edges = T.node('GeometryNodeSetShadeSmooth', {'Mesh': faces.outputs[0],
                                              'Shade Smooth': T.m('LESS_THAN', angle, 0.52)})
edges.domain = 'EDGE'
T.set_output("Geometry", edges.outputs[0])

# --- object -----------------------------------------------------------------
coll = bpy.data.collections["Shukhov_Tower"]
obj = bpy.data.objects.get("Shukhov_Lattice")
if obj is None:
    me = bpy.data.meshes.new("Shukhov_Lattice_Mesh")
    obj = bpy.data.objects.new("Shukhov_Lattice", me)
    coll.objects.link(obj)
mod = obj.modifiers.get("Shukhov_Lattice") or obj.modifiers.new("Shukhov_Lattice", 'NODES')
mod.node_group = T.ng
reset_modifier_inputs(mod)
obj.location = (0.0, 0.0, 0.45)   # footing shows 0.45 m above the ground
