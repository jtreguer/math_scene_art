"""Art Nouveau ornament prototypes for the palm house.

Each motif is drawn from curves (cubic Beziers running into logarithmic
spirals, the "whiplash" line) or turned on a lathe, converted to a mesh and
kept in the hidden collection Palm_House_Prototypes. palm_house_iron.py
instances them along the ridges and at points the base surface marks.

Prototype frames: X along the ridge (cresting) or outward (console), Z up,
origin at the attachment point.

Run inside Blender before palm_house_iron.py:
    exec(open(bpy.path.abspath('//scripts/palm_house_ornament.py')).read())
"""
import bpy
import math
import numpy as np

PROTO_COLL = "Palm_House_Prototypes"


def material(name, color, rough=0.4, metallic=0.0, coat=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    b = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = rough
    b.inputs['Metallic'].default_value = metallic
    b.inputs['Coat Weight'].default_value = coat
    return mat


def bezier(p0, p1, p2, p3, n=24):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = map(np.asarray, (p0, p1, p2, p3))
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def spiral(centre, r0, r1, a0, turns, n=40, direction=1.0):
    """Logarithmic spiral from radius r0 at angle a0 shrinking to r1."""
    t = np.linspace(0, 1, n)
    a = a0 + direction * turns * 2 * np.pi * t
    r = r0 * (r1 / r0) ** t
    return np.c_[centre[0] + r * np.cos(a), centre[1] + r * np.sin(a)]


def ellipse(centre, rx, rz, n=24):
    a = np.linspace(0, 2 * np.pi, n)
    return np.c_[centre[0] + rx * np.cos(a), centre[1] + rz * np.sin(a)]


def xz(pts, y=0.0):
    pts = np.asarray(pts)
    return np.c_[pts[:, 0], np.full(len(pts), y), pts[:, 1]]


def curve_mesh(name, polylines, bevel, mats, mat_index=None, bevel_res=2):
    """Sweep 3D polylines with a round bevel and return a new mesh."""
    cu = bpy.data.curves.new(name + "_tmp", 'CURVE')
    cu.dimensions = '3D'
    cu.bevel_depth = bevel
    cu.bevel_resolution = bevel_res
    cu.use_fill_caps = True
    for k, pl in enumerate(polylines):
        sp = cu.splines.new('POLY')
        sp.points.add(len(pl) - 1)
        for p, co in zip(sp.points, pl):
            p.co = (*co, 1.0)
        sp.material_index = 0 if mat_index is None else mat_index[k]
    for m in mats:
        cu.materials.append(m)
    tmp = bpy.data.objects.new(name + "_tmp", cu)
    bpy.context.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    bpy.data.objects.remove(tmp)
    bpy.data.curves.remove(cu)
    return me


def lathe(profile, segments=24):
    """Vertices and quads of a surface of revolution of (r, z) points."""
    prof = np.asarray(profile, float)
    a = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    verts = [(r * math.cos(t), r * math.sin(t), z) for r, z in prof for t in a]
    faces = []
    for i in range(len(prof) - 1):
        for j in range(segments):
            k, kn = i * segments + j, i * segments + (j + 1) % segments
            faces.append((k, kn, kn + segments, k + segments))
    return verts, faces


def mesh_from(name, parts):
    """parts: list of (verts, faces, material). Returns one mesh."""
    me = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    me.clear_geometry()
    me.materials.clear()
    verts, faces, idx = [], [], []
    for m_i, (v, f, mat) in enumerate(parts):
        o = len(verts)
        verts += list(v)
        faces += [tuple(i + o for i in ff) for ff in f]
        idx += [m_i] * len(f)
        me.materials.append(mat)
    me.from_pydata(verts, [], faces)
    me.polygons.foreach_set('material_index', idx)
    me.polygons.foreach_set('use_smooth', [True] * len(faces))
    me.update()
    return me


def merge_meshes(name, meshes):
    import bmesh
    bm = bmesh.new()
    mats = []
    for me in meshes:
        offset = len(mats)
        mats += list(me.materials)
        tmp = bmesh.new()
        tmp.from_mesh(me)
        for f in tmp.faces:
            f.material_index += offset
        m2 = bpy.data.meshes.new("tmp_merge")
        tmp.to_mesh(m2)
        tmp.free()
        bm.from_mesh(m2)
        bpy.data.meshes.remove(m2)
    out = bpy.data.meshes.get(name) or bpy.data.meshes.new(name)
    bm.to_mesh(out)
    bm.free()
    out.materials.clear()
    for m in mats:
        out.materials.append(m)
    return out


def proto_object(name, mesh):
    coll = bpy.data.collections.get(PROTO_COLL)
    if coll is None:
        coll = bpy.data.collections.new(PROTO_COLL)
        bpy.context.scene.collection.children.link(coll)
        bpy.context.view_layer.layer_collection.children[PROTO_COLL].exclude = True
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, mesh)
        coll.objects.link(obj)
    old = obj.data
    obj.data = mesh
    if old is not mesh and old.users == 0:
        bpy.data.meshes.remove(old)
    return obj


IRON = bpy.data.materials.get("M_Iron_White")
GILT = material("M_Gilt", (0.85, 0.60, 0.25), rough=0.28, metallic=1.0)
GLASS = bpy.data.materials.get("M_Glass_Thin")


