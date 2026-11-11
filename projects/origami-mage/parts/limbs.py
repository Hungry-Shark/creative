"""Limbs (v2): hex bell sleeves with gold cuffs, skin mitten hands, stocking legs, layered boots.

Modelled in the rest T-pose (arms along +/-X at Z["arm"]); the rig poses them later, so the
sleeves are designed to also look right when the arm HANGS: narrow upper sleeve, wide bell
from the elbow to the cuff. Everything is built per side with a sign `s` (+1 = character
LEFT / +X, -1 = RIGHT / -X) straight from vertex data; normals are recalculated per object.
Object names are used by the rig for weighting: keep them.
"""
import math

import bpy
from mathutils import Vector

import lib
import spec

Z, X = spec.Z, spec.X
SIDES = ((-1, "R"), (1, "L"))
ARM_Z = Z["arm"]
WRIST = X["wrist"]                 # bottom of the cuff (top edge is DROOP shorter)
DROOP = 0.02
CUFF_TOP = WRIST - DROOP


# ------------------------------------------------------------------ mesh helpers
def _loft_data(rings, cap_start=True, cap_end=True, closed=True):
    n = len(rings[0])
    verts = [tuple(p) for r in rings for p in r]
    faces = []
    seg = n if closed else n - 1
    for r in range(len(rings) - 1):
        for i in range(seg):
            a = r * n + i
            b = r * n + (i + 1) % n
            faces.append((a, b, b + n, a + n))
    if closed and cap_start:
        faces.append(tuple(range(n - 1, -1, -1)))
    if closed and cap_end:
        last = (len(rings) - 1) * n
        faces.append(tuple(range(last, last + n)))
    return verts, faces


def _merge(datas):
    verts, faces = [], []
    for v, f in datas:
        off = len(verts)
        verts += v
        faces += [tuple(i + off for i in face) for face in f]
    return verts, faces


def _obj(name, datas, material, coll):
    v, f = _merge(datas) if isinstance(datas, list) else datas
    return lib.mesh_object(name, v, f, material=material, coll=coll)


def _clamp01(t):
    return max(0.0, min(1.0, t))


# ------------------------------------------------------------------ sleeves
# (x, radius): narrow upper sleeve, an elbow at X["elbow"], then the hanging bell.
# A ring every ~0.05 m so the rig can bend the elbow cleanly.
_E = X["elbow"]
SLEEVE_STATIONS = [
    (0.10, 0.045), (0.15, 0.045), (0.20, 0.046), (0.25, 0.047), (0.30, 0.049),
    (_E - 0.04, 0.053), (_E, 0.058), (_E + 0.04, 0.064), (0.45, 0.075), (0.50, 0.088),
    (0.55, 0.100), (CUFF_TOP, 0.110),
]


def _radius(x):
    st = SLEEVE_STATIONS
    for (x0, r0), (x1, r1) in zip(st, st[1:]):
        if x0 <= x <= x1:
            return r0 + (r1 - r0) * (x - x0) / (x1 - x0)
    return st[-1][1] if x > st[-1][0] else st[0][1]


def _bell_t(x):
    """0 up to the start of the bell, 1 at the cuff: drives the longer bottom side."""
    return _clamp01((x - 0.45) / (CUFF_TOP - 0.45))


def _sleeve_ring(s, x, r, inset=0.0, droop=None, n=6):
    """Hex ring in the YZ plane: vertices on top/bottom (creases), flat facets front/back."""
    t = _bell_t(x) if droop is None else droop
    up = r * (1.0 - 0.04 * t) + inset
    dn = r * (1.0 + 0.16 * t) + inset
    dx = DROOP * t
    pts = []
    for i in range(n):
        a = math.radians(30) + 2 * math.pi * i / n
        c, sn = math.cos(a), math.sin(a)
        pts.append(Vector((s * (x + dx * max(0.0, -sn)),
                           c * (r + inset),
                           ARM_Z + sn * (up if sn > 0 else dn))))
    return pts


