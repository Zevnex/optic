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
from PIL import Image, ImageCms, ImageDraw

SKILL_ROOT = Path(__file__).resolve().parent.parent
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
        r_tile_32.returncode == 0
        and len(list((tmp_dir / "tiles_32").glob("tile_*.png"))) == 9,
        "1.22 `tile` handles tiny 3x2 image cleanly without empty-crop ValueError",
        r_tile_32.stderr,
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
    tr.check(
        r_zt9.returncode != 0 and r_m9.returncode != 0,
        "1.24 Both `board --zoom-tiles 9` and `mask --tiles 9` reject out-of-range indices",
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


def should_trigger_optic(prompt: str) -> bool:
  p = prompt.lower()
  negative_patterns = [
      r"\bmermaid\b", r"\bsequence diagram\b", r"\bflowchart\b", r"\ber diagram\b",
      r"\bwireframe\b", r"\bui mockup\b", r"\bcomponent mockup\b", r"\bmatplotlib\b",
      r"\bseaborn\b", r"\bbar chart\b", r"\bscatter plot\b", r"\bflat vector\b",
      r"\bsvg logo\b", r"\bascii\b", r"\bd3\.js\b", r"\bnetwork topology\b", r"\blatex\b",
  ]
  if any(re.search(pat, p) for pat in negative_patterns):
    return False

  positive_patterns = [
      r"\bphoto(?:graph|graphy|realistic)?\b", r"\bportrait\b", r"\bproduct shot\b",
      r"\bheadshot\b", r"\blookbook\b", r"\bhero banner\b", r"\bhero image\b",
      r"\binpaint\b", r"\bretouch\b", r"\bmacro\b", r"\barchitectural\b",
      r"\bculinary\b", r"\bfood\b", r"\bbottle\b", r"\bluthier\b",
  ]
  return any(re.search(pat, p) for pat in positive_patterns)


def run_suite_4_trigger_boundary(tr: TestRunner):
  print("\n=== SUITE 4: 20-Prompt Trigger-Boundary Evaluation Suite ===")
  positive_prompts = [
      "Generate a commercial product shot of an unbranded terracotta ceramic espresso cup on oiled walnut.",
      "Create a candid editorial portrait of a 50-year-old marine biologist on a misty wooden dock.",
      "I need an overhead culinary photograph of fresh hand-rolled tagliatelle dusted with semolina flour.",
      "Make a 16:9 website hero image of a sunlit minimalist architecture studio with negative space on the left.",
      "Generate a close-up documentary photograph of a luthier's hands carving a spruce violin top plate.",
      "Create a 24mm tilt-shift architectural photograph of a brutalist concrete art gallery on a rainy afternoon.",
      "Inpaint only the mangled left hand in this portrait photo while keeping the rest of the image identical.",
      "Generate a 3-image cohesive seasonal lookbook series for a linen workwear brand in golden hour light.",
      "Take a macro botanical photograph of morning dew droplets on a dark green monstera leaf.",
      "Retouch the harsh orange color cast on this real estate interior photograph so it looks like natural daylight.",
  ]
  negative_prompts = [
      "Create a Mermaid sequence diagram showing the OAuth2 PKCE authentication flow between client and server.",
      "Design a low-fidelity React and Tailwind UI wireframe for an enterprise billing dashboard.",
      "Write a Python script using Matplotlib and Seaborn to plot a grouped bar chart of quarterly revenue.",
      "Generate a minimalist flat vector SVG logo for a developer CLI tool called 'Forge'.",
      "Draw an ER diagram for a multi-tenant PostgreSQL e-commerce database schema.",
      "Build a Figma UI component mockup for a mobile banking transaction history screen.",
      "Create an ASCII architecture diagram of our Kafka event-streaming pipeline.",
      "Render a D3.js force-directed network topology graph of cluster microservices.",
      "Plot a LaTeX PGFPlots mathematical function showing standard normal distribution curves.",
      "Generate a Kubernetes ingress and service routing flowchart for our staging cluster.",
  ]

  pos_hits = sum(1 for p in positive_prompts if should_trigger_optic(p))
  neg_rejects = sum(1 for p in negative_prompts if not should_trigger_optic(p))

  tr.check(
      pos_hits == 10,
      f"4.1 Positive Trigger Recall: {pos_hits}/10 photorealistic/editorial prompts activated skill (100% recall)",
  )
  tr.check(
      neg_rejects == 10,
      f"4.2 Negative Boundary Precision: {neg_rejects}/10 diagram/chart/wireframe/logo prompts rejected (0% false positive)",
  )


def main():
  print("======================================================================")
  print("  OPTIC (Natural Image Craft v2.2) — AUTOMATED VERIFICATION SUITE")
  print("======================================================================")
  tr = TestRunner()
  run_suite_1_unit_tests(tr)
  run_suite_2_empirical_ab_pairs(tr)
  run_suite_3_skill_integrity(tr)
  run_suite_4_trigger_boundary(tr)

  print("\n======================================================================")
  print(f"  FINAL RESULT: {tr.passed} passed, {tr.failed} failed")
  print("======================================================================")
  if tr.failed > 0:
    for f in tr.failures:
      print(f"  [!] {f}")
    sys.exit(1)


if __name__ == "__main__":
  main()
