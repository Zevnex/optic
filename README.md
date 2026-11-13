<div align="center">
  <img src="assets/logo.svg" alt="Optic Logo" width="96" height="96" />
  <h1>Optic (<code>optic</code>) — Natural Image Craft v2.2</h1>
  <p><strong>Photorealistic Image Generation, Optical Telemetry QC, Level-1 Post-Processing &amp; C2PA-Style Unsigned Provenance Toolkit for AI Agents</strong></p>
  <p>
    <a href="#quickstart-installation--how-to-invoke">Quickstart</a> •
    <a href="#why-optic-verified-6-pair--12-image-empirical-benchmark">Empirical Benchmark</a> •
    <a href="#scriptsqc_toolspy-v22--10-subcommand-cli-reference">CLI Toolkit (<code>qc_tools.py</code>)</a> •
    <a href="#architecture--directory-layout">Architecture</a> •
    <a href="#running-the-automated-verification-suite">66-Check Test Suite</a>
  </p>
</div>

---

`optic` (**Natural Image Craft v2.2**) transforms how AI coding and creative agents (**Google Antigravity, Cursor, OpenAI Codex, Freebuff AI, Windsurf, and Claude**) plan, prompt, inspect, and remediate photorealistic and editorial visuals.

Instead of relying on cargo-cult buzzwords (`"8k, hyperrealistic, masterpiece, trending on artstation"`) and trusting vision models to "eyeball" their own outputs, `optic` enforces **real camera physics, biological micro-texture, motivated surface entropy, and deterministic computer-vision quality control** via [`scripts/qc_tools.py`](scripts/qc_tools.py).

---

## Why `optic`? (Verified 6-Pair / 12-Image Empirical Benchmark)

Across 6 standardized A/B benchmark pairs (**12 generated source images** stored in [`tests/`](tests/run_test_suite.py) and documented in [`references/test_suite_and_eval.md`](references/test_suite_and_eval.md)), `optic` v2.2 achieved:

| Metric | Without Skill (6 Naïve Prompts) | With `optic` v2.2 (6 Skilled Prompts) | Verified Improvement |
| :--- | :---: | :---: | :--- |
| **Mean 100-Point Rubric Score** | `51.3 / 100` | **`94.0 / 100`** | **+42.7 pts (+83.2%)** |
| **Critical / Major Visual Defects** | `6 / 6 images` (`"ROTANICAL"` typo, 2 wristwatches, floating mid-air knife, baked-in fake HTML buttons, scalpel on assembled violin, radioactive cyan/orange LUT) | **`0 / 6 images`** | **100% defect elimination** |
| **Automated `qc_tools.py` Flags** | `5 / 6 flagged` | **`0 / 6 flagged` (`PASS_AUTOMATED_METRICS`)** | **100% automated telemetry pass rate** |
| **Mean Teal-Orange Split-Tone Index** | `17.4` (Peak `57.4`) | **`6.2` (Peak `12.5`)** | **-64.4% synthetic split-tone bias** |
| **Mean Neon Gamut Clipping (`S > 230`)** | `2.23%` (Peak `4.54%`) | **`1.06%` (Peak `2.58%`)** | **-52.5% gamut clipping** |
| **Trigger-Boundary Precision/Recall** | — | **`10/10` Positive, `10/10` Negative Rejected** | **100% recall, 0% diagram/UI false positives** |

### Visual A/B Benchmark Overview — Pairs 2–6 (Left: Naïve Prompt · Right: `optic` v2.2)

*(Shows 10 images across Pairs 2–6: Window Portrait, Culinary Macro, Web Hero Banner + Typography, Active Woodworking Hands, and Brutalist Courtyard; Pair 1 product bottle shots are also stored in `tests/` and verified in `tests/run_test_suite.py`.)*

![10-Image A/B Benchmark Contact Sheet (Pairs 2-6)](assets/benchmark_ab_contact_sheet.png)

---

## Quickstart: Installation & How to Invoke

### 1. Install Dependencies & Sync to Your Agent

```bash
# 1. Install Python dependencies (Pillow & NumPy)
pip install -r requirements.txt

# 2. Verify environment
python install.py --check

# 3. Install into a project workspace (.agents/skills/optic + .cursor/rules/optic.mdc)
python install.py --target all-local --workspace-dir /path/to/your/project

# Or install globally across ALL agents at once (Antigravity + Freebuff + Codex + Claude)
python install.py --target all-global
```