def _sleeve(s, side, coll):
    rings = [_sleeve_ring(s, x, r) for x, r in SLEEVE_STATIONS]
    # open bell mouth: thin lip, then a funnel running back and closing on the wrist
    r_cuff = SLEEVE_STATIONS[-1][1]
    rings.append(_sleeve_ring(s, CUFF_TOP, r_cuff, inset=-0.008, droop=1.0))
    rings.append(_sleeve_ring(s, 0.55, 0.088, droop=0.0))
    rings.append(_sleeve_ring(s, 0.51, 0.030, droop=0.0))
    arm = _obj(f"Arm.{side}", _loft_data(rings), lib.mat("paper_white"), coll)

    # gold cuff band, flush with the cuff edge
    out = 0.004
    band_rings = [_sleeve_ring(s, x, _radius(x), inset=out) for x in (0.565, CUFF_TOP)]
    band = _obj(f"Sleeve.Cuff.{side}",
                _loft_data(band_rings, cap_start=False, cap_end=False),
                lib.gold(), coll)
    objs = [arm, band]
    if side == "L":
        objs += _tab(s, coll)
    return objs


def _tab(s, coll):
    """Gold tab (long axis along the arm, pointing to the cuff edge) with a red dot, on the
    front facet of the left cuff. Follows the slope of the flared cuff."""
    cos30 = math.cos(math.radians(30))
    zc = ARM_Z - 0.004

    def y_surf(x):                      # front facet plane incl. band outset
        return -(_radius(x) + 0.004) * cos30

    x0, x1, w = 0.552, CUFF_TOP - 0.002, 0.013
    poly = [(x0, w), (x1 - 0.014, w), (x1, 0.0), (x1 - 0.014, -w), (x0, -w)]
    back = [Vector((s * px, y_surf(px) + 0.0005, zc + pz)) for px, pz in poly]
    front = [Vector((s * px, y_surf(px) - 0.005, zc + pz)) for px, pz in poly]
    tab = _obj("Sleeve.Tab.L", _loft_data([back, front]), lib.gold(), coll)

    dx_ = x0 + 0.011
    dot_back, dot_front = [], []
    for k in range(6):
        a = 2 * math.pi * k / 6
        px, pz = dx_ + 0.0055 * math.cos(a), 0.0055 * math.sin(a)
        dot_back.append(Vector((s * px, y_surf(px) - 0.0045, zc + pz)))
        dot_front.append(Vector((s * px, y_surf(px) - 0.0085, zc + pz)))
    dot = _obj("Sleeve.TabDot.L", _loft_data([dot_back, dot_front]), lib.mat("red"), coll)
    return [tab, dot]


# ------------------------------------------------------------------ hands
def _hand_ring(s, cx, cz, phi, ry, rz, n=8):
    """Octagon ring centred (cx, 0, cz), plane perpendicular to a direction pitched down by
    `phi` radians from +X (mirrored for s=-1)."""
    dvx, dvz = s * math.sin(phi), math.cos(phi)       # ring 'up' vector (XZ plane)
    pts = []
    for i in range(n):
        a = math.pi / 8 + 2 * math.pi * i / n
        u, v = math.cos(a) * ry, math.sin(a) * rz
        pts.append(Vector((s * cx + dvx * v, u, cz + dvz * v)))
    return pts


