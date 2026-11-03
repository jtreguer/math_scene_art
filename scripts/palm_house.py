"""Cyclide palm house: crescent glass vaults round a domed central pavilion.

This script builds the base surface (glass panes as faces) with numpy and
tags its edges; the ironwork is built on it by Geometry Nodes, so the
members stay adjustable.

Wings: one band of a Dupin cyclide (a, c, d), u around the ring, v around
the tube. Both families of parameter lines are circles (lines of curvature)
and every (u, v) quad is planar, so the panes are flat glass:
    x = (d (c - a cos u cos v) + b^2 cos u) / (a - c cos u cos v)
    y =  b sin u (a - d cos v)              / (a - c cos u cos v)
    z =  b sin v (c cos u - d)              / (a - c cos u cos v),  b^2 = a^2 - c^2
v in [pi, 2 pi] is the upper half of the tube. The tube is fattest at u = pi
(the pavilion) and tapers to the wing ends. Each wing is trimmed exactly
where it meets the drum cylinder; only that row of panes is cut to fit.

Dome: top of a spindle torus (meridian circles of radius rr centred Rs beyond
the axis), on a glazed drum opened where the wings come in.

Edge attributes (int 0/1): "rib" (u = const arches), "purlin" (v = const),
"ring" (drum and dome horizontals), "meridian" (drum and dome verticals),
"seam" (wing or porch against drum), "mullion" and "transom" (gable and porch
walls), "sill" (ground edges that stand on the brick plinth), "ridge" (crown
lines and the drum cornice that carry cresting).
Loose vertices mark ornament: point attribute "orn" (1 finial, 2 lantern,
3 console) and "orn_dir" (outward direction for consoles).
Face attribute "part": 0 wing, 1 drum, 2 dome, 3 door, 4 gable and porch glass.

Local frame: dome axis at the origin, the crescent opens toward +X.

Run inside Blender:
    exec(open(bpy.path.abspath('//scripts/palm_house.py')).read())
"""
import bpy
import bmesh
import math
import numpy as np

SITE = (-110.0, -130.0)      # keep in step with environment.py FLAT_SITES
FACING_DEG = 90.0            # object Z rotation; the open side faces +X locally

A, C, D = 18.0, 3.0, 4.5     # cyclide
WING_END = 1.6               # radians from u = pi
RIBS_PER_WING = 18           # rib spacing along the wing (ribs inside the drum are dropped)
PANES_PER_RIB = 14           # around each half-circle arch
DRUM_R, DRUM_H = 9.0, 7.5
DRUM_SEGMENTS, DRUM_ROWS = 48, 5
DOME_H, DOME_ROWS = 9.0, 10
PLINTH = 0.8
TAGS = ("rib", "purlin", "ring", "meridian", "seam", "mullion", "transom", "sill", "ridge")
# ornament points (loose vertices with attribute "orn"): 1 finial, 2 lantern, 3 console
ORN_FINIAL, ORN_LANTERN, ORN_CONSOLE = 1, 2, 3
LANTERN_R = 1.5          # lantern prototype radius 1.0 x Lantern Scale in palm_house_iron
# entrance porch on the open side (+X): half-cylinder roof springing from glazed walls
PORCH_W, PORCH_SPRING, PORCH_END = 2.6, 3.4, 14.0     # half width, spring height, outer end x
DOOR_H, WING_DOOR_W, PORCH_DOOR_W = 3.0, 2.4, 1.8
MULLION = 0.75                                          # target mullion spacing on gables


def cyclide(u, v, a=A, c=C, d=D):
    b2 = a * a - c * c
    b = math.sqrt(b2)
    den = a - c * np.cos(u) * np.cos(v)
    return np.stack([(d * (c - a * np.cos(u) * np.cos(v)) + b2 * np.cos(u)) / den,
                     b * np.sin(u) * (a - d * np.cos(v)) / den,
                     b * np.sin(v) * (c * np.cos(u) - d) / den], -1)


# the u = pi rib circle is centred on the x axis: put that centre at the origin
X_SHIFT = -0.5 * (cyclide(np.pi, 0.0)[0] + cyclide(np.pi, np.pi)[0])


def wing_point(u, v):
    p = cyclide(u, v)
    p[..., 0] += X_SHIFT
    p[..., 2] += PLINTH
    return p


