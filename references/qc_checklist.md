# Calibrated Quality Control (QC) Checklist & Human Review Gate

This document defines the inspection protocol, capability verification, confidence boundaries, and human review gates for natural image craft.

---

## 1. Capability Verification & Fallbacks

Before running inspection, determine your active tool environment:

| Required Capability | Ideal Path (`qc_tools.py` v2.2) | Fallback Path (When CLI/Script Unavailable) |
| :--- | :--- | :--- |
| **Composite 4-Panel Board (Quick Mode)** | `python "<SKILL_DIR>/scripts/qc_tools.py" board <image>` (1 vision tool call for grid + flip + anomaly map + 100% zoom) | Prompt vision model with quadrant bounding coordinates: inspect `[0,0, 0.33,0.33]` to `[0.66,0.66, 1.0,1.0]`. |
| **Full 3×3 Tiling (Full Mode)** | `python "<SKILL_DIR>/scripts/qc_tools.py" tile <image>` | Zoom into specific high-risk regions manually. |
| **Mirror Flip** | `python "<SKILL_DIR>/scripts/qc_tools.py" flip <image>` (included automatically in Panel 2 of `board`) | Inspect eye axes and horizon slope by checking pixel coordinate levels. |
| **Optical Telemetry & Clipping** | `python "<SKILL_DIR>/scripts/qc_tools.py" analyze <image> --json` (computes 2D Laplacian sharpness, studio-sweep-aware clipping, neon gamut, teal-orange index, and micro-texture) | Visual check of deepest shadow areas and brightest highlights. |
| **Inpainting / Local Fix** | `python "<SKILL_DIR>/scripts/qc_tools.py" mask <image> --tiles X --out mask.png` (or conversational edit) | Level-1 `qc_tools.py crop` / `adjust` or positive re-prompting. |
| **Upscaling** | Bicubic / Real-ESRGAN / API upscaler | Generate directly at target production resolution (e.g. 1536×1024 or 2048×1152). |

---

## 2. Confidence Calibration: What Vision Models Can and Cannot Trust

Vision models (GPT-4o, Claude 3.5/3.7/Opus, Gemini 1.5/2.5/3.0) possess uneven visual perceptual accuracy. Treating all vision self-checks as equally reliable causes silent hallucinated passes.

### Category A: High-Confidence Self-Inspection (Agent Vision is Reliable)
*The agent may mark these PASS/FAIL with high autonomy.*
1. **Dominant Lighting Direction:** Key shadow orientation matches the stated light source.
2. **Gross Anatomy & Silhouette:** Subject has correct number of arms, legs, and heads; no detached limbs or floating torsos.
3. **Horizon & Perspective Balance:** Horizon is level (unless Dutch angle intended); vertical architectural walls are upright.
4. **General Color Harmony & Palette:** Absence of jarring chromatic aberration or neon color fringing.
5. **Macro Negative Space & Layout:** Copy space is clear; subject placement adheres to intended framing (rule of thirds / centered).

### Category B: Low-Confidence Self-Inspection (Human Review Gate Triggers)
*Vision models frequently hallucinate or overlook errors here. Any check in this category that cannot be verified with 100% mathematical certainty MUST be routed to the Human Review Gate.*
1. **Finger Counts & Joint Articulation:** Individual phalanges, overlapping fingers, thumbnails, and hand-object interactions.
2. **Micro-Typography & Glyph Accuracy:** Brand logos, labels on packaging, book titles, small street signs.
3. **Catchlight & Corneal Reflection Symmetry:** Do highlights in the left and right eyes reflect the exact same physical light source and angle?
4. **Teeth & Dental Anatomy:** Number of visible incisors/canines, absence of continuous fused dental bars.
5. **Contact Shadows & Gravitational Grounding:** Micro-shadow at the exact boundary where an object rests on a surface (absence causes "floating" appearance).
6. **Material Translucency & Refraction:** Light passing through liquids, glass, thin fabric, or ear cartilage (subsurface scattering).

---

## 3. Seven-Stage Inspection Protocol

Follow this exact sequence for each candidate image:

### Stage 1: The Thumbnail Test (200 px)
- Shrink view or step back.
- **Questions:** Does the silhouette read instantly? Is the focal point immediately obvious? Does the emotional tone/mood match the brief?
- **Pass condition:** Primary subject clear in < 1 second.

### Stage 2: The 5-Second Full-Frame Impression
- View at 100% monitor view for 5 uninterrupted seconds.
- **Questions:** Does any element feel synthetic, eerie, or "off"? Is there an unmotivated artificial rim-light or HDR sheen?
- If your initial visual intuition flags an anomaly, isolate the root cause before proceeding.

### Stage 3: Quantitative Optical Telemetry & Anomaly Heatmap
- Run `python "<SKILL_DIR>/scripts/qc_tools.py" board <image>` (or `analyze <image> --json`).
- Check interior subject blown highlights (`< 4.0%`), interior crushed shadows (`< 6.0%`), neon gamut clipping (`S>230`, `< 3.5%`), Teal-Orange split-tone index (`< 30.0`), in-focus micro-texture score (`>= 1.60` or `>= 1.15` on high-separation macro shots; skipped on studio sweeps/dark backdrops or `insufficient_data`), and peak tile Laplacian sharpness (`>= 45.0`). Note: edge-residual micro-texture alone cannot distinguish intentionally smooth matte surfaces from denoised skin, so interpret `WAXY_SMOOTHNESS_WARNING` in scene context.
- Note that clean studio white sweeps (`studio_white_sweep_detected: True`) and studio dark backdrops are automatically excluded from false clipping flags.

