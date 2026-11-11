"""Shared proportions and palette for the Origami Mage. Every part module MUST use these.

v2: proportions re-measured from reference.png (figure height = 1.55 m, as fractions of H):
boots 13.7%, visible legs 7%, robe 0.205H-0.59H, belt at 0.59H, collar top 0.80H,
chin 0.815H. Narrow waist (belt ~12% of H wide), capelet ~28% of H wide, robe hem ~37% of H wide.

Coordinate system
-----------------
* Units: metres. Z is up. Feet stand on z = 0, centred on x = 0.
* The character FACES -Y (towards a camera placed at -Y looking at +Y).
* The character's RIGHT side is -X (viewer's left in the front view).
* MODELLING / REST POSE: T-pose, with arms straight out along +/-X and palms facing down.
  This is the armature rest pose, the Mixamo upload pose.
  The HERO POSE that matches the reference (right hand holding the staff, left arm hanging) is
  applied by posing the armature (parts/rig.py). Never model the hero pose into the meshes.
* Clothing that hangs from the shoulders (the capelet) is modelled in its natural arms-DOWN drape.
  In the T-pose rest the arms simply poke through its sides, which is fine.

Style
-----
Folded paper (origami): low-poly, FLAT-shaded, crisp facets, no smooth shading,
no subdivision. Shapes are built from a few big planar facets. The face is blank,
with no eyes or mouth. Gold paper trim bands outline the clothing edges.
"""

H = 1.55  # figure height to top of hair

# ---------------------------------------------------------------- landmarks (z)
Z = {
    "sole": 0.00,
    "ankle": 0.09,
    "boot_top": 0.21,
    "hem": 0.32,           # bottom edge of robe (bottom of gold hem band)
    "knee": 0.45,
    "hip": 0.80,           # hip joints / top of legs (hidden inside robe)
    "waist": 0.915,        # belt centre
    "belt_half_h": 0.025,  # belt spans waist +/- this
    "capelet_hem": 0.94,   # lowest point of capelet front panels (just above belt top)
    "arm": 1.12,           # T-pose arm axis height = shoulder joint height
    "shoulder_top": 1.17,
    "collar_bottom": 1.17,
    "collar_top": 1.235,
    "chin": 1.26,
    "head_centre": 1.39,
    "head_top": 1.53,      # crown of the skull (hair reaches ~1.56)
}

# ---------------------------------------------------------------- landmarks (x / y)
X = {
    "head_half_w": 0.088,
    "head_half_d": 0.10,     # half depth (y)
    "neck_r": 0.030,
    "torso_waist_half_w": 0.094,
    "torso_waist_half_d": 0.075,
    "torso_chest_half_w": 0.11,
    "torso_chest_half_d": 0.085,
    "capelet_half_w": 0.225, # widest point of the capelet (over the upper arms)
    "shoulder": 0.12,        # T-pose shoulder joint x (+/-)
    "elbow": 0.37,
    "wrist": 0.62,           # sleeve cuff ends here
    "hand_tip": 0.72,
    "robe_waist_half_w": 0.10,
    "robe_hem_half_w": 0.29,
    "robe_hem_half_d": 0.22,
    "leg": 0.062,            # leg centre x (+/-)
    "leg_r": 0.034,
    "boot_len": 0.17,        # toe points towards -Y
}

# Staff: separate prop (NOT part of the Mixamo mesh). Total length 1.445 m.
# Built in REST position: vertical, gripped by the T-pose right hand (-X side).
# Object origin = grip point. The rig moves it into the hero pose.
STAFF = {
    "x": -0.67,
    "y": 0.0,
    "grip_z": 1.12,          # = Z["arm"]
    "below_grip": 0.815,     # spear tip is this far below the grip
    "above_grip": 0.63,      # crescent top is this far above the grip
    "shaft_r": 0.013,
}

# Hero pose targets (world space), measured from the reference
HERO = {
    "staff_bottom": (-0.26, -0.16, 0.045),  # spear tip near the floor, in front of her right side
    "staff_tilt_deg": 4.0,                   # top leans outward (-X)
    # The grip follows from staff_bottom + tilt + STAFF["below_grip"] (≈ (-0.317, -0.16, 0.86)):
    # forearm forward, elbow at her side, like the reference.
    "left_hand": (0.26, -0.03, 0.60),        # left arm hangs down, sleeve bell clear of the robe
    "head_turn_deg": 6.0,                    # slight turn towards her right
}

# ---------------------------------------------------------------- palette (linear-ish sRGB 0..1)
COLORS = {
    "paper_white": (0.86, 0.85, 0.82),
    "hair": (0.80, 0.81, 0.83),
    "hair_shadow": (0.68, 0.69, 0.72),
    "skin": (0.90, 0.74, 0.60),
    "gold": (0.72, 0.53, 0.22),
    "red": (0.45, 0.05, 0.04),
    "black": (0.05, 0.05, 0.055),
    "stocking": (0.12, 0.12, 0.13),
    "boot": (0.30, 0.17, 0.10),
    "backdrop": (0.42, 0.40, 0.38),
}

# ---------------------------------------------------------------- naming
CHARACTER_COLLECTION = "OrigamiMage"   # everything that goes to Mixamo
PROPS_COLLECTION = "Props"             # staff (excluded from Mixamo export)
SCENE_COLLECTION = "Stage"             # backdrop, lights, cameras
RIG_NAME = "OrigamiMage.Rig"           # armature object (Mixamo bone names: mixamorig:Hips ...)
