"""Imported period figures: clean-up and placement.

Sources (Sketchfab, CC Attribution; credit in CLAUDE.md):
- "Victorian gentleman 3d model" by abauerenator (uid d3fd1c10b9cb4113bb1ee7a4ef1fa37f)
- "Dress of a poor woman - Victorian era" by tijerin_art (uid 1f10c47b2a1c47f5bbf75f5016ca4b68)

The woman comes unrigged in an A-pose with an untextured mannequin body.
pose_arms_down() swings each arm about its shoulder with a blend across the
shoulder, dress_woman() adds skin, hair, a straw boater and a parasol
(a domed, scalloped canopy on eight ribs, about 0.8 m across).

Run inside Blender after import:
    exec(open(bpy.path.abspath('//scripts/figure_assets.py')).read())
"""
import bpy
import bmesh
import math
import numpy as np
from mathutils import Matrix, Vector

SHOULDER_X, SHOULDER_Z = 0.19, 1.33    # measured on the imported woman (metres)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def pose_arms_down(obj, extra_deg=47.0, blend=0.12, min_z=1.0):
    """Rotate arm vertices down about the shoulders (no rig needed)."""
    me = obj.data
    co = np.empty(len(me.vertices) * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    for side in (1.0, -1.0):
        dx = side * co[:, 0] - SHOULDER_X              # distance out from the shoulder
        sel = (dx > 0) & (co[:, 2] > min_z)
        w = smoothstep(0.0, blend, dx[sel])
        a = np.radians(extra_deg) * w
        px = dx[sel]
        pz = co[sel, 2] - SHOULDER_Z
        nx = px * np.cos(a) + pz * np.sin(a)          # clockwise in the arm's own frame
        nz = -px * np.sin(a) + pz * np.cos(a)
        co[sel, 0] = side * (nx + SHOULDER_X)
        co[sel, 2] = nz + SHOULDER_Z
    me.vertices.foreach_set('co', co.ravel().astype(np.float32))
    me.update()


def principled(name, color, rough=0.6, sheen=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    b = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = rough
    if sheen:
        b.inputs['Sheen Weight'].default_value = sheen
    return mat


def add_part(bm, kind, at, r1, r2=None, depth=0.1, rot=None, segs=20, mat_index=0, scale=None):
    before = set(bm.faces)
    m = Matrix.Translation(Vector(at))
    if rot is not None:
        m = m @ rot
    if scale is not None:
        m = m @ Matrix.Diagonal((*scale, 1.0))
    if kind == 'ball':
        bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2, radius=r1, matrix=m)
    else:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r1,
                              radius2=r1 if r2 is None else r2, depth=depth, matrix=m)
    for f in set(bm.faces) - before:
        f.material_index = mat_index
        f.smooth = True


