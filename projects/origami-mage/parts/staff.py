"""Staff prop: red hex shaft, gold spear tip, gold collar, gold crescent moon, red gem, red ribbons.

Everything is accumulated into ONE mesh (two materials: red + gold) named "Staff", whose origin
sits at the grip point (x = STAFF x, y = 0, z = Z["arm"]) so it can be parented to the hand bone.
Flat shaded, no subdivision, no modifiers.
"""
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

import lib
import spec

RED, GOLD = 0, 1


class Acc:
    """Accumulates verts/faces/material indices from many little pieces into one mesh."""

    def __init__(self):
        self.verts, self.faces, self.mats = [], [], []

    def add(self, verts, faces, mat):
        o = len(self.verts)
        self.verts.extend(tuple(v) for v in verts)
        for f in faces:
            self.faces.append(tuple(i + o for i in f))
            self.mats.append(mat)


def _frame(axis):
    a = Vector(axis).normalized()
    helper = Vector((1, 0, 0)) if abs(a.z) > 0.9 else Vector((0, 0, 1))
    e1 = helper.cross(a).normalized() if abs(a.z) <= 0.9 else Vector((1, 0, 0))
    e2 = a.cross(e1).normalized()
    return a, e1, e2


def prism(acc, p0, axis, profile, mat, n=6, phase=math.pi / 6, squash=(1.0, 1.0)):
    """Faceted solid of revolution along `axis` from p0. profile = [(t, radius), ...].

    radius 0 at an end makes a pointed apex; radius > 0 at an end gets a flat cap.
    """
    a, e1, e2 = _frame(axis)
    p0 = Vector(p0)
    verts, faces, rings = [], [], []
    for t, r in profile:
        if r <= 0:
            verts.append(p0 + a * t)
            rings.append(("apex", len(verts) - 1))
        else:
            idx = []
            for i in range(n):
                ang = phase + 2 * math.pi * i / n
                verts.append(p0 + a * t + e1 * (math.cos(ang) * r * squash[0])
                             + e2 * (math.sin(ang) * r * squash[1]))
                idx.append(len(verts) - 1)
            rings.append(("ring", idx))
    for (ka, ra), (kb, rb) in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            if ka == "ring" and kb == "ring":
                faces.append((ra[i], ra[j], rb[j], rb[i]))
            elif ka == "apex":
                faces.append((ra, rb[j], rb[i]))
            elif kb == "apex":
                faces.append((ra[i], ra[j], rb))
    if rings[0][0] == "ring":
        faces.append(tuple(reversed(rings[0][1])))
    if rings[-1][0] == "ring":
        faces.append(tuple(rings[-1][1]))
    acc.add(verts, faces, mat)


def sheet(acc, rows, thickness, mat):
    """Thick paper strip. rows = list of polylines (list of Vector across the strip);
    the last row may be a single point (pointed end). Thickness goes along +Y."""
    off = Vector((0, thickness, 0))
    verts, front, back = [], [], []
    for row in rows:
        front.append([])
        back.append([])
        for p in row:
            verts.append(Vector(p))
            front[-1].append(len(verts) - 1)
        for p in row:
            verts.append(Vector(p) + off)
            back[-1].append(len(verts) - 1)
    faces = []
    for r in range(len(rows) - 1):
        fa, fb, ba, bb = front[r], front[r + 1], back[r], back[r + 1]
        if len(fb) == 1:
            for k in range(len(fa) - 1):
                faces.append((fa[k], fa[k + 1], fb[0]))
                faces.append((ba[k + 1], ba[k], bb[0]))
            faces.append((fa[0], fb[0], bb[0], ba[0]))      # left edge to tip
            faces.append((fa[-1], ba[-1], bb[0], fb[0]))    # right edge to tip
            continue
        for k in range(len(fa) - 1):
            faces.append((fa[k], fa[k + 1], fb[k + 1], fb[k]))
            faces.append((ba[k + 1], ba[k], bb[k], bb[k + 1]))
        faces.append((fa[0], fb[0], bb[0], ba[0]))
        faces.append((fa[-1], ba[-1], bb[-1], fb[-1]))
    # top edge cap joining the front and back skins of the first row
    faces.append(tuple(front[0]) + tuple(reversed(back[0])))
    acc.add(verts, faces, mat)


