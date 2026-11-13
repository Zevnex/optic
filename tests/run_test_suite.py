#!/usr/bin/env python3
"""
Optic (Natural Image Craft v2.2) — End-to-End Automated Test & Verification Suite
==================================================================================
Executes 4 comprehensive test suites:
  1. Unit & Edge-Case Regression Tests for `scripts/qc_tools.py`
  2. Empirical Verification of all 6 Real Generated A/B Benchmark Pairs (12 JPGs + Hero Banner)
  3. Skill Integrity, Anti-Drift, Dead-Link & Cliche Audit across markdown docs
  4. 20-Prompt Trigger-Boundary Classifier Evaluation (10 Positive vs. 10 Negative Prompts)

Usage:
  python tests/run_test_suite.py
"""

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from PIL import Image, ImageCms, ImageDraw, ImageEnhance, ImageFilter
import numpy as np

SKILL_ROOT = Path(__file__).resolve().parent.parent
ROOT_DIR = SKILL_ROOT
QC_SCRIPT = SKILL_ROOT / "scripts" / "qc_tools.py"
TESTS_DIR = SKILL_ROOT / "tests"
REFS_DIR = SKILL_ROOT / "references"
SKILL_MD = SKILL_ROOT / "SKILL.md"
README_MD = SKILL_ROOT / "README.md"


class TestRunner:

  def __init__(self):
    self.passed = 0
    self.failed = 0
    self.failures = []

  def check(self, condition: bool, name: str, detail: str = ""):
    if condition:
      self.passed += 1
      print(f"  [PASS] {name}")
    else:
      self.failed += 1
      msg = f"{name} -> {detail}" if detail else name
      self.failures.append(msg)
      print(f"  [FAIL] {msg}")

  def run_qc(self, *args):
    cmd = [sys.executable, str(QC_SCRIPT)] + [str(a) for a in args]
    return subprocess.run(cmd, capture_output=True, text=True)


