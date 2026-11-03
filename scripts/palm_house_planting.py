"""Planting for the palm house: plant prototypes, a floor, and placements.

Placement uses the house's own geometry (palm_house.py): at each candidate
spot inside the footprint the clear height under the glass is computed, and
the species and size are chosen to fit with a margin. Paths are kept clear
along each wing's spine and across the hall from the porch.

Prototypes (hidden collection Palm_House_Prototypes), nominal height in
brackets: feather palm (10 m), fan palm (4 m), banana (2.8 m), tree fern
(3 m), shrub (0.55 m). The point cloud carries "species", "scale" and "turn";
the GN modifier on Palm_House_Planting instances the prototypes.

Run inside Blender after palm_house.py and palm_house_ornament.py:
    exec(open(bpy.path.abspath('//scripts/palm_house_planting.py')).read())
"""
import bpy
import math
import numpy as np

ns = {}
exec(open(bpy.path.abspath('//scripts/palm_house.py')).read().split("\nme = build_mesh()")[0], ns)
exec(open(bpy.path.abspath('//scripts/palm_house_ornament.py')).read().split("\nproto_object(\"Proto_Cresting\"")[0], ns)
exec(open(bpy.path.abspath('//scripts/gn_helpers.py')).read())
H = ns            # palm house geometry and ornament helpers
RNG = np.random.default_rng(1896)

FEATHER, FAN, BANANA, FERN, SHRUB = range(5)
NOMINAL_H = {FEATHER: 10.0, FAN: 4.0, BANANA: 2.8, FERN: 3.0, SHRUB: 0.55}   # measured on the prototypes


# --- materials ----------------------------------------------------------------------------
def leaf_material(name, dark, light, translucent=0.35):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    S = Tree.wrap(nt)
    out = S.node('ShaderNodeOutputMaterial')
    pos = S.node('ShaderNodeNewGeometry').outputs['Position']
    n = S.node('ShaderNodeTexNoise', {'Vector': pos, 'Scale': 1.2, 'Detail': 4.0}).outputs[0]
    ramp = S.node('ShaderNodeValToRGB')
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.35, (*dark, 1)
    e[1].position, e[1].color = 0.70, (*light, 1)
    S.link(n, ramp.inputs['Fac'])
    leaf = S.node('ShaderNodeBsdfPrincipled', {'Base Color': ramp.outputs['Color'], 'Roughness': 0.45})
    back = S.node('ShaderNodeBsdfTranslucent', {'Color': ramp.outputs['Color']})
    mix = S.node('ShaderNodeMixShader', {'Fac': translucent})
    S.link(leaf.outputs[0], mix.inputs[1])
    S.link(back.outputs[0], mix.inputs[2])
    S.link(mix.outputs[0], out.inputs['Surface'])
    return mat