def crescent(acc, centre, theta0=math.radians(45), alpha=math.radians(65),
             r_out=0.10, offset=0.035, half_t=0.011, ridge=0.005, n=10):
    """Flat-faceted C-shaped crescent lying in the XZ plane (faces -Y), opening towards theta0."""
    cx, cz = centre
    u = Vector((math.cos(theta0), math.sin(theta0)))
    tip = Vector((math.cos(theta0 + alpha), math.sin(theta0 + alpha))) * r_out
    ic = u * offset
    ri = (tip - ic).length
    beta_a = math.atan2((tip - ic).dot(Vector((-u.y, u.x))), (tip - ic).dot(u))
    # absolute start angles of both arcs, sweeping the long way round (through the back)
    o0, o1 = theta0 + alpha, theta0 + 2 * math.pi - alpha
    i0, i1 = theta0 + beta_a, theta0 + 2 * math.pi - beta_a

    def pt(c, r, ang, y):
        return Vector((cx + c.x + math.cos(ang) * r, y, cz + c.y + math.sin(ang) * r))

    zero = Vector((0, 0))
    verts, faces = [], []
    rings = []
    for s in range(1, n):
        f = s / n
        po = pt(zero, r_out, o0 + (o1 - o0) * f, 0)
        pi_ = pt(ic, ri, i0 + (i1 - i0) * f, 0)
        pm = (po + pi_) / 2
        ring = [
            po + Vector((0, -half_t, 0)),
            pm + Vector((0, -half_t - ridge, 0)),
            pi_ + Vector((0, -half_t, 0)),
            pi_ + Vector((0, half_t, 0)),
            pm + Vector((0, half_t + ridge, 0)),
            po + Vector((0, half_t, 0)),
        ]
        rings.append(list(range(len(verts), len(verts) + 6)))
        verts.extend(ring)
    apex0 = len(verts)
    verts.append(pt(zero, r_out, o0, 0))
    apex1 = len(verts)
    verts.append(pt(zero, r_out, o1, 0))
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(6):
            kk = (k + 1) % 6
            faces.append((a[k], a[kk], b[kk], b[k]))
    for k in range(6):
        kk = (k + 1) % 6
        faces.append((apex0, rings[0][kk], rings[0][k]))
        faces.append((apex1, rings[-1][k], rings[-1][kk]))
    acc.add(verts, faces, GOLD)
    return Vector((cx, cz)), u, r_out


def gem(acc, centre, radius):
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=radius)
    rot = Matrix.Rotation(math.radians(20), 4, "X") @ Matrix.Rotation(math.radians(15), 4, "Z")
    verts = []
    for v in bm.verts:
        p = rot @ v.co
        p = Vector((p.x * 1.0, p.y * 0.75, p.z * 1.05))
        # tiny deterministic wobble so the facets look hand-folded
        k = 1.0 + 0.05 * math.sin(7.3 * p.x / radius + 3.1 * p.z / radius + 1.7)
        p = p * k
        verts.append(Vector(centre) + p)
    faces = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    acc.add(verts, faces, RED)