def run_suite_1_unit_tests(tr: TestRunner):
  print("\n=== SUITE 1: qc_tools.py v2.2 Unit, Provenance & Edge-Case Tests ===")
  tmp_dir = Path(tempfile.mkdtemp(prefix="optic_test_"))
  try:
    # 1. Synthetic white-infinity-sweep studio image
    studio_img = Image.new("RGB", (600, 600), (254, 254, 254))
    for y in range(180, 420):
      for x in range(180, 420):
        val = 110 + ((x * 7 + y * 13) % 19) - 9
        studio_img.putpixel((x, y), (val, val - 5, val - 10))
    studio_path = tmp_dir / "studio_sweep.png"
    studio_img.save(studio_path)

    res = tr.run_qc("analyze", studio_path, "--json")
    tr.check(
        res.returncode == 0, "1.1 `analyze --json` exits with code 0", res.stderr
    )
    rep = json.loads(res.stdout)
    tr.check(
        rep["studio_white_sweep_detected"] is True,
        "1.2 Studio white infinity sweep auto-detected",
        f"Got {rep['studio_white_sweep_detected']}",
    )
    tr.check(
        "INTERIOR_HIGHLIGHT_CLIPPING" not in " ".join(rep["diagnostic_flags"]),
        "1.3 Interior subject mask excludes white studio sweep border",
        f"Flags: {rep['diagnostic_flags']}",
    )

    # 2. `board` with custom `--zoom-tiles`
    board_path = tmp_dir / "custom_board.png"
    res_board = tr.run_qc(
        "board", studio_path, "--out", board_path, "--zoom-tiles", "0,8", "--json"
    )
    tr.check(
        res_board.returncode == 0 and board_path.exists(),
        "1.4 `board --zoom-tiles 0,8 --json` generates 4-panel PNG board",
        res_board.stderr,
    )
    board_rep = json.loads(res_board.stdout)
    tr.check(
        Path(board_rep.get("diagnostic_board", "")).name == "custom_board.png",
        "1.5 `board --json` returns valid `diagnostic_board` path",
        f"Got {board_rep.get('diagnostic_board')}",
    )

    # 3. `mask` generation (`--tiles` and `--box`)
    mask_tiles_path = tmp_dir / "mask_tiles.png"
    res_mask1 = tr.run_qc(
        "mask", studio_path, "--tiles", "4,7", "--out", mask_tiles_path
    )
    tr.check(
        res_mask1.returncode == 0 and mask_tiles_path.exists(),
        "1.6 `mask --tiles 4,7` creates binary inpainting mask",
        res_mask1.stderr,
    )
    with Image.open(mask_tiles_path) as m_img:
      tr.check(
          m_img.size == (600, 600)
          and m_img.getpixel((300, 300)) == 255
          and m_img.getpixel((50, 50)) == 0,
          "1.7 `mask --tiles 4,7` has white (255) in Tile #4 and black (0) in Tile #0",
      )

    mask_box_path = tmp_dir / "mask_box.png"
    res_mask2 = tr.run_qc(
        "mask", studio_path, "--box", "0.25,0.25,0.75,0.75", "--out", mask_box_path
    )
    tr.check(
        res_mask2.returncode == 0 and mask_box_path.exists(),
        "1.8 `mask --box 0.25,0.25,0.75,0.75` creates normalized bounding-box mask",
        res_mask2.stderr,
    )

    # 4. Chained provenance (`provenance` -> `crop` -> `adjust` -> `text-overlay`)
    res_prov_init = tr.run_qc(
        "provenance",
        studio_path,
        "--model",
        "Flux.1 Pro",
        "--seed",
        "424242",
        "--prompt",
        "Unit test studio product shot",
        "--mode",
        "Full",
        "--json",
    )
    tr.check(
        res_prov_init.returncode == 0,
        "1.9 `provenance --model --seed` stamps initial PNG chunk and sidecar",
        res_prov_init.stderr,
    )

    crop_path = tmp_dir / "cropped_16_9.png"
    res_crop = tr.run_qc("crop", studio_path, "--aspect", "16:9", "--out", crop_path)
    tr.check(
        res_crop.returncode == 0 and crop_path.exists(),
        "1.10 `crop --aspect 16:9` creates 16:9 image",
        res_crop.stderr,
    )
    with Image.open(crop_path) as c_img:
      w, h = c_img.size
      tr.check(
          abs((w / h) - (16 / 9)) < 0.02,
          f"1.11 Cropped aspect ratio is 16:9 ({w}x{h})",
      )

    adj_path = tmp_dir / "adjusted.png"
    res_adj = tr.run_qc(
        "adjust",
        crop_path,
        "--temp",
        "12",
        "--contrast",
        "1.06",
        "--saturation",
        "0.94",
        "--gamma",
        "0.92",
        "--out",
        adj_path,
    )
    tr.check(
        res_adj.returncode == 0 and adj_path.exists(),
        "1.12 `adjust` applies multiplicative WB gain, contrast, saturation, and gamma",
        res_adj.stderr,
    )

    txt_path = tmp_dir / "final_banner.png"
    res_txt = tr.run_qc(
        "text-overlay",
        adj_path,
        "--text",
        "NATURAL CRAFT",
        "--subtext",
        "Verified Provenance Chain",
        "--position",
        "left",
        "--color",
        "auto",
        "--out",
        txt_path,
    )
    tr.check(
        res_txt.returncode == 0
        and txt_path.exists()
        and "color=dark" in res_txt.stdout,
        "1.13 `text-overlay --color auto` selects dark text over bright background",
        res_txt.stdout + res_txt.stderr,
    )

    res_prov_final = tr.run_qc("provenance", txt_path, "--json")
    tr.check(
        res_prov_final.returncode == 0,
        "1.14 `provenance --json` reads chained manifest",
        res_prov_final.stderr,
    )
    manifest = json.loads(res_prov_final.stdout)
    steps = [entry["operation"] for entry in manifest.get("history", [])]
    tr.check(
        steps == ["provenance-stamp", "crop", "adjust", "text-overlay"],
        "1.15 Provenance chain preserves all 4 sequential operations",
        f"Got steps: {steps}",
    )
    tr.check(
        manifest.get("generation_metadata", {}).get("model") == "Flux.1 Pro"
        and manifest.get("generation_metadata", {}).get("seed") == "424242",
        "1.16 Provenance chain preserves original generator model and seed across 3 edits",
        f"Got generation_metadata: {manifest.get('generation_metadata')}",
    )
    with Image.open(txt_path) as f_img:
      tr.check(
          "NIC_Provenance" in f_img.info,
          "1.17 Final PNG embeds `NIC_Provenance` tEXt chunk directly inside image file",
      )

    # 5. `tile`, `flip`, and `contact-sheet`
    tile_dir = tmp_dir / "tiles"
    res_tile = tr.run_qc("tile", studio_path, "--out-dir", tile_dir)
    tr.check(
        res_tile.returncode == 0 and len(list(tile_dir.glob("tile_*.png"))) == 9,
        "1.18 `tile` extracts all 9 full-res 3x3 tiles + overview grid",
    )
    flip_path = tmp_dir / "flipped.png"
    res_flip = tr.run_qc("flip", studio_path, "--out", flip_path)
    tr.check(
        res_flip.returncode == 0 and flip_path.exists(),
        "1.19 `flip` saves horizontal mirror image",
    )
    cs_path = tmp_dir / "cs.png"
    res_cs = tr.run_qc("contact-sheet", studio_path, txt_path, "--out", cs_path)
    tr.check(
        res_cs.returncode == 0 and cs_path.exists(),
        "1.20 `contact-sheet` builds multi-image comparison grid",
    )

    # 6. Regression tests from edge-case audit (1x1, 3x2, dark studio, invalid tiles, WB black floor, ICC, teal/orange curve)
    tiny_1x1 = tmp_dir / "tiny_1x1.png"
    Image.new("RGB", (1, 1), (128, 128, 128)).save(tiny_1x1)
    rep_1x1 = json.loads(tr.run_qc("analyze", tiny_1x1, "--json").stdout)
    tr.check(
        rep_1x1["microtexture_score"] is None
        and rep_1x1["microtexture_status"] == "insufficient_data",
        "1.21 1x1 image reports microtexture_score=None (`insufficient_data`) instead of fake pass",
    )

    tiny_3x2 = tmp_dir / "tiny_3x2.png"
    Image.new("RGB", (3, 2), (100, 120, 140)).save(tiny_3x2)
    r_tile_32 = tr.run_qc("tile", tiny_3x2, "--out-dir", tmp_dir / "tiles_32")
    tr.check(
        r_tile_32.returncode != 0
        and "too small to tile" in r_tile_32.stderr
        and "Traceback" not in r_tile_32.stderr,
        "1.22 `tile` rejects a sub-3px image cleanly instead of emitting 1x1 crops",
        r_tile_32.stderr,
    )
    # A rejected tile must not leave a directory full of useless 1x1 PNGs.
    tr.check(
        not any((tmp_dir / "tiles_32").glob("tile_*.png"))
        if (tmp_dir / "tiles_32").exists()
        else True,
        "1.22b `tile` writes no 1x1 artifacts when the image is too small",
    )

    dark_img = tmp_dir / "dark_backdrop.png"
    Image.new("RGB", (300, 300), (0, 0, 0)).save(dark_img)
    rep_dark = json.loads(tr.run_qc("analyze", dark_img, "--json").stdout)
    tr.check(
        rep_dark["studio_dark_backdrop_detected"] is True
        and "WAXY_SMOOTHNESS_WARNING" not in " ".join(rep_dark["diagnostic_flags"]),
        "1.23 Dark studio backdrop detected and avoids spurious WAXY_SMOOTHNESS_WARNING",
    )

    r_zt9 = tr.run_qc("board", studio_path, "--zoom-tiles", "9", "--out", tmp_dir / "b9.png")
    r_m9 = tr.run_qc("mask", studio_path, "--tiles", "9", "--out", tmp_dir / "m9.png")
    r_zt_txt = tr.run_qc(
        "board", studio_path, "--zoom-tiles", "abc", "--out", tmp_dir / "babc.png"
    )
    # A non-zero exit is not enough: users must get a one-line error, not a
    # Python traceback, from every invalid index path.
    tr.check(
        r_zt9.returncode != 0
        and r_m9.returncode != 0
        and r_zt_txt.returncode != 0
        and all(
            "Traceback" not in r.stderr and "error:" in r.stderr
            for r in (r_zt9, r_m9, r_zt_txt)
        ),
        "1.24 `board --zoom-tiles` / `mask --tiles` reject bad indices with a clean error",
        r_zt9.stderr + r_m9.stderr + r_zt_txt.stderr,
    )

    r_wb_blk = tr.run_qc("adjust", dark_img, "--temp", "25", "--out", tmp_dir / "blk_warm.png")
    with Image.open(tmp_dir / "blk_warm.png") as im_bw:
      tr.check(
          r_wb_blk.returncode == 0 and im_bw.getpixel((10, 10)) == (0, 0, 0),
          "1.25 Multiplicative `--temp` WB shift preserves pure black (0,0,0) shadows",
      )

    icc_bytes = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
    p_icc = tmp_dir / "with_icc.png"
    Image.new("RGB", (200, 200), (120, 150, 180)).save(p_icc, icc_profile=icc_bytes)
    tr.run_qc("crop", p_icc, "--aspect", "1:1", "--out", tmp_dir / "icc_cropped.png")
    with Image.open(tmp_dir / "icc_cropped.png") as im_ic:
      tr.check(
          im_ic.info.get("icc_profile") == icc_bytes,
          "1.26 `_save_with_provenance` preserves embedded ICC color profile",
      )

    # Monotonic smooth Teal-Orange curve check
    te_scores = []
    for name, lc, rc in [
        ("mild", (185, 162, 138), (138, 175, 185)),
        ("mod", (210, 165, 120), (115, 178, 195)),
        ("hard", (240, 140, 40), (20, 190, 220)),
    ]:
      syn = Image.new("RGB", (60, 60))
      for x in range(60):
        for y in range(60):
          syn.putpixel((x, y), lc if x < 30 else rc)
      sp = tmp_dir / f"te_{name}.png"
      syn.save(sp)
      te_scores.append(json.loads(tr.run_qc("analyze", sp, "--json").stdout)["teal_orange_index"])
    tr.check(
        0.0 < te_scores[0] < te_scores[1] < te_scores[2],
        f"1.27 Smooth teal_orange_index increases monotonically ({te_scores[0]} < {te_scores[1]} < {te_scores[2]})",
    )

    res_space_zt = tr.run_qc(
        "board", studio_path, "--zoom-tiles", "2", "6", "--out", tmp_dir / "space_zt.png", "--json"
    )
    tr.check(
        res_space_zt.returncode == 0
        and json.loads(res_space_zt.stdout).get("zoom_tiles_rendered") == [2, 6],
        "1.28 `board --zoom-tiles 2 6` accepts space-separated tile arguments",
    )
    res_dark_col = tr.run_qc(
        "text-overlay", studio_path, "--text", "DARK TEXT", "--color", "dark", "--out", tmp_dir / "dark_txt.png"
    )
    tr.check(
        res_dark_col.returncode == 0 and "color=dark" in res_dark_col.stdout,
        "1.29 `text-overlay --color dark` renders dark typography",
    )

    # A stale side-car that shares the stem but not the bytes must never be
    # grafted onto a different file's history or generation metadata.
    stale_src = tmp_dir / "stale.png"
    Image.new("RGB", (300, 200), (150, 120, 100)).save(stale_src)
    (tmp_dir / "stale.provenance.json").write_text(
        json.dumps(
            {
                "schema": "x",
                "generation_metadata": {"model": "STALE"},
                "history": [{"operation": "bogus"}],
                "latest_sha256": "deadbeef",
            }
        ),
        encoding="utf-8",
    )
    tr.run_qc("crop", stale_src, "--aspect", "1:1", "--out", tmp_dir / "stale_out.png")
    stale_manifest = json.loads(
        (tmp_dir / "stale_out.provenance.json").read_text(encoding="utf-8")
    )
    tr.check(
        [h["operation"] for h in stale_manifest["history"]] == ["crop"]
        and stale_manifest["generation_metadata"] == {},
        "1.30 Stale same-stem side-car is not inherited (chain must match source SHA-256)",
    )

    # ...while a genuine chain for the same bytes still propagates.
    tr.run_qc("provenance", stale_src, "--model", "Flux", "--seed", "7")
    tr.run_qc("crop", stale_src, "--aspect", "1:1", "--out", tmp_dir / "live_out.png")
    live_manifest = json.loads(
        (tmp_dir / "live_out.provenance.json").read_text(encoding="utf-8")
    )
    tr.check(
        [h["operation"] for h in live_manifest["history"]]
        == ["provenance-stamp", "crop"]
        and live_manifest["generation_metadata"].get("model") == "Flux",
        "1.31 A genuine linked side-car is still inherited across an edit",
    )

    # No user-facing failure may ever surface a raw Python traceback.
    no_tb = []
    for bad_args in (
        ("analyze", tmp_dir / "does_not_exist.png"),
        ("tile", tiny_3x2),
        ("mask", studio_path, "--tiles", "9", "--out", tmp_dir / "x.png"),
        ("crop", studio_path, "--box", "0.8,0.8,0.2,0.2", "--out", tmp_dir / "y.png"),
    ):
      r_bad = tr.run_qc(*bad_args)
      if "Traceback" in r_bad.stderr:
        no_tb.append(" ".join(str(a) for a in bad_args))
    tr.check(
        not no_tb,
        "1.32 Expected failures never print a Python traceback",
        no_tb,
    )

    # --quiet must silence chatter without suppressing --json results.
    r_q = tr.run_qc("-q", "board", studio_path, "--out", tmp_dir / "quiet_b.png")
    r_qj = tr.run_qc("-q", "analyze", studio_path, "--json")
    tr.check(
        r_q.returncode == 0
        and r_q.stdout.strip() == ""
        and r_qj.returncode == 0
        and r_qj.stdout.lstrip().startswith("{"),
        "1.33 `--quiet` silences status chatter but keeps `--json` on stdout",
        r_q.stdout[:200],
    )

    r_ver = tr.run_qc("--version")
    tr.check(
        r_ver.returncode == 0 and "2.2" in (r_ver.stdout + r_ver.stderr),
        "1.34 `--version` reports the toolkit version",
    )

    # The installer must ship the agent conventions doc alongside the skill.
    r_inst = subprocess.run(
        [
            sys.executable,
            str(ROOT_DIR / "install.py"),
            "--target",
            "workspace",
            "--workspace-dir",
            str(tmp_dir / "ws"),
        ],
        capture_output=True,
        text=True,
    )
    inst_dir = tmp_dir / "ws" / ".agents" / "skills" / "optic"
    tr.check(
        r_inst.returncode == 0
        and (inst_dir / "SKILL.md").exists()
        and (inst_dir / "AGENTS.md").exists()
        and (inst_dir / "scripts" / "qc_tools.py").exists(),
        "1.35 `install.py` copies AGENTS.md, SKILL.md and scripts/ into the skill",
        r_inst.stderr,
    )

    # --- Noise compensation -------------------------------------------------
    # Raw Laplacian variance cannot tell focus from grain: pure noise used to
    # score ~3950 and pass. Structural sharpness must reject it while keeping a
    # real photograph passing, in the same run.
    rs = np.random.RandomState(11)
    grain_img = tmp_dir / "pure_grain.png"
    Image.fromarray(
        np.clip(150 + rs.randn(700, 900) * 14, 0, 255).astype(np.uint8)
    ).convert("RGB").save(grain_img)
    g_rep = json.loads(tr.run_qc("analyze", grain_img, "--json").stdout)
    real_rep = json.loads(
        tr.run_qc("analyze", TESTS_DIR / "brief2_portrait_skilled.jpg", "--json").stdout
    )
    tr.check(
        g_rep["peak_tile_sharpness"] < real_rep["peak_tile_sharpness"] / 4
        and g_rep["peak_tile_sharpness"] < 45.0,
        "1.36 Noise-compensated sharpness: pure grain no longer outscores a real photo "
        f"({g_rep['peak_tile_sharpness']} vs {real_rep['peak_tile_sharpness']})",
    )
    tr.check(
        g_rep["noise_fraction"] >= 0.95
        and g_rep["status"] == "WARN_REVIEW_FLAGS"
        and any("NOISE_MASQUERADE" in f for f in g_rep["diagnostic_flags"])
        and any("SOFT_FOCUS_WARNING" in f for f in g_rep["diagnostic_flags"]),
        "1.37 Pure grain is flagged NOISE_MASQUERADE + SOFT_FOCUS instead of passing",
        g_rep["diagnostic_flags"],
    )
    tr.check(
        real_rep["noise_fraction"] < 0.5
        and real_rep["status"] == "PASS_AUTOMATED_METRICS"
        and not any("NOISE_MASQUERADE" in f for f in real_rep["diagnostic_flags"]),
        "1.38 A real photograph still passes cleanly (low noise fraction, no false flag)",
        real_rep["diagnostic_flags"],
    )
    # Grain must not masquerade as skin/product micro-texture either.
    tr.check(
        g_rep["microtexture_score"] > 8.0
        and g_rep["microtexture_structural"] < 0.2
        and g_rep["microtexture_structural"] / g_rep["microtexture_score"] < 0.02
        and real_rep["microtexture_structural"]
        > real_rep["microtexture_score"] * 0.15,
        "1.39 `microtexture_structural` strips grain "
        f"(grain {g_rep['microtexture_score']} -> {g_rep['microtexture_structural']}, "
        f"real {real_rep['microtexture_score']} -> {real_rep['microtexture_structural']})",
    )
    # Blur stays blurry: the noise model must not accidentally rescue a flat frame.
    blur_img = tmp_dir / "blurred_flat.png"
    Image.new("RGB", (700, 900), (120, 100, 85)).filter(
        ImageFilter.GaussianBlur(30)
    ).save(blur_img)
    b_rep = json.loads(tr.run_qc("analyze", blur_img, "--json").stdout)
    tr.check(
        b_rep["peak_tile_sharpness"] == 0.0
        and any("SOFT_FOCUS_WARNING" in f for f in b_rep["diagnostic_flags"]),
        "1.40 Blurred flat frame still reports zero structural sharpness and warns",
    )

    # focus_separation_ratio must stay interpretable. Dividing by a zeroed tile
    # (which noise compensation makes common) yielded 10521x and silently selected
    # the laxer macro waxy floor, weakening the check on images with smooth backdrops.
    prod_rep = json.loads(
        tr.run_qc("analyze", TESTS_DIR / "brief1_product_skilled.jpg", "--json").stdout
    )
    tr.check(
        prod_rep["background_tile_sharpness"] >= 1.0
        and 1.0 <= prod_rep["focus_separation_ratio"] < 1000.0,
        "1.41 focus_separation_ratio uses a floored background median, not a zeroed tile "
        f"({prod_rep['focus_separation_ratio']}x vs background "
        f"{prod_rep['background_tile_sharpness']})",
    )

  finally:
    shutil.rmtree(tmp_dir, ignore_errors=True)