You can also target a single agent environment (or pass `--include-tests` to bundle `tests/`, or `--clean-legacy` to remove an older sibling `natural-image-craft` directory):

```bash
python install.py --target freebuff-global     # ~/.agents/skills/optic (enables /skill:optic)
python install.py --target codex-global        # ~/.codex/skills/optic & ~/.agents/skills/optic
python install.py --target antigravity-global  # ~/.gemini/config/skills/optic
python install.py --target claude-global       # ~/.claude/skills/optic (enables /optic)
python install.py --target cursor              # .cursor/skills/optic + .cursor/rules/optic.mdc (@optic)
```

### 2. How to Trigger `optic` Across Agents

| Agent Environment | How to Invoke in Chat | Example |
| :--- | :--- | :--- |
| **Freebuff AI (Codebuff)** | **Slash Command (`/skill:optic`):** Type `/skill:optic` followed by your brief, or let it auto-trigger via `AGENTS.md`. | `/skill:optic Generate a studio product shot of a ceramic coffee dripper and run qc_tools.py board` |
| **Claude Code / CLI Agents** | **Slash Command (`/optic`):** Type `/optic` followed by your brief, or let it auto-trigger by description. | `/optic editorial portrait of a structural engineer in natural window light` |
| **Cursor** | **`@` Rule Mention (`@optic`):** Type `@optic` in Composer/Agent chat, or let Cursor auto-attach `.cursor/rules/optic.mdc`. | `@optic generate a 16:9 SaaS hero banner with left copy space` |
| **OpenAI Codex** | **Slash / Auto-Discovery:** Discovered from `~/.codex/skills/optic/SKILL.md` or `.agents/skills/optic/SKILL.md`. | `"Use optic to audit tests/brief2_portrait_skilled.jpg with qc_tools.py board"` |
| **Google Antigravity** | **Automatic (Zero-Click):** Triggers automatically on any realistic image/photo prompt, or say *"Use `optic`..."*. | `"Use optic in Full Mode to generate a studio product shot of a ceramic coffee dripper and run the QC board"` |
| **Claude.ai (Web / Desktop)** | Upload [`SKILL.md`](SKILL.md) (or a `.zip` of the repo) in **Settings → Capabilities → Skills**. | `"Use the optic skill to craft a 24mm tilt-shift architectural prompt"` |

---

## `scripts/qc_tools.py` (v2.2) — 10-Subcommand CLI Reference

```bash
# 1. Single-image 4-panel Composite Diagnostic Board (3x3 grid + mirror flip + anomaly map + 100% zoom strips)
python scripts/qc_tools.py board <image_path> --zoom-tiles 4,7

# 2. Headless JSON optical telemetry (studio-backdrop aware, smooth Teal-Orange index, micro-texture check)
python scripts/qc_tools.py analyze <image_path> --json

# 3. Extract all 9 full-resolution 3x3 tiles + overview grid (safe down to 1x1 images)
python scripts/qc_tools.py tile <image_path>

# 4. Generate binary black/white inpainting mask PNG from tile numbers or bounding box
python scripts/qc_tools.py mask <image_path> --tiles 7,8 --out mask.png

# 5. Level-1 zero-model-cost crop / aspect-ratio reframe (lossless PNG output; q95 JPEG; preserves metadata)
python scripts/qc_tools.py crop <image_path> --aspect 16:9 --out cropped.png

# 6. Level-1 multiplicative R/B white-balance gain, contrast, saturation & shadow gamma adjustment
python scripts/qc_tools.py adjust <image_path> --temp -8 --gamma 0.90 --saturation 0.92 --out calibrated.png

# 7. Level-1 luminance-adaptive typography compositor (eliminates AI spelling errors in copy space)
python scripts/qc_tools.py text-overlay <image_path> --text "KANSO STONEWARE" --subtext "Hand-thrown vessels" --position left --color auto --out banner.png

# 8. Stamp or inspect C2PA-style unsigned provenance (PNG tEXt/iTXt chunks + SHA-256 edit chain sidecar)
python scripts/qc_tools.py provenance <image_path> --model "Flux.1 Pro" --seed 424242 --mode Full --json

# 9. Horizontal mirror flip for compositional balance auditing
python scripts/qc_tools.py flip <image_path>

# 10. Multi-candidate side-by-side comparison contact sheet with embedded telemetry headers
python scripts/qc_tools.py contact-sheet cand1.jpg cand2.jpg --out comparison.png
```

