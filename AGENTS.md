# Project Agent Instructions (`AGENTS.md`)

## Optic Skill (`optic` — Natural Image Craft v2.2)

When the user asks to generate, prompt, edit, retouch, or quality-check photorealistic or authentically crafted visuals (portraits, commercial products, lifestyle, culinary, architecture, website hero banners), or invokes `/skill:optic` / `/optic`:

1. **Load Skill Instructions:** Read `.agents/skills/optic/SKILL.md` (or fallback to `SKILL.md` in the repository root).
2. **Do Not Trigger On:** Technical diagrams (Mermaid/UML), data charts (Matplotlib/Seaborn), UI/UX wireframes, or flat vector SVG logos.
3. **Run Optical QC (`qc_tools.py`):**
   - Quick Mode (1-call composite board): `python ".agents/skills/optic/scripts/qc_tools.py" board <image_path>`
   - Headless JSON telemetry: `python ".agents/skills/optic/scripts/qc_tools.py" analyze <image_path> --json`
   - Level-1 Post-Processing: `crop`, `adjust`, `text-overlay`, `mask`, `provenance`.