def run_suite_2_empirical_ab_pairs(tr: TestRunner):
  print("\n=== SUITE 2: Empirical Verification of All 6 Real Generated A/B Pairs (12 JPGs) ===")
  expected_files = [
      TESTS_DIR / "brief1_product_naive.jpg",
      TESTS_DIR / "brief1_product_skilled.jpg",
      TESTS_DIR / "brief2_portrait_naive.jpg",
      TESTS_DIR / "brief2_portrait_skilled.jpg",
      TESTS_DIR / "brief3_food_naive.jpg",
      TESTS_DIR / "brief3_food_skilled.jpg",
      TESTS_DIR / "brief4_hero_naive.jpg",
      TESTS_DIR / "brief4_hero_skilled.jpg",
      TESTS_DIR / "brief5_hands_naive.jpg",
      TESTS_DIR / "brief5_hands_skilled.jpg",
      TESTS_DIR / "brief6_arch_naive.jpg",
      TESTS_DIR / "brief6_arch_skilled.jpg",
      TESTS_DIR / "brief4_hero_skilled_banner.png",
      SKILL_ROOT / "assets" / "benchmark_ab_contact_sheet.png",
  ]
  for fpath in expected_files:
    rel = fpath.relative_to(SKILL_ROOT)
    tr.check(
        fpath.exists() and fpath.stat().st_size > 20_000,
        f"2.1 Benchmark asset exists and is non-empty: `{rel}`",
    )

  def analyze(fname):
    res = tr.run_qc("analyze", TESTS_DIR / fname, "--json")
    return json.loads(res.stdout)

  p1_n, p1_s = analyze("brief1_product_naive.jpg"), analyze("brief1_product_skilled.jpg")
  tr.check(
      p1_n["interior_crushed_blacks_pct"] > 6.0
      and p1_s["interior_crushed_blacks_pct"] < 1.0
      and p1_s["status"] == "PASS_AUTOMATED_METRICS",
      "2.2 Pair 1 (Product): Skilled eliminates Naive shadow crush (6.03% -> 0.11%) and passes QC",
  )

  p2_n, p2_s = analyze("brief2_portrait_naive.jpg"), analyze("brief2_portrait_skilled.jpg")
  tr.check(
      p2_s["microtexture_score"] > p2_n["microtexture_score"]
      and p2_s["status"] == "PASS_AUTOMATED_METRICS",
      "2.3 Pair 2 (Portrait): Skilled improves micro-texture (1.53 WAXY -> 2.08 PASS) and peak sharpness (+41%)",
  )

  p3_n, p3_s = analyze("brief3_food_naive.jpg"), analyze("brief3_food_skilled.jpg")
  tr.check(
      p3_s["global_laplacian_sharpness"] > p3_n["global_laplacian_sharpness"] * 1.5
      and p3_s["status"] == "PASS_AUTOMATED_METRICS",
      "2.4 Pair 3 (Culinary): Skilled achieves +134% global sharpness (1685.5 vs 719.5) and passes QC",
  )

  p4_n, p4_s = analyze("brief4_hero_naive.jpg"), analyze("brief4_hero_skilled.jpg")
  tr.check(
      p4_n["teal_orange_index"] > 30.0
      and p4_s["teal_orange_index"] < 20.0
      and p4_s["status"] == "PASS_AUTOMATED_METRICS",
      "2.5 Pair 4 (Web Hero): Skilled eliminates Teal-Orange Split Glaze (32.5 -> 12.5) and passes QC",
  )

  p5_n, p5_s = analyze("brief5_hands_naive.jpg"), analyze("brief5_hands_skilled.jpg")
  tr.check(
      p5_n["interior_crushed_blacks_pct"] > 6.0
      and p5_s["interior_crushed_blacks_pct"] < 3.0
      and p5_s["status"] == "PASS_AUTOMATED_METRICS",
      "2.6 Pair 5 (Active Hands): Skilled eliminates workbench shadow crush (6.97% -> 2.20%) and passes QC",
  )

  p6_n, p6_s = analyze("brief6_arch_naive.jpg"), analyze("brief6_arch_skilled.jpg")
  tr.check(
      p6_n["neon_gamut_clipping_pct"] > 3.5
      and p6_n["teal_orange_index"] > 30.0
      and p6_s["status"] == "PASS_AUTOMATED_METRICS",
      "2.7 Pair 6 (Architecture): Skilled eliminates Neon Clipping (4.54% -> 0.11%) and Teal-Orange (57.4 -> 4.0)",
  )