def trim_u(v, side, steps=40):
    """u on this wing where the point at tube angle v crosses the drum wall."""
    lo = np.full_like(v, np.pi)                       # inside the drum
    hi = np.full_like(v, np.pi + side * WING_END)     # outside
    for _ in range(steps):
        mid = 0.5 * (lo + hi)
        inside = np.hypot(*wing_point(mid, v)[..., :2].T) < DRUM_R
        lo = np.where(inside, mid, lo)
        hi = np.where(inside, hi, mid)
    return 0.5 * (lo + hi)


class MeshBuilder:
    def __init__(self):
        self.verts, self.faces, self.part = [], [], []
        self.edge_tags = {}            # (i, j) sorted -> set of tag names
        self.orn = []                  # (vertex index, kind, direction)

    def add_grid(self, P, part, tag_i, tag_j):
        """P: (ni, nj, 3). Edges along j (i fixed) get tag_i, edges along i get tag_j."""
        ni, nj = P.shape[:2]
        base = len(self.verts)
        self.verts.extend(P.reshape(-1, 3))
        idx = lambda i, j: base + i * nj + j
        for i in range(ni - 1):
            for j in range(nj - 1):
                self.faces.append((idx(i, j), idx(i + 1, j), idx(i + 1, j + 1), idx(i, j + 1)))
                self.part.append(part)
        for i in range(ni):
            for j in range(nj - 1):
                self.tag(idx(i, j), idx(i, j + 1), tag_i)
        for i in range(ni - 1):
            for j in range(nj):
                self.tag(idx(i, j), idx(i + 1, j), tag_j)
        return base

    def tag(self, a, b, name):
        self.edge_tags.setdefault((min(a, b), max(a, b)), set()).add(name)

    def ornament(self, kind, point, direction=(1.0, 0.0, 0.0)):
        self.orn.append((len(self.verts), kind, direction))
        self.verts.append(np.asarray(point, float))


def wing(mb, side):
    v = np.linspace(np.pi, 2 * np.pi, PANES_PER_RIB + 1)
    if side < 0:
        v = v[::-1]                    # mirror the winding so both wings face outward
    ut = trim_u(v, side)               # the seam with the drum
    u_ribs = np.pi + side * np.linspace(0.0, WING_END, RIBS_PER_WING + 1)
    edge = ut.max() if side > 0 else ut.min()
    kept = [u for u in u_ribs if side * (u - edge) > 1e-6]
    U = np.array([ut] + [np.full_like(v, u) for u in kept])
    P = wing_point(U, np.broadcast_to(v, U.shape))
    base = mb.add_grid(P, 0, "rib", "purlin")
    ni, nj = P.shape[:2]
    for j in range(nj - 1):
        mb.tag(base + j, base + j + 1, "seam")
    for i in range(ni - 1):                         # both feet of the vault stand on the plinth
        for j in (0, nj - 1):
            mb.tag(base + i * nj + j, base + (i + 1) * nj + j, "sill")
        jr = nj // 2                                 # the crown line (v = 3 pi / 2)
        mb.tag(base + i * nj + jr, base + (i + 1) * nj + jr, "ridge")
    # gable at the wing end: the last rib's plane
    pa, pb = P[-1, 0], P[-1, -1]
    centre = 0.5 * (pa + pb)
    centre[2] = 0.0
    e1 = (pb - pa) / np.linalg.norm(pb - pa)
    r_end = 0.5 * np.linalg.norm(pb - pa)
    gable(mb, centre, e1, r_end, PLINTH, WING_DOOR_W)
    mb.ornament(ORN_FINIAL, centre + np.array([0.0, 0.0, PLINTH + r_end + 0.05]))   # off the vertex below: not merged


