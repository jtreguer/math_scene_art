"""Visitors for scale round the palm house: linked copies of the imported figures.

Positions follow the path layout of palm_house_site.py: a couple walking in
along the path, a lady at the round bed, and two men on the terrace, one
walking to the porch, one by the east wing door.

Run inside Blender after figure_assets.py's models are in the file:
    exec(open(bpy.path.abspath('//scripts/palm_house_figures.py')).read())
"""
import bpy
import numpy as np

FA = {}
exec(open(bpy.path.abspath('//scripts/figure_assets.py')).read(), FA)
SITE = {}
exec(open(bpy.path.abspath('//scripts/palm_house_site.py')).read().split(
    "\ngravel, beds, BED_INFO = build_fields()")[0], SITE)
place = FA['place']
MAN, WOMAN = "Asset_Gentleman_Victorian", "Asset_Woman_Victorian"


def on_path(t, across=0.0):
    """Point on the site path's Bezier at parameter t, `across` metres to its left."""
    a, b, c = (np.array(p) for p in (SITE['BED_C'], SITE['PATH_CTRL'], SITE['PATH_END']))
    p = (1 - t) ** 2 * a + 2 * t * (1 - t) * b + t ** 2 * c
    d = 2 * (1 - t) * (b - a) + 2 * t * (c - b)
    d /= np.linalg.norm(d)
    left = np.array([-d[1], d[0]])
    q = p + across * left
    return (float(q[0]), float(q[1]), 0.0), d


def ahead(p, d, dist):
    return (p[0] + d[0] * dist, p[1] + d[1] * dist)


# couple walking in, toward the house (against the path direction)
p, d = on_path(0.25, -0.35)
place(MAN, "PH_Figure_Gentleman_A", p, ahead(p, d, -10.0))
p, d = on_path(0.25, 0.35)
place(WOMAN, "PH_Figure_Lady_A", p, ahead(p, d, -10.0))
# man on the terrace walking toward the porch
place(MAN, "PH_Figure_Gentleman_B", (-102.5, SITE['TERRACE_Y'] - 0.4, 0.0), (-110.0, SITE['TERRACE_Y'] - 0.4))
# lady on the ring looking at the bed
c, r = SITE['BED_C'], (SITE['BED_R'] + SITE['RING_R']) / 2
place(WOMAN, "PH_Figure_Lady_B", (c[0] + r * 0.8, c[1] + r * 0.6, 0.0), c)
# gentleman on the terrace by the east wing door, facing the round bed
place(MAN, "PH_Figure_Gentleman_C", (-95.0, SITE['TERRACE_Y'], 0.0), c)
