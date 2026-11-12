# Diagnostic Symptom-to-Fix Matrix & Special Workflows

This document details the root causes, cheapest effective remediation steps, and specialized workflows for image creation, editing, and consistency.

---

## 1. Hierarchy of Cheapest Effective Fixes

When a defect is detected during QC, do NOT re-roll blindly. Follow this cost-and-fidelity hierarchy:

```text
[Level 1: Zero Generation Cost — Instant CLI Fixes via qc_tools.py]
  └── Reframe & Crop: `python "<SKILL_DIR>/scripts/qc_tools.py" crop <image> --aspect 16:9 --out fixed.png`
  └── Optical Calibration: `python "<SKILL_DIR>/scripts/qc_tools.py" adjust <image> --temp -12 --saturation 0.88 --gamma 0.92 --out fixed.png`
  └── Text/Logo Overlay: `python "<SKILL_DIR>/scripts/qc_tools.py" text-overlay <image> --text "HEADLINE" --subtext "Copy" --position left --color auto --out banner.png`

[Level 2: Targeted Local Inpainting / Edit (Single Model Call)]
  └── Conversational Edit (Gemini Image / GPT-Image): Pass candidate image and specify localized fix
  └── Binary Mask Inpaint (Flux Fill / SDXL): `python "<SKILL_DIR>/scripts/qc_tools.py" mask <image> --tiles 7,8 --out mask.png`
  └── Pass instruction: "Keep 100% of unmasked background and subject identical"

[Level 3: Prompt Layer Re-alignment (Single Full Re-roll)]
  └── Isolate contradictory tokens (e.g., "cinematic" clashing with "neutral overcast")
  └── Apply positive physical constraint (e.g., "contact shadow grounding mug to surface")
  └── Regenerate candidate with seed adjustment

[Level 4: Scene Simplification (Architecture Redesign)]
  └── Reduce scene complexity (reduce crowd from 4 people to 1; switch from reflective glass to matte surface)
  └── Elevate to Human Review Gate if unresolved after 2 attempts
```

---

## 2. Symptom → Diagnostic Root Cause → Corrective Action

| Observed Defect / Symptom | Root Cause | Cheapest Effective Action | Prompt / Code Fix |
| :--- | :--- | :--- | :--- |
| **Plastic Skin / Waxy Face** | Model beauty-filter defaults; adjectives like "flawless", "smooth", "beautiful". | Prompt keyword swap | Strip all beauty adjectives. Add: `candid documentary photo, natural unretouched skin texture, visible pores, subtle skin tone variation, 5000K daylight`. |
| **Teal & Orange / AI Glow** | Buzzwords like "cinematic", "epic", "dramatic lighting", "hyperdetailed". | Prompt keyword swap | Replace with: `neutral color grade, true-to-life color reproduction, natural ambient lighting, neutral gray balance`. |
| **Floating Objects (No Grounding)** | Missing contact physics; model placed object as independent layer without occlusion. | Inpaint or Prompt Refinement | Explicitly prompt contact geometry: `resting firmly on [surface] with a distinct ambient occlusion contact shadow directly beneath the base`. |
| **Garbled / Alien Typography** | Model lacks glyph dictionary for cursive/small text; text prompt too long. | Level 1: Overlay | Generate with clean blank label/signboard (`smooth blank white ceramic mug`). Overlay high-resolution typography post-generation using HTML/Canvas or graphics tool. |
| **Conflicting Shadow Directions** | Prompt specified multiple conflicting lights (e.g. "golden hour sun AND bright studio neon"). | Prompt keyword swap | Enforce the **One Light Rule**: `one primary light source: 45-degree diffused morning sunlight from camera-left; ambient room fill only`. |
| **Extra / Fused Fingers** | Complex hands requested in open air or holding intricate geometry. | Level 2 Inpaint or Pose Swap | Simplify hand pose: `hands resting flat on table, palms down, five distinct fingers clearly visible` or engage with a simple solid prop (e.g. holding a mug by the base). |
| **Warped Walls / Leaning Buildings** | Wide-angle distortion without perspective correction. | Level 1 Crop or Prompt Swap | Specify: `shot on 24mm architectural tilt-shift lens, straight vertical lines, zero keystone perspective distortion`. |
| **Melting / Hallucinated Background** | Underspecified background left to model random walk. | Prompt Layer 3 Enhancement | Explicitly bound the space: `clean Scandinavian interior, smooth light-gray plaster wall, single framed minimalist line-art print in background`. |