def _hand(s, side, coll):
    bend = math.radians(30)
    k = WRIST + 0.045                     # knuckle x
    flen = X["hand_tip"] - k + 0.006      # finger block length
    tip_x = k + flen * math.cos(bend)
    tip_z = ARM_Z - flen * math.sin(bend)
    rings = [
        _hand_ring(s, WRIST - 0.12, ARM_Z, 0.0, 0.024, 0.024),   # wrist, inside the cuff
        _hand_ring(s, WRIST - 0.015, ARM_Z, 0.0, 0.024, 0.024),
        _hand_ring(s, WRIST + 0.006, ARM_Z, 0.0, 0.031, 0.016),  # back of the palm
        _hand_ring(s, k, ARM_Z, bend / 2, 0.031, 0.016),         # knuckle (mitre of the bend)
        _hand_ring(s, tip_x, tip_z, bend, 0.026, 0.0135),        # fingertips
    ]
    hand = _obj(f"Hand.{side}", _loft_data(rings), lib.mat("skin"), coll)

    # thumb: separate folded wedge pointing forward (-Y)
    def quad(y, xc, hw, zc, hh):
        return [Vector((s * (xc - hw), y, zc - hh)), Vector((s * (xc + hw), y, zc - hh)),
                Vector((s * (xc + hw), y, zc + hh)), Vector((s * (xc - hw), y, zc + hh))]
    zc = ARM_Z - 0.004
    xt = WRIST + 0.025
    t_rings = [quad(-0.012, xt, 0.019, zc, 0.012),
               quad(-0.042, xt + 0.006, 0.014, zc - 0.001, 0.011),
               quad(-0.068, xt + 0.016, 0.005, zc - 0.003, 0.007)]
    thumb = _obj(f"Thumb.{side}", _loft_data(t_rings), lib.mat("skin"), coll)
    return [hand, thumb]


# ------------------------------------------------------------------ legs and boots
def _leg(s, side, coll):
    cx = s * X["leg"]
    r = X["leg_r"]
    stops = [(Z["hip"], r * 1.12), (0.62, r * 1.10), (Z["knee"], r * 1.12), (Z["hem"], r),
             (Z["boot_top"], r * 0.95), (0.12, r * 0.92)]
    rings = [lib.ring((cx, 0.0, z), rr, rr, n=6, phase=0.0) for z, rr in stops]
    return _obj(f"Leg.{side}", _loft_data(rings), lib.mat("stocking"), coll)


def _boot_ring(cx, z, cy, rx, ry_front, ry_back, n=8, phase=0.0):
    """Octagon with a vertex pointing to -Y (toe ridge) and +Y (heel); radii differ front/back."""
    pts = []
    for i in range(n):
        a = phase + 2 * math.pi * i / n
        sn = math.sin(a)
        ry = ry_front if sn < -1e-6 else ry_back
        pts.append(Vector((cx + math.cos(a) * rx, cy + sn * ry, z)))
    return pts


def _boot(s, side, coll):
    cx = s * X["leg"]
    heel = 0.045
    toe = X["boot_len"] - heel          # toe tip at y = -toe
    top = Z["boot_top"]
    rings = []
    for z, y_toe, y_heel, rx in ((0.000, -toe, heel, 0.040),
                                 (0.030, -0.088, heel, 0.043),
                                 (0.065, -0.056, heel, 0.043),
                                 (0.115, -0.043, 0.044, 0.041),
                                 (top - 0.006, -0.041, 0.043, 0.040)):
        cy = (y_toe + y_heel) / 2
        half = (y_heel - y_toe) / 2
        rings.append(_boot_ring(cx, z, cy, rx, half, half))
    foot = _obj(f"Boot.{side}", _loft_data(rings), lib.mat("boot"), coll)

    # two stacked, slightly rotated folded-paper cuff layers
    layers = []
    zc0, zc1 = 0.118, top
    zm = (zc0 + zc1) / 2
    for z0, z1, r, dy, ph in ((zc0, zm + 0.002, 0.051, 0.004, math.pi / 8),
                              (zm + 0.002, zc1, 0.048, -0.003, 0.0)):
        rr = [_boot_ring(cx, z0, dy + 0.002, r, r, r, phase=ph),
              _boot_ring(cx, z1, dy + 0.002, r, r, r, phase=ph)]
        layers.append(_loft_data(rr, cap_start=(len(layers) == 0)))
    cuffs = _obj(f"Boot.Cuff.{side}", layers, lib.mat("boot"), coll)
    return [foot, cuffs]


# ------------------------------------------------------------------ entry point
def build():
    coll = lib.part_collection("Limbs")
    objs = []
    for s, side in SIDES:
        objs += _sleeve(s, side, coll)
        objs += _hand(s, side, coll)
        objs.append(_leg(s, side, coll))
        objs += _boot(s, side, coll)
    faces = sum(len(o.data.polygons) for o in objs)
    print(f"LIMBS faces={faces}")
    return objs
