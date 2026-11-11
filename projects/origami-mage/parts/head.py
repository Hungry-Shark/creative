"""Head part: neck, faceted blank head (nose-line crease), folded-paper hair built from separate
pieces (crown dome, V-folded bang flaps, V-folded side locks, V-section twin tails),
pointed elf ears and red drop earrings.

Every coordinate derives from spec.Z / spec.X (offsets from chin, head_centre, head_top ...).
Right side of the character is -X.
"""
import math

from mathutils import Vector

import lib
import spec

Z, X = spec.Z, spec.X
CHIN, HC, TOP = Z["chin"], Z["head_centre"], Z["head_top"]
HW, HD, NECK_R = X["head_half_w"], X["head_half_d"], X["neck_r"]
NECK_CY = 0.010


# ------------------------------------------------------------------ helpers
def ring10(z, w, fd, bd, cy=0.0):
    """10-point head ring: front centre point F (nose line), 2 front-cheek, 2 side, 2 rear, back."""
    p = [(0.0, -fd), (0.55 * w, -0.85 * fd), (w, -0.30 * fd), (w, 0.50 * bd),
         (0.55 * w, 0.92 * bd), (0.0, bd)]
    left = [(-x, y) for x, y in reversed(p[1:-1])]
    return [Vector((x, cy + y, z)) for x, y in p + left]


# head shape table: (z, w, fd, bd, cy)
HEAD_TABLE = [
    (CHIN,        0.30 * HW, 0.40 * HD, 0.30 * HD, -0.012),   # pointed chin
    (CHIN + 0.05, 0.72 * HW, 0.82 * HD, 0.62 * HD, 0.0),      # narrow jaw
    (HC - 0.02,   1.00 * HW, 1.00 * HD, 0.98 * HD, 0.0),      # widest
    (HC + 0.05,   1.00 * HW, 0.97 * HD, 1.02 * HD, 0.0),
    (TOP - 0.045, 0.74 * HW, 0.78 * HD, 0.88 * HD, 0.0),
    (TOP,         0.35 * HW, 0.38 * HD, 0.50 * HD, 0.0),      # crown
]


def head_params(z):
    t = HEAD_TABLE
    z = min(max(z, t[0][0]), t[-1][0])
    for a, b in zip(t, t[1:]):
        if a[0] <= z <= b[0]:
            k = (z - a[0]) / (b[0] - a[0])
            return tuple(a[i] + (b[i] - a[i]) * k for i in range(1, 5))
    return t[-1][1:]


def surf_y(x, z):
    """y of the head's front surface at (x, z) (follows the nose crease and cheek planes)."""
    w, fd, bd, cy = head_params(z)
    ax = min(abs(x), w)
    pts = [(0.0, -fd), (0.55 * w, -0.85 * fd), (w, -0.30 * fd)]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if ax <= x1:
            return cy + y0 + (y1 - y0) * (ax - x0) / (x1 - x0)
    return cy + pts[-1][1]


def pts(lst):
    return [Vector(p) for p in lst]


def torus(name, center, R, r, material, coll, major=6, minor=4):
    """Tiny faceted ring lying in the XZ plane (hole axis along Y)."""
    cx, cy, cz = center
    verts, faces = [], []
    for i in range(major):
        a = 2 * math.pi * i / major
        for j in range(minor):
            b = 2 * math.pi * j / minor + math.pi / 4
            rr = R + r * math.cos(b)
            verts.append((cx + rr * math.cos(a), cy + r * math.sin(b), cz + rr * math.sin(a)))
    for i in range(major):
        for j in range(minor):
            a0 = i * minor + j
            a1 = i * minor + (j + 1) % minor
            b0 = ((i + 1) % major) * minor + j
            b1 = ((i + 1) % major) * minor + (j + 1) % minor
            faces.append((a0, a1, b1, b0))
    return lib.mesh_object(name, verts, faces, material=material, coll=coll)


def sheet(name, verts, faces, mats, coll, mat_idx=None, thickness=0.004):
    obj = lib.mesh_object(name, verts, faces, materials=mats, coll=coll, face_mats=mat_idx)
    lib.solidify(obj, thickness)
    return obj


def vflap(verts, faces, mi, a, b, tip, push=(0.0, -0.008, 0.0), swap=False):
    """Append a V-folded triangle: root edge a-b, tip, crease from the root midpoint to the tip
    (root midpoint pushed by `push` so the two halves are angled)."""
    a, b, tip = Vector(a), Vector(b), Vector(tip)
    m = (a + b) / 2 + Vector(push)
    i = len(verts)
    verts.extend([a, m, b, tip])
    faces.append((i, i + 1, i + 3))
    faces.append((i + 1, i + 2, i + 3))
    mi.extend([1, 0] if swap else [0, 1])


