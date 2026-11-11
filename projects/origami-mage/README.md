# Origami Mage

A folded-paper elf mage built in Blender 5.3 entirely from Python scripts, in a T-pose so Mixamo can rig it. [reference.png](reference.png) is the target look.

## Files
| File | What it is |
|---|---|
| `spec.py` | Shared proportions, landmarks, palette and naming. Every part uses these numbers. |
| `lib.py` | Helpers: paper materials, lofting, trim bands, mirroring, collections. |
| `parts/head.py` | Head, neck, hair and twin tails, elf ears, earrings. |
| `parts/body.py` | Robe, striped shirt, belt, high collar, capelet. |
| `parts/limbs.py` | T-pose bell sleeves, hands, legs, boots. |
| `parts/staff.py` | Crescent-moon staff (a separate prop, not part of the rig). |
| `parts/rig.py` | Armature with Mixamo bone names (`mixamorig:*`), procedural skin weights, and the hero pose that matches the reference. |
| `parts/stage.py` | Seamless studio backdrop, lights, orthographic hero camera, render settings. |
| `build.py` | Builds everything, plus optional preview renders, final render and save. |
| `export_mixamo.py` | Joins the body into one mesh and exports FBX files for Mixamo. |

## Build
From the repo root:
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" --background --factory-startup `
  --python projects/origami-mage/build.py -- `
  --save media/origami-mage/origami_mage.blend --render media/origami-mage/hero.png
```
Build only some parts and get auto-framed previews: `-- --parts head --preview media/origami-mage/previews/head`.
Add `--pose rest` to see the T-pose (the armature's rest pose) instead of the hero pose.

The meshes are modelled in a T-pose because that is the armature's rest pose and what Mixamo expects.
The scene shows her posed like the reference by posing the armature. The export switches back to the T-pose automatically.

## Mixamo
```powershell
& "C:\Program Files\Blender Foundation\Blender 5.3\blender.exe" --background --factory-startup `
  --python projects/origami-mage/export_mixamo.py
```
This writes `media/origami-mage/origami_mage_mixamo.fbx` (the body) and `origami_mage_staff.fbx`.
1. Upload the body FBX at mixamo.com → **Upload Character**.
2. Place the markers on the chin, wrists, elbows, knees and groin, and choose **Standard Skeleton**.
3. Download animations as **FBX Binary, With Skin**, then import them into Blender. Parent the staff to the `mixamorig:RightHand` bone.

Mixamo drops the procedural paper materials, which is expected. The animated rig gets the
materials back from `origami_mage.blend` in the next project.