> **Note on Provenance & Metrics:** `qc_tools.py provenance` embeds unsigned C2PA-style `NIC_Provenance` PNG metadata and a SHA-256-chained `<stem>.provenance.json` audit log (no cryptographically signed C2PA CBOR/X.509 certificate). Similarly, `microtexture_score` measures high-frequency midtone residuals and cannot distinguish intentionally smooth matte objects (ceramics/anodized metal) from denoised skin without scene context (`studio_white_sweep_detected` and `studio_dark_backdrop_detected` suppress backdrop false alarms).

---

## Architecture & Directory Layout

```text
optic/
├── SKILL.md                           # Core 12-step workflow (Steps 0–11; Quick, Full & Headless modes)
├── AGENTS.md                          # Workspace agent instructions for Freebuff AI & OpenAI Codex
├── plugin.json                        # Antigravity plugin manifest
├── install.py                         # Cross-agent installer (Antigravity, Cursor, Codex, Freebuff, Claude)
├── requirements.txt                   # Python dependencies (Pillow, numpy)
├── LICENSE                            # MIT License
├── assets/
│   ├── logo.svg                       # Plugin vector icon
│   └── benchmark_ab_contact_sheet.png # 10-image visual A/B overview grid (Pairs 2–6)
├── scripts/
│   └── qc_tools.py                    # 10-subcommand CV Optical Telemetry, Level-1 Remediation & Provenance CLI
├── references/
│   ├── tool_profiles.md               # Agent & Model syntax profiles (Flux, GPT-Image, Gemini, Midjourney, SD3.5, Ideogram)
│   ├── qc_checklist.md                # Calibrated High-Confidence vs. Low-Confidence QC & Human Review Gate
│   ├── scene_sheet_recipes.md         # 6 production recipes, Physical Entropy Engine, Active Hands Framework
│   ├── symptom_fix_matrix.md          # Cheapest-Effective Fix Hierarchy (Level 1 Post -> Level 2 Inpaint -> Level 3 Re-roll)
│   ├── worked_example.md              # Complete end-to-end trace (Kanso Ware Stoneware Campaign)
│   ├── diversity_and_ethics.md        # Fitzpatrick I–VI skin lighting, hair textures 1A–4C, provenance conventions
│   └── test_suite_and_eval.md         # 100-point rubric + verified telemetry for all 6 A/B pairs (12 images)
└── tests/
    ├── run_test_suite.py              # 66-check automated verification harness (Unit + Empirical + Integrity + Boundary)
    ├── brief1..brief6_*.jpg           # All 12 real generated A/B benchmark source images
    └── brief4_hero_skilled_banner.png # Level-1 text-overlay banner output
```

---

## Running the Automated Verification Suite

```bash
python tests/run_test_suite.py
```

Executes **66 automated checks** across 4 suites:
1. **Suite 1 (`29 checks`):** Unit and edge-case regression tests across all 10 `qc_tools.py` subcommands—covering `1×1` / `3×2` tiny-image safety, `insufficient_data` micro-texture reporting, dark & white studio backdrop separation, consistent `--zoom-tiles` / `--tiles` bounds validation, multiplicative `--temp` shadow preservation, ICC color-profile preservation, monotonic Teal-Orange curves, and 4-step SHA-256 provenance chaining (`provenance-stamp -> crop -> adjust -> text-overlay`).
2. **Suite 2 (`20 checks`):** Empirical verification of all 6 real generated A/B pairs (`12` JPGs + banner + contact sheet) confirming `PASS_AUTOMATED_METRICS` (`0` flags) on every `Skilled` generation.
3. **Suite 3 (`15 checks`):** Skill integrity, anti-drift (`v2.2`, `S>230`), zero broken markdown links, subcommand coverage, and cliché audit across [`SKILL.md`](SKILL.md), [`README.md`](README.md), and [`references/`](references/test_suite_and_eval.md).
4. **Suite 4 (`2 checks / 20 prompts`):** Trigger-boundary classifier evaluation (`10/10` positive recall on photorealistic briefs, `10/10` negative rejection on Mermaid diagrams, React wireframes, Matplotlib charts, and SVG logos).

---

## License

Released under the [MIT License](LICENSE).