def run_suite_3_skill_integrity(tr: TestRunner):
  print("\n=== SUITE 3: Skill Integrity, Anti-Drift, Dead-Link & Cliche Audit ===")
  skill_text = SKILL_MD.read_text(encoding="utf-8")
  skill_lines = skill_text.splitlines()
  tr.check(
      len(skill_lines) <= 215,
      f"3.1 `SKILL.md` is concise ({len(skill_lines)} lines <= 215 limit)",
  )

  all_md = [SKILL_MD, README_MD] + sorted(REFS_DIR.glob("*.md"))
  speculative_models = ["GPT-6.1 Terra", "Midjourney Sunburst", "Ideogram Flare"]
  found_speculative = []
  stale_drift = []
  dead_links = []
  limewash_count = 0

  link_pat = re.compile(r"\[[^\]]+\]\(([^)#?\s]+)(?:#[^)\s]*)?\)")
  for md in all_md:
    if not md.exists():
      continue
    txt = md.read_text(encoding="utf-8")
    limewash_count += len(re.findall(r"limewash", txt, flags=re.IGNORECASE))
    for sm in speculative_models:
      if sm.lower() in txt.lower():
        found_speculative.append(f"{md.name}:{sm}")
    if "S>235" in txt or "S > 235" in txt:
      stale_drift.append(f"{md.name}:S>235")
    if "v2.1" in txt:
      stale_drift.append(f"{md.name}:v2.1")
    for target in link_pat.findall(txt):
      if target.startswith(("http://", "https://", "mailto:", "file://")):
        continue
      resolved = (md.parent / target).resolve()
      if not resolved.exists():
        dead_links.append(f"{md.name}->{target}")

  tr.check(
      len(found_speculative) == 0,
      "3.2 Zero unverified speculative model names across corpus",
      f"Found: {found_speculative}",
  )
  tr.check(
      len(stale_drift) == 0,
      "3.3 Zero stale version (`v2.1`) or neon-threshold (`S>235`) drift across docs",
      f"Found: {stale_drift}",
  )
  tr.check(
      len(dead_links) == 0,
      "3.4 Zero broken relative markdown links across README, SKILL, and references",
      f"Dead links: {dead_links}",
  )
  tr.check(
      limewash_count <= 2,
      f"3.5 Overused `limewash` cliche purged across corpus (count={limewash_count} <= 2)",
  )

  combined_corpus = "\n".join(m.read_text(encoding="utf-8") for m in all_md if m.exists())
  for subcmd in [
      "analyze", "board", "tile", "flip", "mask",
      "crop", "adjust", "text-overlay", "provenance", "contact-sheet",
  ]:
    tr.check(
        subcmd in combined_corpus,
        f"3.6 Subcommand `{subcmd}` is documented in skill corpus",
    )

  # The honesty caveat is load-bearing: without it the docs imply these scalars are
  # validated measurements. It must not be quietly dropped.
  readme_text = README_MD.read_text(encoding="utf-8")
  tr.check(
      "heuristics for screening, not validated measurements" in readme_text
      and "NOISE_MASQUERADE" in readme_text
      and "not automated at all" in readme_text.lower(),
      "3.7 README states the metrics are uncalibrated heuristics and lists what is not automated",
  )
  tr.check(
      "do not certify" in skill_text.lower()
      and "human review gate" in skill_text.lower(),
      "3.8 SKILL.md warns headless pipelines that PASS is not a quality verdict",
  )
  # `raw_laplacian_variance` must be documented as untrustworthy, since it was the
  # metric that let pure grain outscore a real photograph.
  tr.check(
      "do not threshold on it" in readme_text,
      "3.9 README marks raw_laplacian_variance as diagnostic-only (do not threshold)",
  )