def gable(mb, centre, e1, r, spring, door_w):
    """Flat glazed end wall: a semicircle of radius r springing at height
    `spring`, standing on the plinth, with a door of width door_w at the
    centre that runs down to the ground. centre is at ground level, e1 the
    horizontal direction across the wall."""
    up = np.array([0.0, 0.0, 1.0])
    n = max(4, int(round(2 * r / MULLION)))
    xs = np.unique(np.round(np.r_[np.linspace(-r, r, n + 1), -door_w / 2, door_w / 2], 6))
    xs = xs[(xs >= -r) & (xs <= r)]
    top = spring + np.sqrt(np.maximum(r * r - xs ** 2, 0.0))
    P = lambda x, z: centre + e1 * x + up * z
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        is_door = x0 >= -door_w / 2 - 1e-6 and x1 <= door_w / 2 + 1e-6
        bottom = 0.0 if is_door else PLINTH
        m0, m1 = min(DOOR_H, top[i]), min(DOOR_H, top[i + 1])
        base = len(mb.verts)
        mb.verts.extend([P(x0, bottom), P(x1, bottom), P(x1, m1), P(x0, m0)])
        mb.faces.append((base, base + 1, base + 2, base + 3))
        mb.part.append(3 if is_door else 4)
        mb.tag(base, base + 3, "mullion")
        mb.tag(base + 1, base + 2, "mullion")
        mb.tag(base + 3, base + 2, "transom")
        if not is_door:
            mb.tag(base, base + 1, "sill")
        if top[i] > DOOR_H + 1e-6 or top[i + 1] > DOOR_H + 1e-6:
            b2 = len(mb.verts)
            mb.verts.extend([P(x0, m0), P(x1, m1), P(x1, top[i + 1]), P(x0, top[i])])
            mb.faces.append((b2, b2 + 1, b2 + 2, b2 + 3))
            mb.part.append(4)
            mb.tag(b2, b2 + 3, "mullion")
            mb.tag(b2 + 1, b2 + 2, "mullion")


