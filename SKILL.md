---
name: optic
description: Use this skill when generating, prompting, editing, or quality-checking photorealistic or authentically crafted visuals (portraits, lifestyle scenes, commercial products, architecture, culinary, editorial) where physical believability is essential. Do NOT use for technical diagrams, charts, UI mockups, flat vector logos, or wireframes.
---

# Optic (v2.2) — Natural Image Craft & Optical QC

**Goal:** Visuals that appear photographed, designed, or rendered on purpose—internally coherent, obeying physical optics and materials, and free from telltale "AI slop" signatures (waxy skin, neon rim-lights, teal-orange split glazes, floating objects, duplicate accessories, and garbled anatomy).

> **Path Resolution Rule (`<SKILL_DIR>`):** Resolve `<SKILL_DIR>` as the directory containing this `SKILL.md` file (e.g., `~/.gemini/config/skills/optic`, `~/.agents/skills/optic`, or `<workspace>/.agents/skills/optic`). Always invoke scripts and references using `<SKILL_DIR>/scripts/qc_tools.py` and `<SKILL_DIR>/references/...` so commands never fail when your current working directory is a different project folder.

---

## Reference Navigation Map

Consult the modular markdown references in `<SKILL_DIR>/references/` based on your task:

| When You Need To... | Read This Reference |
| :--- | :--- |
| **Adapt prompt syntax for your specific agent/model** (Freebuff, Cursor, Codex, Antigravity, Windsurf, Flux, GPT-Image, Midjourney, Ideogram) | `<SKILL_DIR>/references/tool_profiles.md` |
| **Execute the 7-stage QC protocol or check the Human Review Gate** | `<SKILL_DIR>/references/qc_checklist.md` |
| **Grab ready-to-use recipes for products, portraits, web heroes, food, or architecture** | `<SKILL_DIR>/references/scene_sheet_recipes.md` |
| **Diagnose and fix a specific visual flaw** (plastic skin, floating items, weird hands, lens distortion) | `<SKILL_DIR>/references/symptom_fix_matrix.md` |
| **Inspect an end-to-end trace** (brief → assumptions → prompt → QC → inpaint → report) | `<SKILL_DIR>/references/worked_example.md` |
| **Inspect verified A/B test runs & `qc_tools.py` benchmark telemetry** | `<SKILL_DIR>/references/test_suite_and_eval.md` |
| **Render authentic diverse skin tones (Fitzpatrick I–VI), hair textures, or verify ethics** | `<SKILL_DIR>/references/diversity_and_ethics.md` |

---

## 1. Scope and Exclusions

### ✅ When to Trigger This Skill
- Generating or improving prompts for realistic photography (portraits, lifestyle, commercial goods, food, interiors, street, documentary).
- Website hero banners and editorial visuals requiring natural negative copy space.
- Reviewing, auditing, or performing quality control (QC) on an AI-generated image.
- Inpainting or performing targeted edits on existing realistic photos.
- Crafting stylistically coherent illustration or 3D art (using non-photographic realism rules).

### ❌ Do NOT Use For
- Technical flowcharts, UML diagrams, entity-relationship schemas (use Mermaid or SVG).
- Software UI/UX wireframes, mobile app mockups, website component layouts (use HTML/CSS/Tailwind).
- Vector logos, flat icons, favicon designs (use SVG code).
- Data visualizations, statistical charts, graphs (use Matplotlib, Chart.js, or SVG).
- Memes, casual conversational sketches, or text-heavy infographics.

---

## 2. Capability Check & Fallbacks

Before running the workflow, verify your agent's available execution tools:

```text
[Tool Environment Check]
├── Has Shell/Python? ──── Yes ──► Run `python "<SKILL_DIR>/scripts/qc_tools.py" board <image>`
│                          │       (Generates a 1-file 4-panel Diagnostic Board + optical telemetry).
│                          └── No  ──► Fallback: Inspect full image via coordinate quadrants.
├── Has Edit/Inpaint? ──── Yes ──► Conversational edit (GPT-Image/Gemini) OR generate binary mask
│                          │       via `qc_tools.py mask <image> --tiles X --out mask.png`.
│                          └── No  ──► Fallback: Level 1 crop/adjust (`qc_tools.py crop|adjust`) or re-prompt.
└── Has Vision Input? ──── Yes ──► Inspect `<stem>_qc_board.png` in 1 tool call + apply Human Gate.
                           └── No  ──► Headless Mode: Run `qc_tools.py analyze <image> --json` & log flags.
```

