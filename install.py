#!/usr/bin/env python3
"""
Optic (Natural Image Craft v2.2) — Cross-Agent Installer & Sync Utility
=======================================================================
Installs or updates the `optic` skill package across modern AI coding agents:
  - Google Antigravity (`~/.gemini/config/skills/optic` or workspace `.agents/skills/optic`)
  - OpenAI Codex / Freebuff AI / Windsurf (workspace `.agents/skills/optic` & global `~/.agents/skills/optic`)
  - Cursor (workspace `.cursor/skills/optic` + `.cursor/rules/optic.mdc`)
  - Claude Code (`~/.claude/skills/optic` or workspace `.claude/skills/optic`)

Usage:
  python install.py --target all-local          # Install into current workspace (.agents/skills/optic + .cursor/)
  python install.py --target freebuff-global    # Install into ~/.agents/skills/optic (enables /skill:optic)
  python install.py --target codex-global       # Install into ~/.codex/skills/optic & ~/.agents/skills/optic
  python install.py --target antigravity-global # Install into ~/.gemini/config/skills/optic
  python install.py --target claude-global      # Install into ~/.claude/skills/optic (enables /optic)
  python install.py --target cursor             # Install into .cursor/skills/optic and .cursor/rules/optic.mdc (@optic)
  python install.py --target all-global         # Install globally across Antigravity, Freebuff, Codex & Claude
  python install.py --check                     # Verify installation and Python dependencies (Pillow, NumPy)
"""

import argparse
from pathlib import Path
import shutil
import sys

SKILL_NAME = "optic"
LEGACY_NAME = "natural-image-craft"
REPO_ROOT = Path(__file__).resolve().parent
CORE_ITEMS = [
    "SKILL.md",
    "plugin.json",
    "README.md",
    "requirements.txt",
    "scripts",
    "references",
    "assets",
]


def check_dependencies() -> bool:
  missing = []
  for mod in ("PIL", "numpy"):
    try:
      __import__(mod)
    except ImportError:
      missing.append(mod)
  if missing:
    print(f"[!] Missing required Python packages: {', '.join(missing)}")
    print("    Install with: pip install -r requirements.txt  (or pip install Pillow numpy)")
    return False
  print("[OK] Python dependencies verified (Pillow, numpy).")
  return True


def sync_skill_tree(
    dest: Path, include_tests: bool = False, clean_legacy: bool = False
):
  dest = dest.resolve()
  legacy_dir = dest.parent / LEGACY_NAME
  if legacy_dir.exists() and legacy_dir != dest:
    if clean_legacy:
      shutil.rmtree(legacy_dir, ignore_errors=True)
      print(f"[OK] Removed legacy sibling directory: {legacy_dir}")
    else:
      print(
          f"[!] Note: Legacy directory `{legacy_dir}` exists alongside `{dest}`. "
          f"Pass --clean-legacy to remove it and prevent duplicate skill loading."
      )

  dest.mkdir(parents=True, exist_ok=True)
  items = list(CORE_ITEMS)
  if include_tests:
    if (REPO_ROOT / "tests").exists():
      items.append("tests")
    else:
      print(
          f"[!] Warning: --include-tests requested, but `{REPO_ROOT / 'tests'}` was not found."
      )

  for name in items:
    src = REPO_ROOT / name
    dst = dest / name
    if not src.exists():
      continue
    if src.is_dir():
      if dst.exists():
        shutil.rmtree(dst)
      shutil.copytree(
          src,
          dst,
          ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*_qc_tiles"),
      )
    else:
      shutil.copy2(src, dst)
  print(f"[OK] Installed `{SKILL_NAME}` (v2.2) to: {dest}")