---

## 3. Reconciling Post-Processing: Correction vs. Embellishment

A frequent error in image craft is confusing **optical calibration** with **artificial filter overlays**.

### Permissible Optical Calibration (All Realistic Images)
- **White Balance Correction:** Removing unwanted yellow/blue ambient cast to achieve neutral whites.
- **Dynamic Range Optimization:** Preventing blown highlights (<248 luminance) and crushed shadows (>8 luminance).
- **Geometric Alignment:** Straightening horizons and correcting vertical keystoning.
- **Output-Size Sharpening:** Applying a subtle unsharp mask only after resizing to target display dimensions.

### Forbidden vs. Conditional Embellishments
- 🚫 **Forbidden in Clean Commercial / Product / Architecture / UI:**
  - Artificial film grain overlays
  - Heavy vignettes (darkened edges)
  - Chromatic aberration (color fringing at edges)
  - Artificial lens flares and volumetric light beams
- ⚠️ **Permissible ONLY When Explicitly Mandated by Historical / Film Brief:**
  - When the brief explicitly requests `1970s 35mm film aesthetic` or `vintage Polaroid look`: subtle 35mm organic film grain and mild edge light falloff are acceptable, but must be physically motivated by the simulated film stock.

---

## 4. Specialized Workflows

### 4.1 Editing an Uploaded Photo (Inpainting & Preservation)
When modifying an existing image provided by the user:
1. **Preservation First:** Never regenerate the whole image if only a sub-element needs alteration.
2. **Mask Isolation:** Create a bounding box or alpha mask strictly around the element to be modified (e.g., changing a shirt color or removing a distracting background item).
3. **Context Anchor:** In the edit prompt, describe the surrounding environment to ensure the boundary blends seamlessly: *"Seamlessly blend with the existing wooden table surface and lighting direction."*
4. **Resolution Match:** Export at the exact pixel dimensions and DPI of the source file.

### 4.2 Reference Image & Style Transfer
When given a reference image for style, composition, or character:
1. **Deconstruct Attributes:** Break reference down into 3 buckets:
   - *Compositional Structure:* Camera angle, subject placement, horizon height.
   - *Color & Light Profile:* Key light angle, color temperature, shadow softness.
   - *Stylistic Medium:* 35mm film, oil painting, vector illustration, digital 3D.
2. **Transfer Style, Not Subject:** Apply the lighting and medium parameters while substituting the new subject explicitly.
3. **Avoid Token Contamination:** Do not copy arbitrary adjectives from reference descriptions; translate them into concrete physical nouns.

### 4.3 Multi-Image Series & Character / Brand Consistency
When creating a series of 3 or more assets that must look unified:
1. **Lock the Camera & Light Rig:** Keep Focal Length, Aperture, Key Light Direction, and Color Temperature identical across all prompts.
2. **Consistent Color Token Palette:** Define 2 primary colors and 1 neutral background tone in exact terms across the series (e.g., `matte slate gray walls, natural walnut wood, terracotta accent`).
3. **Fixed Character Anchor:** When depicting the same person across multiple scenes:
   - State specific invariant physical traits: `a 34-year-old East Asian woman with shoulder-length straight black hair with middle part, slight freckles across the bridge of nose, wearing an unbranded navy merino wool crewneck sweater`.
   - Keep this anchor string identical across all prompts; vary only the environment, action, and angle.

### 4.4 Non-Photo Realism (Illustrations, 3D Renders, Vector Art)
Do not force photographic rules (skin pores, camera lenses) onto stylized media:
- **Vector / Flat Art:** Specify clean geometric paths, solid pantone fills, sharp vector edges, absence of photographic gradients.
- **3D Render / Product CAD:** Specify rendering engine aesthetic (`clean industrial design 3D visualization, Keyshot render, studio clay backdrop, ambient occlusion`).
- **Concept Art / Digital Matte:** Specify brush stroke characteristics (`painterly digital concept art, visible expressive brushwork, atmospheric perspective`).
- **Adapted QC:** Check for vector overlap artifacts, poly-mesh clipping, and line weight consistency rather than camera optics.