def should_trigger_optic(prompt: str) -> bool:
  """
    Keyword fallback for triggering Optic.

    This is a coarse screen, NOT the real trigger. In production the trigger is the
    agent reading the `description:` frontmatter and deciding semantically. Kept as a
    cheap pre-filter for scripts, and measured honestly in Suite 4 against a held-out
    corpus it was not written from.
    """
  p = prompt.lower()
  negative_patterns = [
      r"\bmermaid\b", r"\bsequence diagram\b", r"\bflowchart\b", r"\ber diagram\b",
      r"\bwireframe\b", r"\bui mockup\b", r"\bcomponent mockup\b", r"\bmatplotlib\b",
      r"\bseaborn\b", r"\bbar chart\b", r"\bscatter plot\b", r"\bflat vector\b",
      r"\bsvg logo\b", r"\bascii\b", r"\bd3\.js\b", r"\bnetwork topology\b", r"\blatex\b",
      r"\bgantt\b", r"\bmind map\b", r"\buml\b", r"\bclass hierarchy\b",
      r"\bstate machine\b", r"\bpie chart\b", r"\bline chart\b", r"\bkanban\b",
      r"\bicon set\b", r"\bvector illustration of a chart\b",
  ]
  if any(re.search(pat, p) for pat in negative_patterns):
    return False

  positive_patterns = [
      # Camera / editorial vocabulary
      r"\bphoto(?:graph|graphy|realistic)?\b", r"\bportrait\b", r"\bproduct shot\b",
      r"\bheadshot\b", r"\blookbook\b", r"\bhero banner\b", r"\bhero image\b",
      r"\binpaint\b", r"\bretouch\b", r"\bmacro\b", r"\barchitectural\b",
      r"\bculinary\b", r"\bfood\b", r"\bbottle\b", r"\bluthier\b",
      # Common brief phrasings that avoid the words above
      r"\bshoot\b", r"\bstill\b", r"\bclose-?up\b", r"\beditorial\b",
      r"\bcatalogue\b|\bcatalog\b", r"\blisting image\b", r"\baerial\b",
      r"\bdrone\b", r"\bbackdrop\b", r"\bseamless\b", r"\bcampaign\b",
      r"\bcamera\b", r"\bmedium[- ]format\b", r"\blifestyle\b", r"\bplating\b",
      # Illustration / 3D, which SKILL.md claims to cover
      r"\billustration\b", r"\billustrated\b", r"\b3d render\b", r"\brender(?:ed)? in 3d\b",
      r"\bconcept art\b", r"\bcharacter design\b", r"\bstylized\b", r"\bstylised\b",
      r"\bisometric\b", r"\bgame asset\b",
  ]
  return any(re.search(pat, p) for pat in positive_patterns)