# ------------------------------------------------------------------ parts
def build_neck(coll, skin):
    z0 = Z["collar_bottom"] - 0.03
    z1 = CHIN + 0.05
    zs = [z0, (z0 + z1) / 2, z1]
    rs = [NECK_R, NECK_R * 0.95, NECK_R * 0.92]
    rings = [lib.ring((0, NECK_CY, z), r, r, n=6, phase=math.pi / 6) for z, r in zip(zs, rs)]
    return lib.loft("Neck", rings, material=skin, coll=coll)


def build_head(coll, skin):
    rings = [ring10(*row) for row in HEAD_TABLE]
    return lib.loft("Head", rings, material=skin, coll=coll, cap_start=True, cap_end=True)


def cap_front_y(ax):
    """Front surface y of the crown dome (|x|), used to seat the fringe roots."""
    return -0.070 + max(0.0, ax - 0.05) / 0.075 * 0.050


def build_cap(coll, hair, shadow):
    """Faceted dome that is wide above the ears. Its front edge is set back and up so the
    fringe flaps (rooted near the apex) fully cover it. Short bob behind the ears."""
    bz = CHIN + 0.04                     # bob bottom behind the ears (~1.30)
    ww = HW + 0.037                      # dome half width (~0.125) above the ears
    zw = HC + 0.050                      # z of the widest point
    r0 = pts([(-0.050, -0.070, HC + 0.075), (0.050, -0.070, HC + 0.075), (ww, -0.020, zw),
              (ww - 0.012, 0.070, bz + 0.020), (0.058, 0.108, bz), (-0.058, 0.108, bz),
              (-ww + 0.012, 0.070, bz + 0.020), (-ww, -0.020, zw)])
    r1 = pts([(-0.050, -0.075, TOP - 0.030), (0.050, -0.075, TOP - 0.030),
              (ww, -0.018, TOP - 0.045), (ww, 0.067, TOP - 0.045),
              (0.062, 0.114, TOP - 0.045), (-0.062, 0.114, TOP - 0.045),
              (-ww, 0.067, TOP - 0.045), (-ww, -0.018, TOP - 0.045)])
    r2 = pts([(-0.034, -0.062, TOP + 0.018), (0.034, -0.062, TOP + 0.020),
              (0.078, -0.012, TOP + 0.012), (0.078, 0.060, TOP + 0.012),
              (0.040, 0.090, TOP + 0.010), (-0.040, 0.090, TOP + 0.010),
              (-0.078, 0.060, TOP + 0.012), (-0.078, -0.012, TOP + 0.012)])
    apex = Vector((0.004, 0.010, TOP + 0.040))
    n = 8
    verts = r0 + r1 + r2 + [apex]
    faces, mi = [], []
    for r in range(2):
        for i in range(n):
            a, b = r * n + i, r * n + (i + 1) % n
            faces.append((a, b, b + n, a + n))
            mi.append(1 if (r == 0 and i in (3, 4, 5, 6)) else 0)
    for i in range(n):
        a, b = 2 * n + i, 2 * n + (i + 1) % n
        faces.append((a, b, 3 * n))
        mi.append(1 if i in (3, 4, 5) else 0)
    return sheet("Hair.Cap", verts, faces, [hair, shadow], coll, mi, 0.004)


def build_bangs(coll, hair, shadow):
    """5 overlapping V-folded triangular flaps radiating from near the crown apex over the
    front of the dome and down the forehead. Each entry:
    (root_x0, root_x1, tip_x, tip_z, surface offset). Right (-X) side is longer."""
    root_z = TOP + 0.022
    flaps = [
        (-0.078, -0.016, -0.092, HC - 0.022, 0.014),    # right outer: longest, to the temple
        (-0.054, 0.006, -0.054, HC + 0.005, 0.017),     # right mid
        (-0.030, 0.034, 0.004, HC + 0.040, 0.021),      # centre, short
        (-0.006, 0.054, 0.050, HC + 0.014, 0.017),      # left mid
        (0.012, 0.074, 0.090, HC - 0.012, 0.014),       # left outer
    ]
    verts, faces, mi = [], [], []
    for k, (x0, x1, xt, zt, off) in enumerate(flaps):
        ra = (x0, cap_front_y(abs(x0)) * 0.85 - 0.010, root_z - 0.020 * abs(x0) / 0.08)
        rb = (x1, cap_front_y(abs(x1)) * 0.85 - 0.010, root_z - 0.020 * abs(x1) / 0.08)
        tip = (xt, surf_y(xt, zt) - off, zt)
        vflap(verts, faces, mi, ra, rb, tip, push=(0.0, -0.010, 0.0), swap=bool(k % 2))
    return sheet("Hair.Bangs", verts, faces, [hair, shadow], coll, mi, 0.006)