def bark_material(name, dark, light, rings=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    S = Tree.wrap(nt)
    out = S.node('ShaderNodeOutputMaterial')
    co = S.node('ShaderNodeTexCoord').outputs['Object']
    if rings:      # palm trunks: horizontal leaf-scar rings
        w = S.node('ShaderNodeTexWave', {'Vector': co, 'Scale': rings, 'Distortion': 1.5},
                   wave_type='BANDS', bands_direction='Z').outputs['Fac']
    else:
        w = S.node('ShaderNodeTexNoise', {'Vector': co, 'Scale': 12.0, 'Detail': 6.0}).outputs[0]
    ramp = S.node('ShaderNodeValToRGB')
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.3, (*dark, 1)
    e[1].position, e[1].color = 0.8, (*light, 1)
    S.link(w, ramp.inputs['Fac'])
    bsdf = S.node('ShaderNodeBsdfPrincipled', {'Base Color': ramp.outputs['Color'], 'Roughness': 0.85})
    bump = S.node('ShaderNodeBump', {'Height': w, 'Strength': 0.5, 'Distance': 0.02})
    S.link(bump.outputs[0], bsdf.inputs['Normal'])
    S.link(bsdf.outputs[0], out.inputs['Surface'])
    return mat


LEAF = leaf_material("M_Leaf_Palm", (0.025, 0.06, 0.015), (0.06, 0.11, 0.025))
LEAF_LIGHT = leaf_material("M_Leaf_Banana", (0.05, 0.10, 0.02), (0.11, 0.17, 0.04), 0.45)
LEAF_FERN = leaf_material("M_Leaf_Fern", (0.03, 0.07, 0.02), (0.07, 0.13, 0.03))
TRUNK = bark_material("M_Trunk_Palm", (0.06, 0.05, 0.04), (0.16, 0.13, 0.10), rings=6.0)
FERN_TRUNK = bark_material("M_Trunk_Fern", (0.015, 0.01, 0.008), (0.05, 0.035, 0.025))


# --- geometry helpers ------------------------------------------------------------------------
class Parts:
    """Collect vertices/faces per material, then build one mesh."""
    def __init__(self):
        self.parts = {}

    def add(self, mat, verts, faces):
        v, f = self.parts.setdefault(mat, ([], []))
        o = len(v)
        v.extend(verts)
        f.extend(tuple(i + o for i in ff) for ff in faces)

    def quad(self, mat, a, b, c, d):
        self.add(mat, [a, b, c, d], [(0, 1, 2, 3)])

    def mesh(self, name):
        return H['mesh_from'](name, [(v, f, m) for m, (v, f) in self.parts.items()])


def trunk(P, mat, height, r0, r1, bend=0.0, segments=10, rows=12):
    z = np.linspace(0, height, rows)
    r = np.linspace(r0, r1, rows)
    off = bend * (z / height) ** 2
    a = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    verts = [(off[i] + r[i] * math.cos(t), r[i] * math.sin(t), z[i]) for i in range(rows) for t in a]
    faces = [(i * segments + j, i * segments + (j + 1) % segments,
              (i + 1) * segments + (j + 1) % segments, (i + 1) * segments + j)
             for i in range(rows - 1) for j in range(segments)]
    P.add(mat, verts, faces)
    return np.array([off[-1], 0.0, height])


def rotz(v, a):
    c, s = math.cos(a), math.sin(a)
    return np.array([c * v[0] - s * v[1], s * v[0] + c * v[1], v[2]])


def frond(P, mat, base, azimuth, length, elevation, droop, leaflets, leaflet_len, leaflet_w,
          leaflet_down=0.35, rachis_r=0.02):
    """Feather frond: arching rachis with paired leaflets, pointing along azimuth."""
    s = np.linspace(0, 1, leaflets + 1)
    x = length * s * math.cos(elevation)
    z = length * (s * math.sin(elevation) - droop * s ** 2)
    pts = [base + rotz(np.array([x[k], 0.0, z[k]]), azimuth) for k in range(len(s))]
    for k in range(1, len(s)):
        p, q = pts[k - 1], pts[k]
        t = (q - p) / max(np.linalg.norm(q - p), 1e-6)
        if k > len(s) * 0.12:
            ln = leaflet_len * math.sin(math.pi * min(s[k], 0.98)) ** 0.6
            for side in (1, -1):
                lat = rotz(np.array([0.0, side, 0.0]), azimuth)
                d = lat * 0.85 + t * 0.35 - np.array([0, 0, leaflet_down])
                d /= np.linalg.norm(d)
                w = t * leaflet_w * 0.5
                P.quad(mat, p - w, p + w, p + w + d * ln, p - w + d * ln * 0.9)
    # rachis as a thin flat strip, enough at this scale
    for k in range(1, len(pts)):
        p, q = pts[k - 1], pts[k]
        up = np.array([0, 0, rachis_r])
        P.quad(mat, p - up, q - up, q + up, p + up)


def feather_palm():
    P = Parts()
    top = trunk(P, TRUNK, 8.6, 0.32, 0.24, bend=0.35)
    for k in range(16):
        az = 2 * math.pi * k / 16 + RNG.uniform(-0.15, 0.15)
        elev = math.radians(RNG.uniform(-5, 55))
        frond(P, LEAF, top, az, RNG.uniform(3.6, 4.6), elev, RNG.uniform(0.35, 0.6), 28, 0.9, 0.05)
    return P.mesh("Proto_Plant_FeatherPalm_Mesh")


def fan_palm():
    P = Parts()
    top = trunk(P, TRUNK, 2.4, 0.22, 0.18, bend=0.1)
    for k in range(12):
        az = 2 * math.pi * k / 12 + RNG.uniform(-0.2, 0.2)
        el = math.radians(RNG.uniform(15, 65))
        d = rotz(np.array([math.cos(el), 0.0, math.sin(el)]), az)
        stalk = top + d * 1.1
        P.quad(LEAF, top - np.array([0, 0, 0.02]), stalk - np.array([0, 0, 0.02]),
               stalk + np.array([0, 0, 0.02]), top + np.array([0, 0, 0.02]))
        # pleated fan: radial segments alternating up and down
        n, R = 18, 0.75
        lat = rotz(np.array([0.0, 1.0, 0.0]), az)
        upv = np.cross(d, lat)
        verts, faces = [stalk], []
        for j in range(n + 1):
            a = -math.pi * 0.45 + math.pi * 0.9 * j / n
            pleat = 0.06 * (1 if j % 2 else -1)
            verts.append(stalk + d * R * math.cos(a) * 0.9 + lat * R * math.sin(a) + upv * pleat)
        for j in range(n):
            faces.append((0, j + 1, j + 2))
        P.add(LEAF, verts, faces)
    return P.mesh("Proto_Plant_FanPalm_Mesh")


def banana():
    P = Parts()
    top = trunk(P, LEAF_LIGHT, 1.8, 0.16, 0.11)
    for k in range(8):
        az = 2 * math.pi * k / 8 * 1.37
        el = math.radians(RNG.uniform(20, 70))
        L, W = RNG.uniform(1.6, 2.2), RNG.uniform(0.45, 0.6)
        s = np.linspace(0, 1, 12)
        mid = [top + rotz(np.array([L * t * math.cos(el), 0.0, L * (t * math.sin(el) - 0.45 * t * t)]), az)
               for t in s]
        lat = rotz(np.array([0.0, 1.0, 0.0]), az)
        for i in range(len(s) - 1):
            w0 = W * 0.5 * math.sin(math.pi * max(s[i], 0.05)) ** 0.7
            w1 = W * 0.5 * math.sin(math.pi * max(s[i + 1], 0.05)) ** 0.7
            sag = np.array([0, 0, -0.06])
            P.quad(LEAF_LIGHT, mid[i] - lat * w0 + sag, mid[i + 1] - lat * w1 + sag,
                   mid[i + 1] + lat * w1 + sag, mid[i] + lat * w0 + sag)
    return P.mesh("Proto_Plant_Banana_Mesh")


def tree_fern():
    P = Parts()
    top = trunk(P, FERN_TRUNK, 2.6, 0.2, 0.16, bend=0.15)
    for k in range(14):
        az = 2 * math.pi * k / 14 + RNG.uniform(-0.1, 0.1)
        frond(P, LEAF_FERN, top, az, RNG.uniform(1.8, 2.3), math.radians(RNG.uniform(10, 45)),
              RNG.uniform(0.5, 0.8), 30, 0.32, 0.035, leaflet_down=0.2, rachis_r=0.012)
    return P.mesh("Proto_Plant_TreeFern_Mesh")


def shrub():
    P = Parts()
    for k in range(36):
        az = RNG.uniform(0, 2 * math.pi)
        el = math.radians(RNG.uniform(35, 80))
        L, W = RNG.uniform(0.5, 0.9), RNG.uniform(0.07, 0.12)
        s = np.linspace(0, 1, 6)
        base = np.array([RNG.uniform(-0.15, 0.15), RNG.uniform(-0.15, 0.15), 0.0])
        mid = [base + rotz(np.array([L * t * math.cos(el), 0.0, L * (t * math.sin(el) - 0.3 * t * t)]), az)
               for t in s]
        lat = rotz(np.array([0.0, 1.0, 0.0]), az)
        for i in range(len(s) - 1):
            w0, w1 = (W * 0.5 * math.sin(math.pi * max(x, 0.08)) for x in (s[i], s[i + 1]))
            P.quad(LEAF, mid[i] - lat * w0, mid[i + 1] - lat * w1, mid[i + 1] + lat * w1, mid[i] + lat * w0)
    return P.mesh("Proto_Plant_Shrub_Mesh")


PROTOS = {FEATHER: ("Proto_Plant_FeatherPalm", feather_palm), FAN: ("Proto_Plant_FanPalm", fan_palm),
          BANANA: ("Proto_Plant_Banana", banana), FERN: ("Proto_Plant_TreeFern", tree_fern),
          SHRUB: ("Proto_Plant_Shrub", shrub)}


# --- where things can grow ------------------------------------------------------------------
def ceiling(points):
    """Clear height under the glass (local coords), and which space each point is in.
    Returns (height, zone) with zone 0 outside, 1 hall, 2 wing."""
    xy = points[:, :2]
    r = np.hypot(xy[:, 0], xy[:, 1])
    h = np.zeros(len(points))
    zone = np.zeros(len(points), int)
    # hall: drum then dome profile
    Rs = (H['DOME_H'] ** 2 - H['DRUM_R'] ** 2) / (2 * H['DRUM_R'])
    rr = Rs + H['DRUM_R']
    hall = r < H['DRUM_R'] - 0.6
    zt = np.sqrt(np.maximum(rr ** 2 - (r + Rs) ** 2, 0.0))
    h[hall] = H['PLINTH'] + H['DRUM_H'] + zt[hall]
    zone[hall] = 1
    # wings: nearest rib circle along the band
    us = np.linspace(np.pi - H['WING_END'], np.pi + H['WING_END'], 600)
    cen = 0.5 * (H['wing_point'](us, np.full_like(us, np.pi)) + H['wing_point'](us, np.zeros_like(us)))
    rad = np.linalg.norm(H['wing_point'](us, np.full_like(us, 1.5 * np.pi)) - cen, axis=1)
    for i in np.where(~hall)[0]:
        d = np.hypot(*(cen[:, :2] - xy[i]).T)
        k = d.argmin()
        if d[k] < rad[k] - 0.6 and abs(us[k] - np.pi) < H['WING_END'] - 0.05:
            h[i] = cen[k, 2] + math.sqrt(rad[k] ** 2 - d[k] ** 2)
            zone[i] = 2
    return h, zone, cen, us


def on_path(points, cen):
    """Gravel paths: along the wing spines and across the hall to the porch."""
    xy = points[:, :2]
    d_spine = np.min(np.hypot(xy[:, None, 0] - cen[None, ::6, 0], xy[:, None, 1] - cen[None, ::6, 1]), 1)
    to_porch = (xy[:, 0] > 0) & (np.abs(xy[:, 1]) < 1.0)
    ring = np.abs(np.hypot(xy[:, 0], xy[:, 1]) - 4.2) < 0.7
    return (d_spine < 0.9) | to_porch | ring


SPACING = {FEATHER: 3.6, FAN: 2.6, BANANA: 2.4, FERN: 2.4, SHRUB: 1.3}   # minimum gaps, metres


def choose(p, hc, zone):
    """Species and target height for a spot, or None when there is no room."""
    room = hc - 1.0                                           # a metre under the glass
    if room > 9:
        sp = FEATHER if RNG.random() < 0.7 else FAN
        return sp, (min(room, RNG.uniform(7.5, 12.0)) if sp == FEATHER else RNG.uniform(3.5, 5.0))
    if room > 4.5:
        sp = int(RNG.choice([FEATHER, BANANA, FERN, FAN], p=[0.3, 0.25, 0.25, 0.2]))
        return sp, min(room, {FEATHER: RNG.uniform(5, 7), BANANA: RNG.uniform(3, 4.2),
                              FERN: RNG.uniform(3, 4.5), FAN: RNG.uniform(3, 4.5)}[sp])
    if room > 1.2:
        sp = SHRUB if RNG.random() < 0.7 else FERN
        return sp, min(room, RNG.uniform(0.8, 1.5) if sp == SHRUB else RNG.uniform(1.5, 2.5))
    return None


def placements():
    """Largest plants first, each keeping a gap that suits its size."""
    cand = np.c_[RNG.uniform(-30, 30, (6000, 2)), np.zeros(6000)]
    h, zone, cen, us = ceiling(cand)
    ok = (zone > 0) & ~on_path(cand, cen)
    cand, h, zone = cand[ok], h[ok], zone[ok]
    order = np.argsort(-(h + RNG.uniform(0, 1.5, len(h))))   # roomiest spots first, a little shuffled
    kept, species, scale, gap = [np.array([0.3, 0.2, 0.0])], [FEATHER], [13.5 / NOMINAL_H[FEATHER]], [SPACING[FEATHER]]
    for i in order:
        pick = choose(cand[i], h[i], zone[i])
        if pick is None:
            continue
        sp, target = pick
        d = np.hypot(*(np.array(kept)[:, :2] - cand[i, :2]).T)
        if np.any(d < np.maximum(np.array(gap), SPACING[sp]) * 0.85):
            continue
        kept.append(cand[i])
        species.append(sp)
        scale.append(target / NOMINAL_H[sp])
        gap.append(SPACING[sp])
    return np.array(kept), np.array(species), np.array(scale)


def floor_mesh(cen):
    """Planted soil inside the footprint, gravel on the paths (0.3 m cells)."""
    cell = 0.3
    g = np.arange(-30, 30, cell)
    X, Y = np.meshgrid(g, g)
    c = np.c_[X.ravel() + cell / 2, Y.ravel() + cell / 2, np.zeros(X.size)]
    h, zone, _, _ = ceiling(c)
    inside = (zone > 0) | (np.hypot(c[:, 0], c[:, 1]) < H['DRUM_R'])
    path = on_path(c, cen)
    verts, faces, mat_idx = [], [], []
    for p, ins, pa in zip(c, inside, path):
        if not ins:
            continue
        o = len(verts)
        x, y = p[0] - cell / 2, p[1] - cell / 2
        verts += [(x, y, 0.03), (x + cell, y, 0.03), (x + cell, y + cell, 0.03), (x, y + cell, 0.03)]
        faces.append((o, o + 1, o + 2, o + 3))
        mat_idx.append(1 if pa else 0)
    soil = bark_material("M_Soil_Planted", (0.012, 0.008, 0.006), (0.035, 0.025, 0.018))
    gravel = H['material']("M_Path_Gravel", (0.20, 0.17, 0.13), rough=0.9)
    me = bpy.data.meshes.get("Palm_House_Floor_Mesh") or bpy.data.meshes.new("Palm_House_Floor_Mesh")
    me.clear_geometry()
    me.materials.clear()
    me.from_pydata(verts, [], faces)
    me.materials.append(soil)
    me.materials.append(gravel)
    me.polygons.foreach_set('material_index', mat_idx)
    me.update()
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
    bm.to_mesh(me)
    bm.free()
    return me


def placed_object(name, mesh):
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, mesh)
        bpy.data.collections["Palm_House"].objects.link(obj)
    obj.data = mesh
    house = bpy.data.objects["Palm_House"]
    obj.location, obj.rotation_euler = house.location.copy(), house.rotation_euler.copy()
    return obj


