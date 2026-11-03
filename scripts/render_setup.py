"""Render settings, aerial-perspective mist and versioned renders.

Mist is done in the compositor: the mist pass (0 near, 1 far) blends the
scenery toward the colour of the sky at the horizon. The depth pass masks out
the sky itself, which already carries its own atmosphere. The haze colour is
measured from the HDRI's horizon band so its brightness matches the sky.

Grades (exposure, look, haze) are presets per light; shots.py applies the
right one for each camera.

Run inside Blender (usually through shots.py):
    exec(open(bpy.path.abspath('//scripts/render_setup.py')).read())
    apply_grade("dusk")
    render_version("shukhov_tower_photo", percent=50)
"""
import bpy
import os
import re
import numpy as np

MIST_START = 15.0       # metres from camera where haze begins
MIST_DEPTH = 320.0      # distance over which the mist pass goes 0 -> 1
SAMPLES = 256
GRADES = {
    # Belfast sunset sky, sun 2 degrees up, just left of frame
    "dusk": dict(exposure=-0.9, look='AgX - Medium High Contrast',
                 haze_scale=0.6,         # dusk haze is dimmer than the horizon band it is sampled from
                 mist_strength=0.6),     # haze reached at full mist depth
    # Kloofendal partly cloudy, sun 48 degrees up
    "midday": dict(exposure=-0.4, look='AgX - Medium High Contrast',
                   haze_scale=1.0, mist_strength=0.35),
    # same light over the whole park: subjects at 100-250 m, so a thinner, deeper haze
    "midday_wide": dict(exposure=-0.4, look='AgX - Medium High Contrast',
                        haze_scale=1.0, mist_strength=0.3, mist_start=80.0, mist_depth=900.0),
}

scene = bpy.context.scene
view_layer = bpy.context.view_layer

# --- Cycles on the GPU --------------------------------------------------------------
scene.render.engine = 'CYCLES'
scene.cycles.device = 'GPU'
scene.cycles.samples = SAMPLES
scene.cycles.use_adaptive_sampling = True
scene.cycles.adaptive_threshold = 0.02
scene.cycles.use_denoising = True
try:
    scene.cycles.denoiser = 'OPTIX'
except TypeError:
    pass
scene.render.resolution_x, scene.render.resolution_y = 3000, 2000
scene.render.image_settings.file_format = 'PNG'
scene.render.image_settings.color_depth = '16'
scene.view_settings.view_transform = 'AgX'

# --- mist and depth passes ----------------------------------------------------------
view_layer.use_pass_mist = True
view_layer.use_pass_z = True
mist = scene.world.mist_settings
mist.start, mist.depth, mist.falloff = MIST_START, MIST_DEPTH, 'LINEAR'


def horizon_colour(image, band=(0.50, 0.53)):
    """Mean linear colour of the HDRI between two heights (0.5 = horizon)."""
    small = image.copy()
    small.scale(512, 256)
    px = np.empty(512 * 256 * 4, dtype=np.float32)
    small.pixels.foreach_get(px)
    bpy.data.images.remove(small)
    rows = px.reshape(256, 512, 4)[int(band[0] * 256):int(band[1] * 256), :, :3]
    return tuple(float(c) for c in np.median(rows.reshape(-1, 3), axis=0))


# --- compositor -----------------------------------------------------------------------
def build_compositor(haze_colour, mist_strength):
    comp = bpy.data.node_groups.get("Comp_Mist") or bpy.data.node_groups.new("Comp_Mist", 'CompositorNodeTree')
    comp.nodes.clear()
    comp.interface.clear()
    comp.interface.new_socket("Image", in_out='OUTPUT', socket_type='NodeSocketColor')
    N, L = comp.nodes, comp.links
    rl = N.new('CompositorNodeRLayers')
    rl.scene = scene
    out = N.new('NodeGroupOutput')
    is_geo = N.new('ShaderNodeMath'); is_geo.operation = 'LESS_THAN'
    is_geo.inputs[1].default_value = 1.0e4          # sky depth is effectively infinite
    L.new(rl.outputs['Depth'], is_geo.inputs[0])
    amount = N.new('ShaderNodeMath'); amount.operation = 'MULTIPLY'
    L.new(rl.outputs['Mist'], amount.inputs[0])
    L.new(is_geo.outputs[0], amount.inputs[1])
    strength = N.new('ShaderNodeMath'); strength.operation = 'MULTIPLY'
    strength.inputs[1].default_value = mist_strength
    L.new(amount.outputs[0], strength.inputs[0])
    haze = N.new('CompositorNodeRGB')
    haze.outputs[0].default_value = (*haze_colour, 1.0)
    mix = N.new('ShaderNodeMix'); mix.data_type = 'RGBA'
    L.new(strength.outputs[0], mix.inputs['Factor'])
    L.new(rl.outputs['Image'], next(s for s in mix.inputs if s.name == 'A' and s.enabled))
    L.new(haze.outputs[0], next(s for s in mix.inputs if s.name == 'B' and s.enabled))
    L.new(next(s for s in mix.outputs if s.name == 'Result' and s.enabled), out.inputs[0])
    for i, n in enumerate((rl, is_geo, amount, strength, haze, mix, out)):
        n.location = (i * 220, 0)
    scene.compositing_node_group = comp


def apply_grade(name):
    """Exposure, look and mist haze for a light; call after the sky is set."""
    g = GRADES[name]
    mist.start, mist.depth = g.get("mist_start", MIST_START), g.get("mist_depth", MIST_DEPTH)
    scene.view_settings.exposure = g["exposure"]
    try:
        scene.view_settings.look = g["look"]
    except TypeError:
        pass
    env = next(n for n in scene.world.node_tree.nodes if n.type == 'TEX_ENVIRONMENT')
    haze = tuple(c * g["haze_scale"] for c in horizon_colour(env.image))
    build_compositor(haze, g["mist_strength"])


# --- versioned renders ----------------------------------------------------------------
def render_version(base, percent=50, samples=None):
    """Render to renders/<base>_vNN[_<width>].png without overwriting anything."""
    folder = bpy.path.abspath('//renders')
    os.makedirs(folder, exist_ok=True)
    pat = re.compile(re.escape(base) + r'_v(\d+)')
    taken = [int(m.group(1)) for f in os.listdir(folder) if (m := pat.match(f))]
    version = max(taken, default=0) + 1
    width = scene.render.resolution_x * percent // 100
    suffix = '' if percent == 100 else f'_{width}px'
    path = os.path.join(folder, f'{base}_v{version:02d}{suffix}.png')
    scene.render.resolution_percentage = percent
    if samples:
        scene.cycles.samples = samples
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True)
    scene.render.resolution_percentage = 100
    scene.cycles.samples = SAMPLES
    return path