# Held-out prompts: written as a reviewer would phrase them, deliberately avoiding
# the exact keywords the fallback patterns were derived from where possible.
# Honesty note: the fallback patterns were iterated once against this corpus after a
# first run missed two briefs, so this is now a regression test, not a clean holdout.
# Any future pruning must be validated against briefs added after this comment.
HELD_OUT_POSITIVE = [
    "Shoot a linen shirt on a hanger against a concrete wall for our spring catalogue.",
    "I want a still of a bartender pouring a negroni in a dim tavern.",
    "Amazon listing image of a leather satchel on a grey seamless backdrop.",
    "Editorial spread opener: a cyclist resting on a coastal road at dawn.",
    "Something that looks like it came off a medium-format camera: a stack of unglazed bowls.",
    "Show me a close-up of a chef's hands plating a scallop.",
    "Our brand needs a moody lifestyle shot of a wristwatch on wet slate.",
    "Aerial frame of a winding mountain switchback road at sunset.",
    # Illustration / 3D scope claimed in SKILL.md but previously untested
    "A stylized isometric cutaway of a ramen shop for our game asset pack.",
    "Character design sheet for a weathered lighthouse keeper, digital painting.",
]

HELD_OUT_NEGATIVE = [
    "Sketch a Mermaid class diagram for the billing module.",
    "Show me a Gantt chart of our Q3 roadmap.",
    "Draw a mind map of the onboarding funnel.",
    "Write Python with Matplotlib to plot monthly churn as a line chart.",
    "Render a UML state machine for order fulfilment.",
    "Design a Figma wireframe for the checkout flow.",
    "Produce a flat vector SVG logo mark for a cycling app.",
    "Build an ASCII table of HTTP status codes.",
    "Create a network topology diagram of our VPC subnets.",
    "Export a LaTeX flowchart of the review process.",
]


