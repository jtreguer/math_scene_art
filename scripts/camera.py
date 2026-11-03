"""Hero camera for the Shukhov tower: level, eye height, shifted lens.

Keeping the camera level and moving the frame up with lens shift keeps the
tower's verticals vertical, as 1890s architectural photographers did with
rising fronts on their view cameras.

Run inside Blender:
    exec(open(bpy.path.abspath('//scripts/camera.py')).read())
"""
import bpy
import math

EYE = (7.0, -70.0, 1.65)     # beside the gravel path, 70 m out
YAW_TARGET = (4.5, 0.0)      # point on the ground the camera faces (puts tower left of centre)
FOCAL = 35.0
SHIFT_Y = 0.155              # fraction of sensor width; horizon near the lower third

cam_data = bpy.data.cameras.get("CAM_Hero") or bpy.data.cameras.new("CAM_Hero")
cam_data.lens = FOCAL
cam_data.sensor_fit = 'HORIZONTAL'
cam_data.sensor_width = 36.0
cam_data.shift_y = SHIFT_Y
cam_data.clip_end = 2000.0

cam = bpy.data.objects.get("CAM_Hero")
if cam is None:
    cam = bpy.data.objects.new("CAM_Hero", cam_data)
    bpy.data.collections["Helpers"].objects.link(cam)
cam.location = EYE
dx, dy = YAW_TARGET[0] - EYE[0], YAW_TARGET[1] - EYE[1]
cam.rotation_euler = (math.pi / 2, 0.0, math.atan2(dy, dx) - math.pi / 2)

scene = bpy.context.scene
scene.camera = cam
scene.render.resolution_x, scene.render.resolution_y = 3000, 2000
