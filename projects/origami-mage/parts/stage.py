"""Stage: seamless cyclorama backdrop, studio lights, hero camera and render settings."""
import math
import os
import re

import bpy
from mathutils import Vector

import lib
import spec

# Hero camera: orthographic, portrait 9:16 like the reference. Figure z 0..1.56 fills ~80% of the height
# and sits slightly below frame centre.
TARGET = Vector((0.0, -0.02, 0.88))   # frame centre in world space
CAM_AZIMUTH_DEG = 11.0        # camera swings towards the character's LEFT (+X): she appears turned to her right
CAM_PITCH_DEG = 5.0           # camera looks slightly downward
CAM_DIST = 6.0
ORTHO_SCALE = 2.0             # metres covered by the frame's long (vertical) side
RES = (1080, 1920)
KEY_LOC, KEY_W, KEY_SIZE = (-1.7, -2.2, 2.7), float(os.environ.get("STAGE_KEY", "260")), 1.0
FILL_W = float(os.environ.get('STAGE_FILL', '20'))
RIM_W = float(os.environ.get('STAGE_RIM', '200'))
BACKDROP_RGB = (0.215, 0.195, 0.172)   # linear; lands near the reference's warm mid grey

def _set(obj, attr, value, log):
    """Set obj.attr if it exists and accepts the value; remember what happened."""
    if not hasattr(obj, attr):
        log.append(f"  - {attr}: not available")
        return False
    try:
        setattr(obj, attr, value)
        log.append(f"  + {attr} = {value}")
        return True
    except (TypeError, ValueError, AttributeError) as exc:
        log.append(f"  - {attr}: rejected ({exc})")
        return False


VIEW_TRANSFORMS = [os.environ.get("STAGE_VT", "AgX"), "AgX", "Standard"]
LOOKS = [os.environ.get("STAGE_LOOK", "AgX - Punchy"), "AgX - Punchy", "None"]
EXPOSURE = float(os.environ.get("STAGE_EXPOSURE", "0.0"))


def _enum_options(obj, attr):
    """Read the valid enum identifiers at runtime (the RNA enum list is dynamic for colour management)."""
    try:
        setattr(obj, attr, "__probe__")
    except TypeError as exc:
        txt = str(exc)
        return [x for x in re.findall(r"'([^']+)'", txt.split("not found in", 1)[-1])]
    return []


def _backdrop_material():
    """Matte warm grey with a gentle vertical falloff (darker towards the top) like the reference."""
    old = bpy.data.materials.get("Backdrop.Mat")
    if old is not None:
        bpy.data.materials.remove(old)
    mat = bpy.data.materials.new("Backdrop.Mat")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    bsdf.inputs["Roughness"].default_value = 0.95
    for name in ("Specular IOR Level", "Specular"):
        if name in bsdf.inputs:
            bsdf.inputs[name].default_value = 0.1
            break
    coord = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    zramp = nt.nodes.new("ShaderNodeMapRange")      # z 0.4..3.6 -> 1.0..0.52
    zramp.inputs["From Min"].default_value = 0.4
    zramp.inputs["From Max"].default_value = 3.6
    zramp.inputs["To Min"].default_value = 1.0
    zramp.inputs["To Max"].default_value = 0.52
    zramp.clamp = True
    xabs = nt.nodes.new("ShaderNodeMath")
    xabs.operation = "ABSOLUTE"
    xramp = nt.nodes.new("ShaderNodeMapRange")      # |x| 0.5..3 -> 1.0..0.75 (side vignette)
    xramp.inputs["From Min"].default_value = 0.5
    xramp.inputs["From Max"].default_value = 3.0
    xramp.inputs["To Min"].default_value = 1.0
    xramp.inputs["To Max"].default_value = 0.75
    xramp.clamp = True
    mulf = nt.nodes.new("ShaderNodeMath")
    mulf.operation = "MULTIPLY"
    tint = nt.nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs["Factor"].default_value = 1.0
    tint.inputs["A"].default_value = (*BACKDROP_RGB, 1.0)
    L = nt.links.new
    L(coord.outputs["Object"], sep.inputs["Vector"])
    L(sep.outputs["Z"], zramp.inputs["Value"])
    L(sep.outputs["X"], xabs.inputs[0])
    L(xabs.outputs["Value"], xramp.inputs["Value"])
    L(zramp.outputs["Result"], mulf.inputs[0])
    L(xramp.outputs["Result"], mulf.inputs[1])
    L(mulf.outputs["Value"], nt.nodes.new("ShaderNodeCombineColor").inputs["Red"])
    comb = nt.nodes[-1]
    L(mulf.outputs["Value"], comb.inputs["Green"])
    L(mulf.outputs["Value"], comb.inputs["Blue"])
    L(comb.outputs["Color"], tint.inputs["B"])
    L(tint.outputs["Result"], bsdf.inputs["Base Color"])
    mat.diffuse_color = (*BACKDROP_RGB, 1.0)
    return mat


