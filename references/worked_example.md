# End-to-End Worked Example: Crafting a Production Image (v2.2)

This worked example traces a complete generation cycle from raw user brief through delivery report, demonstrating every step, artifact, `qc_tools.py` v2.2 telemetry log, and diagnostic fix.

---

## 1. The User Brief
> **User Request:** "I need a realistic website hero banner for our artisanal ceramics brand, Kanso Ware. It should feature our handmade ceramic pour-over dripper resting on a glass carafe during a coffee brew. Clean Japanese craft aesthetic. Leave space on the left for our headline."

---

## 2. Step 0 & 1: Mode Selection & Assumptions Resolution
- **Mode Selected:** **Full Mode** (commercial product hero banner with copy space and brand-critical fidelity).
- **Tool Adapter:** Flux.1 Pro / Fill (via MCP) or Gemini Image.
- **Aspect Ratio:** 16:9 Landscape (`1792x1024` px).
- **Assumptions Logged (in 1 line):**
  > *Assumptions: Raking morning daylight from right; 60% left copy space; dripper is matte speckled stoneware; glass carafe contains 200ml brewed coffee; no hands in frame to keep 100% focus on ceramic form.*

---

## 3. Step 4: The Completed Scene Sheet

| Layer | Parameter | Specification for Kanso Ware Hero |
| :--- | :--- | :--- |
| **1. Intent & Medium** | Type | Commercial product hero photograph for digital flagship store |
| **2. Subject & Action** | Core Object | Conical ceramic pour-over dripper with interior spiral ribbing, seated on a borosilicate glass server containing 200ml freshly brewed amber coffee |
| **3. Environment & Time** | Setting | Quiet tea-bar counter; dark honed basalt stone counter slab against a textured warm-gray clay plaster backdrop |
| **4. Composition** | Framing & Space | Subject positioned in the right 40% of frame; left 60% uncluttered negative space for web typography |
| **5. Lighting** | Key, Fill, Color | Single key source: low morning sun entering at 35° from camera-right; soft silver bounce card camera-left; 4800K natural daylight |
| **6. Camera & Lens** | Lens & DOF | 85mm medium-telephoto; `f/4.5` (dripper and carafe razor-sharp, background softly out of focus) |
| **7. Materials** | Surface Physics | Unglazed iron-flecked stoneware with tactile sandy grit; clear borosilicate glass with realistic refraction; matte honed basalt |
| **8. Physical Entropy** | Motivated Flaws | 1. Faint steam wisp rising from dripper rim<br>2. Subtle organic iron-spot pooling along the dripper ribs<br>3. Soft condensation band inside upper glass neck |
| **9. Constraints** | Color & Cleanliness | Earthy warm palette (iron-gray, amber, charcoal basalt); positive phrasing; zero lens flares; zero brand text in image |

---

## 4. Step 5: The Layered Production Prompt

```text
A commercial studio-quality product photograph of a handmade Japanese ceramic pour-over coffee dripper resting on a clear borosilicate glass server, situated on a dark honed basalt stone counter. The dripper features an unglazed iron-flecked cream stoneware finish with subtle organic iron-spot variations along the exterior ribs. Inside the carafe sits 200ml of warm, translucent amber-brown brewed coffee with realistic light transmission, topped by faint condensation along the upper inner glass neck and a delicate wisp of steam rising into the air.

Composition is an off-center 16:9 landscape framing with the coffee dripper anchored on the right third, while the left two-thirds provides clean, uncluttered negative space against a matte warm-gray clay wall.

Illuminated by a single dominant light source: natural morning sunlight streaming from a window at camera-right at a 35-degree angle, casting soft, elongated contact shadows toward camera-left. Shot at eye-level on an 85mm prime lens at f/4.5, maintaining crisp edge-to-edge clarity on the ceramic dripper and glass while allowing the background wall to soften into gentle organic bokeh. True-to-life color reproduction, neutral 4800K daylight white balance, physical ambient-occlusion contact shadow anchoring the carafe firmly to the basalt slab.
```

---

## 5. Step 7: Initial Quality Control (Candidate 1)

