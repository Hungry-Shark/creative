"""Rig: Mixamo-named armature, procedural skin weights and the analytic hero pose.

build(pose="hero") -> [armature_obj]

* The armature is built in the REST T-pose from spec landmarks (bone names "mixamorig:*").
* Every character mesh gets vertex groups from procedural, name-driven rules (no bone heat),
  an Armature modifier (first in the stack) and is parented to the rig with the transform kept.
* pose == "hero": the staff is moved into the right hand, the right arm is solved with an
  analytic two-bone IK, the left arm hangs, the head turns. Everything is written as plain pose
  bone transforms (quaternions) computed from armature-space target matrices: no constraints.
* pose == "rest": nothing is posed and the staff is left alone.
"""
import math

import bpy
from mathutils import Matrix, Vector

import lib
import spec

Z, X = spec.Z, spec.X
P = "mixamorig:"

# ---------------------------------------------------------------- tunables (pose / skinning)
CLAVICLE_DROP_DEG = 4.0
HEAD_PITCH_DEG = 3.0
HAND_YAW_IN_DEG = 12.0       # right-hand fingers point forward, turned this much inward (+X)
PALM_SHIFT = 0.010           # shaft sits this far on the palm side of the hand-bone axis
RIGHT_POLE = Vector((-0.75, 0.35, -0.55))  # right elbow: out to her side, down, a little back
LEFT_POLE = Vector((0.25, 1.0, 0.0))       # left elbow: back and slightly out
LEFT_REACH = 0.98            # fraction of full arm length used for the left hand (slight bend)
SHOULDER_BLEND = (-0.06, 0.04)   # shoulder -> arm weight ramp, relative to X["shoulder"]
ELBOW_BLEND = 0.05           # half width of the arm -> forearm ramp around the elbow
WRIST_BLEND = (0.12, 0.045)  # hand weight ramp: from wrist-0.12 (0) to wrist-0.045 (1)
KNEE_BLEND = 0.06
NECK_BLEND = (Z["collar_top"], Z["chin"] + 0.04)


# ================================================================ small maths helpers
def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def ramp(v, lo, hi):
    return smooth((v - lo) / (hi - lo)) if hi != lo else (1.0 if v >= hi else 0.0)


def mat4(rot3, head):
    m = rot3.to_4x4()
    m.translation = head
    return m


def swing(a, b):
    return a.normalized().rotation_difference(b.normalized()).to_matrix()


def about_pivot(rot3, pivot, m):
    """Rotate matrix m by rot3 about the world point `pivot`."""
    return Matrix.Translation(pivot) @ rot3.to_4x4() @ Matrix.Translation(-pivot) @ m


def two_bone(S, W, l1, l2, pole):
    """Elbow position for a two-bone chain from S towards W (clamped to reach)."""
    v = W - S
    d = v.length
    d = max(abs(l1 - l2) + 1e-4, min(l1 + l2 - 1e-4, d))
    dirv = v.normalized()
    a = (l1 * l1 - l2 * l2 + d * d) / (2 * d)
    h = math.sqrt(max(l1 * l1 - a * a, 0.0))
    perp = pole - dirv * pole.dot(dirv)
    perp.normalize()
    return S + dirv * a + perp * h


# ================================================================ armature
def _bone_defs():
    """(name, parent, head, tail, connected, roll_vector) in REST (T-pose), all from spec."""
    zh, zw, zc = Z["hip"], Z["waist"], Z["collar_bottom"]
    z_sp = (zh + zw) / 2             # Spine joint
    z_sp2 = 1.03                     # Spine2 joint
    arm, xs, xe, xw, xt = Z["arm"], X["shoulder"], X["elbow"], X["wrist"], X["hand_tip"]
    xl, zk, za = X["leg"], Z["knee"], Z["ankle"]
    ball = Vector((0, -X["boot_len"] * 0.6, 0.035))
    toe = Vector((0, -X["boot_len"] * 0.72, 0.02))
    FWD, UP = Vector((0, -1, 0)), Vector((0, 0, 1))

    defs = [
        ("Hips", None, (0, 0, zh), (0, 0, z_sp), False, FWD),
        ("Spine", "Hips", (0, 0, z_sp), (0, 0, zw), True, FWD),
        ("Spine1", "Spine", (0, 0, zw), (0, 0, z_sp2), True, FWD),
        ("Spine2", "Spine1", (0, 0, z_sp2), (0, 0, zc), True, FWD),
        ("Neck", "Spine2", (0, 0, zc), (0, 0, Z["chin"]), True, FWD),
        ("Head", "Neck", (0, 0, Z["chin"]), (0, 0, Z["head_top"]), True, FWD),
        ("HeadTop_End", "Head", (0, 0, Z["head_top"]), (0, 0, Z["head_top"] + 0.03), True, FWD),
    ]
    for s, side in ((1, "Left"), (-1, "Right")):
        defs += [
            (f"{side}Shoulder", "Spine2", (s * X["neck_r"], 0, arm), (s * xs, 0, arm), False, UP),
            (f"{side}Arm", f"{side}Shoulder", (s * xs, 0, arm), (s * xe, 0, arm), True, UP),
            (f"{side}ForeArm", f"{side}Arm", (s * xe, 0, arm), (s * xw, 0, arm), True, UP),
            (f"{side}Hand", f"{side}ForeArm", (s * xw, 0, arm), (s * xt, 0, arm), True, UP),
            (f"{side}UpLeg", "Hips", (s * xl, 0, zh), (s * xl, 0, zk), False, FWD),
            (f"{side}Leg", f"{side}UpLeg", (s * xl, 0, zk), (s * xl, 0, za), True, FWD),
            (f"{side}Foot", f"{side}Leg", (s * xl, 0, za), (s * xl, ball.y, ball.z), True, UP),
            (f"{side}ToeBase", f"{side}Foot", (s * xl, ball.y, ball.z), (s * xl, toe.y, toe.z),
             True, UP),
        ]
    return defs