def build_lock(coll, hair, shadow):
    """Right-side (-X): two overlapping broad V-folded triangles in front of the ear."""
    z_t = HC + 0.050
    ox = HW + 0.058                       # outer edge |x| of the outer lock
    ix = HW - 0.014                       # inner edge |x|
    verts, faces, mi = [], [], []
    # long outer lock, tip below the chin
    vflap(verts, faces, mi, (-ox, -0.045, z_t + 0.004), (-ix, -0.085, z_t + 0.008),
          (-(ix + 0.040), -0.074, CHIN - 0.070), push=(-0.004, -0.010, 0.0))
    # shorter inner lock in front (overlap)
    vflap(verts, faces, mi, (-(ox - 0.010), -0.052, z_t - 0.004), (-(ix + 0.002), -0.092, z_t),
          (-(ix + 0.022), -0.086, CHIN - 0.030), push=(-0.002, -0.010, 0.0), swap=True)
    return sheet("Hair.Lock.R", verts, faces, [hair, shadow], coll, mi, 0.005)


def build_tail(coll, hair, shadow):
    """Right (-X) twin tail: long ribbon with a shallow V cross-section (edge, raised crease,
    edge), width along X, thickness ~0.012. rows: (z, cx, cy, half_width)"""
    v, t = 0.015, 0.012
    path = [
        (TOP - 0.050, -0.080, 0.095, 0.036),     # root at back-side of the crown
        (CHIN,        -0.170, 0.210, 0.053),     # kink 1: swept out and back
        (CHIN - 0.240, -0.190, 0.212, 0.053),    # kink 2
        (0.800,       -0.160, 0.205, 0.003),     # pointed tip
    ]
    rings = []
    for z, cx, cy, w in path:
        tt = t if w > 0.01 else 0.003
        vv = v if w > 0.01 else 0.003
        rings.append([Vector((cx - w, cy, z)), Vector((cx, cy - vv, z)), Vector((cx + w, cy, z)),
                      Vector((cx + w, cy + tt, z)), Vector((cx, cy - vv + tt, z)),
                      Vector((cx - w, cy + tt, z))])
    face_mats = []
    for r in range(len(rings) - 1):
        face_mats += [r % 2, (r + 1) % 2, 1, 1, 1, 1]
    face_mats += [1, 1]
    return lib.loft("Hair.Tail.R", rings, coll=coll, materials=[hair, shadow],
                    face_mats=face_mats, cap_start=True, cap_end=True)


def build_ear(coll, skin):
    """Flat folded paper triangle: two facets on a centre crease, ~0.008 thick."""
    rx = HW - 0.003
    A = (-rx, 0.030, HC + 0.030)
    B = (-rx, 0.030, HC - 0.040)
    M = (-(rx - 0.003), 0.014, HC - 0.005)      # crease start, pushed forward
    T = (-(HW + 0.162), 0.042, HC + 0.015)      # tip: outward, slightly back and up
    verts = [A, M, T, B]
    faces = [(0, 1, 2), (1, 3, 2)]
    return sheet("Ear.R", verts, faces, [skin], coll, None, 0.008)


def build_earring(coll, red, gold):
    ring_c = (-(HW + 0.006), 0.014, HC - 0.075)
    ring = torus("Earring.Hoop.R", ring_c, 0.0065, 0.0016, gold, coll)
    top_z = ring_c[2] - 0.0065 - 0.0025
    mid_z = top_z - 0.017
    bot_z = top_z - 0.052
    cx, cy, h = ring_c[0], ring_c[1], 0.0075
    verts = [(cx, cy, top_z), (cx - h, cy, mid_z), (cx, cy - h * 0.8, mid_z),
             (cx + h, cy, mid_z), (cx, cy + h * 0.8, mid_z), (cx, cy, bot_z)]
    faces = [(0, 2, 1), (0, 3, 2), (0, 4, 3), (0, 1, 4), (5, 1, 2), (5, 2, 3), (5, 3, 4), (5, 4, 1)]
    gem = lib.mesh_object("Earring.R", verts, faces, material=red, coll=coll)
    return [ring, gem]


# ------------------------------------------------------------------ entry
def build():
    coll = lib.part_collection("Head")
    skin, hair, shadow = lib.mat("skin"), lib.mat("hair"), lib.mat("hair_shadow")
    red, gold = lib.mat("red"), lib.gold()

    objs = [build_neck(coll, skin), build_head(coll, skin), build_cap(coll, hair, shadow),
            build_bangs(coll, hair, shadow)]
    for o in (build_lock(coll, hair, shadow), build_tail(coll, hair, shadow),
              build_ear(coll, skin)):
        objs += [o, lib.mirror_x(o)]
    for o in build_earring(coll, red, gold):
        objs += [o, lib.mirror_x(o)]
    nfaces = sum(len(o.data.polygons) for o in objs)
    print(f"HEAD faces: {nfaces}")
    return objs
