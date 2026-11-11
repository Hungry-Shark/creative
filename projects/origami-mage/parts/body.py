"""Body part (v2 proportions): robe, torso (striped shirt), belt + buckle, collar + gem, capelet.

Everything is built around the vertical axis x=y=0, faces -Y, feet at z=0.
Closed paper shells are built with an explicit inner skin (no modifiers); the open
capelet sheet and its trim strips are given thickness with a SOLIDIFY that is baked.
"""
import math

import bpy
from mathutils import Vector

import lib
import spec

Z = spec.Z
X = spec.X

PHASE8 = math.pi / 8     # octagon with a flat facet facing -Y
PHASE12 = math.pi / 12   # 12-gon with a flat facet facing -Y


# ------------------------------------------------------------------ geometry helpers
def _lerp(a, b, t):
    return a + (b - a) * t


def _pw(table, v):
    """Piecewise-linear lookup in a sorted list of (key, value)."""
    if v <= table[0][0]:
        return table[0][1]
    for (k0, v0), (k1, v1) in zip(table, table[1:]):
        if v <= k1:
            return _lerp(v0, v1, (v - k0) / (k1 - k0))
    return table[-1][1]


def _geo(rings, ring_closed=True, seq_closed=False, base=0):
    n = len(rings[0])
    verts = [tuple(p) for r in rings for p in r]
    nr = len(rings)
    segs = n if ring_closed else n - 1
    pairs = nr if seq_closed else nr - 1
    faces = []
    for r in range(pairs):
        r2 = (r + 1) % nr
        for i in range(segs):
            i2 = (i + 1) % n
            faces.append((base + r * n + i, base + r * n + i2,
                          base + r2 * n + i2, base + r2 * n + i))
    return verts, faces


def _inset(ringpts, t):
    out = []
    for p in ringpts:
        d = math.hypot(p.x, p.y)
        k = max(0.2, 1.0 - t / d) if d > 1e-6 else 1.0
        out.append(Vector((p.x * k, p.y * k, p.z)))
    return out


def _shell(name, rings, t, material, coll):
    """Closed thin-walled tube: outer rings top->bottom, then the inset skin back up."""
    seq = list(rings) + [_inset(r, t) for r in reversed(rings)]
    v, f = _geo(seq, ring_closed=True, seq_closed=True)
    return lib.mesh_object(name, v, f, material=material, coll=coll)


def _merge(parts):
    verts, faces = [], []
    for v, f in parts:
        base = len(verts)
        verts += v
        faces += [tuple(i + base for i in face) for face in f]
    return verts, faces