def build_instancer(proto_names):
    T = Tree("GN_Palm_House_Planting")
    T.input("Geometry", 'NodeSocketGeometry')
    T.output("Geometry")
    geos = []
    for name in proto_names:                     # species order
        n = T.node('GeometryNodeObjectInfo', {'As Instance': True}, transform_space='ORIGINAL')
        n.inputs['Object'].default_value = bpy.data.objects[name]
        geos.append(n.outputs['Geometry'])
    kinds = T.instances(geos)
    attr = lambda name, kind: T.node('GeometryNodeInputNamedAttribute', {'Name': name},
                                     data_type=kind).outputs['Attribute']
    s = attr("scale", 'FLOAT')
    sw = T.m('SQRT', s)          # girth and spread grow more slowly than height
    rot = T.node('FunctionNodeEulerToRotation', {'Euler': T.xyz(0.0, 0.0, attr("turn", 'FLOAT'))}).outputs[0]
    pts = T.node('GeometryNodeMeshToPoints', {'Mesh': T.gi("Geometry")}).outputs[0]
    inst = T.node('GeometryNodeInstanceOnPoints', {'Points': pts, 'Instance': kinds,
                                                   'Pick Instance': True,
                                                   'Instance Index': attr("species", 'INT'),
                                                   'Rotation': rot, 'Scale': T.xyz(sw, sw, s)}).outputs[0]
    T.set_output("Geometry", inst)
    return T.ng


# prototypes
names = []
for sp in sorted(PROTOS):
    name, fn = PROTOS[sp]
    H['proto_object'](name, fn())
    names.append(name)

# placements as a point cloud with attributes
pts, species, scale = placements()
turn = RNG.uniform(0, 2 * np.pi, len(species))
pm = bpy.data.meshes.get("Palm_House_Planting_Points") or bpy.data.meshes.new("Palm_House_Planting_Points")
pm.clear_geometry()
pm.from_pydata(pts.tolist(), [], [])
for name, kind, vals in (("species", 'INT', species), ("scale", 'FLOAT', scale), ("turn", 'FLOAT', turn)):
    a = pm.attributes.get(name) or pm.attributes.new(name, kind, 'POINT')
    a.data.foreach_set('value', vals.astype(int if kind == 'INT' else float))
planting = placed_object("Palm_House_Planting", pm)
mod = planting.modifiers.get("Planting") or planting.modifiers.new("Planting", 'NODES')
mod.node_group = build_instancer(names)
planting.update_tag()

_, _, cen, _ = ceiling(np.zeros((1, 3)))
placed_object("Palm_House_Floor", floor_mesh(cen))
print("plants:", len(species), {k: int((species == k).sum()) for k in range(5)})
