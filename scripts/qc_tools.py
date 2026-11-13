#!/usr/bin/env python3
"""
qc_tools.py (v2.2) - Deterministic Optical QC, Telemetry, Remediation & Provenance Toolkit
for Optic (Natural Image Craft).

Capabilities:
  1. analyze       - Optical telemetry (2D Laplacian sharpness per tile, studio-backdrop-aware
                     clipping, neon gamut clipping S>230, smooth teal-orange index,
                     midtone micro-texture score) with --json output.
  2. board         - Single-file 4-panel Composite Diagnostic Board (3x3 grid + per-tile
                     sharpness, Mirror Flip, Clipping/Gamut Heatmap, and 100% Native Pixel
                     Zoom strips) with scalable TrueType typography.
  3. tile          - Extracts all 9 full-resolution 3x3 tiles + overview grid.
  4. flip          - Horizontal mirror flip for symmetry/perspective audit.
  5. mask          - Generates binary black/white inpainting mask PNGs from tile IDs
                     (--tiles 7,8) or bounding boxes (--box x1,y1,x2,y2).
  6. crop          - Level-1 deterministic zero-model-cost crop/reframe (lossless for PNG;
                     quality=95 re-encoded for JPEG; preserves metadata & provenance chain).
  7. adjust        - Level-1 multiplicative R/B color-temperature shift, contrast,
                     saturation, and shadow gamma adjustment (preserves metadata/provenance).
  8. text-overlay  - Level-1 typography compositor with automatic background-luminance
                     contrast detection for copy space.
  9. provenance    - C2PA-style unsigned provenance stamping & SHA-256 edit chain audit
                     (PNG tEXt/iTXt chunks + <stem>.provenance.json sidecar).
 10. contact-sheet - Side-by-side candidate comparison board with embedded telemetry.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps, PngImagePlugin

TILE_LABELS = [
    "top_left",
    "top_center",
    "top_right",
    "mid_left",
    "mid_center",
    "mid_right",
    "bot_left",
    "bot_center",
    "bot_right",
]

# Single source-of-truth optical telemetry thresholds
NEON_SAT_THRESHOLD = 230
NEON_CLIP_PCT_LIMIT = 3.5
TEAL_ORANGE_THRESHOLD = 30.0
BLOWN_HIGHLIGHT_LIMIT = 4.0
CRUSHED_SHADOW_LIMIT = 6.0
SOFT_FOCUS_THRESHOLD = 45.0
WAXY_FLOOR_DEFAULT = 1.60
WAXY_FLOOR_MACRO = 1.15


def _tile_box(w: int, h: int, idx: int) -> tuple[int, int, int, int]:
  """Returns guaranteed non-empty (x0, y0, x1, y1) bounds for tile index 0..8."""
  if not (0 <= idx <= 8):
    raise ValueError(f"Tile index must be 0..8, got {idx}")
  r, c = idx // 3, idx % 3
  x0 = min(w - 1, (c * w) // 3)
  y0 = min(h - 1, (r * h) // 3)
  raw_x1 = ((c + 1) * w) // 3 if c < 2 else w
  raw_y1 = ((r + 1) * h) // 3 if r < 2 else h
  x1 = max(x0 + 1, min(w, raw_x1))
  y1 = max(y0 + 1, min(h, raw_y1))
  return (x0, y0, x1, y1)


def _parse_tile_indices(spec: str | list[str]) -> list[int]:
  """Parses comma- or space-separated tile indices (0..8), raising ValueError on bad input."""
  tokens = (
      ",".join(spec) if isinstance(spec, list) else str(spec)
  ).replace(" ", ",")
  indices = []
  for tok in tokens.split(","):
    tok = tok.strip()
    if not tok:
      continue
    idx = int(tok)
    if not (0 <= idx <= 8):
      raise ValueError(f"Tile index must be 0..8, got {idx}")
    indices.append(idx)
  return indices


def _load_scalable_font(size: int, bold: bool = True):
  """Loads a scalable TrueType system font, falling back cleanly across OSes."""
  candidates = (
      [
          "segoeuib.ttf",
          "arialbd.ttf",
          "calibrib.ttf",
          "georgiab.ttf",
          "DejaVuSans-Bold.ttf",
      ]
      if bold
      else [
          "segoeui.ttf",
          "arial.ttf",
          "calibri.ttf",
          "georgia.ttf",
          "DejaVuSans.ttf",
      ]
  )
  for fn in candidates:
    try:
      return ImageFont.truetype(fn, size=size)
    except Exception:
      continue
  try:
    return ImageFont.load_default(size=size)
  except TypeError:
    return ImageFont.load_default()


def _draw_badge(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font,
    fg=(255, 255, 255),
    bg=(0, 0, 0),
    pad_x: int = 6,
    pad_y: int = 3,
):
  """Draws text over an auto-sized background box using exact font metrics."""
  x, y = xy
  bbox = draw.textbbox((x + pad_x, y + pad_y), text, font=font)
  draw.rectangle(
      (bbox[0] - pad_x, bbox[1] - pad_y, bbox[2] + pad_x, bbox[3] + pad_y),
      fill=bg,
  )
  draw.text((x + pad_x, y + pad_y), text, font=font, fill=fg)


def _compute_laplacian_variance(gray_arr: np.ndarray) -> float:
  """Computes discrete 2D Laplacian variance as a measure of high-frequency edge sharpness."""
  if gray_arr.shape[0] < 4 or gray_arr.shape[1] < 4:
    return 0.0
  g = gray_arr.astype(np.float32)
  lap = (
      g[:-2, 1:-1]
      + g[2:, 1:-1]
      + g[1:-1, :-2]
      + g[1:-1, 2:]
      - 4.0 * g[1:-1, 1:-1]
  )
  return float(np.var(lap))


def _compute_microtexture_score(gray_arr: np.ndarray) -> float | None:
  """
    Measures fine micro-texture (pore/grain residual) in smooth midtone patches.
    Returns None when image dimensions (<16px) or smooth-midtone sample size (<200px)
    are insufficient for a reliable measurement.
    Note: Edge-residual energy alone cannot distinguish intentionally smooth matte surfaces
    (ceramics, anodized metal) from over-denoised plastic skin without semantic context.
    """
  g = gray_arr.astype(np.float32)
  if g.shape[0] < 16 or g.shape[1] < 16:
    return None
  smooth = (
      g[:-2, :-2]
      + g[:-2, 1:-1]
      + g[:-2, 2:]
      + g[1:-1, :-2]
      + g[1:-1, 1:-1]
      + g[1:-1, 2:]
      + g[2:, :-2]
      + g[2:, 1:-1]
      + g[2:, 2:]
  ) / 9.0
  center = g[1:-1, 1:-1]
  residual = np.abs(center - smooth)

  grad_y = np.abs(g[2:, 1:-1] - g[:-2, 1:-1])
  grad_x = np.abs(g[1:-1, 2:] - g[1:-1, :-2])
  macro_grad = grad_x + grad_y

  mask = (center > 65) & (center < 205) & (macro_grad < 18.0)
  if int(np.sum(mask)) < 200:
    return None
  return float(np.mean(residual[mask]))


def compute_optical_telemetry(image_path: str) -> dict:
  """Computes full optical, exposure, sharpness, and color telemetry for an image."""
  img_path = Path(image_path).resolve()
  if not img_path.exists():
    raise FileNotFoundError(f"Image not found: {img_path}")

  with Image.open(img_path) as im:
    im_rgb = im.convert("RGB")
    w, h = im_rgb.size
    gray_arr = np.asarray(ImageOps.grayscale(im_rgb), dtype=np.uint8)
    hsv_arr = np.asarray(im_rgb.convert("HSV"), dtype=np.uint8)

  # 1. Border vs Interior separation (outer 8% margin vs interior 84%, safe for tiny images)
  margin_x = max(1, min(max(1, w // 4), int(w * 0.08)))
  margin_y = max(1, min(max(1, h // 4), int(h * 0.08)))
  border_mask = np.ones((h, w), dtype=bool)
  if h > 2 * margin_y and w > 2 * margin_x:
    border_mask[margin_y : h - margin_y, margin_x : w - margin_x] = False
  interior_mask = ~border_mask

  border_gray = gray_arr[border_mask] if np.any(border_mask) else gray_arr.ravel()
  interior_gray = (
      gray_arr[interior_mask] if np.any(interior_mask) else gray_arr.ravel()
  )

  # Detect clean studio white sweep or studio dark backdrop
  studio_white_sweep = float(np.mean(border_gray > 246) * 100.0) > 35.0
  studio_dark_backdrop = float(np.mean(border_gray < 10) * 100.0) > 35.0

  global_blown_pct = float(np.mean(gray_arr > 250) * 100.0)
  global_crushed_pct = float(np.mean(gray_arr < 6) * 100.0)

  if studio_white_sweep:
    s_interior = hsv_arr[:, :, 1][interior_mask]
    non_sweep_interior = interior_gray[(interior_gray <= 246) | (s_interior > 18)]
    interior_blown_pct = (
        float(np.mean(non_sweep_interior > 250) * 100.0)
        if len(non_sweep_interior) > 0
        else 0.0
    )
  else:
    interior_blown_pct = float(np.mean(interior_gray > 250) * 100.0)

  if studio_dark_backdrop:
    non_dark_interior = interior_gray[interior_gray >= 10]
    interior_crushed_pct = (
        float(np.mean(non_dark_interior < 6) * 100.0)
        if len(non_dark_interior) > 0
        else 0.0
    )
  else:
    interior_crushed_pct = float(np.mean(interior_gray < 6) * 100.0)

  # 2. Sharpness (Global + 3x3 Per-Tile Laplacian Variance)
  global_sharpness = _compute_laplacian_variance(gray_arr)
  tile_sharpness = {}
  for idx in range(9):
    x0, y0, x1, y1 = _tile_box(w, h, idx)
    t_var = _compute_laplacian_variance(gray_arr[y0:y1, x0:x1])
    tile_sharpness[f"tile_{idx}_{TILE_LABELS[idx]}"] = round(t_var, 1)

  sharp_vals = list(tile_sharpness.values())
  peak_tile_name = max(tile_sharpness, key=tile_sharpness.get)
  peak_sharpness = max(sharp_vals)
  min_sharpness = max(0.1, min(sharp_vals))
  focus_separation_ratio = round(peak_sharpness / min_sharpness, 2)

  # 3. Color & Saturation Telemetry
  h_chan = hsv_arr[:, :, 0].astype(np.float32) * (360.0 / 255.0)
  s_chan = hsv_arr[:, :, 1].astype(np.float32)
  v_chan = hsv_arr[:, :, 2].astype(np.float32)

  mean_saturation = float(np.mean(s_chan))
  p95_saturation = float(np.percentile(s_chan, 95))

  neon_mask = (
      (s_chan > NEON_SAT_THRESHOLD) & (v_chan > 40) & (gray_arr < 245)
  )
  neon_clipping_pct = float(np.mean(neon_mask) * 100.0)

  # Smooth saturation-weighted Teal-Orange split-tone index (avoids sharp S=70 cliff)
  valid_chrom = (v_chan > 35) & (gray_arr < 245) & (s_chan > 35)
  chrom_weights = np.where(
      valid_chrom, np.clip((s_chan - 35.0) / 165.0, 0.0, 1.0), 0.0
  )
  w_sum = float(np.sum(chrom_weights))
  w_ratio = w_sum / float(gray_arr.size)
  if w_sum > 1e-6 and w_ratio > 0.02:
    is_orange = (h_chan >= 12.0) & (h_chan <= 44.0)
    is_teal = (h_chan >= 165.0) & (h_chan <= 210.0)
    orange_frac = float(np.sum(chrom_weights[is_orange])) / w_sum
    teal_frac = float(np.sum(chrom_weights[is_teal])) / w_sum
    bimodal_purity = math.sqrt(orange_frac * teal_frac) * 2.0
    coverage_factor = min(1.0, w_ratio / 0.70)
    teal_orange_index = round(bimodal_purity * coverage_factor * 100.0, 1)
  else:
    teal_orange_index = 0.0

  # 4. In-Focus Subject Micro-Texture
  in_focus_scores = []
  for idx in range(9):
    t_key = f"tile_{idx}_{TILE_LABELS[idx]}"
    if tile_sharpness[t_key] >= max(35.0, 0.25 * peak_sharpness):
      x0, y0, x1, y1 = _tile_box(w, h, idx)
      sc = _compute_microtexture_score(gray_arr[y0:y1, x0:x1])
      if sc is not None:
        in_focus_scores.append(sc)
  if in_focus_scores:
    raw_micro = float(np.mean(in_focus_scores))
  else:
    raw_micro = _compute_microtexture_score(gray_arr)

  microtexture_score = round(raw_micro, 2) if raw_micro is not None else None
  microtexture_status = (
      "measured" if microtexture_score is not None else "insufficient_data"
  )

  # 5. Calibrated Diagnostic Flags
  flags = []
  if interior_blown_pct > BLOWN_HIGHLIGHT_LIMIT:
    flags.append(
        f"INTERIOR_HIGHLIGHT_CLIPPING: {interior_blown_pct:.2f}% of subject pixels are blown (>250)."
    )
  if interior_crushed_pct > CRUSHED_SHADOW_LIMIT:
    flags.append(
        f"INTERIOR_SHADOW_CRUSH: {interior_crushed_pct:.2f}% of subject pixels are crushed black (<6)."
    )
  if neon_clipping_pct > NEON_CLIP_PCT_LIMIT:
    flags.append(
        f"NEON_GAMUT_CLIPPING: {neon_clipping_pct:.2f}% of pixels have extreme neon saturation (S>{NEON_SAT_THRESHOLD})."
    )
  if teal_orange_index > TEAL_ORANGE_THRESHOLD:
    flags.append(
        f"TEAL_ORANGE_SPLIT_GLAZE: High bimodal cyan/amber concentration (index={teal_orange_index} > {TEAL_ORANGE_THRESHOLD})."
    )
  if peak_sharpness < SOFT_FOCUS_THRESHOLD:
    flags.append(
        f"SOFT_FOCUS_WARNING: Peak tile Laplacian variance is very low ({peak_sharpness:.1f}); image may be blurry."
    )
  waxy_floor = (
      WAXY_FLOOR_MACRO if focus_separation_ratio > 25.0 else WAXY_FLOOR_DEFAULT
  )
  if (
      microtexture_score is not None
      and microtexture_score < waxy_floor
      and not studio_white_sweep
      and not studio_dark_backdrop
  ):
    flags.append(
        f"WAXY_SMOOTHNESS_WARNING: Midtone micro-texture score ({microtexture_score} < {waxy_floor}) indicates heavy denoising or uniformly smooth surfaces."
    )

  return {
      "file": str(img_path),
      "dimensions": f"{w}x{h}",
      "width": w,
      "height": h,
      "aspect_ratio": f"{w / h:.2f}:1",
      "mean_luminance": round(float(np.mean(gray_arr)), 1),
      "rms_contrast": round(float(np.std(gray_arr)), 1),
      "studio_white_sweep_detected": studio_white_sweep,
      "studio_dark_backdrop_detected": studio_dark_backdrop,
      "global_blown_highlights_pct": round(global_blown_pct, 2),
      "interior_blown_highlights_pct": round(interior_blown_pct, 2),
      "global_crushed_blacks_pct": round(global_crushed_pct, 2),
      "interior_crushed_blacks_pct": round(interior_crushed_pct, 2),
      "mean_saturation": round(mean_saturation, 1),
      "p95_saturation": round(p95_saturation, 1),
      "neon_saturation_threshold": NEON_SAT_THRESHOLD,
      "neon_gamut_clipping_pct": round(neon_clipping_pct, 2),
      "teal_orange_index": teal_orange_index,
      "teal_orange_threshold": TEAL_ORANGE_THRESHOLD,
      "microtexture_score": microtexture_score,
      "microtexture_status": microtexture_status,
      "waxy_floor": waxy_floor,
      "global_laplacian_sharpness": round(global_sharpness, 1),
      "peak_focus_tile": peak_tile_name,
      "peak_tile_sharpness": round(peak_sharpness, 1),
      "focus_separation_ratio": focus_separation_ratio,
      "tile_sharpness": tile_sharpness,
      "diagnostic_flags": flags,
      "status": (
          "PASS_AUTOMATED_METRICS"
          if len(flags) == 0
          else "WARN_REVIEW_FLAGS"
      ),
  }


def print_telemetry(report: dict, as_json: bool = False):
  if as_json:
    print(json.dumps(report, indent=2))
    return
  print("=== Optical & Physical Telemetry (Optic / Natural Image Craft v2.2) ===")
  print(f"  File                          : {Path(report['file']).name}")
  print(f"  Dimensions / Aspect           : {report['dimensions']} ({report['aspect_ratio']})")
  print(f"  Mean Luminance / Contrast     : {report['mean_luminance']} / {report['rms_contrast']}")
  print(f"  Studio Backdrop Detected      : WhiteSweep={report['studio_white_sweep_detected']}, Dark={report['studio_dark_backdrop_detected']}")
  print(f"  Interior Blown Highlights     : {report['interior_blown_highlights_pct']}% (Global: {report['global_blown_highlights_pct']}%)")
  print(f"  Interior Crushed Shadows      : {report['interior_crushed_blacks_pct']}% (Global: {report['global_crushed_blacks_pct']}%)")
  print(f"  Mean / P95 Saturation         : {report['mean_saturation']} / {report['p95_saturation']} (0-255 scale)")
  print(f"  Neon Gamut Clipping (S>{NEON_SAT_THRESHOLD})   : {report['neon_gamut_clipping_pct']}%")
  print(f"  Teal-Orange Split-Tone Index  : {report['teal_orange_index']} (Threshold: {TEAL_ORANGE_THRESHOLD})")
  if report["microtexture_score"] is not None:
    print(f"  Midtone Micro-Texture Score   : {report['microtexture_score']} (Waxy floor: {report['waxy_floor']})")
  else:
    print(f"  Midtone Micro-Texture Score   : N/A (insufficient_data; Waxy floor: {report['waxy_floor']})")
  print(f"  Sharpness (Global / Peak)     : {report['global_laplacian_sharpness']} / {report['peak_tile_sharpness']} ({report['peak_focus_tile']})")
  print(f"  Focus Separation Ratio        : {report['focus_separation_ratio']}x")
  if report["diagnostic_flags"]:
    print("\n  Diagnostic Flags:")
    for f in report["diagnostic_flags"]:
      print(f"    [!] {f}")
  else:
    print("\n  [OK] All quantitative optical metrics within natural thresholds.")


def build_diagnostic_board(
    image_path: str,
    out_path: str = None,
    as_json: bool = False,
    zoom_tiles: str = None,
) -> dict:
  """
    Creates a single 4-panel Composite Diagnostic Board (<stem>_qc_board.png):
      - Top-Left: Original with 3x3 coordinate grid & per-tile sharpness scores
      - Top-Right: Horizontal Mirror Flip (symmetry & perspective check)
      - Bottom-Left: Optical Anomaly Map (Red=Blown, Cyan=Crushed, Magenta=Neon)
      - Bottom-Right: Two 100% Native Resolution Zoom Crops
    """
  img_path = Path(image_path).resolve()
  custom_tiles = _parse_tile_indices(zoom_tiles) if zoom_tiles else []
  report = compute_optical_telemetry(str(img_path))

  if out_path is None:
    out_path = img_path.parent / f"{img_path.stem}_qc_board.png"
  else:
    out_path = Path(out_path).resolve()
  out_path.parent.mkdir(parents=True, exist_ok=True)

  f_header = _load_scalable_font(18, bold=True)
  f_badge = _load_scalable_font(13, bold=True)
  f_foot = _load_scalable_font(14, bold=False)

  with Image.open(img_path) as im:
    im_rgb = im.convert("RGB")
    w, h = im_rgb.size

    panel_w = 720
    panel_h = max(420, min(680, int(720 * (h / w))))

    # --- PANEL 1: 3x3 Grid + Per-Tile Sharpness ---
    p1 = ImageOps.contain(im_rgb, (panel_w, panel_h), Image.Resampling.LANCZOS)
    p1_w, p1_h = p1.size
    draw1 = ImageDraw.Draw(p1)
    for idx in range(9):
      x0, y0, x1, y1 = _tile_box(p1_w, p1_h, idx)
      draw1.rectangle(
          (x0, y0, max(x0, x1 - 1), max(y0, y1 - 1)),
          outline=(255, 70, 70),
          width=2,
      )
      t_key = f"tile_{idx}_{TILE_LABELS[idx]}"
      s_val = report["tile_sharpness"][t_key]
      badge = f"#{idx} {TILE_LABELS[idx]} (S:{s_val})"
      _draw_badge(
          draw1,
          (x0 + 4, y0 + 4),
          badge,
          f_badge,
          fg=(255, 230, 100),
          bg=(0, 0, 0),
          pad_x=4,
          pad_y=2,
      )

    # --- PANEL 2: Horizontal Mirror Flip ---
    p2 = ImageOps.mirror(
        ImageOps.contain(im_rgb, (panel_w, panel_h), Image.Resampling.LANCZOS)
    )
    draw2 = ImageDraw.Draw(p2)
    for frac in (0.25, 0.5, 0.75):
      y_line = int(p2.size[1] * frac)
      draw2.line((0, y_line, p2.size[0], y_line), fill=(80, 220, 255), width=1)
    _draw_badge(
        draw2,
        (6, 6),
        "HORIZONTAL MIRROR FLIP (Symmetry / Horizon Check)",
        f_badge,
        fg=(160, 235, 255),
        bg=(0, 0, 0),
    )

    # --- PANEL 3: Clipping & Gamut Anomaly Map ---
    small_rgb = ImageOps.contain(
        im_rgb, (panel_w, panel_h), Image.Resampling.BILINEAR
    )
    arr_gray = np.asarray(ImageOps.grayscale(small_rgb), dtype=np.uint8)
    arr_hsv = np.asarray(small_rgb.convert("HSV"), dtype=np.uint8)

    base = (arr_gray // 2).astype(np.uint8)
    anom = np.stack([base, base, base], axis=-1)
    anom[arr_gray > 250] = [255, 40, 40]
    anom[arr_gray < 6] = [0, 240, 255]
    neon = (
        (arr_hsv[:, :, 1] > NEON_SAT_THRESHOLD)
        & (arr_hsv[:, :, 2] > 40)
        & (arr_gray < 245)
    )
    anom[neon] = [255, 0, 255]

    p3 = Image.fromarray(anom, mode="RGB")
    draw3 = ImageDraw.Draw(p3)
    legend = f"ANOMALY MAP: Red=Blown(>250) | Cyan=Crushed(<6) | Magenta=Neon(S>{NEON_SAT_THRESHOLD})"
    _draw_badge(draw3, (6, 6), legend, f_badge, fg=(255, 255, 255), bg=(0, 0, 0))

    # --- PANEL 4: Two 100% Native Pixel Zoom Strips ---
    p4 = Image.new("RGB", (p1_w, p1_h), color=(24, 28, 34))
    draw4 = ImageDraw.Draw(p4)
    strip_h = max(24, (p1_h - 54) // 2)
    crop_w1, crop_h1 = min(w, max(1, p1_w - 8)), min(h, strip_h)

    idx_a = (
        custom_tiles[0]
        if len(custom_tiles) >= 1
        else int(report["peak_focus_tile"].split("_")[1])
    )
    ax0, ay0, ax1, ay1 = _tile_box(w, h, idx_a)
    cx_a, cy_a = (ax0 + ax1) // 2, (ay0 + ay1) // 2
    x0_a = max(0, min(w - crop_w1, cx_a - crop_w1 // 2))
    y0_a = max(0, min(h - crop_h1, cy_a - crop_h1 // 2))
    zoom_a = im_rgb.crop((x0_a, y0_a, x0_a + crop_w1, y0_a + crop_h1))
    draw4.text(
        (6, 4),
        f"100% NATIVE ZOOM A: tile_{idx_a}_{TILE_LABELS[idx_a]}",
        font=f_badge,
        fill=(140, 240, 160),
    )
    p4.paste(zoom_a, (4, 24))

    if len(custom_tiles) >= 2:
      idx_b = custom_tiles[1]
      bx0, by0, bx1, by1 = _tile_box(w, h, idx_b)
      cx_b, cy_b = (bx0 + bx1) // 2, (by0 + by1) // 2
      label_b = f"100% NATIVE ZOOM B: tile_{idx_b}_{TILE_LABELS[idx_b]}"
      report["zoom_tiles_rendered"] = [idx_a, idx_b]
    else:
      cx_b, cy_b = w // 2, int(h * 0.72)
      label_b = "100% NATIVE ZOOM B: Lower-Mid Contact / Hand Zone"
      report["zoom_tiles_rendered"] = [idx_a]

    x0_b = max(0, min(w - crop_w1, cx_b - crop_w1 // 2))
    y0_b = max(0, min(h - crop_h1, cy_b - crop_h1 // 2))
    zoom_b = im_rgb.crop((x0_b, y0_b, x0_b + crop_w1, y0_b + crop_h1))
    b_top = 28 + strip_h
    draw4.text((6, b_top), label_b, font=f_badge, fill=(140, 210, 255))
    p4.paste(zoom_b, (4, b_top + 20))

    # --- ASSEMBLE FULL BOARD ---
    board_w = p1_w * 2 + 36
    board_h = p1_h * 2 + 125
    board = Image.new("RGB", (board_w, board_h), color=(18, 20, 26))
    b_draw = ImageDraw.Draw(board)

    title = (
        f"OPTIC v2.2 - DIAGNOSTIC QC BOARD | {img_path.name} "
        f"({report['dimensions']}, {report['aspect_ratio']})"
    )
    b_draw.text((16, 10), title, font=f_header, fill=(240, 245, 255))

    board.paste(p1, (12, 40))
    board.paste(p2, (24 + p1_w, 40))
    board.paste(p3, (12, 52 + p1_h))
    board.paste(p4, (24 + p1_w, 52 + p1_h))

    y_foot = 62 + p1_h * 2
    micro_disp = (
        report["microtexture_score"]
        if report["microtexture_score"] is not None
        else "N/A"
    )
    line1 = (
        f"METRICS: Lum={report['mean_luminance']} | Contrast={report['rms_contrast']} | "
        f"InteriorBlown={report['interior_blown_highlights_pct']}% | InteriorCrushed={report['interior_crushed_blacks_pct']}% | "
        f"NeonClip={report['neon_gamut_clipping_pct']}% | TealOrangeIdx={report['teal_orange_index']} | "
        f"MicroTex={micro_disp} | PeakSharp={report['peak_tile_sharpness']}"
    )
    b_draw.text((16, y_foot), line1, font=f_foot, fill=(200, 215, 230))
    if report["diagnostic_flags"]:
      flag_str = "FLAGS: " + " ; ".join(report["diagnostic_flags"])
      b_draw.text((16, y_foot + 22), flag_str[:210], font=f_foot, fill=(255, 110, 110))
    else:
      b_draw.text(
          (16, y_foot + 22),
          "STATUS: PASS_AUTOMATED_METRICS (0 optical flags; verify low-confidence anatomy/text on 100% zoom)",
          font=f_foot,
          fill=(100, 240, 140),
      )

    board.save(out_path, "PNG")

  report["diagnostic_board"] = str(out_path)
  if as_json:
    print(json.dumps(report, indent=2))
  else:
    print_telemetry(report, as_json=False)
    print(f"\n  [BOARD] Saved 4-panel Composite Diagnostic Board to: {out_path}")
  return report


def tile_image(image_path: str, out_dir: str = None) -> list:
  """Splits image into 9 full-resolution 3x3 tiles + overview grid (safe down to 1x1)."""
  img_path = Path(image_path).resolve()
  if not img_path.exists():
    raise FileNotFoundError(f"Image not found: {img_path}")

  out_dir = (
      Path(out_dir).resolve()
      if out_dir
      else img_path.parent / f"{img_path.stem}_qc_tiles"
  )
  out_dir.mkdir(parents=True, exist_ok=True)

  tile_paths = []
  with Image.open(img_path) as im:
    im_rgb = im.convert("RGB")
    w, h = im_rgb.size
    overview = im_rgb.copy()
    draw = ImageDraw.Draw(overview)
    f_tile = _load_scalable_font(max(12, min(28, w // 45)), bold=True)

    for idx in range(9):
      box = _tile_box(w, h, idx)
      tile = im_rgb.crop(box)
      label = TILE_LABELS[idx]
      t_path = out_dir / f"tile_{idx}_{label}.png"
      tile.save(t_path, "PNG")
      tile_paths.append(str(t_path))
      if w >= 40 and h >= 40:
        draw.rectangle(
            (box[0], box[1], max(box[0], box[2] - 1), max(box[1], box[3] - 1)),
            outline=(255, 60, 60),
            width=max(2, w // 400),
        )
        _draw_badge(
            draw,
            (box[0] + 6, box[1] + 6),
            f"#{idx}: {label}",
            f_tile,
            fg=(255, 240, 120),
            bg=(0, 0, 0),
        )

    ov_path = out_dir / "00_overview_grid.png"
    overview.save(ov_path, "PNG")
    tile_paths.insert(0, str(ov_path))

  print(f"Generated 9 full-res tiles + overview in: {out_dir}")
  return tile_paths


def mirror_flip(image_path: str, out_path: str = None) -> str:
  """Saves horizontal mirror flip."""
  img_path = Path(image_path).resolve()
  out_path = (
      Path(out_path).resolve()
      if out_path
      else img_path.parent / f"{img_path.stem}_mirror_flip.png"
  )
  with Image.open(img_path) as im:
    ImageOps.mirror(im.convert("RGB")).save(out_path, "PNG")
  print(f"Saved horizontal mirror flip to: {out_path}")
  return str(out_path)


def generate_inpaint_mask(
    image_path: str, out_path: str, tiles: str = None, box: str = None
) -> str:
  """
    Generates a binary black/white PNG mask (White 255 = inpaint target, Black 0 = preserve)
    from either 3x3 tile indices (--tiles 7,8) or bounding box (--box x1,y1,x2,y2).
    """
  img_path = Path(image_path).resolve()
  with Image.open(img_path) as im:
    w, h = im.size

  if not tiles and not box:
    raise ValueError(
        "Provide at least one of --tiles (e.g. 7,8) or --box (x1,y1,x2,y2)"
    )

  mask = Image.new("L", (w, h), color=0)
  draw = ImageDraw.Draw(mask)

  if tiles:
    for idx in _parse_tile_indices(tiles):
      x0, y0, x1, y1 = _tile_box(w, h, idx)
      draw.rectangle((x0, y0, max(x0, x1 - 1), max(y0, y1 - 1)), fill=255)

  if box:
    coords = [float(v.strip()) for v in box.split(",")]
    if len(coords) != 4:
      raise ValueError("--box requires 4 values: x1,y1,x2,y2")
    if all(0.0 <= v <= 1.0 for v in coords) and max(coords) <= 1.0:
      b = (
          int(coords[0] * w),
          int(coords[1] * h),
          int(coords[2] * w),
          int(coords[3] * h),
      )
    else:
      b = (int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3]))
    x0, y0 = max(0, min(w, b[0])), max(0, min(h, b[1]))
    x1, y1 = max(0, min(w, b[2])), max(0, min(h, b[3]))
    if x1 <= x0 or y1 <= y0:
      raise ValueError(
          f"Invalid bounding box after clamping: ({x0}, {y0}, {x1}, {y1})"
      )
    draw.rectangle((x0, y0, max(x0, x1 - 1), max(y0, y1 - 1)), fill=255)

  out_p = Path(out_path).resolve()
  out_p.parent.mkdir(parents=True, exist_ok=True)
  mask.save(out_p, "PNG")
  print(f"Generated binary inpaint mask ({w}x{h}) at: {out_p}")
  return str(out_p)


def _file_sha256(path: Path) -> str:
  """Computes SHA-256 hex digest of a file for provenance integrity."""
  h = hashlib.sha256()
  with open(path, "rb") as f:
    for chunk in iter(lambda: f.read(65536), b""):
      h.update(chunk)
  return h.hexdigest()


def _provenance_sidecar_path(img_path: Path) -> Path:
  return img_path.parent / f"{img_path.stem}.provenance.json"


def _save_with_provenance(
    src_path: Path,
    out_im: Image.Image,
    out_path: Path,
    operation: str,
    params: dict,
    extra_meta: dict = None,
) -> dict:
  """
    Saves an image while preserving EXIF, ICC color profiles, DPI, and PNG tEXt/iTXt chunks
    from src_path, embedding unsigned C2PA-style NIC_Provenance metadata into PNG outputs,
    and chaining a <out_stem>.provenance.json SHA-256 edit log.
    """
  out_path.parent.mkdir(parents=True, exist_ok=True)
  now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
  src_sha = _file_sha256(src_path) if src_path and src_path.exists() else None

  existing_info = {}
  exif_bytes = None
  icc_bytes = None
  dpi_val = None
  if src_path and src_path.exists():
    try:
      with Image.open(src_path) as src_im:
        existing_info = dict(src_im.info or {})
        exif_bytes = existing_info.get("exif")
        icc_bytes = existing_info.get("icc_profile")
        dpi_val = existing_info.get("dpi")
    except Exception:
      pass

  src_sidecar = _provenance_sidecar_path(src_path) if src_path else None
  out_sidecar = _provenance_sidecar_path(out_path)
  manifest = {
      "schema": "optic-c2pa-style-provenance/v2.2",
      "signed": False,
      "AI_Synthetic_Media": True,
      "generation_metadata": {},
      "history": [],
  }
  for cand_sc in (out_sidecar, src_sidecar):
    if cand_sc and cand_sc.exists():
      try:
        loaded = json.loads(cand_sc.read_text(encoding="utf-8"))
        manifest["generation_metadata"] = loaded.get("generation_metadata", {})
        manifest["history"] = list(loaded.get("history", []))
        break
      except Exception:
        pass

  if extra_meta:
    for k, v in extra_meta.items():
      if v is not None:
        manifest["generation_metadata"][k] = v

  pnginfo = PngImagePlugin.PngInfo()
  preserved_keys = []
  for k, v in existing_info.items():
    if isinstance(k, str) and isinstance(v, str) and k not in ("NIC_Provenance",):
      try:
        v.encode("latin-1")
        pnginfo.add_text(k, v)
      except UnicodeEncodeError:
        pnginfo.add_itxt(k, v)
      preserved_keys.append(k)

  for mk, mv in manifest["generation_metadata"].items():
    if mv is not None:
      tag = f"NIC_{mk.capitalize()}"
      val_s = str(mv)
      try:
        val_s.encode("latin-1")
        pnginfo.add_text(tag, val_s)
      except UnicodeEncodeError:
        pnginfo.add_itxt(tag, val_s)
      if tag not in preserved_keys:
        preserved_keys.append(tag)

  step_entry = {
      "timestamp_utc": now_utc,
      "operation": operation,
      "parameters": params,
      "source_file": str(src_path) if src_path else None,
      "source_sha256": src_sha,
      "output_file": str(out_path),
  }
  pnginfo.add_text(
      "NIC_Provenance",
      json.dumps({
          "AI_Synthetic_Media": True,
          "signed": False,
          "last_operation": operation,
          "timestamp_utc": now_utc,
          "generation": manifest["generation_metadata"],
      }),
  )

  save_kwargs = {}
  ext = out_path.suffix.lower()
  if ext == ".png":
    save_kwargs["pnginfo"] = pnginfo
  elif ext in (".jpg", ".jpeg"):
    save_kwargs["quality"] = 95
    save_kwargs["subsampling"] = 0
  elif ext == ".webp":
    save_kwargs["quality"] = 95
  if exif_bytes:
    save_kwargs["exif"] = exif_bytes
  if isinstance(icc_bytes, (bytes, bytearray)) and len(icc_bytes) > 0:
    save_kwargs["icc_profile"] = icc_bytes
  if dpi_val:
    save_kwargs["dpi"] = dpi_val

  out_im.save(out_path, **save_kwargs)
  step_entry["output_sha256"] = _file_sha256(out_path)
  manifest["latest_file"] = str(out_path)
  manifest["latest_sha256"] = step_entry["output_sha256"]
  manifest["preserved_metadata_keys"] = preserved_keys
  manifest["history"].append(step_entry)

  out_sidecar.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
  return manifest


def manage_provenance(
    image_path: str,
    model: str = None,
    seed: str = None,
    prompt: str = None,
    mode: str = None,
    as_json: bool = False,
) -> dict:
  """
    Stamps or inspects C2PA-style unsigned AI provenance metadata in both PNG tEXt/iTXt chunks
    and the sidecar <stem>.provenance.json SHA-256 edit manifest.
    """
  img_path = Path(image_path).resolve()
  if not img_path.exists():
    raise FileNotFoundError(f"Image not found: {img_path}")

  has_updates = any(v is not None for v in (model, seed, prompt, mode))
  if has_updates:
    with Image.open(img_path) as im:
      im_copy = im.copy()
    extra = {"model": model, "seed": seed, "prompt": prompt, "mode": mode}
    manifest = _save_with_provenance(
        src_path=img_path,
        out_im=im_copy,
        out_path=img_path,
        operation="provenance-stamp",
        params={k: v for k, v in extra.items() if v is not None},
        extra_meta=extra,
    )
  else:
    sidecar = _provenance_sidecar_path(img_path)
    embedded = {}
    with Image.open(img_path) as im:
      for k, v in (im.info or {}).items():
        if isinstance(k, str) and isinstance(v, (str, int, float)):
          embedded[k] = v
    if sidecar.exists():
      manifest = json.loads(sidecar.read_text(encoding="utf-8"))
    else:
      manifest = {
          "schema": "optic-c2pa-style-provenance/v2.2",
          "signed": False,
          "file": str(img_path),
          "sha256": _file_sha256(img_path),
          "history": [],
      }
    manifest["embedded_png_text_chunks"] = embedded

  if as_json:
    print(json.dumps(manifest, indent=2))
  else:
    print(f"=== C2PA-Style Provenance Manifest ({img_path.name}, unsigned) ===")
    print(
        f"  Latest SHA-256 : {manifest.get('latest_sha256', _file_sha256(img_path))}"
    )
    print(
        f"  Generation Meta: {json.dumps(manifest.get('generation_metadata', {}))}"
    )
    print(f"  History Steps  : {len(manifest.get('history', []))}")
  return manifest


def crop_image(
    image_path: str, out_path: str, box: str = None, aspect: str = None
) -> str:
  """Level-1 deterministic crop/reframe (lossless PNG output; q95 re-encoded JPEG)."""
  img_path = Path(image_path).resolve()
  with Image.open(img_path) as im:
    im_rgb = im.convert("RGB")
    w, h = im_rgb.size

    if box:
      coords = [float(v.strip()) for v in box.split(",")]
      if len(coords) != 4:
        raise ValueError("--box requires 4 values: x1,y1,x2,y2")
      if all(0.0 <= v <= 1.0 for v in coords) and max(coords) <= 1.0:
        b = (
            int(coords[0] * w),
            int(coords[1] * h),
            int(coords[2] * w),
            int(coords[3] * h),
        )
      else:
        b = (int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3]))
      x0, y0 = max(0, min(w, b[0])), max(0, min(h, b[1]))
      x1, y1 = max(0, min(w, b[2])), max(0, min(h, b[3]))
      if x1 <= x0 or y1 <= y0:
        raise ValueError(
            f"Invalid crop box after clamping: ({x0}, {y0}, {x1}, {y1})"
        )
      cropped = im_rgb.crop((x0, y0, x1, y1))
    elif aspect:
      if ":" in aspect:
        aw, ah = [float(x) for x in aspect.split(":")]
        if aw <= 0 or ah <= 0:
          raise ValueError(f"Aspect ratio components must be positive: {aspect}")
        target_ratio = aw / ah
      else:
        target_ratio = float(aspect)
        if target_ratio <= 0:
          raise ValueError(f"Aspect ratio must be positive: {aspect}")
      curr_ratio = w / h
      if curr_ratio > target_ratio:
        new_w = max(1, int(round(h * target_ratio)))
        x0 = (w - new_w) // 2
        cropped = im_rgb.crop((x0, 0, x0 + new_w, h))
      else:
        new_h = max(1, int(round(w / target_ratio)))
        y0 = (h - new_h) // 2
        cropped = im_rgb.crop((0, y0, w, y0 + new_h))
    else:
      raise ValueError("Provide either --box or --aspect")

    out_p = Path(out_path).resolve()
    _save_with_provenance(
        img_path,
        cropped,
        out_p,
        "crop",
        {
            "box": box,
            "aspect": aspect,
            "size": f"{cropped.size[0]}x{cropped.size[1]}",
        },
    )
  print(
      f"Saved cropped image ({cropped.size[0]}x{cropped.size[1]}) with preserved provenance to: {out_p}"
  )
  return str(out_p)


def adjust_image(
    image_path: str,
    out_path: str,
    temp_shift: float = 0.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    gamma: float = 1.0,
) -> str:
  """
    Level-1 deterministic optical calibration (zero generator re-roll cost):
      - temp_shift (-50..+50): multiplicative R/B channel white-balance gain shift
        (preserves pure-black shadows at 0 instead of adding a flat offset)
      - contrast: global contrast multiplier
      - saturation: global color saturation multiplier
      - gamma: tone-curve gamma (<1.0 lifts shadows, >1.0 deepens midtones)
    """
  img_path = Path(image_path).resolve()
  with Image.open(img_path) as im:
    im_rgb = im.convert("RGB")
    arr = np.asarray(im_rgb, dtype=np.float32)

    if abs(temp_shift) > 0.1:
      t_norm = max(-1.0, min(1.0, temp_shift / 50.0))
      r_gain = math.exp(0.35 * t_norm)
      b_gain = math.exp(-0.35 * t_norm)
      arr[:, :, 0] = np.clip(arr[:, :, 0] * r_gain, 0.0, 255.0)
      arr[:, :, 2] = np.clip(arr[:, :, 2] * b_gain, 0.0, 255.0)

    if abs(gamma - 1.0) > 0.01:
      arr = np.clip(255.0 * ((arr / 255.0) ** gamma), 0.0, 255.0)

    out_im = Image.fromarray(arr.astype(np.uint8), mode="RGB")
    if abs(saturation - 1.0) > 0.01:
      out_im = ImageEnhance.Color(out_im).enhance(saturation)
    if abs(contrast - 1.0) > 0.01:
      out_im = ImageEnhance.Contrast(out_im).enhance(contrast)

    out_p = Path(out_path).resolve()
    _save_with_provenance(
        img_path,
        out_im,
        out_p,
        "adjust",
        {
            "temp": temp_shift,
            "contrast": contrast,
            "saturation": saturation,
            "gamma": gamma,
        },
    )

  print(f"Saved optically calibrated image with preserved provenance to: {out_p}")
  return str(out_p)


def overlay_text(
    image_path: str,
    out_path: str,
    text: str,
    subtext: str = None,
    position: str = "left",
    color: str = "auto",
    font_size: int = 0,
) -> str:
  """
    Level-1 zero-model-cost typography compositor with background-luminance contrast selection.
    """
  img_path = Path(image_path).resolve()
  with Image.open(img_path) as im:
    im_rgba = im.convert("RGBA")
    w, h = im_rgba.size
    gray_arr = np.asarray(ImageOps.grayscale(im.convert("RGB")), dtype=np.float32)

    pad_x, pad_y = int(w * 0.07), int(h * 0.12)
    if position == "right":
      x0, x1 = int(w * 0.52), w - pad_x
      y0, y1 = int(h * 0.25), int(h * 0.78)
    elif position == "center":
      x0, x1 = int(w * 0.20), int(w * 0.80)
      y0, y1 = int(h * 0.30), int(h * 0.75)
    elif position == "top-left":
      x0, x1 = pad_x, int(w * 0.55)
      y0, y1 = pad_y, int(h * 0.50)
    elif position == "bottom-left":
      x0, x1 = pad_x, int(w * 0.55)
      y0, y1 = int(h * 0.58), h - pad_y
    else:
      x0, x1 = pad_x, int(w * 0.52)
      y0, y1 = int(h * 0.28), int(h * 0.78)

    zone_lum = (
        float(np.mean(gray_arr[y0:y1, x0:x1])) if (y1 > y0 and x1 > x0) else 128.0
    )
    col_norm = color.strip().lower()
    if col_norm in ("auto", "light", "white", "dark", "black"):
      use_light = (
          (zone_lum < 138.0)
          if col_norm == "auto"
          else (col_norm in ("light", "white"))
      )
      fg_col = (248, 250, 252, 255) if use_light else (24, 30, 40, 255)
      sub_col = (215, 222, 232, 235) if use_light else (55, 65, 81, 235)
      shadow_col = (0, 0, 0, 95) if use_light else (255, 255, 255, 75)
      resolved_tone = "light" if use_light else "dark"
    else:
      hx = color.strip().lstrip("#")
      if len(hx) == 3:
        hx = "".join(ch * 2 for ch in hx)
      rgb_c = (
          tuple(int(hx[i : i + 2], 16) for i in (0, 2, 4))
          if len(hx) == 6
          else (248, 250, 252)
      )
      fg_col = (*rgb_c, 255)
      sub_col = (*rgb_c, 220)
      lum_c = 0.299 * rgb_c[0] + 0.587 * rgb_c[1] + 0.114 * rgb_c[2]
      shadow_col = (0, 0, 0, 85) if lum_c >= 128 else (255, 255, 255, 75)
      resolved_tone = f"#{hx.upper()}" if len(hx) == 6 else "custom"

    h_size = font_size if font_size > 0 else max(24, int(h * 0.055))
    s_size = max(16, int(h_size * 0.52))
    font_main = _load_scalable_font(h_size, bold=True)
    font_sub = _load_scalable_font(s_size, bold=False)

    txt_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(txt_layer)

    max_chars = max(14, int((x1 - x0) / (h_size * 0.52)))
    wrapped_main = textwrap.wrap(text, width=max_chars)
    curr_y = y0

    for line in wrapped_main:
      draw.text((x0 + 2, curr_y + 2), line, font=font_main, fill=shadow_col)
      draw.text((x0, curr_y), line, font=font_main, fill=fg_col)
      curr_y += int(h_size * 1.22)

    if subtext:
      curr_y += int(h_size * 0.35)
      sub_chars = max(22, int((x1 - x0) / (s_size * 0.50)))
      for sline in textwrap.wrap(subtext, width=sub_chars):
        draw.text((x0 + 1, curr_y + 1), sline, font=font_sub, fill=shadow_col)
        draw.text((x0, curr_y), sline, font=font_sub, fill=sub_col)
        curr_y += int(s_size * 1.30)

    composited = Image.alpha_composite(im_rgba, txt_layer).convert("RGB")
    out_p = Path(out_path).resolve()
    _save_with_provenance(
        img_path,
        composited,
        out_p,
        "text-overlay",
        {
            "text": text,
            "subtext": subtext,
            "position": position,
            "color": color,
            "zone_lum": round(zone_lum, 1),
        },
    )

  print(
      f"Saved typography overlay (zone_lum={zone_lum:.1f}, color={resolved_tone}) with preserved provenance to: {out_p}"
  )
  return str(out_p)


def make_contact_sheet(image_paths: list, out_path: str) -> str:
  """Combines candidate images into a labeled comparison sheet with embedded telemetry."""
  valid_paths = [Path(p).resolve() for p in image_paths if Path(p).exists()]
  if not valid_paths:
    raise ValueError("No valid images found for contact sheet.")

  n = len(valid_paths)
  target_w, target_h = 640, 480
  cols = 2 if n > 1 else 1
  rows = (n + cols - 1) // cols

  sheet_w = cols * target_w + (cols + 1) * 20
  sheet_h = rows * (target_h + 76) + 20
  sheet = Image.new("RGB", (sheet_w, sheet_h), color=(20, 22, 28))
  draw = ImageDraw.Draw(sheet)
  f_hdr = _load_scalable_font(15, bold=True)
  f_sub = _load_scalable_font(13, bold=False)

  for i, p in enumerate(valid_paths):
    rep = compute_optical_telemetry(str(p))
    with Image.open(p) as im:
      thumb = ImageOps.contain(
          im.convert("RGB"), (target_w, target_h), Image.Resampling.LANCZOS
      )

    r, c = i // cols, i % cols
    x = 20 + c * (target_w + 20)
    y = 20 + r * (target_h + 76)
    sheet.paste(thumb, (x + (target_w - thumb.size[0]) // 2, y + 48))

    hdr = f"Candidate #{i+1}: {p.name} ({rep['dimensions']})"
    sub = (
        f"Sharp={rep['peak_tile_sharpness']} | Blown={rep['interior_blown_highlights_pct']}% | "
        f"Neon={rep['neon_gamut_clipping_pct']}% | TealOrange={rep['teal_orange_index']} | "
        f"Flags={len(rep['diagnostic_flags'])}"
    )
    draw.text((x, y), hdr, font=f_hdr, fill=(240, 245, 255))
    flag_col = (
        (100, 240, 140)
        if len(rep["diagnostic_flags"]) == 0
        else (255, 130, 110)
    )
    draw.text((x, y + 22), sub, font=f_sub, fill=flag_col)

  out_p = Path(out_path).resolve()
  out_p.parent.mkdir(parents=True, exist_ok=True)
  sheet.save(out_p, "PNG")
  print(f"Contact sheet saved to: {out_p}")
  return str(out_p)


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(
      description="Optic v2.2 Optical QC, Remediation & Provenance Toolkit"
  )
  subparsers = parser.add_subparsers(dest="command", required=True)

  p_an = subparsers.add_parser(
      "analyze", help="Compute optical telemetry & anomaly flags"
  )
  p_an.add_argument("image_path", help="Path to image")
  p_an.add_argument(
      "--json", action="store_true", help="Output machine-readable JSON"
  )
  p_an.set_defaults(
      handler=lambda a: print_telemetry(
          compute_optical_telemetry(a.image_path), as_json=a.json
      )
  )

  p_bd = subparsers.add_parser(
      "board", help="Generate single-image 4-panel Composite Diagnostic Board"
  )
  p_bd.add_argument("image_path", help="Path to image")
  p_bd.add_argument(
      "-o", "--out", default=None, help="Output path for diagnostic board PNG"
  )
  p_bd.add_argument(
      "--zoom-tiles",
      nargs="+",
      default=None,
      help="Comma- or space-separated tile indices (0..8) for 100%% zoom strips",
  )
  p_bd.add_argument(
      "--json", action="store_true", help="Output JSON telemetry alongside board"
  )
  p_bd.set_defaults(
      handler=lambda a: build_diagnostic_board(
          a.image_path,
          a.out,
          as_json=a.json,
          zoom_tiles=",".join(a.zoom_tiles) if a.zoom_tiles else None,
      )
  )

  p_tile = subparsers.add_parser("tile", help="Extract all 9 full-res 3x3 tiles")
  p_tile.add_argument("image_path", help="Path to image")
  p_tile.add_argument("-o", "--out-dir", default=None, help="Output directory")
  p_tile.set_defaults(handler=lambda a: tile_image(a.image_path, a.out_dir))

  p_flip = subparsers.add_parser("flip", help="Save horizontal mirror flip")
  p_flip.add_argument("image_path", help="Path to image")
  p_flip.add_argument("-o", "--out", default=None, help="Output path")
  p_flip.set_defaults(handler=lambda a: mirror_flip(a.image_path, a.out))

  p_mask = subparsers.add_parser(
      "mask", help="Generate binary inpainting mask PNG"
  )
  p_mask.add_argument(
      "image_path", help="Path to source image (for dimensions)"
  )
  p_mask.add_argument(
      "--tiles",
      nargs="+",
      default=None,
      help="Comma- or space-separated tile indices (e.g. 7,8 or 7 8)",
  )
  p_mask.add_argument(
      "--box",
      default=None,
      help="Bounding box x1,y1,x2,y2 (normalized 0..1 or pixels)",
  )
  p_mask.add_argument("-o", "--out", required=True, help="Output mask PNG path")
  p_mask.set_defaults(
      handler=lambda a: generate_inpaint_mask(
          a.image_path,
          a.out,
          tiles=",".join(a.tiles) if a.tiles else None,
          box=a.box,
      )
  )

  p_crop = subparsers.add_parser(
      "crop",
      help="Level-1 zero-model-cost crop/reframe (lossless PNG; q95 JPEG)",
  )
  p_crop.add_argument("image_path", help="Path to image")
  p_crop.add_argument(
      "--box", default=None, help="x1,y1,x2,y2 (normalized 0..1 or pixels)"
  )
  p_crop.add_argument(
      "--aspect", default=None, help="Target aspect ratio W:H (e.g. 16:9)"
  )
  p_crop.add_argument("-o", "--out", required=True, help="Output image path")
  p_crop.set_defaults(
      handler=lambda a: crop_image(
          a.image_path, a.out, box=a.box, aspect=a.aspect
      )
  )

  p_adj = subparsers.add_parser(
      "adjust",
      help="Level-1 multiplicative WB/contrast/gamma adjustment",
  )
  p_adj.add_argument("image_path", help="Path to image")
  p_adj.add_argument(
      "--temp",
      type=float,
      default=0.0,
      help="Multiplicative R/B white-balance gain shift (-50 cool .. +50 warm)",
  )
  p_adj.add_argument(
      "--contrast", type=float, default=1.0, help="Contrast multiplier"
  )
  p_adj.add_argument(
      "--saturation", type=float, default=1.0, help="Saturation multiplier"
  )
  p_adj.add_argument(
      "--gamma", type=float, default=1.0, help="Gamma correction (<1.0 lifts shadows)"
  )
  p_adj.add_argument("-o", "--out", required=True, help="Output image path")
  p_adj.set_defaults(
      handler=lambda a: adjust_image(
          a.image_path,
          a.out,
          temp_shift=a.temp,
          contrast=a.contrast,
          saturation=a.saturation,
          gamma=a.gamma,
      )
  )

  p_txt = subparsers.add_parser(
      "text-overlay",
      help="Level-1 typography compositor with auto-contrast",
  )
  p_txt.add_argument("image_path", help="Path to image")
  p_txt.add_argument("--text", required=True, help="Primary headline text")
  p_txt.add_argument(
      "--subtext", default=None, help="Optional supporting subheadline text"
  )
  p_txt.add_argument(
      "--position",
      "--align",
      "--zone",
      dest="position",
      default="left",
      choices=["left", "right", "center", "top-left", "bottom-left"],
      help="Copy space placement",
  )
  p_txt.add_argument(
      "--color",
      default="auto",
      help="'auto' (luminance-adaptive), dark/light, or hex color e.g. #FFFFFF",
  )
  p_txt.add_argument(
      "--size",
      type=int,
      default=0,
      help="Optional headline font size in px (0=auto-scale)",
  )
  p_txt.add_argument("-o", "--out", required=True, help="Output image path")
  p_txt.set_defaults(
      handler=lambda a: overlay_text(
          a.image_path,
          a.out,
          text=a.text,
          subtext=a.subtext,
          position=a.position,
          color=a.color,
          font_size=a.size,
      )
  )

  p_prov = subparsers.add_parser(
      "provenance",
      help="Stamp or inspect C2PA-style unsigned provenance & SHA-256 edit chain",
  )
  p_prov.add_argument("image_path", help="Path to image")
  p_prov.add_argument("--model", default=None, help="Generator model name")
  p_prov.add_argument("--seed", default=None, help="Generation seed")
  p_prov.add_argument("--prompt", default=None, help="Final generation prompt")
  p_prov.add_argument("--mode", default=None, help="Operational mode")
  p_prov.add_argument(
      "--json", action="store_true", help="Output provenance manifest as JSON"
  )
  p_prov.set_defaults(
      handler=lambda a: manage_provenance(
          a.image_path,
          model=a.model,
          seed=a.seed,
          prompt=a.prompt,
          mode=a.mode,
          as_json=a.json,
      )
  )

  p_cs = subparsers.add_parser(
      "contact-sheet", help="Side-by-side candidate comparison sheet"
  )
  p_cs.add_argument("images", nargs="+", help="Candidate image paths")
  p_cs.add_argument("-o", "--out", required=True, help="Output path")
  p_cs.set_defaults(handler=lambda a: make_contact_sheet(a.images, a.out))

  return parser


def main():
  parser = build_parser()
  args = parser.parse_args()
  args.handler(args)


if __name__ == "__main__":
  main()