def _make_armature():
    old = bpy.data.objects.get(spec.RIG_NAME)
    if old is not None:
        data = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if data.users == 0:
            bpy.data.armatures.remove(data)
    data = bpy.data.armatures.new(spec.RIG_NAME)
    rig = bpy.data.objects.new(spec.RIG_NAME, data)
    lib.collection(spec.CHARACTER_COLLECTION).objects.link(rig)
    rig.show_in_front = True
    data.display_type = "OCTAHEDRAL"

    prev_active = bpy.context.view_layer.objects.active
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    ebs = data.edit_bones
    for name, parent, head, tail, connected, roll_vec in _bone_defs():
        eb = ebs.new(P + name)
        eb.head = Vector(head)
        eb.tail = Vector(tail)
        if parent:
            eb.parent = ebs[P + parent]
            eb.use_connect = connected
        eb.align_roll(roll_vec)
    bpy.ops.object.mode_set(mode="OBJECT")
    rig.select_set(False)
    bpy.context.view_layer.objects.active = prev_active
    data.bones[P + "HeadTop_End"].use_deform = False
    bpy.context.view_layer.update()
    return rig


# ================================================================ skinning
def _classify(name):
    """-> (kind, side) with side in 'L'/'R'/None. kind None = unknown."""
    side = "R" if name.endswith(".R") else "L" if name.endswith(".L") else None
    for prefixes, kind in (
        (("Head", "Hair", "Ear"), "head"),
        (("Neck",), "neck"),
        (("Collar", "Capelet"), "spine2"),
        (("Torso", "Shirt", "Belt"), "torso"),
        (("Robe",), "hips"),
        (("Sleeve.Cuff", "Sleeve.Tab"), "forearm"),
        (("Arm.",), "arm"),
        (("Hand", "Thumb"), "hand"),
        (("Leg.",), "leg"),
        (("Boot",), "foot"),
    ):
        if name.startswith(prefixes):
            return kind, side
    return None, side