def porch(mb):
    """Glazed vestibule on +X: walls at y = +-PORCH_W, half-cylinder roof, a
    gable with a door at x = PORCH_END, trimmed exactly against the drum."""
    w, s = PORCH_W, PORCH_SPRING
    theta = np.linspace(0.0, np.pi, 11)
    y = w * np.cos(theta)
    z = s + w * np.sin(theta)
    x_seam = np.sqrt(DRUM_R ** 2 - y ** 2)
    n_ribs = int(round((PORCH_END - x_seam.max()) / 0.9))
    x_ribs = np.linspace(x_seam.max(), PORCH_END, n_ribs + 1)[1:]
    X = np.array([x_seam] + [np.full_like(y, xr) for xr in x_ribs])
    Pr = np.stack([X, np.broadcast_to(y, X.shape), np.broadcast_to(z, X.shape)], -1)
    base = mb.add_grid(Pr, 4, "rib", "purlin")
    nj = Pr.shape[1]
    for j in range(nj - 1):
        mb.tag(base + j, base + j + 1, "seam")
    for i in range(Pr.shape[0] - 1):
        mb.tag(base + i * nj + nj // 2, base + (i + 1) * nj + nj // 2, "ridge")
    mb.ornament(ORN_FINIAL, (PORCH_END, 0.0, s + w + 0.05))
    # side walls, one column per roof rib
    for side in (1.0, -1.0):
        xw = np.r_[math.sqrt(DRUM_R ** 2 - w * w), x_ribs]
        Zw = np.array([PLINTH, s])
        XX, ZZ = np.meshgrid(xw, Zw, indexing='ij')
        Pw = np.stack([XX, np.full_like(XX, side * w), ZZ], -1)
        if side < 0:
            Pw = Pw[:, ::-1]
        b = mb.add_grid(Pw, 4, "mullion", "transom")
        nj = Pw.shape[1]
        jb = 0 if side > 0 else nj - 1
        for i in range(Pw.shape[0] - 1):
            mb.tag(b + i * nj + jb, b + (i + 1) * nj + jb, "sill")
    gable(mb, np.array([PORCH_END, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), w, s, PORCH_DOOR_W)


def in_porch(points):
    """True for points inside the porch volume (opens the drum wall)."""
    y, z = points[:, 1], points[:, 2]
    roof = PORCH_SPRING + np.sqrt(np.maximum(PORCH_W ** 2 - y ** 2, 0.0))
    return (points[:, 0] > 0) & (np.abs(y) < PORCH_W + 1e-3) & (z < roof + 1e-3)


def drum(mb):
    phi = np.linspace(0, 2 * np.pi, DRUM_SEGMENTS + 1)
    z = np.linspace(PLINTH, PLINTH + DRUM_H, DRUM_ROWS + 1)
    F, Z = np.meshgrid(phi, z, indexing='ij')
    P = np.stack([DRUM_R * np.cos(F), DRUM_R * np.sin(F), Z], -1)
    base = mb.add_grid(P, 1, "meridian", "ring")
    nj = P.shape[1]
    for i in range(P.shape[0] - 1):
        mb.tag(base + i * nj, base + (i + 1) * nj, "sill")
        mb.tag(base + i * nj + nj - 1, base + (i + 1) * nj + nj - 1, "ridge")
    # consoles under the cornice on the main meridians that stay clear of wings and porch
    top = PLINTH + DRUM_H
    for k in range(0, DRUM_SEGMENTS, 4):
        a = 2 * np.pi * k / DRUM_SEGMENTS
        out = np.array([np.cos(a), np.sin(a), 0.0])
        p = out * DRUM_R + np.array([0.0, 0.0, top])
        probe = p + out * 0.3 - np.array([0.0, 0.0, 0.6])
        if not inside_wings(probe[None])[0] and not in_porch(probe[None])[0]:
            mb.ornament(ORN_CONSOLE, p + out * 0.03, out)


def dome(mb):
    Rs = (DOME_H ** 2 - DRUM_R ** 2) / (2 * DRUM_R)
    rr = Rs + DRUM_R
    phi = np.linspace(0, 2 * np.pi, DRUM_SEGMENTS + 1)
    t = np.linspace(0, math.asin(DOME_H / rr), DOME_ROWS + 1)
    F, T = np.meshgrid(phi, t, indexing='ij')
    X = rr * np.cos(T) - Rs
    P = np.stack([X * np.cos(F), X * np.sin(F), rr * np.sin(T) + PLINTH + DRUM_H], -1)
    mb.add_grid(P, 2, "meridian", "ring")
    # lantern seat: where the dome's radius has shrunk to the lantern's
    t_seat = math.acos((LANTERN_R + Rs) / rr)
    mb.ornament(ORN_LANTERN, (0.0, 0.0, rr * math.sin(t_seat) + PLINTH + DRUM_H))


def inside_wings(points):
    """True for points inside either wing's tube (opens the drum wall)."""
    us = np.linspace(np.pi - WING_END, np.pi + WING_END, 400)
    cen = 0.5 * (wing_point(us, np.full_like(us, np.pi)) + wing_point(us, np.zeros_like(us)))
    rad = np.linalg.norm(wing_point(us, np.full_like(us, 1.5 * np.pi)) - cen, axis=1)
    out = np.zeros(len(points), bool)
    for n, p in enumerate(points):
        dist = np.linalg.norm(cen - p, axis=1)
        k = dist.argmin()
        out[n] = dist[k] < rad[k]
    return out


def build_mesh():
    mb = MeshBuilder()
    wing(mb, 1.0)
    wing(mb, -1.0)
    porch(mb)
    drum(mb)
    dome(mb)
    V = np.array(mb.verts)
    faces, part = [], []
    for f, pt in zip(mb.faces, mb.part):
        if pt == 1 and (inside_wings(V[list(f)]).all() or in_porch(V[list(f)]).all()):
            continue                   # opening where a wing or the porch enters the drum
        faces.append(f)
        part.append(pt)
    me = bpy.data.meshes.get("Palm_House_Surface") or bpy.data.meshes.new("Palm_House_Surface")
    me.clear_geometry()
    me.from_pydata(V.tolist(), [], faces)
    me.update()
    bm = bmesh.new()
    bm.from_mesh(me)
    for name in TAGS:                  # tag before merging: keys are the original indices
        lay = bm.edges.layers.int.new(name)
        for e in bm.edges:
            key = tuple(sorted(v.index for v in e.verts))
            e[lay] = 1 if name in mb.edge_tags.get(key, ()) else 0
    orn = bm.verts.layers.int.new("orn")
    orn_dir = bm.verts.layers.float_vector.new("orn_dir")
    bm.verts.ensure_lookup_table()
    for vi, kind, direction in mb.orn:
        bm.verts[vi][orn] = kind
        bm.verts[vi][orn_dir] = direction
    pl = bm.faces.layers.int.new("part")
    for f, p in zip(bm.faces, part):
        f[pl] = p
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)   # close the drum/dome seams
    bmesh.ops.dissolve_degenerate(bm, dist=1e-4, edges=bm.edges)
    bm.to_mesh(me)
    bm.free()
    return me


me = build_mesh()
coll = bpy.data.collections.get("Palm_House")
if coll is None:
    coll = bpy.data.collections.new("Palm_House")
    bpy.context.scene.collection.children.link(coll)
obj = bpy.data.objects.get("Palm_House")
if obj is None:
    obj = bpy.data.objects.new("Palm_House", me)
    coll.objects.link(obj)
obj.data = me
for m in list(obj.modifiers):          # the first draft built the massing in a nodes modifier
    if m.type == 'NODES' and m.node_group and m.node_group.name == "GN_Palm_House":
        obj.modifiers.remove(m)
obj.location = (SITE[0], SITE[1], 0.0)
obj.rotation_euler = (0.0, 0.0, math.radians(FACING_DEG))
