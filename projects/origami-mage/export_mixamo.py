"""Export the Origami Mage body as a single T-pose mesh FBX ready for Mixamo's auto-rigger.

What it does (the scene itself is left untouched):
  1. Builds the character if the OrigamiMage collection is missing.
  2. Copies every mesh in the OrigamiMage collection (NOT the staff or stage), applies
     modifiers such as paper thickness, and joins the copies into one mesh.
  3. Applies transforms, puts the origin at the feet and exports an FBX with Mixamo-friendly settings.
  4. Deletes the temporary joined mesh again.

Background:
    "C:/Program Files/Blender Foundation/Blender 5.3/blender.exe" --background --factory-startup \
        --python projects/origami-mage/export_mixamo.py
Live Blender (MCP):  exec(open(r".../export_mixamo.py").read()); export()

Then upload media/origami-mage/origami_mage_mixamo.fbx at mixamo.com → Upload Character,
place the chin / wrists / elbows / knees / groin markers, and pick "Standard Skeleton".
The staff is exported separately (origami_mage_staff.fbx) so it can be parented to the
right-hand bone after the animation comes back into Blender.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else \
    r"C:\Users\LENOVO\creative\projects\origami-mage"
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import bpy  # noqa: E402

import spec  # noqa: E402

OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "media", "origami-mage"))


def _meshes_in(coll_name):
    coll = bpy.data.collections.get(coll_name)
    return [o for o in coll.all_objects if o.type == "MESH"] if coll else []


def _joined_copy(objs, name):
    """Evaluated (modifiers applied) copies of objs joined into one new mesh object."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    copies = []
    for o in objs:
        me = bpy.data.meshes.new_from_object(o.evaluated_get(depsgraph))
        me.transform(o.matrix_world)
        c = bpy.data.objects.new(f"_tmp_{o.name}", me)
        bpy.context.scene.collection.objects.link(c)
        copies.append(c)
    bpy.ops.object.select_all(action="DESELECT")
    for c in copies:
        c.select_set(True)
    bpy.context.view_layer.objects.active = copies[0]
    bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = name
    joined.data.name = name
    return joined


def _export_fbx(obj, path):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.fbx(
        filepath=path,
        use_selection=True,
        object_types={"MESH"},
        apply_scale_options="FBX_SCALE_ALL",
        axis_forward="-Z",
        axis_up="Y",
        use_mesh_modifiers=True,
        mesh_smooth_type="FACE",
        add_leaf_bones=False,
        bake_anim=False,
        path_mode="AUTO",
    )


def export():
    if not _meshes_in(spec.CHARACTER_COLLECTION):
        import build
        build.main(["--parts", "head,body,limbs,staff"])

    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    os.makedirs(OUT_DIR, exist_ok=True)

    # Export the T-pose: temporarily switch the armature to its rest position
    rig = bpy.data.objects.get(spec.RIG_NAME)
    prev_pose = rig.data.pose_position if rig else None
    if rig:
        rig.data.pose_position = "REST"
    try:
        return _export_all()
    finally:
        if rig:
            rig.data.pose_position = prev_pose
            bpy.context.view_layer.update()


def _export_all():
    bpy.context.view_layer.update()
    # The staff sits in the hand in the hero pose; for the separate staff FBX, the rig
    # part stores its rest matrix in the custom property "rest_matrix" when it moves it.
    staff = bpy.data.objects.get("Staff")
    staff_hero = None
    if staff is not None and "rest_matrix" in staff:
        from mathutils import Matrix
        staff_hero = staff.matrix_world.copy()
        staff.matrix_world = Matrix([list(r) for r in staff["rest_matrix"]])
        bpy.context.view_layer.update()

    results = {}
    for coll_name, obj_name, file_name in (
        (spec.CHARACTER_COLLECTION, "OrigamiMage_Body", "origami_mage_mixamo.fbx"),
        (spec.PROPS_COLLECTION, "OrigamiMage_Staff", "origami_mage_staff.fbx"),
    ):
        objs = _meshes_in(coll_name)
        if not objs:
            print(f"SKIP {coll_name}: no meshes")
            continue
        joined = _joined_copy(objs, obj_name)
        path = os.path.join(OUT_DIR, file_name)
        _export_fbx(joined, path)
        me = joined.data
        dims = tuple(round(d, 3) for d in joined.dimensions)
        results[file_name] = {"faces": len(me.polygons), "verts": len(me.vertices), "size_m": dims}
        print(f"EXPORTED {path} faces={len(me.polygons)} verts={len(me.vertices)} size={dims}")
        bpy.data.objects.remove(joined, do_unlink=True)
        bpy.data.meshes.remove(me)
    if staff_hero is not None:
        staff.matrix_world = staff_hero
    return results


if __name__ == "__main__":
    export()
