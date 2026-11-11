"""Build the Origami Mage scene.

Background (what subagents use, renders preview PNGs):
    "C:/Program Files/Blender Foundation/Blender 5.3/blender.exe" --background --factory-startup \
        --python projects/origami-mage/build.py -- --parts head --preview media/origami-mage/previews/head

Options after `--`:
    --parts a,b,c     parts to build (default: all). Names: head, body, limbs, staff, rig, stage
    --pose hero|rest  hero = posed like the reference (default), rest = T-pose
    --preview PREFIX  render PREFIX_front.png, _side.png, _three_quarter.png, _back.png
                      with auto-framed temporary cameras around what was built
    --render PATH     render the final Stage camera to PATH (needs the stage part)
    --save PATH       save the .blend

Live Blender (MCP execute_blender_code):
    import sys; sys.argv = ["blender", "--", "--save", ".../origami_mage.blend"]
    exec(open(r".../build.py").read())
"""
import argparse
import importlib
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    r"C:\Users\LENOVO\creative\projects\origami-mage"
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import lib  # noqa: E402
import spec  # noqa: E402

ALL_PARTS = ["head", "body", "limbs", "staff", "rig", "stage"]


def add_paper_variation(seed=7):
    """Random per-face value in the FACE attribute 'paper_var' (read by lib.paper materials)."""
    import random
    rnd = random.Random(seed)
    for o in sorted(bpy.data.objects, key=lambda o: o.name):
        if o.type != "MESH" or o.name.startswith("Backdrop"):
            continue
        me = o.data
        attr = me.attributes.get("paper_var") or me.attributes.new("paper_var", "FLOAT", "FACE")
        attr.data.foreach_set("value", [rnd.random() for _ in me.polygons])


def load_part(name):
    for mod in ("spec", "lib"):
        importlib.reload(sys.modules[mod])
    mod = importlib.import_module(f"parts.{name}")
    return importlib.reload(mod)


def set_engine_eevee(scene, samples=32):
    try:
        scene.render.engine = "BLENDER_EEVEE"
    except TypeError:
        scene.render.engine = "BLENDER_EEVEE_NEXT"
    try:
        scene.eevee.taa_render_samples = samples
    except AttributeError:
        pass
    scene.view_settings.view_transform = "AgX"


def render_previews(objs, prefix, res=640):
    """Auto-framed preview renders of `objs` from 4 directions, with temporary lights."""
    scene = bpy.context.scene
    set_engine_eevee(scene, samples=16)
    scene.render.resolution_x = res
    scene.render.resolution_y = res
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("World")
    scene.world.color = (0.35, 0.35, 0.36)

    lo, hi = lib.world_bbox(objs)
    centre = (lo + hi) / 2
    radius = max((hi - lo).length / 2, 0.05)

    temp = []
    has_stage_lights = any(o.type == "LIGHT" for o in scene.objects)
    if not has_stage_lights:
        for loc, energy in (((-2, -3, 3), 400), ((3, -1, 2), 150), ((0, 3, 3), 200)):
            ld = bpy.data.lights.new("PreviewLight", "AREA")
            ld.energy = energy
            ld.size = 2.0
            lo_obj = bpy.data.objects.new("PreviewLight", ld)
            scene.collection.objects.link(lo_obj)
            lo_obj.location = centre + Vector(loc)
            lo_obj.rotation_euler = (centre - lo_obj.location).to_track_quat("-Z", "Y").to_euler()
            temp.append(lo_obj)

    views = {
        "front": Vector((0, -1, 0.15)),
        "side": Vector((1, 0, 0.1)),            # character's left side
        "three_quarter": Vector((-0.7, -1, 0.3)),
        "back": Vector((0, 1, 0.15)),
    }
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 85
    cam = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam)
    temp.append(cam)
    prev_cam = scene.camera
    scene.camera = cam
    fov = 2 * math.atan(cam_data.sensor_width / (2 * cam_data.lens))
    dist = radius / math.sin(fov / 2) * 1.05

    os.makedirs(os.path.dirname(os.path.abspath(prefix)), exist_ok=True)
    for vname, d in views.items():
        cam.location = centre + d.normalized() * dist
        cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam_data.clip_end = dist * 4
        scene.render.filepath = os.path.abspath(f"{prefix}_{vname}.png")
        bpy.ops.render.render(write_still=True)
        print("PREVIEW", scene.render.filepath)

    scene.camera = prev_cam
    for o in temp:
        data, is_light = o.data, o.type == "LIGHT"
        bpy.data.objects.remove(o, do_unlink=True)
        if data.users == 0:
            (bpy.data.lights if is_light else bpy.data.cameras).remove(data)


def main(argv=None):
    argv = argv if argv is not None else (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default=",".join(ALL_PARTS))
    ap.add_argument("--preview")
    ap.add_argument("--render")
    ap.add_argument("--save")
    ap.add_argument("--no-clear", action="store_true")
    ap.add_argument("--pose", default="hero", choices=["hero", "rest"],
                    help="armature pose applied by the rig part (rest = T-pose)")
    args = ap.parse_args(argv)

    if not args.no_clear:
        lib.clear_scene()
    parts = [p.strip() for p in args.parts.split(",") if p.strip()]
    built = []
    for name in parts:
        if name == "rig":
            add_paper_variation()          # before rig, so it only touches finished meshes
            objs = load_part(name).build(pose=args.pose) or []
        else:
            objs = load_part(name).build() or []
        print(f"BUILT {name}: {len(objs)} objects")
        built.extend(objs)
    if "rig" not in parts:
        add_paper_variation()
    bpy.context.view_layer.update()

    if args.preview:
        meshes = [o for o in built if o.type == "MESH" and not o.name.startswith("Backdrop")]
        render_previews(meshes or built, args.preview)
    if args.render:
        scene = bpy.context.scene
        scene.render.filepath = os.path.abspath(args.render)
        bpy.ops.render.render(write_still=True)
        print("RENDER", scene.render.filepath)
    if args.save:
        os.makedirs(os.path.dirname(os.path.abspath(args.save)), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.save))
        print("SAVED", args.save)
    return built


if __name__ == "__main__":
    main()