def write_cursor_mdc(
    workspace_dir: Path, skill_dest: Path, clean_legacy: bool = False
):
  rules_dir = workspace_dir / ".cursor" / "rules"
  rules_dir.mkdir(parents=True, exist_ok=True)
  legacy_mdc = rules_dir / f"{LEGACY_NAME}.mdc"
  if legacy_mdc.exists():
    if clean_legacy:
      legacy_mdc.unlink()
      print(f"[OK] Removed legacy Cursor rule: {legacy_mdc}")
    else:
      print(
          f"[!] Note: Legacy Cursor rule `{legacy_mdc}` exists. Pass --clean-legacy to remove it."
      )

  mdc_path = rules_dir / f"{SKILL_NAME}.mdc"
  skill_md_text = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
  parts = skill_md_text.split("---", 2)
  body = parts[2] if len(parts) >= 3 else skill_md_text
  mdc_content = (
      "---\n"
      "description: Use when generating, prompting, editing, or quality-checking photorealistic or authentically crafted visuals (portraits, lifestyle, products, architecture, culinary, editorial). Do NOT use for diagrams, charts, UI wireframes, or flat logos.\n"
      "globs: \n"
      "alwaysApply: false\n"
      "---\n\n"
      f"> **Skill Directory (`<SKILL_DIR>`):** `{skill_dest.as_posix()}`\n"
      f"{body}"
  )
  mdc_path.write_text(mdc_content, encoding="utf-8")
  print(f"[OK] Wrote Cursor rule wrapper (`@{SKILL_NAME}`) to: {mdc_path}")


def main():
  parser = argparse.ArgumentParser(
      description="Install `optic` (Natural Image Craft v2.2) across AI coding agents"
  )
  parser.add_argument(
      "--target",
      choices=[
          "workspace",
          "cursor",
          "all-local",
          "antigravity-global",
          "codex-global",
          "freebuff-global",
          "claude-global",
          "all-global",
      ],
      default="all-local",
      help="Target agent environment",
  )
  parser.add_argument(
      "--workspace-dir",
      default=".",
      help="Workspace root directory for local targets (default: current directory '.')",
  )
  parser.add_argument(
      "--include-tests",
      action="store_true",
      help="Copy empirical benchmark test suite into skill folder",
  )
  parser.add_argument(
      "--clean-legacy",
      action="store_true",
      help="Remove legacy `natural-image-craft` sibling directory/rule if present",
  )
  parser.add_argument(
      "--check", action="store_true", help="Verify dependencies only"
  )
  args = parser.parse_args()

  if not check_dependencies():
    sys.exit(1)
  if args.check:
    return

  ws = Path(args.workspace_dir).resolve()
  home = Path.home()

  if args.target in ("workspace", "all-local"):
    sync_skill_tree(
        ws / ".agents" / "skills" / SKILL_NAME,
        include_tests=args.include_tests,
        clean_legacy=args.clean_legacy,
    )
  if args.target in ("cursor", "all-local"):
    cursor_skill_dir = ws / ".cursor" / "skills" / SKILL_NAME
    sync_skill_tree(
        cursor_skill_dir,
        include_tests=args.include_tests,
        clean_legacy=args.clean_legacy,
    )
    write_cursor_mdc(ws, cursor_skill_dir, clean_legacy=args.clean_legacy)
  if args.target in ("antigravity-global", "all-global"):
    sync_skill_tree(
        home / ".gemini" / "config" / "skills" / SKILL_NAME,
        include_tests=args.include_tests,
        clean_legacy=args.clean_legacy,
    )
  if args.target in ("codex-global", "all-global"):
    sync_skill_tree(
        home / ".codex" / "skills" / SKILL_NAME,
        include_tests=args.include_tests,
        clean_legacy=args.clean_legacy,
    )
    sync_skill_tree(
        home / ".agents" / "skills" / SKILL_NAME,
        include_tests=args.include_tests,
        clean_legacy=args.clean_legacy,
    )
  if args.target in ("freebuff-global", "all-global"):
    sync_skill_tree(
        home / ".agents" / "skills" / SKILL_NAME,
        include_tests=args.include_tests,
        clean_legacy=args.clean_legacy,
    )
  if args.target in ("claude-global", "all-global"):
    sync_skill_tree(
        home / ".claude" / "skills" / SKILL_NAME,
        include_tests=args.include_tests,
        clean_legacy=args.clean_legacy,
    )


if __name__ == "__main__":
  main()