def _backdrop(coll):
    """Cyclorama: flat floor -> quarter-circle cove (12 segments) -> vertical wall."""
    y_front, y_cove, cove_r, wall_h = -9.0, 0.75, 0.85, 4.5
    half_w = 4.5
    profile = [(y_front, 0.0), (y_cove, 0.0)]
    for i in range(1, 13):
        a = (math.pi / 2) * i / 12
        profile.append((y_cove + cove_r * math.sin(a), cove_r * (1 - math.cos(a))))
    profile.append((y_cove + cove_r, wall_h))

    verts, faces = [], []
    for y, z in profile:
        verts.append((-half_w, y, z))
        verts.append((half_w, y, z))
    for i in range(len(profile) - 1):
        a = 2 * i
        faces.append((a, a + 1, a + 3, a + 2))
    mat = _backdrop_material()
    obj = lib.mesh_object("Backdrop", verts, faces, material=mat, coll=coll)
    obj.data.polygons.foreach_set("use_smooth", [True] * len(obj.data.polygons))
    obj.data.update()
    # make sure normals face the camera (-Y / +Z)
    if sum(p.normal.z for p in obj.data.polygons[:2]) < 0:
        obj.data.flip_normals()
        obj.data.update()
    return obj


def _area_light(name, loc, target, energy, size, colour, coll, size_y=None, shape="RECTANGLE"):
    data = bpy.data.lights.new(name, "AREA")
    data.energy = energy
    data.shape = shape
    data.size = size
    if shape == "RECTANGLE":
        data.size_y = size_y or size
    data.color = colour
    if hasattr(data, "use_shadow"):
        data.use_shadow = True
    if hasattr(data, "use_contact_shadow"):
        data.use_contact_shadow = True
    if hasattr(data, "contact_shadow_distance"):
        data.contact_shadow_distance = 0.3
    obj = bpy.data.objects.new(name, data)
    coll.objects.link(obj)
    obj.location = loc
    obj.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return obj