# --- cresting: a lily between two whiplash tendrils, 0.45 m wide, 0.6 m tall ----------
def cresting_lily(width=0.45):
    lines = [xz([(0, 0.0), (0, 0.42)]),                      # stem
             xz(ellipse((0, 0.50), 0.045, 0.08))]            # bud
    for s in (1, -1):
        # tendril: leaves the foot of the stem, sweeps out and up, curls back toward the bud
        cen = (s * 0.13, 0.47)
        curl = spiral(cen, 0.075, 0.016, 0.0 if s > 0 else math.pi, 1.4, direction=s)
        entry = curl[0]
        approach = bezier((0, 0.02), (s * 0.24, 0.06), (entry[0] + s * 0.02, entry[1] - 0.25), entry)
        lines.append(xz(np.r_[approach, curl[1:]]))
        # a low arch reaching to the neighbouring motif, so the row reads continuous
        lines.append(xz(bezier((0, 0.0), (s * 0.10, 0.12), (s * 0.18, 0.12), (s * width / 2, 0.0), 16)))
    return curve_mesh("Proto_Cresting_Mesh", lines, 0.011, [IRON])


# --- finial: collar, gilded ball and spike, turned ---------------------------------------
def finial(scale=1.0):
    ball = [(0.13 * math.sin(a), 0.33 - 0.13 * math.cos(a)) for a in np.linspace(0.15, math.pi - 0.15, 9)]
    prof = [(0.0, 0.0), (0.11, 0.0), (0.12, 0.03), (0.06, 0.07), (0.05, 0.18)] + ball + \
           [(0.035, 0.48), (0.055, 0.51), (0.03, 0.55), (0.012, 0.95), (0.0, 1.15)]
    prof = [(r * scale, z * scale) for r, z in prof]
    v, f = lathe(prof, 20)
    return v, f


def finial_mesh():
    v, f = finial()
    return mesh_from("Proto_Finial_Mesh", [(v, f, GILT)])


# --- console: whiplash bracket under the drum cornice, 1.1 m tall -------------------------
def console():
    low = spiral((0.10, -1.00), 0.10, 0.025, math.pi, 1.3, direction=-1.0)
    top = spiral((0.42, -0.14), 0.12, 0.03, 0.0, 1.2, direction=-1.0)
    whip = bezier(low[0], (0.05, -0.55), (0.10, -0.08), top[0], 30)
    lines = [xz(np.r_[low[::-1], whip[1:], top[1:]], y) for y in (-0.025, 0.025)]
    lines.append(xz([(0.0, -1.05), (0.0, 0.0), (0.55, 0.0)]))      # back plate and top
    return curve_mesh("Proto_Console_Mesh", lines, 0.022, [IRON])


# --- lantern with a crown of whiplash ribs -------------------------------------------------
def lantern(r=1.0, h=1.6, crown_h=2.9, ribs=8):
    parts = []
    # glazed drum of the lantern and its ogee cap
    gv, gf = lathe([(r, 0.0), (r, h)], 16)
    parts.append((gv, gf, GLASS))
    cap = [(r * 1.12, h), (r * 1.08, h + 0.10), (r * 0.92, h + 0.30), (r * 0.62, h + 0.55),
           (r * 0.38, h + 0.78), (r * 0.20, h + 1.00), (r * 0.10, h + 1.20), (0.0, h + 1.26)]
    cv, cf = lathe(cap, 24)
    parts.append((cv, cf, IRON))
    base_ring, bf = lathe([(r * 1.10, -0.10), (r * 1.10, 0.05), (r * 0.9, 0.05)], 24)
    parts.append((base_ring, bf, IRON))
    body = mesh_from("tmp_lantern_body", parts)
    # crown: ribs leave the cornice, swell outward and close in over the cap
    lines = []
    for k in range(ribs):
        a = 2 * math.pi * k / ribs
        prof = bezier((r * 1.08, h), (r * 1.75, h + 0.6), (r * 0.9, h + crown_h - 0.4), (0.06, h + crown_h), 30)
        curl = spiral((r * 1.20, h - 0.05), 0.12, 0.03, math.pi / 2, 1.0, direction=1.0)
        pts = np.r_[curl[::-1], prof]
        lines.append(np.c_[pts[:, 0] * math.cos(a), pts[:, 0] * math.sin(a), pts[:, 1]])
    # mullions of the lantern
    for k in range(8):
        a = 2 * math.pi * k / 8 + math.pi / 8
        lines.append(np.array([(r * math.cos(a), r * math.sin(a), 0.0), (r * math.cos(a), r * math.sin(a), h)]))
    crown = curve_mesh("tmp_lantern_crown", lines, 0.035, [IRON])
    fv, ff = finial(scale=1.4)
    fv = [(x, y, z + h + crown_h - 0.05) for x, y, z in fv]
    top = mesh_from("tmp_lantern_finial", [(fv, ff, GILT)])
    out = merge_meshes("Proto_Lantern_Mesh", [body, crown, top])
    for m in (body, crown, top):
        bpy.data.meshes.remove(m)
    return out


proto_object("Proto_Cresting", cresting_lily())
proto_object("Proto_Finial", finial_mesh())
proto_object("Proto_Console", console())
proto_object("Proto_Lantern", lantern())
