"""Helpers shared by every part module: collections, paper materials, mesh building.

Everything here works both in background Blender (`blender --background --python build.py`)
and inside the user's live Blender (via the MCP execute_blender_code tool).
"""
import math

import bpy
from mathutils import Vector

import spec


# ============================================================== collections
def collection(name, parent=None):
    """Get or create a collection linked under `parent` (default: scene root)."""
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
    parent = parent or bpy.context.scene.collection
    if coll.name not in parent.children:
        parent.children.link(coll)
    return coll


def part_collection(part_name, group=spec.CHARACTER_COLLECTION):
    """Collection for one part, e.g. OrigamiMage/Head. Cleared of old objects first."""
    group_coll = collection(group)
    coll = collection(f"{group}.{part_name}", group_coll)
    for obj in list(coll.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    return coll


def clear_scene():
    """Delete every object, then purge orphan meshes, materials and collections."""
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    for coll in list(bpy.data.collections):
        bpy.data.collections.remove(coll)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.curves,
                  bpy.data.cameras, bpy.data.lights):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


# ============================================================== materials
def _principled(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def _set_input(node, names, value):
    for name in names:
        sock = node.inputs.get(name)
        if sock is not None:
            sock.default_value = value
            return True
    return False


def paper(name, color, roughness=0.8, metallic=0.0, fiber=0.0, sheen=0.15):
    """Matte folded-paper material: flat colour plus a faint fibre bump. Cached by name.

    `color` is either an RGB tuple or a key of spec.COLORS.
    """
    if isinstance(color, str):
        color = spec.COLORS[color]
    mat_name = f"Paper.{name}"
    mat = bpy.data.materials.get(mat_name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = _principled(mat)
    rgba = (*color, 1.0)
    _set_input(bsdf, ["Base Color"], rgba)
    _set_input(bsdf, ["Roughness"], roughness)
    _set_input(bsdf, ["Metallic"], metallic)
    _set_input(bsdf, ["Sheen Weight", "Sheen"], sheen)
    # Paper has almost no specular. Higher values make EEVEE raytraced reflections speckle
    # on rough facets (found by the limbs agent: checker noise on boot toes, hair, robe).
    _set_input(bsdf, ["Specular IOR Level", "Specular"], 0.04)
    mat.diffuse_color = rgba  # viewport solid colour

    # Per-facet brightness variation (handmade paper): reads the FACE attribute "paper_var"
    # (0..1) that build.add_paper_variation() writes on every mesh. Missing attr = 0.
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "paper_var"
    mul = nt.nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY_ADD"
    mul.inputs[1].default_value = 0.10   # spread
    mul.inputs[2].default_value = 0.95   # base
    hsv = nt.nodes.new("ShaderNodeHueSaturation")
    _set_input(hsv, ["Color"], rgba)
    nt.links.new(attr.outputs["Fac"], mul.inputs[0])
    nt.links.new(mul.outputs[0], hsv.inputs["Value"])
    nt.links.new(hsv.outputs["Color"], bsdf.inputs["Base Color"])

    if fiber > 0:
        coord = nt.nodes.new("ShaderNodeTexCoord")
        noise = nt.nodes.new("ShaderNodeTexNoise")
        _set_input(noise, ["Scale"], 60.0)
        _set_input(noise, ["Detail"], 6.0)
        bump = nt.nodes.new("ShaderNodeBump")
        _set_input(bump, ["Strength"], fiber)
        _set_input(bump, ["Distance"], 0.002)
        nt.links.new(coord.outputs["Object"], noise.inputs["Vector"])
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def gold():
    return paper("Gold", "gold", roughness=0.45, metallic=0.45, fiber=0.0, sheen=0.1)


def mat(key):
    """Shortcut: the standard paper material for a spec.COLORS key (gold is special)."""
    return gold() if key == "gold" else paper(key.title().replace("_", ""), key)


# ============================================================== mesh building
def mesh_object(name, verts, faces, material=None, coll=None, materials=None, face_mats=None):
    """Create a FLAT-shaded mesh object from raw verts/faces.

    materials + face_mats: optional list of materials and a per-face material index list.
    """
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], [tuple(f) for f in faces])
    me.validate(clean_customdata=False)
    me.update()
    for poly in me.polygons:
        poly.use_smooth = False
    obj = bpy.data.objects.new(name, me)
    (coll or bpy.context.scene.collection).objects.link(obj)
    if materials:
        for m in materials:
            me.materials.append(m)
        if face_mats:
            for poly, idx in zip(me.polygons, face_mats):
                poly.material_index = idx
    elif material is not None:
        me.materials.append(material)
    recalc_normals(obj)
    return obj