def _bake(obj):
    """Apply every modifier on obj (bake into mesh) and keep it flat shaded."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(dg))
    old = obj.data
    obj.data = me
    obj.modifiers.clear()
    bpy.data.meshes.remove(old)
    for p in me.polygons:
        p.use_smooth = False
    lib.recalc_normals(obj)


def _sheet(name, verts, faces, material, coll, t=0.004):
    o = lib.mesh_object(name, verts, faces, material=material, coll=coll)
    lib.solidify(o, t)
    _bake(o)
    return o


def _box_geo(center, size):
    cx, cy, cz = center
    sx, sy, sz = (s / 2 for s in size)
    v = [(cx + x * sx, cy + y * sy, cz + z * sz)
         for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return v, f


# ------------------------------------------------------------------ profiles (all from spec)
WAIST, BELT_HH = Z["waist"], Z["belt_half_h"]
BELT_TOP, BELT_BOT = WAIST + BELT_HH, WAIST - BELT_HH
COLLAR_Z0, COLLAR_Z1 = Z["collar_bottom"], Z["collar_top"]
COLLAR_R0 = (0.046, 0.044)     # collar half sizes at the bottom / top (neck r=0.030 passes through)
COLLAR_R1 = (0.050, 0.048)

# --- robe: 16-gon, ridge (even) / valley (odd) pleats, ridge at front centre = centre crease
ROBE_N = 16
ROBE_TOP_Z = BELT_TOP - 0.005                      # open top hidden inside the belt
ROBE_W0, ROBE_W1 = X["robe_waist_half_w"], X["robe_hem_half_w"]
ROBE_RATIO = X["robe_hem_half_d"] / X["robe_hem_half_w"]    # keeps every facet planar
PLEAT_DEPTH = 0.018                                 # valley depth at the hem
ROBE_JIT = [1.0, 1.0 - PLEAT_DEPTH / ROBE_W1] * (ROBE_N // 2)


def robe_r(z):
    t = (WAIST - z) / (WAIST - Z["hem"])
    rx = _lerp(ROBE_W0, ROBE_W1, t)
    return rx, rx * ROBE_RATIO


# --- torso
CH_W, CH_D = X["torso_chest_half_w"], X["torso_chest_half_d"]
WA_W, WA_D = X["torso_waist_half_w"], X["torso_waist_half_d"]
# thin black stripes between belt top and collar bottom
N_STRIPES, STRIPE_H = 6, 0.021
_s0 = BELT_TOP + 0.007
_s_end = COLLAR_Z0 - 0.014
STRIPE_PITCH = (_s_end - STRIPE_H - _s0) / (N_STRIPES - 1)
STRIPES = [(_s0 + STRIPE_PITCH * i, STRIPE_H) for i in range(N_STRIPES)]
CHEST_Z = STRIPES[3][0]                           # chest kink sits on a stripe edge
TORSO_PROFILE = [  # (z, rx, ry)
    (WAIST - 0.06, WA_W, WA_D),
    (WAIST, WA_W, WA_D),
    (CHEST_Z, CH_W, CH_D),
    (COLLAR_Z0, COLLAR_R0[0] * 0.9, COLLAR_R0[1] * 0.9),
]


def torso_r(z):
    rx = _pw([(p[0], p[1]) for p in TORSO_PROFILE], z)
    ry = _pw([(p[0], p[2]) for p in TORSO_PROFILE], z)
    return rx, ry


# ------------------------------------------------------------------ parts
def _robe(coll, out):
    white, gold = lib.mat("paper_white"), lib.gold()
    rings = []
    for z in (ROBE_TOP_Z, Z["hem"]):
        rx, ry = robe_r(z)
        rings.append(lib.ring((0, 0, z), rx, ry, ROBE_N, phase=0.0, jitter=ROBE_JIT))
    out.append(_shell("Robe", rings, 0.005, white, coll))

    # gold hem band following the flare and the pleats exactly
    z0, z1 = Z["hem"], Z["hem"] + 0.035
    brs = []
    for z in (z1, z0):
        rx, ry = robe_r(z)
        brs.append(lib.ring((0, 0, z), rx + 0.006, ry + 0.006, ROBE_N, phase=0.0, jitter=ROBE_JIT))
    out.append(_shell("Robe.HemTrim", brs, 0.003, gold, coll))


def _torso(coll, out):
    white, black = lib.mat("paper_white"), lib.mat("black")
    rings = [lib.ring((0, 0, z), rx, ry, 8, phase=PHASE8) for z, rx, ry in TORSO_PROFILE]
    v, f = _geo(rings)
    n = 8
    f.append(tuple(range(n - 1, -1, -1)))
    last = (len(rings) - 1) * n
    f.append(tuple(range(last, last + n)))
    out.append(lib.mesh_object("Torso", v, f, material=white, coll=coll))

    parts = []
    for z0, h in STRIPES:
        rs = []
        for z in (z0 + h, z0):
            rx, ry = torso_r(z)
            rs.append(lib.ring((0, 0, z), rx + 0.004, ry + 0.004, 8, phase=PHASE8))
        parts.append(_geo(rs + [_inset(r, 0.002) for r in reversed(rs)], seq_closed=True))
    v, f = _merge(parts)
    out.append(lib.mesh_object("Shirt.Stripes", v, f, material=black, coll=coll))


BELT_N = 16
BELT_PH = math.pi / BELT_N      # flat facet facing -Y


def _belt(coll, out):
    black, gold = lib.mat("black"), lib.gold()
    top_rx = max(WA_W + 0.012, robe_r(BELT_TOP)[0] + 0.010)
    bot_rx = robe_r(BELT_BOT)[0] * 1.058
    ratio = 0.78
    rings = [lib.ring((0, 0, BELT_TOP), top_rx, top_rx * ratio, BELT_N, phase=BELT_PH),
             lib.ring((0, 0, BELT_BOT), bot_rx, bot_rx * ratio, BELT_N, phase=BELT_PH)]
    out.append(_shell("Belt", rings, 0.006, black, coll))

    # square gold buckle frame on the front facet
    mid_ry = 0.5 * (top_rx + bot_rx) * ratio
    face_y = -mid_ry * math.cos(BELT_PH)
    d = 0.010
    cy, cz = face_y - d * 0.35, WAIST
    w, h, bar = 0.040, 0.034, 0.007
    parts = [
        _box_geo((0, cy, cz + h / 2 - bar / 2), (w, d, bar)),
        _box_geo((0, cy, cz - h / 2 + bar / 2), (w, d, bar)),
        _box_geo((-(w / 2 - bar / 2), cy, cz), (bar, d, h)),
        _box_geo((w / 2 - bar / 2, cy, cz), (bar, d, h)),
        _box_geo((0, cy - 0.001, cz), (w * 0.62, d * 0.6, 0.004)),   # prong
    ]
    v, f = _merge(parts)
    out.append(lib.mesh_object("Belt.Buckle", v, f, material=gold, coll=coll))


def collar_r(z):
    t = (z - COLLAR_Z0) / (COLLAR_Z1 - COLLAR_Z0)
    return _lerp(COLLAR_R0[0], COLLAR_R1[0], t), _lerp(COLLAR_R0[1], COLLAR_R1[1], t)


def _gem_on(name, centre, normal, r, depth, material, coll):
    """Hexagonal pyramid on a surface point, pointing along `normal`."""
    t = normal.cross(Vector((0, 0, 1)))
    t = t.normalized() if t.length > 1e-6 else Vector((1, 0, 0))
    b = normal.cross(t).normalized()
    base = [centre + (t * math.cos(a) + b * math.sin(a)) * r
            for a in [2 * math.pi * i / 6 for i in range(6)]]
    verts = base + [centre + normal * depth]
    faces = [(i, (i + 1) % 6, 6) for i in range(6)] + [tuple(range(5, -1, -1))]
    return lib.mesh_object(name, verts, faces, material=material, coll=coll)


def _collar(coll, out):
    white, gold, red = lib.mat("paper_white"), lib.gold(), lib.mat("red")
    z0, z1 = COLLAR_Z0, COLLAR_Z1
    rings = [lib.ring((0, 0, z1), *collar_r(z1), 8, phase=PHASE8),
             lib.ring((0, 0, z0), *collar_r(z0), 8, phase=PHASE8)]
    out.append(_shell("Collar", rings, 0.004, white, coll))

    trims = []
    for a, b in ((z0, z0 + 0.014), (z1 - 0.014, z1)):
        rs = []
        for z in (b, a):
            rx, ry = collar_r(z)
            rs.append(lib.ring((0, 0, z), rx + 0.004, ry + 0.004, 8, phase=PHASE8))
        trims.append(_geo(rs + [_inset(r, 0.003) for r in reversed(rs)], seq_closed=True))
    v, f = _merge(trims)
    out.append(lib.mesh_object("Collar.Trim", v, f, material=gold, coll=coll))

    gz = 0.5 * (z0 + z1)
    rx, ry = collar_r(gz)
    ybase = -(ry + 0.004) * math.cos(PHASE8) + 0.001
    out.append(_gem_on("Collar.Gem", Vector((0.0, ybase, gz)), Vector((0, -1, 0)),
                       0.0105, 0.010, red, coll))


# capelet ----------------------------------------------------------------------
# Natural arms-down drape. Four rings: N (neck) -> A (over the shoulder joint) -> B (bell
# break, widest part over the hanging upper arms) -> H (hem). Angles are degrees from the
# front towards +X; first/last angle of each ring is the front opening edge (the V).
MID_ANG = [50, 90, 135, 180]
NECK_R = 0.042
CAPE_Z_NECK = COLLAR_Z0 + 0.002
V_TOP, V_HEM = 0.015, 0.055          # half-width of the V opening at the collar / at the hem


def v_half(z):
    t = (CAPE_Z_NECK - z) / (CAPE_Z_NECK - Z["capelet_hem"])
    return _lerp(V_TOP, V_HEM, max(0.0, t))


CAPE_W = X["capelet_half_w"]
CAPE_RINGS = [  # rx (side), ryf, ryb, z at front edge / side / back
    dict(rx=NECK_R, ryf=NECK_R, ryb=NECK_R, zf=CAPE_Z_NECK, zs=CAPE_Z_NECK, zb=CAPE_Z_NECK),
    dict(rx=X["shoulder"] + 0.005, ryf=0.085, ryb=0.085, zf=1.125, zs=Z["shoulder_top"] + 0.002, zb=1.125),
    dict(rx=CAPE_W, ryf=0.120, ryb=0.115, zf=1.03, zs=1.10, zb=1.04),
    dict(rx=CAPE_W + 0.003, ryf=0.140, ryb=0.142, zf=Z["capelet_hem"], zs=0.965, zb=0.955),
]


def _cape_ring(cfg):
    fa = math.degrees(math.asin(min(0.99, v_half(cfg["zf"]) / cfg["rx"])))
    ztab = [(0, cfg["zf"]), (fa, cfg["zf"]), (90, cfg["zs"]), (180, cfg["zb"])]
    angs = [fa] + MID_ANG + [360 - a for a in reversed(MID_ANG[:-1])] + [360 - fa]
    pts = []
    for t in angs:
        a = math.radians(t)
        s, c = math.sin(a), math.cos(a)
        ry = cfg["ryf"] if c >= 0 else cfg["ryb"]
        pts.append(Vector((cfg["rx"] * s, -ry * c, _pw(ztab, min(t, 360 - t)))))
    return pts


def _outset(p, d=0.0045):
    rad = Vector((p.x, p.y, 0.0))
    rad = rad.normalized() if rad.length > 1e-6 else Vector((0, -1, 0))
    return p + (rad + Vector((0, 0, 1))).normalized() * d


def _facet_pt(rings, ring_i, seg_i, u, v):
    """Bilinear point on the facet between rings[ring_i], rings[ring_i+1], points seg_i, seg_i+1."""
    a, b = rings[ring_i][seg_i], rings[ring_i][seg_i + 1]
    d, c = rings[ring_i + 1][seg_i], rings[ring_i + 1][seg_i + 1]
    return (a.lerp(b, u)).lerp(d.lerp(c, u), v)


def _facet_normal(rings, ring_i, seg_i):
    a, b = rings[ring_i][seg_i], rings[ring_i][seg_i + 1]
    d = rings[ring_i + 1][seg_i]
    n = (b - a).cross(d - a).normalized()
    centre = _facet_pt(rings, ring_i, seg_i, 0.5, 0.5)
    if n.dot(Vector((centre.x, centre.y, 0.0))) < 0:
        n = -n
    return n


def _capelet(coll, out):
    white, gold, red = lib.mat("paper_white"), lib.gold(), lib.mat("red")
    rings = [_cape_ring(c) for c in CAPE_RINGS]
    v, f = _geo(rings, ring_closed=False)
    out.append(_sheet("Capelet", v, f, white, coll, t=0.004))

    # hem strip (follows the lowest ring, up the surface)
    H, B = rings[-1], rings[-2]
    hem_w = 0.032
    inner = [h + (b - h) * min(0.6, hem_w / (b - h).length) for h, b in zip(H, B)]
    parts = [_geo([[_outset(p) for p in H], [_outset(p) for p in inner]], ring_closed=False)]

    # front opening strips down both V edges, over all rings
    ew = 0.018
    last = len(H) - 1
    for idx, nb in ((0, 1), (last, last - 1)):
        e_pts, i_pts = [], []
        for ring in rings:
            e = ring[idx]
            d = (ring[nb] - e).normalized()
            e_pts.append(_outset(e))
            i_pts.append(_outset(e + d * ew))
        parts.append(_geo([[e_pts[j], i_pts[j]] for j in range(len(rings))], ring_closed=False))
    v, f = _merge(parts)
    out.append(_sheet("Capelet.Trim", v, f, gold, coll, t=0.002))

    # small gold-trimmed rectangular tab on the character's left side (+X), above the hem
    ri, si = len(rings) - 2, 1                  # facet between ring B and H, angles 50 -> 90 deg
    n = _facet_normal(rings, ri, si)
    u0, u1, v0, v1 = 0.26, 0.60, 0.34, 0.86

    def quad(a0, a1, b0, b1, off):
        return [_facet_pt(rings, ri, si, u, v) + n * off
                for u, v in ((a0, b0), (a1, b0), (a1, b1), (a0, b1))]

    du, dv = 0.07, 0.07
    verts = quad(u0, u1, v0, v1, 0.0045) + quad(u0 + du, u1 - du, v0 + dv, v1 - dv, 0.0075)
    tab = lib.mesh_object("Capelet.Tab", verts, [(0, 1, 2, 3), (4, 5, 6, 7)],
                          materials=[gold, white], face_mats=[0, 1], coll=coll)
    lib.solidify(tab, 0.002)
    _bake(tab)
    out.append(tab)
    # little red button at the top of the tab
    c0 = _facet_pt(rings, ri, si, 0.5 * (u0 + u1), v0 + 0.07) + n * 0.0075
    out.append(_gem_on("Capelet.TabButton", c0, n, 0.0065, 0.005, red, coll))


def build():
    coll = lib.part_collection("Body")
    out = []
    _robe(coll, out)
    _torso(coll, out)
    _belt(coll, out)
    _collar(coll, out)
    _capelet(coll, out)
    faces = sum(len(o.data.polygons) for o in out)
    lo, hi = lib.world_bbox(out)
    print(f"BODY faces={faces} bbox lo={tuple(round(c, 3) for c in lo)} hi={tuple(round(c, 3) for c in hi)}")
    for o in out:
        l, h = lib.world_bbox([o])
        print(f"BODY obj {o.name}: faces={len(o.data.polygons)} "
              f"x[{l.x:.3f},{h.x:.3f}] y[{l.y:.3f},{h.y:.3f}] z[{l.z:.3f},{h.z:.3f}]")
    return out