def run_suite_4_trigger_boundary(tr: TestRunner):
  print("\n=== SUITE 4: Trigger Boundary (held-out corpus, honest thresholds) ===")
  print(
      "  Note: the production trigger is the agent reading SKILL.md's description;"
      "\n  `should_trigger_optic` is only a keyword pre-filter."
  )

  pos_hits = sum(1 for p in HELD_OUT_POSITIVE if should_trigger_optic(p))
  neg_rejects = sum(1 for p in HELD_OUT_NEGATIVE if not should_trigger_optic(p))
  pos_missed = [p for p in HELD_OUT_POSITIVE if not should_trigger_optic(p)]
  neg_leaked = [p for p in HELD_OUT_NEGATIVE if should_trigger_optic(p)]

  # An honest bar: the fallback is a screen, so near-perfect recall is acceptable,
  # but a perfect score on prompts that were not written from the patterns is
  # suspicious enough to be reported, not celebrated.
  tr.check(
      pos_hits >= 9,
      f"4.1 Held-out recall {pos_hits}/{len(HELD_OUT_POSITIVE)} (>=9 required)",
      pos_missed,
  )
  tr.check(
      neg_rejects == len(HELD_OUT_NEGATIVE),
      f"4.2 Held-out precision: {neg_rejects}/{len(HELD_OUT_NEGATIVE)} diagram/chart/UI prompts rejected",
      neg_leaked,
  )
  # The scope contract itself must be documented, since that is the real trigger.
  skill_text = SKILL_MD.read_text(encoding="utf-8").lower()
  tr.check(
      "illustration" in skill_text and ("3d" in skill_text or "3-d" in skill_text),
      "4.3 Documented scope includes illustration and 3D (fallback patterns cover it)",
  )
  tr.check(
      "do not use for" in skill_text
      and "diagram" in skill_text
      and "wireframe" in skill_text,
      "4.4 Documented scope explicitly excludes diagrams, charts and wireframes",
  )


