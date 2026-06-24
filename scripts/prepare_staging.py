#!/usr/bin/env python3
"""Prepare staging directory for PyInstaller build with obfuscated core modules.

Usage:
  python scripts/prepare_staging.py              # Full staging (obfuscated + original)
  python scripts/prepare_staging.py --clean-only # Just remove staging dir
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STAGING_DIR = PROJECT_ROOT / "dist" / "staging"
OBFUSCATED_DIR = PROJECT_ROOT / "dist" / "obfuscated"

# Critical modules that are obfuscated
OBFUSCATED_FILES = {
    "src/core/license.py": "src/core/license.py",
    "src/core/device_id.py": "src/core/device_id.py",
    "src/ui/activation_gate.py": "src/ui/activation_gate.py",
    "src/deployment/license.py": "src/deployment/license.py",
}


def clean_staging() -> None:
    """Remove staging directory."""
    if STAGING_DIR.exists():
        shutil.rmtree(STAGING_DIR)
        print(f"Cleaned: {STAGING_DIR}")


def ensure_dir(path: Path) -> None:
    """Create directory if needed and ensure __init__.py exists."""
    path.mkdir(parents=True, exist_ok=True)
    init = path / "__init__.py"
    if not init.exists():
        init.write_text("")


def copy_original_src() -> None:
    """Copy all original src/ files to staging (excluding obfuscated ones)."""
    src_dir = PROJECT_ROOT / "src"
    staging_src = STAGING_DIR / "src"

    for item in src_dir.rglob("*"):
        if item.is_dir():
            continue
        rel = item.relative_to(src_dir)
        dest = staging_src / rel

        # Skip obfuscated files (will be overwritten later)
        obf_key = str(Path("src") / rel)
        if obf_key in OBFUSCATED_FILES:
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, dest)

    # Ensure all __init__.py files exist (create empty ones for empty dirs)
    for item in src_dir.rglob("__init__.py"):
        rel = item.relative_to(src_dir)
        dest = staging_src / rel
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)

    print(f"Copied original src/ (excluding obfuscated) → {staging_src}")


def copy_obfuscated() -> None:
    """Copy obfuscated files into staging, overwriting originals."""
    for rel_src, rel_dest in OBFUSCATED_FILES.items():
        obf_file = OBFUSCATED_DIR / rel_src
        dest_file = STAGING_DIR / rel_dest

        if not obf_file.exists():
            print(f"  [WARNING] Obfuscated file not found: {obf_file}")
            continue

        dest_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(obf_file, dest_file)
        orig_size = (PROJECT_ROOT / rel_src).stat().st_size if (PROJECT_ROOT / rel_src).exists() else 0
        obf_size = obf_file.stat().st_size
        print(f"  Obfuscated: {rel_dest} ({orig_size} → {obf_size} bytes)")


def copy_pyarmor_runtime() -> None:
    """Copy pyarmor_runtime to staging root."""
    runtime_dir = OBFUSCATED_DIR / "pyarmor_runtime_000000"
    if not runtime_dir.exists():
        print("  [WARNING] pyarmor_runtime not found!")
        return
    dest = STAGING_DIR / "pyarmor_runtime_000000"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(runtime_dir, dest)
    print(f"  Copied pyarmor_runtime → {dest}")


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Prepare staging for PyInstaller build")
    parser.add_argument("--clean-only", action="store_true", help="Only clean staging dir")
    args = parser.parse_args()

    if args.clean_only:
        clean_staging()
        return

    print("=" * 60)
    print("QuantSage Staging Preparation")
    print("=" * 60)

    clean_staging()
    STAGING_DIR.mkdir(parents=True, exist_ok=True)
    ensure_dir(STAGING_DIR)

    print("\n1. Copying original src/...")
    copy_original_src()

    print("\n2. Overlaying obfuscated modules...")
    copy_obfuscated()

    print("\n3. Copying pyarmor_runtime...")
    copy_pyarmor_runtime()

    print(f"\nStaging ready at: {STAGING_DIR}")
    print(f"Next: pyinstaller pyinstaller_quantsage.spec --noconfirm")


if __name__ == "__main__":
    main()