def build():
    S = spec.STAFF
    xs, ys = S["x"], S["y"]
    grip_z = S["grip_z"]
    z0, z1 = grip_z - S["below_grip"], grip_z + S["above_grip"]
    r = S["shaft_r"]
    grip = Vector((xs, 0.0, grip_z))

    coll = lib.part_collection("Staff", group=spec.PROPS_COLLECTION)
    acc = Acc()

    # ---------------------------------------------------------------- crescent (placed first: it fixes the collar height)
    probe = Acc()
    # centre is offset left of the shaft so the shaft meets the crescent's lower right
    cx = xs - 0.03
    c_probe = crescent(probe, (cx, 0.0), n=10)
    zmax = max(v[2] for v in probe.verts)
    cz = z1 - zmax                      # top of crescent lands exactly on z_top
    crescent(acc, (cx, cz), n=10)
    # outer point nearest the shaft axis (bottom of the C)
    ang_b = -math.acos(max(-1, min(1, (xs - cx) / 0.10)))
    z_b = cz + 0.10 * math.sin(ang_b)   # underside of crescent above the shaft

    # ---------------------------------------------------------------- gem + pin
    u = Vector((math.cos(math.radians(45)), math.sin(math.radians(45))))
    gem_c = Vector((cx + 0.016 * u.x, 0.0, cz + 0.016 * u.y + 0.004))
    gem(acc, gem_c, 0.052)
    # slim gold pin from crescent bottom to gem
    prism(acc, (xs, 0.0, z_b), (gem_c.x - xs, 0.0, gem_c.z - z_b - 0.03),
          [(0.0, 0.0042), (math.hypot(gem_c.x - xs, gem_c.z - z_b - 0.03), 0.0042)],
          GOLD, n=4, phase=math.pi / 4)

    # ---------------------------------------------------------------- collar (gold, under the crescent)
    prism(acc, (xs, ys, z_b - 0.105), (0, 0, 1), [
        (0.000, 0.0155),
        (0.012, 0.0265),   # swelling
        (0.034, 0.0265),
        (0.052, 0.0170),
        (0.058, 0.0215),   # top ring
        (0.074, 0.0215),
        (0.088, 0.0150),
        (0.106, 0.0110),   # tucks into the crescent's underside
    ], GOLD, n=6)

    # ---------------------------------------------------------------- shaft (red hexagon)
    z_ferrule_top = z0 + 0.16
    z_collar_bot = z_b - 0.105
    prism(acc, (xs, ys, z_ferrule_top - 0.02), (0, 0, 1),
          [(0.0, r), (z_collar_bot + 0.004 - (z_ferrule_top - 0.02), r)], RED, n=6)

    # ---------------------------------------------------------------- spear tip + ferrule (gold)
    # diamond blade, pointed down: 4 facets, flattened in Y like a folded leaf
    prism(acc, (xs, ys, z0), (0, 0, 1), [
        (0.000, 0.0),
        (0.050, 0.0215),
        (0.082, 0.0105),
        (0.092, 0.0075),
    ], GOLD, n=4, phase=math.pi / 2, squash=(1.0, 0.62))
    # ferrule: small hex collar where the shaft starts
    prism(acc, (xs, ys, z0 + 0.088), (0, 0, 1), [
        (0.000, 0.0110),
        (0.007, 0.0175),
        (0.022, 0.0175),
        (0.030, 0.0145),
        (0.040, 0.0145),
        (0.046, 0.0165),
        (0.056, 0.0165),
        (0.062, 0.0130),
    ], GOLD, n=6)

    # ---------------------------------------------------------------- ribbons (red folded strips)
    def ribbon(x_start, z_start, y_start, length, drift, widths, folds, thickness=0.0035):
        rows = []
        m = len(widths)
        for i, w in enumerate(widths):
            t = i / m
            x = x_start + drift * (t ** 1.3)
            z = z_start - length * t
            y = y_start + folds[i % len(folds)] * 0.0
            c = Vector((x, y, z))
            fold = folds[i % len(folds)]
            rows.append([c + Vector((-w / 2, 0.0, 0.0)),
                         c + Vector((0.0, fold, 0.0)),
                         c + Vector((w / 2, 0.0, 0.0))])
        # pointed tip
        t = 1.0
        tip = Vector((x_start + drift, y_start, z_start - length))
        rows.append([tip])
        sheet(acc, rows, thickness, RED)

    z_r = cz - 0.1 + 0.012
    ribbon(xs - 0.052, z_r, -0.020, 0.25, -0.050,
           [0.026, 0.030, 0.030, 0.026, 0.020, 0.012], [-0.006, 0.005, -0.005, 0.005, -0.004, 0.003])
    ribbon(xs - 0.050, z_r, 0.000, 0.165, -0.014,
           [0.020, 0.022, 0.020, 0.015, 0.009], [-0.005, 0.004, -0.004, 0.004, -0.003])

    # ---------------------------------------------------------------- final object, origin at the grip
    verts = [Vector(v) - grip for v in acc.verts]
    obj = lib.mesh_object("Staff", verts, acc.faces, coll=coll,
                          materials=[lib.mat("red"), lib.gold()], face_mats=acc.mats)
    obj.location = grip
    bpy.context.view_layer.update()  # refresh matrix_world so world_bbox() is right
    return [obj]
