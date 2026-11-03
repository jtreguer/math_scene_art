"""Period looks made from the photoreal render: albumen print and engraving.

albumen(src, dst)
    1890s photograph. Plates of the time were sensitive to blue light only, so
    the tone is taken mostly from the blue channel: the sky prints near white,
    red iron and green grass print dark. Then sepia/purple toning, lens
    softness and fall-off toward the edges, paper grain and a card mount.

engraving_data(dst)
    Renders a data image with Freestyle: R = line ink for the tower and the
    figures (grass and leaves would only make noise), G = sky mask.

engraving(src_photo, src_data, dst)
    Freestyle lines plus hatching built from the photo's tones: diagonal
    hatching with cross-hatching in the darks, ruled horizontal lines in the
    sky, as in a steel engraving.

Run inside Blender (numpy is bundled):
    exec(open(bpy.path.abspath('//scripts/period_looks.py')).read())
"""
import bpy
import numpy as np


# --- image io (values as stored in the file, rows bottom-up as Blender keeps them) ---
def load(path):
    img = bpy.data.images.load(path, check_existing=False)
    img.colorspace_settings.name = 'Non-Color'
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)[..., :3].copy()


def save(rgb, path):
    h, w = rgb.shape[:2]
    img = bpy.data.images.new("tmp_out", w, h, alpha=False, float_buffer=True, is_data=True)
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[..., :3] = np.clip(rgb, 0.0, 1.0)
    img.pixels.foreach_set(rgba.ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)
    return path


# --- small numpy helpers --------------------------------------------------------------
def box_blur(a, r, axis):
    if r < 1:
        return a
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r + 1, r)
    c = np.cumsum(np.pad(a, pad, mode='edge'), axis=axis, dtype=np.float64)
    hi = np.take(c, np.arange(2 * r + 1, c.shape[axis]), axis=axis)
    lo = np.take(c, np.arange(0, c.shape[axis] - 2 * r - 1), axis=axis)
    return ((hi - lo) / (2 * r + 1)).astype(np.float32)


def blur(a, radius):
    """Approximate Gaussian: three box passes per axis."""
    r = max(1, int(radius / 1.7))
    for _ in range(3):
        a = box_blur(box_blur(a, r, 0), r, 1)
    return a


def radius_map(h, w):
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    return np.hypot((x - w / 2) / (w / 2), (y - h / 2) / (h / 2)) / np.sqrt(2)


def tone_ramp(t, stops):
    """Map a 0-1 tone through colour stops [(pos, (r, g, b)), ...]."""
    pos = np.array([p for p, _ in stops], dtype=np.float32)
    out = np.empty(t.shape + (3,), dtype=np.float32)
    for c in range(3):
        out[..., c] = np.interp(t, pos, [col[c] for _, col in stops])
    return out


# --- albumen print ----------------------------------------------------------------------
def albumen(src, dst, seed=1896):
    rgb = load(src)
    h, w = rgb.shape[:2]
    rng = np.random.default_rng(seed)
    # blue-sensitive plate
    t = rgb @ np.array([0.04, 0.24, 0.72], dtype=np.float32)
    t = np.clip((t - 0.05) / 0.62, 0.0, 1.0) ** 0.85       # sky and clouds burn out
    # lens: softer and darker toward the corners
    r = radius_map(h, w)
    soft = blur(t, 4.0)
    k = np.clip((r - 0.35) / 0.6, 0.0, 1.0) ** 1.5
    t = t * (1 - k) + soft * k
    t = t * (1.0 - 0.45 * r ** 2.2)
    # emulsion and paper grain, slightly clumped
    grain = blur(rng.normal(0.0, 1.0, (h, w)).astype(np.float32), 1.2)
    t = np.clip(t + grain * 0.035, 0.0, 1.0)
    # albumen tone: purple-brown shadows, warm mid-tones, cream highlights
    print_rgb = tone_ramp(t, [(0.0, (0.16, 0.09, 0.08)),
                              (0.35, (0.38, 0.24, 0.17)),
                              (0.7, (0.74, 0.58, 0.40)),
                              (1.0, (0.95, 0.89, 0.74))])
    # faded highlights: albumen paper never reaches pure white
    print_rgb = 0.04 + 0.92 * print_rgb
    # card mount with a thin gold-ish rule
    m = int(0.035 * h)
    card = np.array([0.86, 0.82, 0.72], dtype=np.float32)
    out = np.broadcast_to(card, rgb.shape).copy()
    out[m:h - m, m:w - m] = print_rgb[m:h - m, m:w - m]
    rule = np.array([0.55, 0.45, 0.28], dtype=np.float32)
    g = m - 10
    out[g:g + 3, g:w - g] = rule
    out[h - g - 3:h - g, g:w - g] = rule
    out[g:h - g, g:g + 3] = rule
    out[g:h - g, w - g - 3:w - g] = rule
    return save(out, dst)


