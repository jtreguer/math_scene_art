"""World sky: a Poly Haven pure-sky HDRI turned so its sun lands where wanted.

The sun is found as the brightest pixel of the HDRI. Blender's equirect
mapping puts image column u at azimuth (0.5 - u) * 2 pi (measured from +X
toward +Y), which was checked against the shadow direction in a render. The
Mapping node's Z rotation r moves an image azimuth a to world azimuth a - r.

Each piece has its own sky preset; shots.py picks one per camera.

Run inside Blender:
    exec(open(bpy.path.abspath('//scripts/sky.py')).read())
    apply_sky("palm_midday")
"""
import bpy
import math
import numpy as np

SKIES = {
    # dusk: Belfast sunset, sun ~2 degrees up, set just inside the left of the tower frame
    "shukhov_dusk": dict(hdri="//../_shared/hdris/belfast_sunset_puresky_8k.hdr",
                         image="HDRI_BelfastSunset", sun_azimuth=112.0),
    # midday: Kloofendal partly cloudy, sun 48 degrees up, behind the left shoulder of
    # CAM_PalmHouse (which looks south-southwest). Tried 0 (front in shade), 40, 75 (flat):
    # palm_house_photo_v01-v03.
    "palm_midday": dict(hdri="//../_shared/hdris/kloofendal_48d_partly_cloudy_puresky_8k.hdr",
                        image="HDRI_Kloofendal", sun_azimuth=40.0),
}


def find_sun(image):
    small = image.copy()
    small.scale(1024, 512)
    px = np.empty(1024 * 512 * 4, dtype=np.float32)
    small.pixels.foreach_get(px)
    bpy.data.images.remove(small)
    lum = px.reshape(512, 1024, 4)[..., :3].sum(-1)
    y, x = np.unravel_index(lum.argmax(), lum.shape)
    u, v = (x + 0.5) / 1024, (y + 0.5) / 512
    return (0.5 - u) * 2 * math.pi, (v - 0.5) * math.pi     # azimuth, elevation


def apply_sky(name, sun_azimuth=None):
    """Load the preset's HDRI into the world and turn its sun to the azimuth (degrees)."""
    sky = SKIES[name]
    world = bpy.context.scene.world
    img = bpy.data.images.get(sky["image"]) or bpy.data.images.load(bpy.path.abspath(sky["hdri"]))
    img.name, img.filepath = sky["image"], sky["hdri"]
    nt = world.node_tree
    env = next(n for n in nt.nodes if n.type == 'TEX_ENVIRONMENT')
    env.image = img
    az, elev = find_sun(img)
    target = sky["sun_azimuth"] if sun_azimuth is None else sun_azimuth
    nt.nodes["Sky_Rotation"].inputs['Rotation'].default_value[2] = az - math.radians(target)
    print(f"{name}: sun elevation {math.degrees(elev):.1f} deg, placed at azimuth {target} deg")
    return img