### Single-Command Composite QC Board & Telemetry (`python "<SKILL_DIR>/scripts/qc_tools.py" board candidate_1.png`)
```text
=== Optical & Physical Telemetry (Optic / Natural Image Craft v2.2) ===
  File                          : candidate_1.png
  Dimensions / Aspect           : 1792x1024 (1.75:1)
  Mean Luminance / Contrast     : 118.4 / 49.2
  Studio Backdrop Detected      : WhiteSweep=False, Dark=False
  Interior Blown Highlights     : 0.12% (Global: 0.25%)
  Interior Crushed Shadows      : 0.45% (Global: 0.60%)
  Mean / P95 Saturation         : 48.2 / 142.0 (0-255 scale)
  Neon Gamut Clipping (S>230)   : 0.0%
  Teal-Orange Split-Tone Index  : 8.4 (Threshold: 30.0)
  Midtone Micro-Texture Score   : 2.34 (Waxy floor: 1.15)
  Sharpness (Global / Peak)     : 412.6 / 1284.0 (tile_5_mid_right)
  Focus Separation Ratio        : 34.2x

  [OK] All quantitative optical metrics within natural thresholds.
  [BOARD] Saved 4-panel Composite Diagnostic Board to: candidate_1_qc_board.png
```

### Visual Audit of `candidate_1_qc_board.png`
- **Panel 1 (3×3 Grid & Sharpness):**
  - `Tile #0, #1, #3, #4, #6`: Clean negative space on left 60% (`S: 28.0–37.5`).
  - `Tile #5 (Mid-Right, S: 1284.0)`: Iron-flecked stoneware texture is crisp and authentic.
  - `Tile #8 (Bot-Right, S: 690.2)`: **CRITICAL DEFECT FOUND.** Contact shadow under the right rim of the glass carafe is missing; the carafe base appears to hover 2mm above the basalt slab.
- **Panel 2 (Horizontal Mirror Flip):** Tabletop horizon is strictly level (`0.0°` tilt).

---

## 6. Step 8: Targeted Remediation (Level 2 Masked Inpaint)
Rather than re-rolling the entire image (which would discard the clean copy space and ceramic texture), generate a binary mask for `Tile #8` using `qc_tools.py`:

```powershell
python "<SKILL_DIR>/scripts/qc_tools.py" mask candidate_1.png --tiles 8 --out candidate_1_mask_tile8.png
```

Pass `candidate_1.png` and `candidate_1_mask_tile8.png` to the inpaint tool (or pass `candidate_1.png` to a conversational edit model) with:
> *"Keep 100% of the upper dripper and left background identical. Ground the flat borosilicate glass carafe base firmly onto the dark honed basalt slab with a crisp, dark ambient-occlusion contact shadow directly beneath the glass rim."*

---

## 7. Re-Inspection of Fixed Image (`candidate_1_fixed.png`)
- **Panel 4 (100% Native Zoom B):** Contact shadow now grounds the carafe base to the basalt counter.
- **Defect Count:** 0 Critical, 0 Major, 0 Minor.
- **Human Review Gate:** Approved (`Tile #8` glass-to-stone boundary noted for routine designer check).

---

## 8. Final Delivery Report (Full Mode)

```markdown
### Natural Image Craft Delivery Report

**Project:** Kanso Ware Pour-Over Website Hero Banner | **Output:** 1792 × 1024 px (16:9)  
**Generator:** Flux.1 Pro + Fill | **Mode:** Full Mode | **Runs Used:** 2 / 6 (1 initial + 1 targeted inpaint)  

#### 1. Scene & Optical Setup
- **Camera & Lighting:** 85mm prime at f/4.5, eye-level; single 35° morning sunlight key from camera-right (4800K) + left bounce fill
- **Materials & Motivated Entropy:** Iron-flecked stoneware dripper, borosilicate server, honed basalt slab; steam wisp, condensation band, iron glaze pooling

#### 2. Calibrated QC & Telemetry Summary (`qc_tools.py`)
- **Quantitative Telemetry:** Luminance `118.4`, Contrast `49.2`, Interior Blown `0.12%`, Interior Crushed `0.45%`, Micro-Texture `2.34`, Peak Sharpness `1284.0` (`tile_5_mid_right`)
- **High-Confidence Automated Checks:** 14 / 14 Passed
- **Low-Confidence Items Flagged for Human Eye:** 1 item (`Tile #8`: verify carafe base contact shadow contrast against basalt slab)
- **Defects Remediated:** Critical: 1 (floating carafe base fixed via `qc_tools.py mask --tiles 8` inpaint) | Major: 0 | Minor: 0

#### 3. Human Review Gate & Provenance
- **Gate Status:** APPROVED FOR PRODUCTION (Verify headline text contrast against left wall luminance `L=118`)
- **Provenance Note:** *Synthetic visual generated via AI synthesis; disclose as illustrative media when deployed in consumer or editorial contexts.*
```