def _spine_blend(z, centres):
    """Piecewise-linear blend of bones whose weights peak at the given (z, bone) centres."""
    if z <= centres[0][0]:
        return {centres[0][1]: 1.0}
    if z >= centres[-1][0]:
        return {centres[-1][1]: 1.0}
    for (z0, b0), (z1, b1) in zip(centres, centres[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            return {b0: 1 - t, b1: t}


def _weights_for(kind, side, p, ctx):
    """Bone weights (dict short bone name -> weight) for a point p in armature space."""
    S = "Left" if side == "L" else "Right"
    ax = abs(p.x)
    if kind == "head":
        return {"Head": 1.0}
    if kind == "neck":
        t = ramp(p.z, *NECK_BLEND)
        return {"Neck": 1 - t, "Head": t}
    if kind == "spine2":
        return {"Spine2": 1.0}
    if kind == "hips":
        return {"Hips": 1.0}
    if kind == "torso":
        return _spine_blend(p.z, ctx["spine_centres"])
    if kind == "forearm":
        return {f"{S}ForeArm": 1.0}
    if kind == "foot":
        return {f"{S}Foot": 1.0}
    if kind == "arm":
        t_s = ramp(ax, X["shoulder"] + SHOULDER_BLEND[0], X["shoulder"] + SHOULDER_BLEND[1])
        t_e = ramp(ax, X["elbow"] - ELBOW_BLEND, X["elbow"] + ELBOW_BLEND)
        return {f"{S}Shoulder": (1 - t_e) * (1 - t_s), f"{S}Arm": (1 - t_e) * t_s,
                f"{S}ForeArm": t_e}
    if kind == "hand":
        t = ramp(ax, X["wrist"] - WRIST_BLEND[0], X["wrist"] - WRIST_BLEND[1])
        return {f"{S}Hand": t, f"{S}ForeArm": 1 - t}
    if kind == "leg":
        t = ramp(p.z, Z["knee"] + KNEE_BLEND, Z["knee"] - KNEE_BLEND)   # 1 below the knee
        return {f"{S}Leg": t, f"{S}UpLeg": 1 - t}
    raise ValueError(kind)


def _nearest_bone(rig, pts):
    """Fallback for unknown mesh names: the deform bone whose segment is closest to the centroid."""
    c = sum(pts, Vector()) / max(len(pts), 1)
    best, best_d = None, 1e9
    for b in rig.data.bones:
        if not b.use_deform:
            continue
        h, t = b.head_local, b.tail_local
        seg = t - h
        u = max(0.0, min(1.0, (c - h).dot(seg) / seg.length_squared))
        d = (c - (h + seg * u)).length
        if d < best_d:
            best, best_d = b.name, d
    return best


def _skin(rig, meshes):
    centres = []
    for nm in ("Spine", "Spine1", "Spine2"):
        b = rig.data.bones[P + nm]
        centres.append(((b.head_local.z + b.tail_local.z) / 2, nm))
    ctx = {"spine_centres": centres}
    report = {}
    for obj in meshes:
        for vg in list(obj.vertex_groups):
            obj.vertex_groups.remove(vg)
        for m in [m for m in obj.modifiers if m.type == "ARMATURE"]:
            obj.modifiers.remove(m)
        mw = obj.matrix_world
        pts = [mw @ v.co for v in obj.data.vertices]
        kind, side = _classify(obj.name)
        if kind is None:
            bone = _nearest_bone(rig, pts)
            print(f"RIG WARNING: no skin rule for '{obj.name}', all vertices -> {bone}")
            fixed = {bone[len(P):]: 1.0}
        else:
            fixed = None
            if side is None and kind in ("arm", "hand", "leg", "foot", "forearm"):
                side = "L" if sum(p.x for p in pts) >= 0 else "R"
                print(f"RIG WARNING: '{obj.name}' has no side suffix, using {side} from its position")
        groups = {}
        for i, p in enumerate(pts):
            w = fixed if fixed else _weights_for(kind, side, p, ctx)
            tot = sum(w.values())
            for bn, val in w.items():
                if val / tot > 1e-4:
                    groups.setdefault(bn, []).append((i, val / tot))
        for bn, items in groups.items():
            vg = obj.vertex_groups.new(name=P + bn)
            for i, val in items:
                vg.add([i], val, "REPLACE")
        mod = obj.modifiers.new("Armature", "ARMATURE")
        mod.object = rig
        mod.use_vertex_groups = True
        # Deform before solidify etc. NOTE: compare by name. RNA wrappers are new Python
        # objects on every access, so `obj.modifiers[0] is not mod` is always True (infinite loop).
        if obj.modifiers[0].name != mod.name:
            obj.modifiers.move(len(obj.modifiers) - 1, 0)
        obj.parent = rig
        obj.parent_type = "OBJECT"
        obj.matrix_parent_inverse = rig.matrix_world.inverted()
        weighted = {i for items in groups.values() for i, _ in items}
        report[obj.name] = (len(weighted), len(pts), sorted(groups))
    return report


# ================================================================ pose
def _staff_pose(staff):
    """Move the staff into the hero pose. Returns (grip_world, shaft_axis)."""
    staff["rest_matrix"] = [list(row) for row in staff.matrix_world]
    rest = staff.matrix_world.copy()
    tilt = math.radians(spec.HERO["staff_tilt_deg"])
    rot = Matrix.Rotation(-tilt, 3, "Y")             # +Z -> (-sin, 0, cos): top leans to -X
    axis = rot @ Vector((0, 0, 1))
    tip = Vector(spec.HERO["staff_bottom"])
    grip = tip + axis * spec.STAFF["below_grip"]
    staff.matrix_world = Matrix.Translation(grip) @ (rot @ rest.to_3x3()).to_4x4()
    bpy.context.view_layer.update()
    return grip, axis, rest


def _solve_pose(rig, staff_info):
    """Compute armature-space matrices for every bone, then write pose-bone transforms."""
    bones = rig.data.bones
    rest = {b.name: b.matrix_local.copy() for b in bones}
    order = []

    def visit(b):
        order.append(b)
        for c in b.children:
            visit(c)
    for b in bones:
        if b.parent is None:
            visit(b)

    posed = {}
    plan = {}
    N = lambda s: P + s  # noqa: E731

    def default(b):
        if b.parent is None:
            return rest[b.name].copy()
        rel = rest[b.parent.name].inverted() @ rest[b.name]
        return posed[b.parent.name] @ rel

    grip, axis, staff_rest = staff_info
    drop = math.radians(CLAVICLE_DROP_DEG)

    def head_handler(b, m0):
        d = Matrix.Rotation(math.radians(-spec.HERO["head_turn_deg"]), 3, "Z") @ \
            Matrix.Rotation(math.radians(HEAD_PITCH_DEG), 3, "X")
        return about_pivot(d, m0.translation, m0)

    def shoulder_handler(side_sign):
        def h(b, m0):
            target = Vector((side_sign * math.cos(drop), 0, -math.sin(drop)))
            q = swing(m0.col[1].to_3d(), target)
            return about_pivot(q, m0.translation, m0)
        return h

    def arm_handler(side):
        s = 1 if side == "Left" else -1

        def h(b, m0):
            S = m0.translation.copy()
            l1 = bones[N(f"{side}Arm")].length
            l2 = bones[N(f"{side}ForeArm")].length
            hand_b = bones[N(f"{side}Hand")]
            hand_len = hand_b.length
            if side == "Right":
                # --- hand frame: thumb up the shaft, fingers forward, palm towards the staff
                t = axis.normalized()
                yaw = math.radians(HAND_YAW_IN_DEG)
                f = Vector((math.sin(yaw), -math.cos(yaw), 0.0))
                f = (f - t * f.dot(t)).normalized()
                n = t.cross(f)                      # palm normal (f x n = t)
                Rh = rest[hand_b.name].to_3x3()
                f_rest = Rh.col[1]
                b_rest = Vector((0, 0, 1))          # back of the hand in the rest T-pose
                b_rest = (b_rest - f_rest * b_rest.dot(f_rest)).normalized()
                b_new = -n
                B_rest = Matrix((f_rest, b_rest, f_rest.cross(b_rest))).transposed()
                B_new = Matrix((f, b_new, f.cross(b_new))).transposed()
                Q = B_new @ B_rest.transposed()
                R_new = Q @ Rh
                # anchor = where the staff grip sits relative to the hand bone in rest
                g_rest = staff_rest.translation
                loc = Rh.transposed() @ (g_rest - rest[hand_b.name].translation)
                b_loc = Rh.transposed() @ b_rest
                loc = loc - b_loc * PALM_SHIFT
                W = grip - R_new @ loc
                plan["hand_R"] = (R_new, loc)
                pole = RIGHT_POLE
            else:
                T = Vector(spec.HERO["left_hand"])
                u = (T - S).normalized()
                W = T - u * (hand_len / 2)
                v = W - S
                reach = LEFT_REACH * (l1 + l2)
                if v.length > reach:
                    W = S + v.normalized() * reach
                pole = LEFT_POLE
            E = two_bone(S, W, l1, l2, pole)
            plan[side + "_W"] = E + (W - E).normalized() * l2
            u1 = (E - S).normalized()
            q = swing(m0.col[1].to_3d(), u1)
            return mat4(q @ m0.to_3x3(), S)
        return h

    def forearm_handler(side):
        def h(b, m0):
            E = m0.translation
            u2 = (plan[side + "_W"] - E).normalized()
            q = swing(m0.col[1].to_3d(), u2)
            return mat4(q @ m0.to_3x3(), E)
        return h

    def hand_handler(b, m0):
        R_new, _ = plan["hand_R"]
        return mat4(R_new, m0.translation)

    handlers = {
        N("Head"): head_handler,
        N("LeftShoulder"): shoulder_handler(+1),
        N("RightShoulder"): shoulder_handler(-1),
        N("LeftArm"): arm_handler("Left"),
        N("RightArm"): arm_handler("Right"),
        N("LeftForeArm"): forearm_handler("Left"),
        N("RightForeArm"): forearm_handler("Right"),
        N("RightHand"): hand_handler,
    }

    for b in order:
        m0 = default(b)
        posed[b.name] = handlers[b.name](b, m0) if b.name in handlers else m0

    # ---- write pose-bone basis transforms (no constraints)
    for b in order:
        pb = rig.pose.bones[b.name]
        pb.rotation_mode = "QUATERNION"
        if b.parent is None:
            basis = rest[b.name].inverted() @ posed[b.name]
        else:
            rel = rest[b.parent.name].inverted() @ rest[b.name]
            basis = rel.inverted() @ posed[b.parent.name].inverted() @ posed[b.name]
        loc, rotq, _ = basis.decompose()
        pb.location = loc
        pb.rotation_quaternion = rotq
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()
    return posed


# ================================================================ validation
def _validate(rig, report, pose, staff_info, posed):
    print("RIG bones (rest head -> tail):")
    for b in rig.data.bones:
        h, t = b.head_local, b.tail_local
        print(f"RIG   {b.name:28s} ({h.x:+.3f},{h.y:+.3f},{h.z:+.3f}) -> "
              f"({t.x:+.3f},{t.y:+.3f},{t.z:+.3f}) parent={b.parent.name if b.parent else '-'}"
              f"{' connected' if b.use_connect else ''}")
    print("RIG weighted vertices per object:")
    bad = []
    for name, (n_w, n_all, groups) in report.items():
        flag = "" if n_w == n_all else "  <-- UNWEIGHTED VERTS"
        if flag:
            bad.append(name)
        print(f"RIG   {name:22s} {n_w:5d}/{n_all:<5d} groups={[g[:14] for g in groups]}{flag}")
    print("RIG unweighted objects:", bad or "none")

    if pose != "hero":
        return
    dg = bpy.context.evaluated_depsgraph_get()
    rig_eval = rig.evaluated_get(dg)

    def pose_head_tail(name):
        pb = rig_eval.pose.bones[P + name]
        return pb.head.copy(), pb.tail.copy()

    # check my analytic matrices match what Blender evaluated
    err = max((pose_head_tail(n)[0] - posed[P + n].translation).length
              for n in ("Head", "RightHand", "LeftHand", "RightForeArm", "LeftForeArm"))
    print(f"RIG pose max head mismatch (analytic vs evaluated): {err:.5f} m")

    grip, axis, _ = staff_info
    h, t = pose_head_tail("RightHand")
    mid = (h + t) / 2
    print(f"RIG right hand bone centre {tuple(round(c, 3) for c in mid)}  staff grip "
          f"{tuple(round(c, 3) for c in grip)}  distance {(mid - grip).length:.4f} m")
    hand = bpy.data.objects.get("Hand.R")
    if hand is not None:
        me = hand.evaluated_get(dg).to_mesh()
        pts = [hand.matrix_world @ v.co for v in me.vertices]
        c = sum(pts, Vector()) / len(pts)
        off = (c - grip)
        along = off.dot(axis)
        perp = (off - axis * along).length
        print(f"RIG Hand.R mesh centroid {tuple(round(v, 3) for v in c)}: {perp:.4f} m from the "
              f"shaft axis, {along:+.3f} m along it from the grip")
        hand.evaluated_get(dg).to_mesh_clear()
    h, t = pose_head_tail("LeftHand")
    mid = (h + t) / 2
    lh = Vector(spec.HERO["left_hand"])
    print(f"RIG left hand bone centre {tuple(round(c, 3) for c in mid)} vs HERO left_hand "
          f"{tuple(lh)}: distance {(mid - lh).length:.4f} m")
    for nm in ("RightArm", "RightForeArm", "RightHand", "LeftArm", "LeftForeArm"):
        h, t = pose_head_tail(nm)
        print(f"RIG   posed {nm:14s} head {tuple(round(c, 3) for c in h)} "
              f"tail {tuple(round(c, 3) for c in t)}")


# ================================================================ entry point
def _character_meshes():
    coll = bpy.data.collections.get(spec.CHARACTER_COLLECTION)
    if coll is None:
        return []
    return sorted((o for o in coll.all_objects if o.type == "MESH"), key=lambda o: o.name)


def build(pose="hero"):
    meshes = _character_meshes()
    rig = _make_armature()
    report = _skin(rig, meshes)
    bpy.context.view_layer.update()

    staff_info = None
    posed = None
    if pose == "hero":
        staff = bpy.data.objects.get("Staff")
        if staff is None:
            raise RuntimeError("rig: hero pose needs the Staff object (build the staff part first)")
        staff_info = _staff_pose(staff)
        posed = _solve_pose(rig, staff_info)
    _validate(rig, report, pose, staff_info, posed)
    print(f"RIG built '{rig.name}' pose={pose}: {len(rig.data.bones)} bones, "
          f"{len(report)} skinned meshes")
    return [rig]