### Stage 4: 3×3 Grid & 100% Native Pixel Zoom Inspection
- **Quick Mode (1 Vision Read):** Inspect Panel 1 (3×3 grid with per-tile sharpness scores) and Panel 4 (100% Native Zoom A & B) on the generated `<stem>_qc_board.png`.
- **Full Mode (Deep Tile Audit):** If any tile shows potential defects, run `python "<SKILL_DIR>/scripts/qc_tools.py" tile <image>` and review the 9 full-res tiles:
  - **Tile 0 (Top-Left):** Sky/ceiling continuity, light falloff, background consistency.
  - **Tile 1 (Top-Center):** Headroom, hair boundaries (no melting into background), overhead light fixtures.
  - **Tile 2 (Top-Right):** Background architecture, edge distortion.
  - **Tile 3 (Mid-Left):** Fill light behavior, secondary props.
  - **Tile 4 (Mid-Center):** Primary subject facial features, iris symmetry, skin micro-texture, fabric weave.
  - **Tile 5 (Mid-Right):** Key light shadows, horizon continuity across subject.
  - **Tile 6 (Bot-Left):** Surface textures, foreground props, hand placement (if low).
  - **Tile 7 (Bot-Center):** Contact shadows, lap/table interactions, feet/footwear contact.
  - **Tile 8 (Bot-Right):** Secondary contact shadows, framing edges.

### Stage 5: The Horizontal Mirror Flip
- Inspect Panel 2 of `<stem>_qc_board.png` (or run `python "<SKILL_DIR>/scripts/qc_tools.py" flip <image>`).
- Viewing the mirror image with cyan horizontal alignment guides breaks neural familiarity:
  - Check whether the subject's face or eye axis appears lopsided or distorted.
  - Check whether vertical walls visibly lean inward.
  - Check whether perspective lines converge to a plausible level horizon.

### Stage 6: The "Could This Be Photographed?" Reality Check
- **Camera:** Where is the physical tripod/operator standing? Is the lens distance physically possible in this room?
- **Lighting:** What is the physical light source? (Sun, lamp, softbox). Where is it located in 3D space?
- **Physics:** What supports every object in the frame? Are cords plugged in? Are liquids level with gravity?

### Stage 7: Production Context Test
- View the candidate at actual deployment dimensions (e.g. cropped to 16:9 for website header, 1:1 for Instagram, or 9:16 for mobile story).
- Verify that critical subjects, faces, or product labels are not cut off by responsive container crops.

---

## 4. Defect Classification & Scoring Rubric

### Critical Defects (Severity 1 — Must Fix Before Delivery)
*An image with even ONE unresolved Critical defect CANNOT be delivered.*
- Incompatible with brief core intent or messaging.
- Physical impossibility (floating objects with no contact shadow, impossible limb twist).
- Deformed human anatomy (extra fingers, fused digits, warped eyes, missing joints).
- Conflicting primary shadow directions (e.g. shadow falling left while key light is on the left).
- Garbled or misspelled prominent brand text/logos.

### Major Defects (Severity 2 — Fix If Possible; Otherwise Disclose)
*Maximum 2 allowed in final delivery, provided both are explicitly disclosed in the report.*
- Material incoherence (metal looking like wet plastic; wood grain bending unnaturally).
- Minor background repetition or melting geometry in non-focal areas.
- Slight perspective convergence error on non-primary architecture.
- Inconsistent eye catchlight shape across pupils.
- Unnatural color temperature clash between subject and background.

### Minor Defects (Severity 3 — Polish Level)
*Permissible in final delivery with note.*
- Mild compression artifacts or slight edge softening in deep background.
- Faint color banding in smooth gradients (e.g. dusk sky).
- Minor hair strands fading slightly into background bokeh.

---

## 5. The Human Review Gate

### Mandatory Trigger Conditions
The agent MUST pause and flag the image for human review if ANY of the following occur:
1. Hands or feet are in the primary focal plane (Tile 4, 6, or 7) and contain overlapping fingers.
2. Generated image contains text intended for commercial use.
3. Depicts a real existing product where dimensions, ports, buttons, or branding must match reality.
4. Realism target is photojournalism, documentary, or executive portraiture.
5. More than 2 targeted prompt fixes have been attempted without resolving a defect.

### Standard Output Format for QC Gate
Never output a blanket statement like *"QC Passed without issues."* Always output the calibrated status:

```markdown
### Quality Control Verification Report
- **Inspection Tool:** qc_tools.py (3×3 tiling, mirror flip, histogram analysis)
- **High-Confidence Automated Checks:** 14/14 Passed
- **Low-Confidence Risk Items Flagged for Human Eye:** 2 items
  1. *Tile 6 (Bottom-Left):* Left hand index finger partially occluded by cup handle — human should verify knuckle count.
  2. *Tile 4 (Center):* Check catchlight reflection angle in left eye pupil.
- **Defect Summary:** 0 Critical, 1 Major (disclosed), 1 Minor.
- **Gate Recommendation:** APPROVED FOR PROTOTYPE / PENDING HUMAN EYE SIGN-OFF FOR PRODUCTION.
```