# --- engraving data render ------------------------------------------------------------
def engraving_data(dst, line_px=1.1, creases=False):
    scene = bpy.context.scene
    vl = bpy.context.view_layer
    # collection holding only what gets ink lines
    ink = bpy.data.collections.get("Ink_Lines")
    if ink is None:
        ink = bpy.data.collections.new("Ink_Lines")
        scene.collection.children.link(ink)
    for name in ["Shukhov_Lattice"] + [o.name for o in bpy.data.collections["Figures"].objects]:
        obj = bpy.data.objects[name]
        if obj.name not in ink.objects:
            ink.objects.link(obj)

    fs = vl.freestyle_settings
    fs.as_render_pass = True
    fs.crease_angle = 2.4                     # about 137 degrees
    ls = fs.linesets[0] if len(fs.linesets) else fs.linesets.new("Ink")
    ls.name = "Ink"
    ls.select_by_visibility = True
    ls.select_by_edge_types = True
    ls.select_by_collection = True
    ls.collection = ink
    ls.select_silhouette = ls.select_border = True
    # creases would outline every corner of every angle iron and blacken the lattice
    ls.select_crease = creases
    ls.select_external_contour = True
    style = bpy.data.linestyles.get("LS_Engraving") or bpy.data.linestyles.new("LS_Engraving")
    ls.linestyle = style
    style.color = (0.0, 0.0, 0.0)
    style.thickness = line_px * scene.render.resolution_x / 3000.0
    scene.render.use_freestyle = True
    scene.render.line_thickness_mode = 'ABSOLUTE'

    # compositor: R = line alpha, G = sky mask
    comp = bpy.data.node_groups.get("Comp_Engraving_Data") or \
        bpy.data.node_groups.new("Comp_Engraving_Data", 'CompositorNodeTree')
    comp.nodes.clear()
    comp.interface.clear()
    comp.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    N, L = comp.nodes, comp.links
    rl = N.new('CompositorNodeRLayers')
    rl.scene = scene
    sep = N.new('CompositorNodeSeparateColor')
    L.new(rl.outputs['Freestyle'], sep.inputs[0])
    sky = N.new('ShaderNodeMath')
    sky.operation = 'GREATER_THAN'
    sky.inputs[1].default_value = 1.0e4
    L.new(rl.outputs['Depth'], sky.inputs[0])
    comb = N.new('CompositorNodeCombineColor')
    L.new(sep.outputs['Alpha'], comb.inputs[0])
    L.new(sky.outputs[0], comb.inputs[1])
    out = N.new('NodeGroupOutput')
    L.new(comb.outputs[0], out.inputs[0])

    photo_comp = scene.compositing_node_group
    vt, look = scene.view_settings.view_transform, scene.view_settings.look
    samples = scene.cycles.samples
    scene.compositing_node_group = comp
    scene.view_settings.view_transform = 'Standard'   # keep the masks as plain data
    scene.cycles.samples = 16                            # only masks are needed
    scene.render.filepath = dst
    # Freestyle builds its view map from every face in the scene, whatever the
    # lineset selects; the grass and leaf cards make that crawl, so hide them.
    # Their tones come from the photo anyway.
    # (A first run with them visible ran out of 31 GB of RAM and was killed.)
    heavy = [bpy.data.objects[n] for n in ("Lawn_Grass", "Tree_Belt") if n in bpy.data.objects]
    for o in heavy:
        o.hide_render = True
    # the ground only has to block the sky mask here, so a coarse grid will do
    ground_res = None
    gmod = bpy.data.objects["Ground"].modifiers.get("Ground_Terrain")
    if gmod is not None:
        for item in gmod.node_group.interface.items_tree:
            if item.item_type == 'SOCKET' and item.in_out == 'INPUT' and item.name == "Vertices":
                ground_res = getattr(gmod.properties.inputs, item.identifier)
        if ground_res is not None:
            full_res, ground_res.value = ground_res.value, 81
            gmod.id_data.update_tag()
    try:
        bpy.ops.render.render(write_still=True)
    finally:
        for o in heavy:
            o.hide_render = False
        if ground_res is not None:
            ground_res.value = full_res
            gmod.id_data.update_tag()
        scene.compositing_node_group = photo_comp
        scene.view_settings.view_transform, scene.view_settings.look = vt, look
        scene.cycles.samples = samples
        scene.render.use_freestyle = False
    return dst


# --- engraving --------------------------------------------------------------------------
def engraving(src_photo, src_data, dst, period=7.0):
    rgb = load(src_photo)
    data = load(src_data)
    h, w = rgb.shape[:2]
    lines, sky = data[..., 0], data[..., 1] > 0.5
    tone = rgb @ np.array([0.30, 0.55, 0.15], dtype=np.float32)
    tone = blur(np.clip((tone - 0.02) / 0.7, 0, 1), 1.2) ** 0.6   # engravings are mostly paper
    # the data render hides the trees, so keep as sky only what is also blue
    # and fairly bright in the photo
    sky &= (rgb[..., 2] > rgb[..., 1]) & (tone > 0.55)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)

    def stroke(angle_deg, per, cover):
        """Anti-aliased line screen; `cover` (0-1) sets how wide each line swells."""
        a = np.radians(angle_deg)
        phase = (x * np.cos(a) + y * np.sin(a)) / per
        dist = np.abs(phase - np.floor(phase) - 0.5) * 2.0 * per / 2   # px from line centre
        half = np.clip(cover, 0, 1) * per / 2
        return np.clip(half - dist + 0.5, 0.0, 1.0)

    dark = 1.0 - tone
    # land and objects: 45 degree hatch, cross-hatch only in the deep darks
    ink = stroke(45, period, dark * 0.7)
    ink = np.maximum(ink, stroke(-45, period, (dark - 0.55) * 1.2))
    # sky: ruled horizontal lines that thin out to nothing in the clouds
    sky_ink = stroke(90, period * 0.75, np.clip(dark - 0.08, 0, 1) * 0.8)
    ink = np.where(sky, sky_ink, ink)
    ink = np.maximum(ink, np.clip(lines * 1.3, 0, 1))
    paper = np.array([0.94, 0.92, 0.86], dtype=np.float32)
    inkc = np.array([0.10, 0.09, 0.09], dtype=np.float32)
    out = paper * (1 - ink[..., None]) + inkc * ink[..., None]
    return save(out, dst)
