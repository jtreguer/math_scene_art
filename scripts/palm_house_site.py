"""Grounds of the palm house: gravel apron, terrace and path, flower beds.

The layout is drawn as two signed distance fields (metres, positive inside)
over a rectangle round the house and saved as an EXR in textures/:
    R  gravel: the whole interior (under Palm_House_Floor, so no lawn grows
       through the floor), an apron along the plinth, a terrace linking the three doors,
       the porch walk, a ring round the central bed, and a path curving
       out under CAM_PalmHouse toward the main park path
    G  flower beds: a round bed on the axis and two beds following the inner
       curve of the wings, kept at least BED_CLEARANCE of lawn from gravel
Values are stored plus SD_OFFSET so that sampling outside the image (which
returns 0) reads as far from everything. The ground material, the lawn
scatter (environment.py) and the bedding scatter all sample this image.

The last stretch of path, from PATH_END east to the tower's path, lies outside
the image and is drawn analytically in environment.py (SITE_PATH_LINK).

Run inside Blender after palm_house.py:
    exec(open(bpy.path.abspath('//scripts/palm_house_site.py')).read())
"""
import bpy
import numpy as np

MASK_FILE = "//textures/palm_house_site_mask.exr"
MASK_IMAGE = "Palm_House_Site_Mask"
# image rectangle in world metres and its resolution
X0, X1, Y0, Y1 = -136.0, -60.0, -144.0, -56.0
PX = 0.05
SD_OFFSET = 10.0
SD_CLAMP = 8.0
PAD = 3.0                     # distances are exact this far beyond each shape

APRON_W = 1.6                 # gravel out from the plinth line
TERRACE_Y, TERRACE_HW = -108.0, 1.6
TERRACE_X = (-132.5, -87.5)     # the outer corners of the wing gables
PORCH_DOOR = (-110.0, -116.0)
WALK_HW = 1.4                 # porch walk
BED_C, BED_R, RING_R = (-110.0, -99.0), 3.2, 5.4    # round bed and its gravel ring
PATH_HW = 1.3
# quadratic Bezier from the ring to PATH_END; it passes under CAM_PalmHouse, so the
# camera stands on the path and it leads from the bottom of the frame to the bed
PATH_CTRL, PATH_END = (-86.0, -63.5), (-66.0, -60.0)
BED_HW = 0.8                  # half width of the curved wing beds
BED_CLEARANCE = 1.0           # lawn between any bed and the gravel


def grid():
    xs = np.arange(X0 + PX / 2, X1, PX)
    ys = np.arange(Y0 + PX / 2, Y1, PX)
    return xs, ys


def capsules(field, xs, ys, segs, hw):
    """field = max(field, hw - distance to each segment), within PAD of it."""
    for (ax, ay), (bx, by) in segs:
        lo_x, hi_x = min(ax, bx) - hw - PAD, max(ax, bx) + hw + PAD
        lo_y, hi_y = min(ay, by) - hw - PAD, max(ay, by) + hw + PAD
        i0, i1 = np.searchsorted(xs, [lo_x, hi_x])
        j0, j1 = np.searchsorted(ys, [lo_y, hi_y])
        if i0 >= i1 or j0 >= j1:
            continue
        px = xs[i0:i1][None, :] - ax
        py = ys[j0:j1][:, None] - ay
        dx, dy = bx - ax, by - ay
        t = np.clip((px * dx + py * dy) / max(dx * dx + dy * dy, 1e-12), 0.0, 1.0)
        d = np.hypot(px - t * dx, py - t * dy)
        np.maximum(field[j0:j1, i0:i1], hw - d, out=field[j0:j1, i0:i1])


def polyline(points):
    return list(zip(points[:-1], points[1:]))


def bezier(a, b, c, n=80):
    t = np.linspace(0.0, 1.0, n)[:, None]
    a, b, c = (np.array(p) for p in (a, b, c))
    return [tuple(p) for p in (1 - t) ** 2 * a + 2 * t * (1 - t) * b + t ** 2 * c]


def sill_segments():
    """Plinth line of the house in world XY, from its "sill" edges."""
    ph = bpy.data.objects["Palm_House"]
    me = ph.data
    mw = np.array(ph.matrix_world)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = np.c_[co.reshape(-1, 3), np.ones(len(me.vertices))] @ mw.T
    ev = np.empty(len(me.edges) * 2, dtype=np.int64)
    me.edges.foreach_get('vertices', ev)
    sill = np.empty(len(me.edges), dtype=np.int64)
    me.attributes['sill'].data.foreach_get('value', sill)
    seg = co[ev.reshape(-1, 2)[sill.astype(bool)]][:, :, :2]
    return [(tuple(a), tuple(b)) for a, b in seg]


def floor_inside(xs, ys):
    """True on pixels under Palm_House_Floor (the house interior)."""
    fl = bpy.data.objects["Palm_House_Floor"]
    me = fl.data
    me.calc_loop_triangles()
    mw = np.array(fl.matrix_world)
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = (np.c_[co.reshape(-1, 3), np.ones(len(me.vertices))] @ mw.T)[:, :2]
    tri = np.empty(len(me.loop_triangles) * 3, dtype=np.int64)
    me.loop_triangles.foreach_get('vertices', tri)
    inside = np.zeros((len(ys), len(xs)), dtype=bool)
    for a, b, c in co[tri.reshape(-1, 3)]:
        lo, hi = np.minimum(np.minimum(a, b), c), np.maximum(np.maximum(a, b), c)
        i0, i1 = np.searchsorted(xs, [lo[0], hi[0]])
        j0, j1 = np.searchsorted(ys, [lo[1], hi[1]])
        if i0 >= i1 or j0 >= j1:
            continue
        px, py = xs[i0:i1][None, :], ys[j0:j1][:, None]
        d = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(d) < 1e-12:
            continue
        l1 = ((b[1] - c[1]) * (px - c[0]) + (c[0] - b[0]) * (py - c[1])) / d
        l2 = ((c[1] - a[1]) * (px - c[0]) + (a[0] - c[0]) * (py - c[1])) / d
        inside[j0:j1, i0:i1] |= (l1 >= 0) & (l2 >= 0) & (l1 + l2 <= 1)
    return inside