def dress_woman(obj):
    me = obj.data
    names = {m.name: i for i, m in enumerate(me.materials)}
    # mannequin body: skin instead of black
    body = me.materials[names["lambert1"]]
    body.name = "M_Woman_Skin"
    b = next(n for n in body.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    b.inputs['Base Color'].default_value = (0.50, 0.33, 0.25, 1.0)
    b.inputs['Roughness'].default_value = 0.5
    for old, new in (("VRayMtl16", "M_Woman_Blouse"), ("VRayMtl14", "M_Woman_Skirt"),
                     ("VRayMtl15", "M_Woman_Overskirt")):
        if old in names:
            me.materials[names[old]].name = new
    # accessories as extra material slots
    extra = [principled("M_Hair_Brown", (0.035, 0.018, 0.010), 0.45, sheen=0.3),
             principled("M_Straw", (0.45, 0.33, 0.16), 0.75),
             principled("M_Hat_Ribbon", (0.02, 0.02, 0.05), 0.5)]
    base = len(me.materials)
    for m in extra:
        me.materials.append(m)
    hair, straw, ribbon = range(base, base + 3)

    co = np.array([v.co for v in me.vertices])
    head = co[co[:, 2] > 1.50]
    hc = (head[:, 0].mean(), head[:, 1].mean())
    top = head[:, 2].max()
    back = head[:, 1].max()          # the model's back is +Y (front faces -Y)
    bm = bmesh.new()
    bm.from_mesh(me)
    # hair: a cap over the crown and a bun at the back
    add_part(bm, 'ball', (hc[0], hc[1] + 0.01, top - 0.075), 0.105, mat_index=hair,
             scale=(1.0, 1.08, 0.85))
    add_part(bm, 'ball', (hc[0], back - 0.005, top - 0.10), 0.055, mat_index=hair)
    # straw boater: brim, crown, ribbon band
    add_part(bm, 'cone', (hc[0], hc[1], top + 0.005), 0.19, depth=0.012, mat_index=straw, segs=32)
    add_part(bm, 'cone', (hc[0], hc[1], top + 0.045), 0.10, depth=0.07, mat_index=straw, segs=32)
    add_part(bm, 'cone', (hc[0], hc[1], top + 0.03), 0.102, depth=0.025, mat_index=ribbon, segs=32)
    bm.to_mesh(me)
    bm.free()
    me.update()
    boots(obj)
    parasol(obj)


def slot(me, mat):
    """Index of `mat` in the mesh's slots, appending it if missing."""
    for i, m in enumerate(me.materials):
        if m == mat:
            return i
    me.materials.append(mat)
    return len(me.materials) - 1


def boots(obj, height=0.13):
    """The mannequin's bare feet become black leather boots."""
    me = obj.data
    skin = slot(me, bpy.data.materials["M_Woman_Skin"])
    leather = slot(me, principled("M_Boot_Leather", (0.012, 0.010, 0.010), 0.35))
    for f in me.polygons:
        if f.material_index == skin and f.center.z < height:
            f.material_index = leather
    me.update()


HAND = Vector((0.325, 0.066, 0.83))     # centre of the lowered right hand, measured on the mesh


def silk_material(name="M_Parasol_Silk", color=(0.55, 0.44, 0.30)):
    """Cream silk: a sheen on top and some sun showing through."""
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    b = nt.nodes.new('ShaderNodeBsdfPrincipled')
    b.inputs['Base Color'].default_value = (*color, 1.0)
    b.inputs['Roughness'].default_value = 0.6
    b.inputs['Sheen Weight'].default_value = 0.5
    t = nt.nodes.new('ShaderNodeBsdfTranslucent')
    t.inputs['Color'].default_value = (*color, 1.0)
    mix = nt.nodes.new('ShaderNodeMixShader')
    mix.inputs['Fac'].default_value = 0.3
    nt.links.new(b.outputs[0], mix.inputs[1])
    nt.links.new(t.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs['Surface'])
    return mat


def canopy(bm, m, radius, depth, ribs, mat_index, sag=0.035, scallop=0.05, rings=6, per_panel=4):
    """Domed parasol canopy in the frame `m` (apex at the origin, opening down -Z).

    The silk sags between the ribs and the hem scallops up between rib tips.
    """
    n = ribs * per_panel
    rows = []
    for i in range(1, rings + 1):
        f = i / rings                                  # 0 apex .. 1 hem
        row = []
        for j in range(n):
            th = 2 * math.pi * j / n
            between = math.sin(math.pi * (j % per_panel) / per_panel)   # 0 on ribs, 1 mid-panel
            r = radius * f * (1 - scallop * between * f ** 3)
            z = -depth * f ** 1.6 - sag * between * f + scallop * radius * between * f ** 6
            row.append(bm.verts.new(m @ Vector((r * math.cos(th), r * math.sin(th), z))))
        rows.append(row)
    apex = bm.verts.new(m @ Vector((0.0, 0.0, 0.0)))
    faces = [bm.faces.new((apex, rows[0][j], rows[0][(j + 1) % n])) for j in range(n)]
    for a, b in zip(rows[:-1], rows[1:]):
        faces += [bm.faces.new((a[j], b[j], b[(j + 1) % n], a[(j + 1) % n])) for j in range(n)]
    for f in faces:
        f.material_index = mat_index
        f.smooth = True


def parasol(obj, above=1.15, below=0.12, radius=0.40, depth=0.20, ribs=8,
            lean_back=12.0, lean_in=16.0):
    """Parasol held in the lowered right hand, its canopy tipped back over her head.

    `above` and `below` are the stick lengths either side of the grip.
    Replaces any parasol already on the mesh.
    """
    me = obj.data
    silk = slot(me, silk_material())
    stick = slot(me, principled("M_Parasol_Stick", (0.05, 0.03, 0.02), 0.4))
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index in (silk, stick)],
                     context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    # lean back (+Y is behind her) and in over the shoulder
    tilt = Matrix.Rotation(math.radians(-lean_back), 4, 'X') @ Matrix.Rotation(math.radians(-lean_in), 4, 'Y')
    up = tilt @ Vector((0.0, 0.0, 1.0))
    add_part(bm, 'cone', HAND + up * ((above - below) / 2), 0.007,
             depth=above + below, rot=tilt, mat_index=stick, segs=8)
    add_part(bm, 'ball', HAND - up * below, 0.022, mat_index=stick, segs=12)           # knob
    add_part(bm, 'cone', HAND + up * (above + 0.04), 0.006, 0.001,
             depth=0.08, rot=tilt, mat_index=stick, segs=8)                            # tip
    apex = HAND + up * (above - 0.01)
    canopy(bm, Matrix.Translation(apex) @ tilt, radius, depth, ribs, silk)
    bm.to_mesh(me)
    bm.free()
    me.update()


def place(asset_name, name, location, facing, collection="Figures"):
    """Linked copy of an asset (shared mesh) at `location`, facing a ground point.

    The imported models face -Y, so the copy is turned to put -Y toward `facing`.
    """
    asset = bpy.data.objects[asset_name]
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, asset.data)
        bpy.data.collections[collection].objects.link(obj)
    obj.data = asset.data
    obj.location = location
    dx, dy = facing[0] - location[0], facing[1] - location[1]
    obj.rotation_euler = (0.0, 0.0, math.atan2(dy, dx) + math.pi / 2)
    return obj
