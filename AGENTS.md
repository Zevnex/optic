# Project Agent Instructions (`AGENTS.md`)

## Optic Skill (`optic` — Natural Image Craft v2.2)

When the user asks to generate, prompt, edit, retouch, or quality-check photorealistic or authentically crafted visuals (portraits, commercial products, lifestyle, culinary, architecture, website hero banners), or invokes `/skill:optic` / `/optic`:

1. **Load Skill Instructions:** Read `.agents/skills/optic/SKILL.md` (or fallback to `SKILL.md` in the repository root).
2. **Do Not Trigger On:** Technical diagrams (Mermaid/UML), data charts (Matplotlib/Seaborn), UI/UX wireframes, or flat vector SVG logos.
3. **Run Optical QC (`qc_tools.py`):**
   - Quick Mode (1-call composite board): `python ".agents/skills/optic/scripts/qc_tools.py" board <image_path>`
   - Headless JSON telemetry: `python ".agents/skills/optic/scripts/qc_tools.py" analyze <image_path> --json`
   - Level-1 Post-Processing: `crop`, `adjust`, `text-overlay`, `mask`, `provenance`.

---

## Contributing Conventions

These are the invariants the test suite enforces. Keep them true when editing.

- **Thresholds are single-source constants.** `NEON_S_THRESHOLD`, `TEAL_ORANGE_LIMIT`,
  `WAXY_FLOOR_*`, `SOFT_FOCUS_FLOOR` live at the top of `scripts/qc_tools.py` and are
  interpolated into flag text, the board legend and the console report. Never retype a
  threshold into prose — Suite 3 fails on drift.
- **`microtexture_score` may be `None`.** `None` (with `microtexture_status ==
  "insufficient_data"`) means "not enough midtone area to judge". It is never a pass.
- **CLI errors are one line on stderr, exit 1.** `main()` catches
  `FileNotFoundError`/`ValueError`/`OSError`; every expected failure must print
  `qc_tools.py: error: ...` and never a traceback (check 1.32).
- **Status chatter goes through `_log()`.** `--quiet` silences it while `--json` keeps
  printing to stdout (check 1.33).
- **Never emit degenerate output on invalid input.** `tile` rejects images under 3x3
  rather than writing nine 1x1 crops (checks 1.22 / 1.22b).
- **Sharpness is noise-compensated.** `peak_tile_sharpness` / `global_laplacian_sharpness`
  are Laplacian variance *minus* the Immerkaer grain floor (`20*sigma^2`). Tile scores
  all use the **global** sigma — per-tile estimation is unstable on small patches and
  lets grain sneak past the focus threshold. `raw_laplacian_variance` is diagnostic
  only; never threshold on it (checks 1.36–1.38).
- **`focus_separation_ratio` divides by a floored median.** Noise compensation makes flat
  tiles score exactly 0, so dividing by the minimum produced absurd ratios (10521x) and
  silently selected the laxer macro waxy floor. It now compares the peak tile against
  the median of the other eight, floored at 1.0 (check 1.41). Never reintroduce a
  min-tile denominator.
- **Micro-texture reports both numbers.** `microtexture_score` is the raw residual;
  `microtexture_structural` subtracts `MICROTEXTURE_GRAIN_GAIN * sigma`. Never present
  the raw score as "detail" (check 1.39).
- **The metrics screen; they do not certify.** There is no ground-truth calibration. The
  README caveat table and the SKILL.md headless warning are enforced by checks 3.7–3.9 —
  do not delete them to tidy up wording. `PASS_AUTOMATED_METRICS` means "no scalar
  threshold tripped", not "the image is good".
- **The trigger is the description, not the regex.** `should_trigger_optic()` in the test
  suite is a keyword pre-filter only. Suite 4's corpus was iterated once after a first
  run, so it is a regression test now; any pruning must be re-validated on new briefs.
- **Series consistency is a cross-frame check.** No single-image call can see a cast that
  hits every frame. Suite 5 compares frames; keep its fixtures photographic (flat
  synthetic blocks are legitimately flagged waxy and measure the fixture, not the code).
- **Provenance chains must be linked.** A side-car is only inherited when its
  `latest_sha256` equals the source file's SHA-256; a shared stem is not proof
  (checks 1.30 / 1.31). Provenance is C2PA-*style* and **unsigned** — never describe it
  as signed or tamper-proof.
- **Only PNG→PNG is lossless.** `.jpg` output re-encodes at quality 95.

## Before committing

```bash
python tests/run_test_suite.py
```

Must end with `0 failed`. The suite uses the bundled `tests/*.jpg` benchmark images for
Suite 2 and synthesizes its edge-case fixtures in a temp dir, so it needs no extra files.

## Adding a subcommand

1. Write the function; route status messages through `_log()`.
2. Register the subparser and `set_defaults(handler=...)` in `build_parser()`.
3. Add at least one check to `tests/run_test_suite.py` (Suite 1) — assert *correct*
   behaviour, not merely the current behaviour.
4. Document it in the README CLI block and SKILL.md Step 8 if it is a fix path.