def _render_settings(scene):
    log = []
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    log.append(f"engine = {scene.render.engine}")
    scene.render.resolution_x, scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False

    ev = scene.eevee
    _set(ev, "taa_render_samples", 64, log)
    _set(ev, "taa_samples", 32, log)
    _set(ev, "use_taa_reprojection", True, log)
    _set(ev, "use_shadows", True, log)
    _set(ev, "shadow_ray_count", 2, log)
    _set(ev, "shadow_step_count", 8, log)
    _set(ev, "use_soft_shadows", True, log)
    _set(ev, "light_threshold", 0.005, log)
    _set(ev, "use_raytracing", True, log)
    _set(ev, "use_gtao", True, log)             # legacy AO toggle
    _set(ev, "gtao_distance", 0.4, log)
    _set(ev, "gtao_factor", 1.0, log)
    _set(ev, "fast_gi_method", "AMBIENT_OCCLUSION_ONLY", log)
    _set(ev, "fast_gi_distance", 0.6, log)
    _set(ev, "fast_gi_thickness_near", 0.05, log)
    ro = getattr(ev, "ray_tracing_options", None)
    if ro is not None:
        _set(ro, "resolution_scale", "1", log)
        _set(ro, "use_denoise", True, log)
    _set(ev, "use_volumetric_shadows", False, log)

    vs = scene.view_settings
    vt_options, look_options = _enum_options(vs, "view_transform"), None
    pick_vt = next((c for c in VIEW_TRANSFORMS if c in vt_options), vt_options[0])
    vs.view_transform = pick_vt
    look_options = _enum_options(vs, "look")
    pick_look = next((c for c in LOOKS if c in look_options), "None")
    vs.look = pick_look
    log.append(f"available view transforms: {vt_options}")
    log.append(f"available looks ({pick_vt}): {look_options}")
    vs.exposure = EXPOSURE
    vs.gamma = 1.0
    log.append(f"view_transform = {vs.view_transform}, look = {vs.look}, exposure = {vs.exposure}")
    scene.display_settings.display_device = "sRGB"
    scene.render.filter_size = 1.2

    # dim warm world
    world = bpy.data.worlds.get("StageWorld") or bpy.data.worlds.new("StageWorld")
    world.use_nodes = True
    bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
    if bg is not None:
        bg.inputs["Color"].default_value = (0.30, 0.285, 0.27, 1.0)
        bg.inputs["Strength"].default_value = 0.2
    world.color = (0.30, 0.285, 0.27)
    scene.world = world
    log.append("world = warm grey, strength 0.2")
    print("STAGE render settings:\n" + "\n".join(log))


def build():
    scene = bpy.context.scene
    coll = lib.part_collection("Stage", group=spec.SCENE_COLLECTION)
    objs = []

    objs.append(_backdrop(coll))

    # --- lights. Character's right = -X, so upper-left in the camera view = -X, -Y, +Z.
    # Small, directional key so facets facing it are bright and the others clearly darker.
    tgt = (0.0, 0.0, 0.95)
    objs.append(_area_light("Light.Key", KEY_LOC, tgt, KEY_W, KEY_SIZE, (1.0, 0.96, 0.90), coll,
                            size_y=KEY_SIZE))
    # weak, broad fill from the front-right keeps shadow sides mid-grey
    objs.append(_area_light("Light.Fill", (2.8, -3.2, 1.4), tgt, FILL_W, 2.5, (0.92, 0.95, 1.0), coll))
    rim = bpy.data.lights.new("Light.Rim", "SPOT")
    rim.energy = RIM_W
    rim.spot_size = math.radians(38)
    rim.spot_blend = 0.6
    rim.shadow_soft_size = 0.15
    rim.color = (1.0, 0.97, 0.92)
    rim_obj = bpy.data.objects.new("Light.Rim", rim)
    coll.objects.link(rim_obj)
    rim_obj.location = (1.5, 1.0, 2.4)
    rim_obj.rotation_euler = (Vector((0.0, 0.0, 1.3)) - rim_obj.location).to_track_quat("-Z", "Y").to_euler()
    objs.append(rim_obj)

    # --- camera: orthographic, portrait, far away
    az, pitch = math.radians(CAM_AZIMUTH_DEG), math.radians(CAM_PITCH_DEG)
    loc = TARGET + CAM_DIST * Vector((math.sin(az) * math.cos(pitch),
                                      -math.cos(az) * math.cos(pitch), math.sin(pitch)))
    cam_data = bpy.data.cameras.new("Camera.Hero")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ORTHO_SCALE
    cam_data.sensor_fit = "AUTO"
    cam_data.clip_start = 0.5
    cam_data.clip_end = CAM_DIST + 12.0
    cam_data.dof.use_dof = False
    cam = bpy.data.objects.new("Camera.Hero", cam_data)
    coll.objects.link(cam)
    cam.location = loc
    cam.rotation_euler = (TARGET - loc).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam
    objs.append(cam)

    _render_settings(scene)
    bpy.context.view_layer.update()
    print("STAGE camera", tuple(round(v, 3) for v in cam.location),
          tuple(round(math.degrees(a), 2) for a in cam.rotation_euler), "ortho_scale", cam_data.ortho_scale)
    return objs