---

## 3. Four Core Principles Above Everything

1. **One Scene, One Light, One Camera:** One physical 3D space, one viewpoint, and one dominant light source. Never blend conflicting lighting styles (e.g. golden hour sun + overcast diffuse + neon rim).
2. **Describe Physical Evidence, Not Adjectives:** State what a camera sensor records (surface roughness, reflection angle, light falloff, contact shadow), never empty quality buzzwords (`photorealistic`, `8k`, `hyperdetailed`, `masterpiece`, `stunning`).
3. **Inspect, Diagnose, Then Apply the Cheapest Effective Fix:** Never re-roll an entire image blindly. Diagnose the root cause and fix with the lowest-cost intervention (`qc_tools.py crop/adjust` → Text Overlay → Targeted Inpaint → Prompt Layer Adjustment).
4. **Calibrated Quality Assurance:** Acknowledge vision model limitations. Never issue blanket assurances (*"QC Passed without defects"*). Always separate high-confidence checks from low-confidence items flagged for human eyes.

---

## 4. Operational Modes: Quick Mode vs. Full Mode

Select the operational mode immediately after reading the brief:

```text
Is this a simple, single-subject, low-risk request?
  ├── YES ──► QUICK MODE (Steps 0, 1, 4, 5, 6, 7-Quick, 11-Compact | Max 3 generations total)
  │           • Step 7-Quick: Run `qc_tools.py board <image>` and inspect ONLY the single
  │             composite `<stem>_qc_board.png` file (1 vision read call total).
  │           • Step 11-Compact: Output the 3-line Compact Delivery Summary.
  └── NO  ──► FULL MODE  (All 12 steps | Commercial / Multi-element / Brand-critical | Hard cap: 6)
              • Step 7-Full: Run `qc_tools.py board <image>` + `tile` for deep 100% tile audit.
              • Step 11-Full: Output the full 4-part Delivery Audit Report.
```

### Headless / Automated Pipeline Mode
If running in an automated background pipeline (CI/CD or headless agent with no human present):
- Skip Step 0 questions entirely; log all assumptions explicitly.
- Default to Quick Mode unless configured otherwise.
- Run `python "<SKILL_DIR>/scripts/qc_tools.py" analyze <image> --json` and include the JSON telemetry in the output.

> **⚠️ The metrics screen; they do not certify.** `PASS_AUTOMATED_METRICS` means no
> scalar threshold tripped — it is not a quality verdict. The scores are heuristics with
> no ground-truth calibration. Anatomy, catchlights, contact shadows, glyph legibility,
> duplicated props, and brief adherence are **not** measurable by these numbers; route
> them to the human review gate. In headless mode, report the flags you got and say
> plainly that visual correctness was not verified. Trust `peak_tile_sharpness` /
> `microtexture_structural` (grain-compensated) over `raw_laplacian_variance` and
> `microtexture_score`, which are both dominated by noise.

---

## 5. Master Workflow (Step-by-Step)

### Step 0: Ask or Assume
- If interactive: Ask **at most 2 targeted questions** ONLY if missing information materially changes the physical scene (aspect ratio, copy space placement, mandatory product color).
- Otherwise, state assumptions in one sentence and proceed immediately.

### Step 1: Read the Brief & Identify Constraints
- Purpose, deployment surface (web, mobile, print), aspect ratio, brand palette, real people/products involved, mandatory copy space.

### Step 2: Choose One Realism Target
- Product / E-commerce, Editorial Portrait, Lifestyle / Documentary, Architecture / Interior, Culinary, or Stylized Art. (See `<SKILL_DIR>/references/scene_sheet_recipes.md`).