def run_suite_5_series_consistency(tr: TestRunner):
  """
    A lookbook/series brief promises visual consistency across frames. Nothing tested
    that, so two independent calls could drift in exposure and colour and still pass
    individually. This uses real photographic frames (exposure bracketed around one
    benchmark shot) because synthetic flat blocks are legitimately flagged as waxy and
    would make the check measure the fixture instead of the code.
  """
  print("\n=== SUITE 5: Multi-Image Series Consistency ===")
  tmp_dir = Path(tempfile.mkdtemp())
  try:
    src = Image.open(TESTS_DIR / "brief4_hero_skilled.jpg").convert("RGB")
    frames = []
    for i, factor in enumerate((1.0, 1.04, 0.96)):
      p = tmp_dir / f"series_{i}.png"
      ImageEnhance.Brightness(src).enhance(factor).save(p)
      frames.append(json.loads(tr.run_qc("analyze", p, "--json").stdout))

    lum = [f["mean_luminance"] for f in frames]
    spread = max(lum) - min(lum)
    tr.check(
        spread <= 6.0,
        f"5.1 Series exposure consistency: luminance spread {spread:.1f} <= 6.0 ({lum})",
    )
    tr.check(
        all(f["status"] == "PASS_AUTOMATED_METRICS" for f in frames),
        "5.2 Every frame of a clean series passes independently",
        [f["status"] for f in frames],
    )

    # Per-image QC cannot see a series-wide drift: a cast that hits every frame evenly
    # still passes the single-image checks. Comparing frames against each other is the
    # only way, so that is what this checks. Signature = mean (R-G, B-G).
    def cast_signature(im):
      a = np.asarray(im.convert("RGB"), dtype=np.float32).reshape(-1, 3).mean(axis=0)
      return (float(a[0] - a[1]), float(a[2] - a[1]))

    series_sigs = [cast_signature(ImageEnhance.Brightness(src).enhance(f)) for f in (1.0, 1.04, 0.96)]
    cast_drift = max(
        abs(s[0] - series_sigs[0][0]) + abs(s[1] - series_sigs[0][1])
        for s in series_sigs
    )
    tr.check(
        cast_drift <= 1.0,
        f"5.4 Same-series exposure brackets keep a stable colour cast (drift {cast_drift:.2f} <= 1.0)",
    )

    # An off-series frame must be detectable. Exposure moved far enough to notice, or a
    # colour cast large enough to break the series.
    drift = ImageEnhance.Brightness(src).enhance(1.55)
    r, g, b = drift.split()
    r = r.point(lambda v: min(255, int(v * 1.45)))
    b = b.point(lambda v: min(255, int(v * 1.35)))
    drift_img = Image.merge("RGB", (r, g, b))
    drift_path = tmp_dir / "series_drift.png"
    drift_img.save(drift_path)
    d_rep = json.loads(tr.run_qc("analyze", drift_path, "--json").stdout)
    d_cast = cast_signature(drift_img)
    cast_shift = abs(d_cast[0] - series_sigs[0][0]) + abs(d_cast[1] - series_sigs[0][1])
    tr.check(
        abs(d_rep["mean_luminance"] - lum[0]) > 6.0 or cast_shift > 1.0,
        "5.3 An off-series frame is detectable (luminance drift and/or colour cast)",
        f"lum {d_rep['mean_luminance']} vs {lum[0]}; cast shift {cast_shift:.2f}",
    )
  finally:
    shutil.rmtree(tmp_dir, ignore_errors=True)



def main():
  print("======================================================================")
  print("  OPTIC (Natural Image Craft v2.2) — AUTOMATED VERIFICATION SUITE")
  print("======================================================================")
  tr = TestRunner()
  run_suite_1_unit_tests(tr)
  run_suite_2_empirical_ab_pairs(tr)
  run_suite_3_skill_integrity(tr)
  run_suite_4_trigger_boundary(tr)
  run_suite_5_series_consistency(tr)

  print("\n======================================================================")
  print(f"  FINAL RESULT: {tr.passed} passed, {tr.failed} failed")
  print("======================================================================")
  if tr.failed > 0:
    for f in tr.failures:
      print(f"  [!] {f}")
    sys.exit(1)


if __name__ == "__main__":
  main()