def fit_circle(pts):
    """Least-squares circle through 2D points: centre, radius."""
    p = np.asarray(pts)
    A = np.c_[2 * p, np.ones(len(p))]
    sol = np.linalg.lstsq(A, (p ** 2).sum(1), rcond=None)[0]
    c = sol[:2]
    return c, float(np.sqrt(sol[2] + c @ c))


def wing_bed(gravel, xs, ys, sills, side):
    """Arc bed concentric with one wing's inner foot, in the courtyard.

    side +1: the wing at larger x. The arc is offset into the courtyard and
    trimmed to the longest run that keeps BED_CLEARANCE of lawn from gravel.
    """
    cx = BED_C[0]
    inner = [p for s in sills for p in s
             if side * (p[0] - cx) > 4.0 and p[1] > -124.0 and side * (p[0] - cx) < 14.0
             and p[1] < -110.9]
    c, r = fit_circle(inner)
    # the courtyard lies inside the foot circle; 0.25 m spare so the clearance test has room
    rb = r - APRON_W - BED_CLEARANCE - BED_HW - 0.25
    ang = np.linspace(0.0, 2 * np.pi, 720, endpoint=False)
    arc = np.c_[c[0] + rb * np.cos(ang), c[1] + rb * np.sin(ang)]
    # clear of gravel by BED_CLEARANCE beyond the bed's own half width
    i = np.clip(((arc[:, 0] - X0) / PX).astype(int), 0, len(xs) - 1)
    j = np.clip(((arc[:, 1] - Y0) / PX).astype(int), 0, len(ys) - 1)
    ok = gravel[j, i] < -(BED_HW + BED_CLEARANCE)
    ok &= (side * (arc[:, 0] - cx) > 0) & (arc[:, 1] < TERRACE_Y)
    # longest contiguous run (the ring wraps)
    best, run, start, best_start = 0, 0, 0, 0
    for k in range(2 * len(ok)):
        if ok[k % len(ok)]:
            if run == 0:
                start = k
            run += 1
            if run > best and run <= len(ok):
                best, best_start = run, start
        else:
            run = 0
    idx = [(best_start + k) % len(ok) for k in range(best)]
    pts = [tuple(p) for p in arc[idx]]
    return polyline(pts), (tuple(c), r, rb)


def build_fields():
    xs, ys = grid()
    gravel = np.full((len(ys), len(xs)), -SD_CLAMP)
    sills = sill_segments()
    capsules(gravel, xs, ys, sills, APRON_W)
    gravel[floor_inside(xs, ys)] = SD_CLAMP
    capsules(gravel, xs, ys, [((TERRACE_X[0], TERRACE_Y), (TERRACE_X[1], TERRACE_Y))], TERRACE_HW)
    capsules(gravel, xs, ys, [(PORCH_DOOR, (BED_C[0], TERRACE_Y))], WALK_HW)
    capsules(gravel, xs, ys, [((BED_C[0], TERRACE_Y), BED_C)], WALK_HW)
    capsules(gravel, xs, ys, polyline(bezier(BED_C, PATH_CTRL, PATH_END)), PATH_HW)
    d_c = np.hypot(xs[None, :] - BED_C[0], ys[:, None] - BED_C[1])
    np.maximum(gravel, RING_R - d_c, out=gravel)

    beds = np.full_like(gravel, -SD_CLAMP)
    np.maximum(beds, BED_R - d_c, out=beds)
    info = []
    for side in (1, -1):
        segs, circ = wing_bed(gravel, xs, ys, sills, side)
        capsules(beds, xs, ys, segs, BED_HW)
        info.append((side, circ, segs[0][0], segs[-1][1]))
    # beds are cut out of the gravel (the round bed sits inside its ring)
    gravel = np.minimum(gravel, -beds)
    return np.clip(gravel, -SD_CLAMP, SD_CLAMP), np.clip(beds, -SD_CLAMP, SD_CLAMP), info


def save_mask(gravel, beds):
    h, w = gravel.shape
    img = bpy.data.images.get(MASK_IMAGE)
    if img is not None and (img.size[0], img.size[1]) != (w, h):
        bpy.data.images.remove(img)
        img = None
    if img is None:
        img = bpy.data.images.new(MASK_IMAGE, w, h, alpha=False, float_buffer=True)
    px = np.zeros((h, w, 4), dtype=np.float32)
    px[..., 0] = gravel + SD_OFFSET
    px[..., 1] = beds + SD_OFFSET
    px[..., 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    img.file_format = 'OPEN_EXR'
    img.filepath_raw = MASK_FILE
    img.save()
    img.colorspace_settings.is_data = True
    img.source = 'FILE'
    img.filepath = MASK_FILE
    img.reload()
    return img


gravel, beds, BED_INFO = build_fields()
mask_image = save_mask(gravel, beds)
for side, (c, r, rb), a, b in BED_INFO:
    print(f"wing bed {side:+d}: foot circle centre ({c[0]:.2f}, {c[1]:.2f}) r {r:.2f}, bed r {rb:.2f}, "
          f"ends ({a[0]:.1f}, {a[1]:.1f}) ({b[0]:.1f}, {b[1]:.1f})")