### Step 3: Design Around Known Model Weaknesses Before Prompting
- Limit people in primary focal plane (1–2 max).
- Give hands active, weight-bearing physical tasks (gripping a tool handle, resting palms on a surface)—never prompt "hide hands in pockets".
- **Typography Routing by Model Tier:**
  - **Tier 1 Text Models (Gemini Image / Nano Banana Pro, Ideogram 3, GPT-Image):** Short headlines or labels (≤ 5 words) may be generated in-image using exact quotation marks (`reading "EXACT TEXT"`).
  - **Tier 2 Text Models (Flux, SDXL, DALL-E 3):** Exclude text/logos from the generative prompt (`unbranded matte bottle`); generate clean copy space and overlay typography post-generation.
- Avoid multi-plane mirrors, complex crowd backgrounds, and symmetrical background props.

### Step 4: Fill the Scene Sheet (The 9 Layers)
1. **Type & Intent:** Commercial studio product, candid documentary portrait, architectural interior.
2. **Subject & Action:** Core entity, physical orientation, purposeful activity.
3. **Environment & Time:** Specific physical room/landscape, time of day, weather, atmosphere.
4. **Composition & Framing:** Camera height, framing rule (thirds, off-center), negative copy space.
5. **Lighting Architecture:** ONE key light source (direction, softness, color temperature), fill bounce, ambient level.
6. **Camera & Lens:** Focal length (24/35/50/85/100mm), aperture (`f/2.8` to `f/11`), camera elevation. *(Note: camera numbers act as stylistic depth-of-field and perspective cues).*
7. **Materials & Surface Physics:** Exact material properties and specular behavior.
8. **Physical Entropy (Motivated Imperfections):** 2–3 imperfections physically caused by thermal change, mechanical handling, gravity, or climate. **Never reuse the same imperfection set across images.**
9. **Color & Clean Constraints:** Color palette, white balance (`3200K–6000K`), positive physical affirmations.

### Step 5: Write the Layered Prompt
- Check `<SKILL_DIR>/references/tool_profiles.md` for your active generator's rules.
- Write concrete, descriptive prose using physical nouns.
- Eliminate negative tokens on Flux, Gemini Image, and GPT-Image; state the desired physical state positively (`unbranded glass bottle`, `sharp focus throughout`).

### Step 6: Generate Candidate(s)
- Generate 1 candidate (Quick Mode) or 2–4 candidates varying one parameter (Full Mode).
- Initial candidate batch counts as **Generation Run #1**.

### Step 7: Run Calibrated Quality Control (QC)
- **Quick Mode (1 Vision Call):**
  Run `python "<SKILL_DIR>/scripts/qc_tools.py" board <image_path> [--zoom-tiles 2,6]` and inspect the single generated `<stem>_qc_board.png` file, which displays:
  1. The 3×3 coordinate grid (`#0`–`#8`) with per-tile Laplacian sharpness scores.
  2. The Horizontal Mirror Flip with alignment lines.
  3. The Clipping & Gamut Anomaly Map (Red = Blown, Cyan = Crushed, Magenta = Neon).
  4. Two 100% Native Pixel Zoom strips (defaults to Peak Focus + Lower-Mid Contact Zone, or any 2 tiles passed via `--zoom-tiles`) + optical telemetry bar.
- **Full Mode:** Run `board` first; if any tile shows potential micro-defects, run `python "<SKILL_DIR>/scripts/qc_tools.py" tile <image_path>` to inspect individual full-res tiles.
- Evaluate against `<SKILL_DIR>/references/qc_checklist.md`: Log defects as **Critical**, **Major**, or **Minor**.

### Step 8: Diagnose & Apply Cheapest Effective Fix
- Consult `<SKILL_DIR>/references/symptom_fix_matrix.md`.
- **Level 1 (Zero Model Cost — Instant CLI Fix):**
  - Reframe/crop edge defects: `python "<SKILL_DIR>/scripts/qc_tools.py" crop <image> --aspect 16:9 --out fixed.png`
  - Fix color cast, saturation spike, or shadow crush: `python "<SKILL_DIR>/scripts/qc_tools.py" adjust <image> --temp -10 --saturation 0.90 --gamma 0.92 --out fixed.png`
  - Composite clean typography onto copy space: `python "<SKILL_DIR>/scripts/qc_tools.py" text-overlay <image> --text "HEADLINE" --subtext "Subheadline" --position left --color auto --out banner.png`