def recalc_normals(obj):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()


def ring(center, rx, ry=None, n=8, axis="Z", phase=0.0, jitter=None):
    """Points of an n-gon ellipse around `center`, in the plane normal to `axis`.

    axis 'Z': ring lies in XY (for vertical lofts such as robe, legs, staff).
    axis 'X': ring lies in YZ (for lofts along the T-pose arms).
    phase: rotation in radians. jitter: optional list of per-point radius multipliers
    (handy for irregular, hand-folded facets).
    """
    ry = rx if ry is None else ry
    cx, cy, cz = center
    pts = []
    for i in range(n):
        a = phase + 2 * math.pi * i / n
        k = jitter[i % len(jitter)] if jitter else 1.0
        u, v = math.cos(a) * rx * k, math.sin(a) * ry * k
        if axis == "Z":
            pts.append(Vector((cx + u, cy + v, cz)))
        elif axis == "X":
            pts.append(Vector((cx, cy + u, cz + v)))
        else:  # 'Y'
            pts.append(Vector((cx + u, cy, cz + v)))
    return pts


def loft(name, rings, material=None, coll=None, cap_start=True, cap_end=True,
         closed=True, materials=None, face_mats=None):
    """Skin a list of equal-length point rings into one faceted mesh.

    closed=False lofts open strips (for ribbons, capes, hair locks).
    """
    n = len(rings[0])
    assert all(len(r) == n for r in rings), "all rings need the same point count"
    verts = [p for r in rings for p in r]
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
    return mesh_object(name, verts, faces, material=material, coll=coll,
                       materials=materials, face_mats=face_mats)


def band(name, center, rx, ry, z0, z1, n=8, material=None, coll=None, outset=0.004,
         rx_top=None, ry_top=None, phase=0.0):
    """Trim band: a short open tube between z0 and z1 (gold hem, cuffs, collar edges).

    rx_top/ry_top let it follow a flared surface. `outset` pushes it just outside the
    surface it sits on so it never z-fights.
    """
    cx, cy, _ = center
    rx_top = rx if rx_top is None else rx_top
    ry_top = ry if ry_top is None else ry_top
    r0 = ring((cx, cy, z0), rx + outset, ry + outset, n, phase=phase)
    r1 = ring((cx, cy, z1), rx_top + outset, ry_top + outset, n, phase=phase)
    return loft(name, [r0, r1], material=material or gold(), coll=coll,
                cap_start=False, cap_end=False)


def box(name, center, size, material=None, coll=None):
    """Axis-aligned box from centre and full size (x, y, z)."""
    cx, cy, cz = center
    sx, sy, sz = (s / 2 for s in size)
    v = [(cx + x * sx, cy + y * sy, cz + z * sz)
         for z in (-1, 1) for y in (-1, 1) for x in (-1, 1)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return mesh_object(name, v, f, material=material, coll=coll)


def mirror_x(obj, name=None):
    """Duplicate an object mirrored across the YZ plane (left/right symmetry)."""
    new = obj.copy()
    new.data = obj.data.copy()
    new.name = name or obj.name.replace(".R", ".L").replace("_R", "_L")
    for v in new.data.vertices:
        v.co.x = -v.co.x
    new.data.flip_normals()
    new.data.update()
    for c in obj.users_collection:
        c.objects.link(new)
    return new


def solidify(obj, thickness=0.004):
    """Give an open sheet (cape, hair lock, ribbon) a paper thickness."""
    mod = obj.modifiers.new("PaperThickness", "SOLIDIFY")
    mod.thickness = thickness
    mod.offset = 0.0
    return mod


def world_bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi
