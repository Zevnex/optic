#!/usr/bin/env python3
"""
qc_tools.py (v2.2) - Deterministic Optical QC, Telemetry, Remediation & Provenance Toolkit
for Natural Image Craft.

Capabilities:
  1. analyze       - True optical telemetry (2D Laplacian sharpness per tile,
                     studio-sweep-aware clipping, neon gamut clipping,
                     teal-orange split-tone index, micro-texture waxy detector)
                     with --json output.
  2. board         - Single-file 4-panel Composite Diagnostic Board (3x3 grid +
                     per-tile sharpness, Mirror Flip, Clipping/Gamut Heatmap,
                     and 100% Native Pixel Zoom strips) -> cuts 11 vision tool
                     calls down to 1.
  3. tile          - Extracts all 9 full-resolution 3x3 tiles + overview grid.
  4. flip          - Horizontal mirror flip for symmetry/perspective check.
  5. mask          - Generates binary black/white inpainting mask PNGs from
                     tile IDs (--tiles 7,8) or bounding boxes (--box x1,y1,x2,y2).
  6. crop          - Level-1 zero-cost reframing (--box or --aspect W:H).
  7. adjust        - Level-1 zero-cost optical calibration (white balance temp,
                     contrast, saturation restraint, gamma lift).
  8. text-overlay  - Level-1 zero-cost typography compositor with automatic
                     background-luminance contrast detection for copy space.
  9. provenance    - C2PA-aligned provenance stamping & SHA-256 edit chain audit.
 10. contact-sheet - Side-by-side candidate comparison board with metrics.
"""

import sys
import os
import json
import math
import hashlib
import textwrap
import argparse
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from PIL import Image, ImageOps, ImageDraw, ImageEnhance, ImageFont, PngImagePlugin

TILE_LABELS = [
    "top_left", "top_center", "top_right",
    "mid_left", "mid_center", "mid_right",
    "bot_left", "bot_center", "bot_right"
]


def _compute_laplacian_variance(gray_arr: np.ndarray) -> float:
    """Computes discrete 2D Laplacian variance as a measure of high-frequency edge sharpness."""
    if gray_arr.shape[0] < 4 or gray_arr.shape[1] < 4:
        return 0.0
    g = gray_arr.astype(np.float32)
    lap = (
        g[:-2, 1:-1] + g[2:, 1:-1] +
        g[1:-1, :-2] + g[1:-1, 2:] -
        4.0 * g[1:-1, 1:-1]
    )
    return float(np.var(lap))


def _compute_microtexture_score(gray_arr: np.ndarray) -> float:
    """
    Measures fine micro-texture (pore/grain energy) in smooth midtone patches.
    Low score (< 1.8) in non-studio scenes indicates over-denoised 'waxy/plastic' look.
    """
    g = gray_arr.astype(np.float32)
    if g.shape[0] < 16 or g.shape[1] < 16:
        return 5.0
    # 3x3 box blur approximation via slicing
    smooth = (
        g[:-2, :-2] + g[:-2, 1:-1] + g[:-2, 2:] +
        g[1:-1, :-2] + g[1:-1, 1:-1] + g[1:-1, 2:] +
        g[2:, :-2] + g[2:, 1:-1] + g[2:, 2:]
    ) / 9.0
    center = g[1:-1, 1:-1]
    residual = np.abs(center - smooth)

    # Macro gradient to exclude sharp structural edges
    grad_y = np.abs(g[2:, 1:-1] - g[:-2, 1:-1])
    grad_x = np.abs(g[1:-1, 2:] - g[1:-1, :-2])
    macro_grad = grad_x + grad_y

    # Midtone smooth patches: luminance 65..205 and low macro edge gradient (< 18)
    mask = (center > 65) & (center < 205) & (macro_grad < 18.0)
    if np.sum(mask) < 200:
        return 5.0
    return float(np.mean(residual[mask]))


def compute_optical_telemetry(image_path: str) -> dict:
    """Computes full optical, exposure, sharpness, and color telemetry for an image."""
    img_path = Path(image_path).resolve()
    if not img_path.exists():
        raise FileNotFoundError(f"Image not found: {img_path}")

    with Image.open(img_path) as im:
        im_rgb = im.convert("RGB")
        w, h = im_rgb.size
        rgb_arr = np.asarray(im_rgb, dtype=np.uint8)
        gray_arr = np.asarray(ImageOps.grayscale(im_rgb), dtype=np.uint8)
        hsv_arr = np.asarray(im_rgb.convert("HSV"), dtype=np.uint8)

    total_px = w * h

    # 1. Border vs Interior separation (outer 8% margin vs interior 84%, safe for tiny images)
    margin_x = max(1, min(max(1, w // 4), int(w * 0.08)))
    margin_y = max(1, min(max(1, h // 4), int(h * 0.08)))
    border_mask = np.ones((h, w), dtype=bool)
    if h > 2 * margin_y and w > 2 * margin_x:
        border_mask[margin_y:h - margin_y, margin_x:w - margin_x] = False
    interior_mask = ~border_mask

    border_gray = gray_arr[border_mask] if np.any(border_mask) else gray_arr.ravel()
    interior_gray = gray_arr[interior_mask] if np.any(interior_mask) else gray_arr.ravel()

    # Detect clean studio white sweep or studio dark backdrop
    border_white_pct = float(np.mean(border_gray > 246) * 100.0)
    border_black_pct = float(np.mean(border_gray < 10) * 100.0)
    studio_white_sweep = border_white_pct > 35.0
    studio_dark_backdrop = border_black_pct > 35.0

    # Global clipping vs Interior subject clipping
    global_blown_pct = float(np.mean(gray_arr > 250) * 100.0)
    global_crushed_pct = float(np.mean(gray_arr < 6) * 100.0)

    if studio_white_sweep:
        # Exclude pure studio white pixels (>248 with near-zero saturation) from interior subject clipping
        s_interior = hsv_arr[:, :, 1][interior_mask]
        non_sweep_interior = interior_gray[(interior_gray <= 246) | (s_interior > 18)]
        interior_blown_pct = float(np.mean(non_sweep_interior > 250) * 100.0) if len(non_sweep_interior) > 0 else 0.0
    else:
        interior_blown_pct = float(np.mean(interior_gray > 250) * 100.0)

    if studio_dark_backdrop:
        non_dark_interior = interior_gray[interior_gray >= 10]
        interior_crushed_pct = float(np.mean(non_dark_interior < 6) * 100.0) if len(non_dark_interior) > 0 else 0.0
    else:
        interior_crushed_pct = float(np.mean(interior_gray < 6) * 100.0)

    # 2. Sharpness (Global + 3x3 Per-Tile Laplacian Variance)
    global_sharpness = _compute_laplacian_variance(gray_arr)
    tile_w, tile_h = w // 3, h // 3
    tile_sharpness = {}
    for idx in range(9):
        r, c = idx // 3, idx % 3
        y0, y1 = r * tile_h, (r + 1) * tile_h if r < 2 else h
        x0, x1 = c * tile_w, (c + 1) * tile_w if c < 2 else w
        t_var = _compute_laplacian_variance(gray_arr[y0:y1, x0:x1])
        tile_sharpness[f"tile_{idx}_{TILE_LABELS[idx]}"] = round(t_var, 1)

    sharp_vals = list(tile_sharpness.values())
    peak_tile_name = max(tile_sharpness, key=tile_sharpness.get)
    peak_sharpness = max(sharp_vals)
    min_sharpness = max(0.1, min(sharp_vals))
    focus_separation_ratio = round(peak_sharpness / min_sharpness, 2)

    # 3. Color & Saturation Telemetry (Calibrated to avoid false positives on warm wood/skin)
    h_chan = hsv_arr[:, :, 0].astype(np.float32) * (360.0 / 255.0)  # 0..360 deg
    s_chan = hsv_arr[:, :, 1].astype(np.float32)                    # 0..255
    v_chan = hsv_arr[:, :, 2].astype(np.float32)                    # 0..255

    mean_saturation = float(np.mean(s_chan))
    p95_saturation = float(np.percentile(s_chan, 95))

    # True Neon / Gamut Clipping: S > 230 (>90% saturation) in non-white luminance range (40 < V, Gray < 245)
    neon_mask = (s_chan > 230) & (v_chan > 40) & (gray_arr < 245)
    neon_clipping_pct = float(np.mean(neon_mask) * 100.0)

    # Teal-Orange Split-Tone Slop Detector:
    # True split-toning tints shadows/backgrounds teal and midtones/highlights orange across the whole frame,
    # leaving few neutral grays. Weight bimodal hue concentration by overall chromatic coverage (S > 70).
    chromatic_mask = (s_chan > 70) & (v_chan > 35) & (gray_arr < 245)
    chromatic_ratio = float(np.mean(chromatic_mask))
    if chromatic_ratio > 0.08:
        h_chrom = h_chan[chromatic_mask]
        orange_frac = float(np.mean((h_chrom >= 12.0) & (h_chrom <= 44.0)))
        teal_frac = float(np.mean((h_chrom >= 165.0) & (h_chrom <= 210.0)))
        bimodal_purity = math.sqrt(orange_frac * teal_frac) * 2.0  # 0..1 when equal 50/50 split
        # Scale by chromatic coverage so neutral concrete/gray scenes with one wood table don't false-positive
        coverage_factor = min(1.0, chromatic_ratio / 0.45)
        teal_orange_index = round(bimodal_purity * coverage_factor * 100.0, 1)
    else:
        teal_orange_index = 0.0

    # 4. In-Focus Subject Micro-Texture (Waxy/Plastic detector)
    # Evaluate micro-texture specifically across in-focus tiles (>= 25% of peak tile sharpness)
    # so out-of-focus bokeh backgrounds do not dilute the subject's surface texture score.
    in_focus_scores = []
    for idx in range(9):
        t_key = f"tile_{idx}_{TILE_LABELS[idx]}"
        if tile_sharpness[t_key] >= max(35.0, 0.25 * peak_sharpness):
            r, c = idx // 3, idx % 3
            y0, y1 = r * tile_h, (r + 1) * tile_h if r < 2 else h
            x0, x1 = c * tile_w, (c + 1) * tile_w if c < 2 else w
            in_focus_scores.append(_compute_microtexture_score(gray_arr[y0:y1, x0:x1]))
    if in_focus_scores:
        microtexture_score = round(float(np.mean(in_focus_scores)), 2)
    else:
        microtexture_score = round(_compute_microtexture_score(gray_arr), 2)

    # 5. Calibrated Diagnostic Flags
    flags = []
    if interior_blown_pct > 4.0:
        flags.append(
            f"INTERIOR_HIGHLIGHT_CLIPPING: {interior_blown_pct:.2f}% of subject pixels are blown (>250)."
        )
    if interior_crushed_pct > 6.0:
        flags.append(
            f"INTERIOR_SHADOW_CRUSH: {interior_crushed_pct:.2f}% of subject pixels are crushed black (<6)."
        )
    if neon_clipping_pct > 3.5:
        flags.append(
            f"NEON_GAMUT_CLIPPING: {neon_clipping_pct:.2f}% of pixels have extreme neon saturation (S>235)."
        )
    if teal_orange_index > 48.0:
        flags.append(
            f"TEAL_ORANGE_SPLIT_GLAZE: High bimodal cyan/amber concentration (index={teal_orange_index})."
        )
    if peak_sharpness < 45.0:
        flags.append(
            f"SOFT_FOCUS_WARNING: Peak tile Laplacian variance is very low ({peak_sharpness:.1f}); image may be blurry."
        )
    waxy_floor = 1.15 if focus_separation_ratio > 25.0 else 1.60
    if microtexture_score < waxy_floor and not studio_white_sweep:
        flags.append(
            f"WAXY_SMOOTHNESS_WARNING: Midtone micro-texture score ({microtexture_score} < {waxy_floor}) indicates heavy denoising/plastic sheen."
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
        "neon_gamut_clipping_pct": round(neon_clipping_pct, 2),
        "teal_orange_index": teal_orange_index,
        "microtexture_score": microtexture_score,
        "global_laplacian_sharpness": round(global_sharpness, 1),
        "peak_focus_tile": peak_tile_name,
        "peak_tile_sharpness": round(peak_sharpness, 1),
        "focus_separation_ratio": focus_separation_ratio,
        "tile_sharpness": tile_sharpness,
        "diagnostic_flags": flags,
        "status": "PASS_AUTOMATED_METRICS" if len(flags) == 0 else "WARN_REVIEW_FLAGS"
    }


def print_telemetry(report: dict, as_json: bool = False):
    if as_json:
        print(json.dumps(report, indent=2))
        return
    print("=== Optical & Physical Telemetry (Natural Image Craft v2.2) ===")
    print(f"  File                          : {Path(report['file']).name}")
    print(f"  Dimensions / Aspect           : {report['dimensions']} ({report['aspect_ratio']})")
    print(f"  Mean Luminance / Contrast     : {report['mean_luminance']} / {report['rms_contrast']}")
    print(f"  Studio Backdrop Detected      : WhiteSweep={report['studio_white_sweep_detected']}, Dark={report['studio_dark_backdrop_detected']}")
    print(f"  Interior Blown Highlights     : {report['interior_blown_highlights_pct']}% (Global: {report['global_blown_highlights_pct']}%)")
    print(f"  Interior Crushed Shadows      : {report['interior_crushed_blacks_pct']}% (Global: {report['global_crushed_blacks_pct']}%)")
    print(f"  Mean / P95 Saturation         : {report['mean_saturation']} / {report['p95_saturation']} (0-255 scale)")
    print(f"  Neon Gamut Clipping (S>235)   : {report['neon_gamut_clipping_pct']}%")
    print(f"  Teal-Orange Split-Tone Index  : {report['teal_orange_index']} (Threshold: 48.0)")
    print(f"  Midtone Micro-Texture Score   : {report['microtexture_score']} (Waxy floor: 1.6)")
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
    zoom_tiles: str = None
) -> dict:
    """
    Creates a single 4-panel Composite Diagnostic Board (<stem>_qc_board.png):
      - Top-Left: Original with 3x3 coordinate grid & per-tile sharpness scores
      - Top-Right: Horizontal Mirror Flip (symmetry & perspective check)
      - Bottom-Left: Optical Anomaly Map (Red=Blown, Cyan=Crushed, Magenta=Neon)
      - Bottom-Right: Two 100% Native Resolution Zoom Crops (Peak Focus + Contact Zone,
        or user-specified tile indices via --zoom-tiles e.g. --zoom-tiles 2,6)
    Allows a vision model to inspect everything in 1 single file read instead of 11!
    """
    img_path = Path(image_path).resolve()
    report = compute_optical_telemetry(str(img_path))

    if out_path is None:
        out_path = img_path.parent / f"{img_path.stem}_qc_board.png"
    else:
        out_path = Path(out_path).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(img_path) as im:
        im_rgb = im.convert("RGB")
        w, h = im_rgb.size

        panel_w, panel_h = 720, int(720 * (h / w))
        panel_h = max(420, min(680, panel_h))

        # --- PANEL 1: 3x3 Grid + Per-Tile Sharpness ---
        p1 = ImageOps.contain(im_rgb, (panel_w, panel_h), Image.Resampling.LANCZOS)
        p1_w, p1_h = p1.size
        draw1 = ImageDraw.Draw(p1)
        tw, th = p1_w // 3, p1_h // 3
        for idx in range(9):
            r, c = idx // 3, idx % 3
            x0, y0 = c * tw, r * th
            x1 = (c + 1) * tw if c < 2 else p1_w - 1
            y1 = (r + 1) * th if r < 2 else p1_h - 1
            draw1.rectangle((x0, y0, x1, y1), outline=(255, 70, 70), width=2)
            t_key = f"tile_{idx}_{TILE_LABELS[idx]}"
            s_val = report["tile_sharpness"][t_key]
            badge = f"#{idx} {TILE_LABELS[idx]} (S:{s_val})"
            draw1.rectangle((x0 + 4, y0 + 4, x0 + 4 + len(badge) * 6 + 6, y0 + 20), fill=(0, 0, 0))
            draw1.text((x0 + 7, y0 + 6), badge, fill=(255, 230, 100))

        # --- PANEL 2: Horizontal Mirror Flip ---
        p2 = ImageOps.mirror( ImageOps.contain(im_rgb, (panel_w, panel_h), Image.Resampling.LANCZOS) )
        draw2 = ImageDraw.Draw(p2)
        # Draw horizontal reference lines to spot tilted horizons / eyes
        for frac in (0.25, 0.5, 0.75):
            y_line = int(p2.size[1] * frac)
            draw2.line((0, y_line, p2.size[0], y_line), fill=(80, 220, 255), width=1)

        # --- PANEL 3: Clipping & Gamut Anomaly Map ---
        small_rgb = ImageOps.contain(im_rgb, (panel_w, panel_h), Image.Resampling.BILINEAR)
        arr_rgb = np.asarray(small_rgb, dtype=np.uint8)
        arr_gray = np.asarray(ImageOps.grayscale(small_rgb), dtype=np.uint8)
        arr_hsv = np.asarray(small_rgb.convert("HSV"), dtype=np.uint8)

        # Dimmed grayscale backdrop so color anomalies pop
        base = (arr_gray // 2).astype(np.uint8)
        anom = np.stack([base, base, base], axis=-1)

        # Blown highlights (>250) -> Bright Red
        blown = arr_gray > 250
        anom[blown] = [255, 40, 40]

        # Crushed shadows (<6) -> Bright Cyan
        crushed = arr_gray < 6
        anom[crushed] = [0, 240, 255]

        # Neon gamut clipping (S > 230, V > 40, Gray < 245) -> Bright Magenta
        neon = (arr_hsv[:, :, 1] > 230) & (arr_hsv[:, :, 2] > 40) & (arr_gray < 245)
        anom[neon] = [255, 0, 255]

        p3 = Image.fromarray(anom, mode="RGB")
        draw3 = ImageDraw.Draw(p3)
        legend = "ANOMALY MAP: Red=Blown(>250) | Cyan=Crushed(<6) | Magenta=Neon(S>235)"
        draw3.rectangle((4, 4, 4 + len(legend) * 6 + 8, 22), fill=(0, 0, 0))
        draw3.text((8, 7), legend, fill=(255, 255, 255))

        # --- PANEL 4: Two 100% Native Pixel Zoom Strips ---
        p4 = Image.new("RGB", (p1_w, p1_h), color=(24, 28, 34))
        draw4 = ImageDraw.Draw(p4)
        strip_h = (p1_h - 36) // 2
        crop_w1, crop_h1 = min(w, p1_w - 8), min(h, strip_h)

        custom_tiles = []
        if zoom_tiles:
            for t_str in str(zoom_tiles).replace(" ", ",").split(","):
                if not t_str.strip():
                    continue
                t_idx = int(t_str.strip())
                if 0 <= t_idx <= 8:
                    custom_tiles.append(t_idx)

        # Strip A: Custom tile #1 or Peak Focus Tile center
        idx_a = custom_tiles[0] if len(custom_tiles) >= 1 else int(report["peak_focus_tile"].split("_")[1])
        pr_a, pc_a = idx_a // 3, idx_a % 3
        cx_a = int((pc_a + 0.5) * (w / 3.0))
        cy_a = int((pr_a + 0.5) * (h / 3.0))
        x0_a = max(0, min(w - crop_w1, cx_a - crop_w1 // 2))
        y0_a = max(0, min(h - crop_h1, cy_a - crop_h1 // 2))
        zoom_a = im_rgb.crop((x0_a, y0_a, x0_a + crop_w1, y0_a + crop_h1))
        p4.paste(zoom_a, (4, 18))
        label_a = f"tile_{idx_a}_{TILE_LABELS[idx_a]}"
        draw4.text((6, 3), f"100% NATIVE ZOOM A: {label_a}", fill=(140, 240, 160))

        # Strip B: Custom tile #2 or Lower-Center Contact / Hand Zone
        if len(custom_tiles) >= 2:
            idx_b = custom_tiles[1]
            pr_b, pc_b = idx_b // 3, idx_b % 3
            cx_b = int((pc_b + 0.5) * (w / 3.0))
            cy_b = int((pr_b + 0.5) * (h / 3.0))
            label_b = f"100% NATIVE ZOOM B: tile_{idx_b}_{TILE_LABELS[idx_b]}"
            report["zoom_tiles_rendered"] = [idx_a, idx_b]
        else:
            cx_b, cy_b = w // 2, int(h * 0.72)
            label_b = "100% NATIVE ZOOM B: Lower-Mid Contact / Hand Zone"
            report["zoom_tiles_rendered"] = [idx_a]
        x0_b = max(0, min(w - crop_w1, cx_b - crop_w1 // 2))
        y0_b = max(0, min(h - crop_h1, cy_b - crop_h1 // 2))
        zoom_b = im_rgb.crop((x0_b, y0_b, x0_b + crop_w1, y0_b + crop_h1))
        p4.paste(zoom_b, (4, 22 + strip_h + 12))
        draw4.text((6, 20 + strip_h), label_b, fill=(140, 210, 255))

        # --- ASSEMBLE FULL BOARD ---
        board_w = p1_w * 2 + 36
        board_h = p1_h * 2 + 130
        board = Image.new("RGB", (board_w, board_h), color=(18, 20, 26))
        b_draw = ImageDraw.Draw(board)

        # Header bar (use ASCII hyphen so default bitmap font never renders missing-glyph boxes)
        title = f"NATURAL IMAGE CRAFT v2.2 - DIAGNOSTIC QC BOARD | {img_path.name} ({report['dimensions']}, {report['aspect_ratio']})"
        b_draw.text((16, 10), title, fill=(240, 245, 255))

        # Paste 4 panels
        board.paste(p1, (12, 34))
        board.paste(p2, (24 + p1_w, 34))
        board.paste(p3, (12, 46 + p1_h))
        board.paste(p4, (24 + p1_w, 46 + p1_h))

        # Footer Telemetry Summary
        y_foot = 56 + p1_h * 2
        line1 = (
            f"METRICS: Lum={report['mean_luminance']} | Contrast={report['rms_contrast']} | "
            f"InteriorBlown={report['interior_blown_highlights_pct']}% | InteriorCrushed={report['interior_crushed_blacks_pct']}% | "
            f"NeonClip={report['neon_gamut_clipping_pct']}% | TealOrangeIdx={report['teal_orange_index']} | "
            f"MicroTex={report['microtexture_score']} | PeakSharp={report['peak_tile_sharpness']}"
        )
        b_draw.text((16, y_foot), line1, fill=(200, 215, 230))
        if report["diagnostic_flags"]:
            flag_str = "FLAGS: " + " ; ".join(report["diagnostic_flags"])
            b_draw.text((16, y_foot + 20), flag_str[:210], fill=(255, 110, 110))
        else:
            b_draw.text((16, y_foot + 20), "STATUS: PASS_AUTOMATED_METRICS (0 optical flags; verify low-confidence anatomy/text on 100% zoom)", fill=(100, 240, 140))

        board.save(out_path, "PNG")

    report["diagnostic_board"] = str(out_path)
    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print_telemetry(report, as_json=False)
        print(f"\n  [BOARD] Saved 4-panel Composite Diagnostic Board to: {out_path}")
    return report


def tile_image(image_path: str, out_dir: str = None) -> list:
    """Splits image into 9 full-resolution 3x3 tiles + overview grid."""
    img_path = Path(image_path).resolve()
    if not img_path.exists():
        raise FileNotFoundError(f"Image not found: {img_path}")

    out_dir = Path(out_dir).resolve() if out_dir else img_path.parent / f"{img_path.stem}_qc_tiles"
    out_dir.mkdir(parents=True, exist_ok=True)

    tile_paths = []
    with Image.open(img_path) as im:
        im_rgb = im.convert("RGB")
        w, h = im_rgb.size
        tw, th = w // 3, h // 3
        overview = im_rgb.copy()
        draw = ImageDraw.Draw(overview)

        for idx in range(9):
            r, c = idx // 3, idx % 3
            box = (c * tw, r * th, (c + 1) * tw if c < 2 else w, (r + 1) * th if r < 2 else h)
            tile = im_rgb.crop(box)
            label = TILE_LABELS[idx]
            t_path = out_dir / f"tile_{idx}_{label}.png"
            tile.save(t_path, "PNG")
            tile_paths.append(str(t_path))
            draw.rectangle(box, outline=(255, 60, 60), width=max(2, w // 400))
            draw.text((box[0] + 10, box[1] + 10), f"#{idx}: {label}", fill=(255, 60, 60))

        ov_path = out_dir / "00_overview_grid.png"
        overview.save(ov_path, "PNG")
        tile_paths.insert(0, str(ov_path))

    print(f"Generated 9 full-res tiles + overview in: {out_dir}")
    return tile_paths


def mirror_flip(image_path: str, out_path: str = None) -> str:
    """Saves horizontal mirror flip."""
    img_path = Path(image_path).resolve()
    out_path = Path(out_path).resolve() if out_path else img_path.parent / f"{img_path.stem}_mirror_flip.png"
    with Image.open(img_path) as im:
        ImageOps.mirror(im.convert("RGB")).save(out_path, "PNG")
    print(f"Saved horizontal mirror flip to: {out_path}")
    return str(out_path)


def generate_inpaint_mask(image_path: str, out_path: str, tiles: str = None, box: str = None) -> str:
    """
    Generates a binary black/white PNG mask (White 255 = inpaint target, Black 0 = preserve)
    from either 3x3 tile indices (--tiles 7,8) or bounding box (--box x1,y1,x2,y2).
    """
    img_path = Path(image_path).resolve()
    with Image.open(img_path) as im:
        w, h = im.size

    if not tiles and not box:
        raise ValueError("Provide at least one of --tiles (e.g. 7,8) or --box (x1,y1,x2,y2)")

    mask = Image.new("L", (w, h), color=0)
    draw = ImageDraw.Draw(mask)

    if tiles:
        tw, th = w // 3, h // 3
        for t_str in tiles.replace(" ", ",").split(","):
            if not t_str.strip():
                continue
            idx = int(t_str.strip())
            if not (0 <= idx <= 8):
                raise ValueError(f"Tile index must be 0..8, got {idx}")
            r, c = idx // 3, idx % 3
            b = (c * tw, r * th, (c + 1) * tw if c < 2 else w, (r + 1) * th if r < 2 else h)
            draw.rectangle(b, fill=255)

    if box:
        coords = [float(v.strip()) for v in box.split(",")]
        if len(coords) != 4:
            raise ValueError("--box requires 4 values: x1,y1,x2,y2")
        # Support normalized (0.0..1.0) or pixel coordinates
        if all(0.0 <= v <= 1.0 for v in coords) and max(coords) <= 1.0:
            b = (int(coords[0] * w), int(coords[1] * h), int(coords[2] * w), int(coords[3] * h))
        else:
            b = (int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3]))
        x0, y0 = max(0, min(w, b[0])), max(0, min(h, b[1]))
        x1, y1 = max(0, min(w, b[2])), max(0, min(h, b[3]))
        if x1 <= x0 or y1 <= y0:
            raise ValueError(f"Invalid bounding box after clamping: ({x0}, {y0}, {x1}, {y1})")
        draw.rectangle((x0, y0, x1, y1), fill=255)

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
    extra_meta: dict = None
) -> dict:
    """
    Saves an image while preserving all existing EXIF and PNG tEXt/iTXt metadata chunks
    from src_path, embedding NIC_Provenance metadata into the PNG, and writing/chaining
    a sidecar <out_stem>.provenance.json audit log.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    src_sha = _file_sha256(src_path) if src_path and src_path.exists() else None

    # Read existing metadata from source image if present
    existing_info = {}
    exif_bytes = None
    if src_path and src_path.exists():
        try:
            with Image.open(src_path) as src_im:
                existing_info = dict(src_im.info or {})
                exif_bytes = existing_info.get("exif")
        except Exception:
            pass

    # Inherit existing provenance sidecar chain if available
    src_sidecar = _provenance_sidecar_path(src_path) if src_path else None
    out_sidecar = _provenance_sidecar_path(out_path)
    manifest = {
        "schema": "natural-image-craft-provenance/v2.2",
        "AI_Synthetic_Media": True,
        "generation_metadata": {},
        "history": []
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

    # Build PNG metadata container preserving prior text keys
    pnginfo = PngImagePlugin.PngInfo()
    preserved_keys = []
    for k, v in existing_info.items():
        if isinstance(k, str) and isinstance(v, str) and k not in ("NIC_Provenance",):
            pnginfo.add_text(k, v)
            preserved_keys.append(k)

    for mk, mv in manifest["generation_metadata"].items():
        if mv is not None:
            tag = f"NIC_{mk.capitalize()}"
            pnginfo.add_text(tag, str(mv))
            if tag not in preserved_keys:
                preserved_keys.append(tag)

    step_entry = {
        "timestamp_utc": now_utc,
        "operation": operation,
        "parameters": params,
        "source_file": str(src_path) if src_path else None,
        "source_sha256": src_sha,
        "output_file": str(out_path)
    }
    pnginfo.add_text("NIC_Provenance", json.dumps({
        "AI_Synthetic_Media": True,
        "last_operation": operation,
        "timestamp_utc": now_utc,
        "generation": manifest["generation_metadata"]
    }))

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
    as_json: bool = False
) -> dict:
    """
    Stamps or inspects C2PA-aligned AI provenance metadata in both PNG tEXt chunks
    and the sidecar <stem>.provenance.json manifest.
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
            extra_meta=extra
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
                "schema": "natural-image-craft-provenance/v2.2",
                "file": str(img_path),
                "sha256": _file_sha256(img_path),
                "history": []
            }
        manifest["embedded_png_text_chunks"] = embedded

    if as_json:
        print(json.dumps(manifest, indent=2))
    else:
        print(f"=== Provenance & Edit Audit Manifest ({img_path.name}) ===")
        print(f"  Latest SHA-256 : {manifest.get('latest_sha256', _file_sha256(img_path))}")
        print(f"  Generation Meta: {json.dumps(manifest.get('generation_metadata', {}))}")
        print(f"  History Steps  : {len(manifest.get('history', []))}")
    return manifest


def crop_image(image_path: str, out_path: str, box: str = None, aspect: str = None) -> str:
    """Level 1 zero-cost lossless crop/reframe by bounding box or target aspect ratio (e.g. 16:9)."""
    img_path = Path(image_path).resolve()
    with Image.open(img_path) as im:
        im_rgb = im.convert("RGB")
        w, h = im_rgb.size

        if box:
            coords = [float(v.strip()) for v in box.split(",")]
            if len(coords) != 4:
                raise ValueError("--box requires 4 values: x1,y1,x2,y2")
            if all(0.0 <= v <= 1.0 for v in coords) and max(coords) <= 1.0:
                b = (int(coords[0] * w), int(coords[1] * h), int(coords[2] * w), int(coords[3] * h))
            else:
                b = (int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3]))
            x0, y0 = max(0, min(w, b[0])), max(0, min(h, b[1]))
            x1, y1 = max(0, min(w, b[2])), max(0, min(h, b[3]))
            if x1 <= x0 or y1 <= y0:
                raise ValueError(f"Invalid crop box after clamping: ({x0}, {y0}, {x1}, {y1})")
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
        _save_with_provenance(img_path, cropped, out_p, "crop", {"box": box, "aspect": aspect, "size": f"{cropped.size[0]}x{cropped.size[1]}"})
    print(f"Saved cropped image ({cropped.size[0]}x{cropped.size[1]}) with preserved provenance to: {out_p}")
    return str(out_p)


def adjust_image(
    image_path: str,
    out_path: str,
    temp_shift: float = 0.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    gamma: float = 1.0
) -> str:
    """
    Level 1 zero-cost optical calibration:
      - temp_shift (-50..+50): shifts white balance cooler (-) or warmer (+)
      - contrast (e.g. 0.95..1.1): adjusts global contrast
      - saturation (e.g. 0.85..1.05): tames AI oversaturation
      - gamma (e.g. 0.9..1.15): lifts crushed shadows (<1.0) or deepens midtones (>1.0)
    """
    img_path = Path(image_path).resolve()
    with Image.open(img_path) as im:
        im_rgb = im.convert("RGB")
        arr = np.asarray(im_rgb, dtype=np.float32)

        if abs(temp_shift) > 0.1:
            arr[:, :, 0] = np.clip(arr[:, :, 0] + temp_shift * 0.8, 0, 255)  # Red
            arr[:, :, 2] = np.clip(arr[:, :, 2] - temp_shift * 0.8, 0, 255)  # Blue

        if abs(gamma - 1.0) > 0.01:
            arr = np.clip(255.0 * ((arr / 255.0) ** gamma), 0, 255)

        out_im = Image.fromarray(arr.astype(np.uint8), mode="RGB")
        if abs(saturation - 1.0) > 0.01:
            out_im = ImageEnhance.Color(out_im).enhance(saturation)
        if abs(contrast - 1.0) > 0.01:
            out_im = ImageEnhance.Contrast(out_im).enhance(contrast)

        out_p = Path(out_path).resolve()
        _save_with_provenance(
            img_path, out_im, out_p, "adjust",
            {"temp": temp_shift, "contrast": contrast, "saturation": saturation, "gamma": gamma}
        )

    print(f"Saved optically calibrated image with preserved provenance to: {out_p}")
    return str(out_p)


def _load_scalable_font(size: int, bold: bool = True):
    """Loads a scalable TrueType system font, falling back cleanly across OSes."""
    candidates = (
        ["segoeuib.ttf", "arialbd.ttf", "calibrib.ttf", "georgiab.ttf", "DejaVuSans-Bold.ttf"]
        if bold else
        ["segoeui.ttf", "arial.ttf", "calibri.ttf", "georgia.ttf", "DejaVuSans.ttf"]
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


def overlay_text(
    image_path: str,
    out_path: str,
    text: str,
    subtext: str = None,
    position: str = "left",
    color: str = "auto",
    font_size: int = 0
) -> str:
    """
    Level 1 zero-cost typography compositor for Tier-2 generators (Flux/SDXL) or web banners.
    Samples local background luminance in the copy-space zone to automatically choose
    high-contrast light (#F8FAFC) or dark (#1A202C) typography when --color auto.
    """
    img_path = Path(image_path).resolve()
    with Image.open(img_path) as im:
        im_rgba = im.convert("RGBA")
        w, h = im_rgba.size
        gray_arr = np.asarray(ImageOps.grayscale(im.convert("RGB")), dtype=np.float32)

        # Determine anchor box based on position
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
        else:  # default "left" (left two-thirds copy space)
            x0, x1 = pad_x, int(w * 0.52)
            y0, y1 = int(h * 0.28), int(h * 0.78)

        # Sample local luminance under text zone for auto-contrast
        zone_lum = float(np.mean(gray_arr[y0:y1, x0:x1])) if (y1 > y0 and x1 > x0) else 128.0
        col_norm = color.strip().lower()
        if col_norm in ("auto", "light", "white", "dark", "black"):
            use_light = (zone_lum < 138.0) if col_norm == "auto" else (col_norm in ("light", "white"))
            fg_col = (248, 250, 252, 255) if use_light else (24, 30, 40, 255)
            sub_col = (215, 222, 232, 235) if use_light else (55, 65, 81, 235)
            shadow_col = (0, 0, 0, 95) if use_light else (255, 255, 255, 75)
            resolved_tone = "light" if use_light else "dark"
        else:
            hx = color.strip().lstrip("#")
            if len(hx) == 3:
                hx = "".join(ch * 2 for ch in hx)
            rgb_c = tuple(int(hx[i:i+2], 16) for i in (0, 2, 4)) if len(hx) == 6 else (248, 250, 252)
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
            img_path, composited, out_p, "text-overlay",
            {"text": text, "subtext": subtext, "position": position, "color": color, "zone_lum": round(zone_lum, 1)}
        )

    print(f"Saved typography overlay (zone_lum={zone_lum:.1f}, color={resolved_tone}) with preserved provenance to: {out_p}")
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
    sheet_h = rows * (target_h + 70) + 20
    sheet = Image.new("RGB", (sheet_w, sheet_h), color=(20, 22, 28))
    draw = ImageDraw.Draw(sheet)

    for i, p in enumerate(valid_paths):
        rep = compute_optical_telemetry(str(p))
        with Image.open(p) as im:
            thumb = ImageOps.contain(im.convert("RGB"), (target_w, target_h), Image.Resampling.LANCZOS)

        r, c = i // cols, i % cols
        x = 20 + c * (target_w + 20)
        y = 20 + r * (target_h + 70)
        sheet.paste(thumb, (x + (target_w - thumb.size[0]) // 2, y + 45))

        hdr = f"Candidate #{i+1}: {p.name} ({rep['dimensions']})"
        sub = (
            f"Sharp={rep['peak_tile_sharpness']} | Blown={rep['interior_blown_highlights_pct']}% | "
            f"Neon={rep['neon_gamut_clipping_pct']}% | TealOrange={rep['teal_orange_index']} | "
            f"Flags={len(rep['diagnostic_flags'])}"
        )
        draw.text((x, y), hdr, fill=(240, 245, 255))
        flag_col = (100, 240, 140) if len(rep["diagnostic_flags"]) == 0 else (255, 130, 110)
        draw.text((x, y + 18), sub, fill=flag_col)

    out_p = Path(out_path).resolve()
    out_p.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_p, "PNG")
    print(f"Contact sheet saved to: {out_p}")
    return str(out_p)


def main():
    parser = argparse.ArgumentParser(description="Natural Image Craft v2.2 Optical QC & Provenance Toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_an = subparsers.add_parser("analyze", help="Compute optical telemetry & anomaly flags")
    p_an.add_argument("image_path", help="Path to image")
    p_an.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    p_bd = subparsers.add_parser("board", help="Generate single-image 4-panel Composite Diagnostic Board")
    p_bd.add_argument("image_path", help="Path to image")
    p_bd.add_argument("-o", "--out", default=None, help="Output path for diagnostic board PNG")
    p_bd.add_argument("--zoom-tiles", nargs="+", default=None, help="Comma- or space-separated tile indices (0..8) for 100%% zoom strips (e.g. 2,6 or 2 6)")
    p_bd.add_argument("--json", action="store_true", help="Output JSON telemetry alongside board")

    p_tile = subparsers.add_parser("tile", help="Extract all 9 full-res 3x3 tiles")
    p_tile.add_argument("image_path", help="Path to image")
    p_tile.add_argument("-o", "--out-dir", default=None, help="Output directory")

    p_flip = subparsers.add_parser("flip", help="Save horizontal mirror flip")
    p_flip.add_argument("image_path", help="Path to image")
    p_flip.add_argument("-o", "--out", default=None, help="Output path")

    p_mask = subparsers.add_parser("mask", help="Generate binary inpainting mask PNG")
    p_mask.add_argument("image_path", help="Path to source image (for dimensions)")
    p_mask.add_argument("--tiles", nargs="+", default=None, help="Comma- or space-separated tile indices (e.g. 7,8 or 7 8)")
    p_mask.add_argument("--box", default=None, help="Bounding box x1,y1,x2,y2 (normalized 0..1 or pixels)")
    p_mask.add_argument("-o", "--out", required=True, help="Output mask PNG path")

    p_crop = subparsers.add_parser("crop", help="Level 1 lossless crop/reframe (preserves metadata & provenance)")
    p_crop.add_argument("image_path", help="Path to image")
    p_crop.add_argument("--box", default=None, help="x1,y1,x2,y2 (normalized 0..1 or pixels)")
    p_crop.add_argument("--aspect", default=None, help="Target aspect ratio W:H (e.g. 16:9)")
    p_crop.add_argument("-o", "--out", required=True, help="Output image path")

    p_adj = subparsers.add_parser("adjust", help="Level 1 optical calibration (preserves metadata & provenance)")
    p_adj.add_argument("image_path", help="Path to image")
    p_adj.add_argument("--temp", type=float, default=0.0, help="Color temp shift (-50 cool .. +50 warm)")
    p_adj.add_argument("--contrast", type=float, default=1.0, help="Contrast multiplier (e.g. 0.95..1.1)")
    p_adj.add_argument("--saturation", type=float, default=1.0, help="Saturation multiplier (e.g. 0.85..1.05)")
    p_adj.add_argument("--gamma", type=float, default=1.0, help="Gamma correction (e.g. 0.9 lifts shadows)")
    p_adj.add_argument("-o", "--out", required=True, help="Output image path")

    p_txt = subparsers.add_parser("text-overlay", help="Level 1 zero-cost typography compositor with auto-contrast")
    p_txt.add_argument("image_path", help="Path to image")
    p_txt.add_argument("--text", required=True, help="Primary headline text")
    p_txt.add_argument("--subtext", default=None, help="Optional supporting subheadline text")
    p_txt.add_argument("--position", "--align", "--zone", dest="position", default="left", choices=["left", "right", "center", "top-left", "bottom-left"], help="Copy space placement")
    p_txt.add_argument("--color", default="auto", help="'auto' (luminance-adaptive) or hex color e.g. #FFFFFF")
    p_txt.add_argument("--size", type=int, default=0, help="Optional headline font size in px (0=auto-scale)")
    p_txt.add_argument("-o", "--out", required=True, help="Output image path")

    p_prov = subparsers.add_parser("provenance", help="Stamp or inspect C2PA-aligned AI provenance metadata & edit chain")
    p_prov.add_argument("image_path", help="Path to image")
    p_prov.add_argument("--model", default=None, help="Generator model name (e.g. 'Flux.1 Pro')")
    p_prov.add_argument("--seed", default=None, help="Generation seed")
    p_prov.add_argument("--prompt", default=None, help="Final generation prompt")
    p_prov.add_argument("--mode", default=None, help="Operational mode (Quick/Full/Headless)")
    p_prov.add_argument("--json", action="store_true", help="Output provenance manifest as JSON")

    p_cs = subparsers.add_parser("contact-sheet", help="Side-by-side candidate comparison sheet")
    p_cs.add_argument("images", nargs="+", help="Candidate image paths")
    p_cs.add_argument("-o", "--out", required=True, help="Output path")

    args = parser.parse_args()

    if args.command == "analyze":
        rep = compute_optical_telemetry(args.image_path)
        print_telemetry(rep, as_json=args.json)
    elif args.command == "board":
        zt = ",".join(args.zoom_tiles) if args.zoom_tiles else None
        build_diagnostic_board(args.image_path, args.out, as_json=args.json, zoom_tiles=zt)
    elif args.command == "tile":
        tile_image(args.image_path, args.out_dir)
    elif args.command == "flip":
        mirror_flip(args.image_path, args.out)
    elif args.command == "mask":
        mt = ",".join(args.tiles) if args.tiles else None
        generate_inpaint_mask(args.image_path, args.out, tiles=mt, box=args.box)
    elif args.command == "crop":
        crop_image(args.image_path, args.out, box=args.box, aspect=args.aspect)
    elif args.command == "adjust":
        adjust_image(args.image_path, args.out, temp_shift=args.temp, contrast=args.contrast, saturation=args.saturation, gamma=args.gamma)
    elif args.command == "text-overlay":
        overlay_text(args.image_path, args.out, text=args.text, subtext=args.subtext, position=args.position, color=args.color, font_size=args.size)
    elif args.command == "provenance":
        manage_provenance(args.image_path, model=args.model, seed=args.seed, prompt=args.prompt, mode=args.mode, as_json=args.json)
    elif args.command == "contact-sheet":
        make_contact_sheet(args.images, args.out)


if __name__ == "__main__":
    main()