- **Level 2 (Targeted Local Edit / Inpaint — 1 Model Call):**
  - For conversational editors (Gemini Image / GPT-Image): pass the candidate image back and instruct the specific localized fix (*"Keep 100% of the image identical except add a dark contact shadow directly under the bottle base"*).
  - For mask-based inpaint APIs (Flux Fill / SDXL): generate a binary mask via `python "<SKILL_DIR>/scripts/qc_tools.py" mask <image> --tiles 7,8 --out mask.png`.
- **Level 3 (Prompt Layer Re-alignment):** Fix contradictory prompt tokens and regenerate.

### Step 9: Enforcement of Iteration Caps & Budget Limits
- **Quick Mode:** Max 2 re-rolls (Hard cap: **3 total runs**).
- **Full Mode:** Max 2 targeted fix attempts per defect (Hard cap: **6 total runs**).
- If a Critical defect persists at the cap, stop re-rolling and report diagnostic options to the user.

### Step 10: Optical Polish & Provenance Stamping
- Use `qc_tools.py adjust` for multiplicative white-balance gain, saturation, or gamma calibration if needed. Level-1 tools (`crop`, `adjust`, `text-overlay`) run at zero generator cost (lossless for PNG output; `quality=95` re-encoded for JPEG), preserve EXIF/ICC/`tEXt` metadata, and append a SHA-256 chained step to `<stem>.provenance.json`.
- For production assets, stamp C2PA-style unsigned provenance metadata (PNG `tEXt`/`iTXt` chunks + SHA-256 audit sidecar) onto the final image:
  ```bash
  python "<SKILL_DIR>/scripts/qc_tools.py" provenance <image_path> --model "<Model Name>" --seed "<Seed>" --mode "<Quick|Full>"
  ```
- Restrict film grain and vignettes strictly to vintage/historical briefs; forbid them on clean commercial/product visuals.

### Step 11: Deliver with Calibrated Report & Human Review Gate

#### Option A: Compact Delivery Summary (Default for Quick Mode)
```markdown
**Delivered:** `<filename>` ([Dimensions], [Model]) | **QC Telemetry:** Sharpness `[PeakSharp]`, Interior Clipping `[Blown]%` blown / `[Crushed]%` crushed, Flags: `[0 or list]`
**Scene & Assumptions:** [1-line summary of lens, lighting, and assumptions]
**Human Review Gate:** [APPROVED | Verify `<Tile #>` for `<specific hand/text/contact detail>`]
```

#### Option B: Full Production Audit Report (Required for Full Mode)
```markdown
### Natural Image Craft Delivery Report

**Project:** [Brief Title] | **Output:** [Dimensions WxH, Aspect Ratio]  
**Generator:** [Model Name] | **Mode:** Full Mode | **Runs Used:** [X / 6]  

#### 1. Scene & Optical Setup
- **Camera & Lighting:** [Focal length, aperture, angle; single key light direction & color temp]
- **Materials & Motivated Entropy:** [Surfaces + 2–3 scene-specific physical entropy elements]

#### 2. Calibrated QC & Telemetry Summary (`qc_tools.py`)
- **Quantitative Telemetry:** Luminance `[Lum]`, Contrast `[Contrast]`, Interior Blown `[X]%`, Interior Crushed `[Y]%`, Micro-Texture `[Score]`, Peak Sharpness `[Score]` (`[Tile]`)
- **High-Confidence Automated Checks:** [X / X Passed]
- **Low-Confidence Items Flagged for Human Eye:** [List specific Tile # and detail to verify]
- **Defects Remediated:** [Critical: X | Major: Y | Minor: Z]

#### 3. Human Review Gate & Provenance
- **Gate Status:** [APPROVED FOR PROTOTYPE | PENDING HUMAN EYE SIGN-OFF FOR PRODUCTION]
- **Provenance Note:** *Synthetic visual generated via AI synthesis; disclose as illustrative media when deployed in consumer or editorial contexts.*
```
