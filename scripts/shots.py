"""Hero shots: camera, sky and grade for each piece, then versioned renders.

Each shot sets the scene camera, turns the world sky to its preset, applies
the matching grade and hides the scatter that only the other shots see
(the two lawn patches are the heavy part of the scene).

Run inside Blender:
    exec(open(bpy.path.abspath('//scripts/shots.py')).read())
    use_shot("palm_house")
    render_version("palm_house_photo", percent=25)
"""
import bpy
import math

exec(open(bpy.path.abspath('//scripts/sky.py')).read())
exec(open(bpy.path.abspath('//scripts/render_setup.py')).read())

SHOTS = {
    # camera from camera.py
    "shukhov": dict(camera="CAM_Hero", sky="shukhov_dusk", grade="dusk",
                    hide=["Lawn_Grass_PalmHouse", "Tree_Park_Framing"]),
    # on the path 60 m north-northeast of the palm house, level, shifted lens
    "palm_house": dict(camera="CAM_PalmHouse", sky="palm_midday", grade="midday",
                       hide=["Lawn_Grass", "Tree_Park_Framing"],
                       eye=(-88.0, -72.0, 1.7), yaw_deg=157.0, focal=35.0, shift_y=0.12),
    # overview of the park from a rise 12 m up, west-northwest of the palm house: its
    # front in three-quarter view on the right, the tower across the lawn on the left.
    # Framing trees: environment.py PARK_TREE_SPOTS (keep the eye and aim in step).
    # Sun turned to azimuth 130, behind the camera's left shoulder (the palm house's 40
    # put it ahead of this camera and washed the view out).
    "park": dict(camera="CAM_Park", sky="palm_midday", grade="midday_wide", sun_azimuth=130.0,
                 hide=["Lawn_Grass", "Lawn_Grass_PalmHouse"],
                 eye=(-210.0, -65.0, 12.0), yaw_deg=-4.0 - 90.0, focal=24.0, shift_y=0.03),
}


def make_camera(shot):
    data = bpy.data.cameras.get(shot["camera"]) or bpy.data.cameras.new(shot["camera"])
    data.lens, data.sensor_fit, data.sensor_width = shot["focal"], 'HORIZONTAL', 36.0
    data.shift_y, data.clip_end = shot["shift_y"], 3000.0
    cam = bpy.data.objects.get(shot["camera"])
    if cam is None:
        cam = bpy.data.objects.new(shot["camera"], data)
        bpy.data.collections["Helpers"].objects.link(cam)
    cam.location = shot["eye"]
    cam.rotation_euler = (math.pi / 2, 0.0, math.radians(shot["yaw_deg"]))
    return cam


def use_shot(name, sun_azimuth=None):
    shot = SHOTS[name]
    cam = make_camera(shot) if "eye" in shot else bpy.data.objects[shot["camera"]]
    scene.camera = cam
    apply_sky(shot["sky"], sun_azimuth if sun_azimuth is not None else shot.get("sun_azimuth"))
    apply_grade(shot["grade"])
    for other in SHOTS.values():
        for obj_name in other["hide"]:
            bpy.data.objects[obj_name].hide_render = obj_name in shot["hide"]
    return cam
