"""SUPERSEDED by figure_assets.py (imported Sketchfab figures). Kept for reference.

Stylised 1890s visitors for scale: a gentleman and a lady with a parasol.

They are seen from 20-50 m, so they are built from a few cones, cylinders
and spheres; what matters is the silhouette (top hat, frock coat, bell
skirt, parasol) and a correct height.

Run inside Blender:
    exec(open(bpy.path.abspath('//scripts/figures.py')).read())
"""
import bpy
import bmesh
import math
from mathutils import Matrix, Vector


def material(name, color, rough=0.8, translucent=0.0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')
    bsdf.inputs['Base Color'].default_value = (*color, 1.0)
    bsdf.inputs['Roughness'].default_value = rough
    if translucent:
        bsdf.inputs['Transmission Weight'].default_value = translucent
    return mat


MATS = {
    "dark": material("M_Cloth_Dark", (0.010, 0.010, 0.012)),
    "grey": material("M_Cloth_Grey", (0.08, 0.075, 0.07)),
    "light": material("M_Cloth_Light", (0.55, 0.52, 0.46)),
    "skin": material("M_Skin", (0.42, 0.27, 0.19), 0.6),
    "parasol": material("M_Parasol", (0.75, 0.73, 0.66), 0.7, 0.3),
}
SLOTS = list(MATS)


def part(bm, kind, mat, at, r1=0.1, r2=None, depth=0.1, rot=None, segs=16):
    """Add a cone/cylinder ('cone') or sphere ('ball') centred at `at`."""
    before = set(bm.faces)
    m = Matrix.Translation(Vector(at))
    if rot is not None:
        m = m @ rot
    if kind == 'ball':
        bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=segs // 2,
                                         radius=r1, matrix=m)
    else:
        bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r1,
                                     radius2=r1 if r2 is None else r2, depth=depth, matrix=m)
    idx = SLOTS.index(mat)
    for f in set(bm.faces) - before:
        f.material_index = idx
        f.smooth = True


def gentleman(bm):
    for x in (-0.09, 0.09):                                  # trousers
        part(bm, 'cone', 'grey', (x, 0, 0.43), 0.075, 0.065, 0.86)
    part(bm, 'cone', 'dark', (0, 0, 1.12), 0.27, 0.21, 0.66)  # frock coat
    part(bm, 'cone', 'dark', (0, 0, 1.38), 0.21, 0.13, 0.12)  # shoulders
    for x in (-1, 1):                                         # sleeves
        part(bm, 'cone', 'dark', (0.24 * x, 0, 1.12), 0.055, 0.05, 0.6,
             rot=Matrix.Rotation(0.12 * x, 4, 'Y'))
        part(bm, 'ball', 'skin', (0.27 * x, 0, 0.8), 0.045)
    part(bm, 'cone', 'skin', (0, 0, 1.47), 0.05, 0.05, 0.08)  # neck
    part(bm, 'ball', 'skin', (0, 0, 1.6), 0.11)               # head
    part(bm, 'cone', 'dark', (0, 0, 1.69), 0.17, 0.17, 0.015)  # hat brim
    part(bm, 'cone', 'dark', (0, 0, 1.79), 0.1, 0.105, 0.2)    # top hat


def lady(bm):
    part(bm, 'cone', 'light', (0, 0, 0.5), 0.46, 0.17, 1.0, segs=24)   # bell skirt
    part(bm, 'cone', 'light', (0, 0, 1.2), 0.16, 0.19, 0.42)          # bodice
    part(bm, 'cone', 'light', (-0.21, 0, 1.17), 0.05, 0.045, 0.5,
         rot=Matrix.Rotation(-0.12, 4, 'Y'))                          # left sleeve
    part(bm, 'cone', 'light', (0.2, 0.08, 1.25), 0.05, 0.045, 0.35,
         rot=Matrix.Rotation(-0.9, 4, 'X'))                            # right arm, raised
    part(bm, 'cone', 'skin', (0, 0, 1.43), 0.045, 0.045, 0.07)
    part(bm, 'ball', 'skin', (0, 0, 1.54), 0.105)
    part(bm, 'cone', 'light', (0, 0, 1.64), 0.22, 0.22, 0.02)          # boater brim
    part(bm, 'cone', 'light', (0, 0, 1.69), 0.11, 0.11, 0.09)
    part(bm, 'cone', 'grey', (0.22, 0.12, 1.65), 0.008, 0.008, 0.95)   # parasol stick
    part(bm, 'cone', 'parasol', (0.22, 0.12, 2.08), 0.5, 0.02, 0.22, segs=24)


def figure(name, builder, location, facing):
    """facing: point on the ground the figure looks toward."""
    bm = bmesh.new()
    builder(bm)
    me = bpy.data.meshes.get(name + "_Mesh") or bpy.data.meshes.new(name + "_Mesh")
    me.materials.clear()          # clearing resets material indices, so do it first
    for k in SLOTS:
        me.materials.append(MATS[k])
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, me)
        coll = bpy.data.collections.get("Figures")
        if coll is None:
            coll = bpy.data.collections.new("Figures")
            bpy.context.scene.collection.children.link(coll)
        coll.objects.link(obj)
    obj.location = location
    dx, dy = facing[0] - location[0], facing[1] - location[1]
    obj.rotation_euler = (0, 0, math.atan2(dy, dx) - math.pi / 2)   # local +Y is the front
    return obj


# Placement calls disabled: the imported figures now use these object names.
# a couple on the gravel ring looking up at the tower, a man walking out on the path
# figure("Figure_Gentleman_A", gentleman, (-3.0, -7.0, 0.0), (0, 0))
# figure("Figure_Lady_A", lady, (-2.3, -7.3, 0.0), (0, 0))
# figure("Figure_Gentleman_B", gentleman, (0.5, -45.0, 0.0), (0, 0))
