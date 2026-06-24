"""PyArmor obfuscation script for QuantSage core modules.

Usage:
  python scripts/obfuscate.py            # Obfuscate all protected modules
  python scripts/obfuscate.py --dry-run  # Show what would be obfuscated

Protected modules (contain valuable logic):
  - src/core/license.py          License verification (public key + Ed25519 verify)
  - src/core/device_id.py        Device identity generation
  - src/ui/activation_gate.py    Activation gate UI
  - src/data/market_data.py      Data bridge (multi-source market data)
  - src/analysis/indicators.py   Technical indicator calculation
  - src/plugins/kronos_service/  Kronos K-line prediction (MIT code)
  - src/core/config_manager.py   Configuration management
  - src/deployment/license.py    License persistence

Output: dist/obfuscated/ (replaces src/ in the PyInstaller build)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "dist" / "obfuscated"

# Modules worth protecting (contain proprietary/valuable logic)
PROTECTED_MODULES = [
    "src/core/license.py",
    "src/core/device_id.py",
    "src/ui/activation_gate.py",
    "src/data/market_data.py",
    "src/analysis/indicators.py",
    "src/core/config_manager.py",
    "src/deployment/license.py",
]


def run_pyarmor(target_files: list[str], output_dir: Path) -> bool:
    """Run pyarmor gen on the target files."""
    cmd = [
        "pyarmor", "gen",
        "--output", str(output_dir),
        "--recursive",
        *target_files,
    ]
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    if result.returncode != 0:
        print(f"PyArmor failed:\n{result.stderr}")
        return False
    print(result.stdout)
    return True


def verify_obfuscated(output_dir: Path) -> bool:
    """Quick verification that obfuscated files exist."""
    for mod in PROTECTED_MODULES:
        obf_path = output_dir / mod
        if not obf_path.exists():
            print(f"  [MISSING] {mod}")
            return False
        orig_size = (PROJECT_ROOT / mod).stat().st_size
        obf_size = obf_path.stat().st_size
        print(f"  [OK] {mod}: {orig_size} → {obf_size} bytes (obfuscated)")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Obfuscate QuantSage core modules with PyArmor")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be obfuscated")
    parser.add_argument("--output", type=str, default=str(OUTPUT_DIR), help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output)

    print("=" * 60)
    print("QuantSage PyArmor Obfuscation")
    print("=" * 60)
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Output: {output_dir}")
    print(f"Modules to protect: {len(PROTECTED_MODULES)}")
    for mod in PROTECTED_MODULES:
        print(f"  - {mod}")

    if args.dry_run:
        print("\n[Dry run — no changes made]")
        return

    # Clean output
    if output_dir.exists():
        shutil.rmtree(output_dir)

    # Obfuscate
    print(f"\nObfuscating...")
    target_dirs = list({str(Path(m).parent) for m in PROTECTED_MODULES})
    if not run_pyarmor(target_dirs, output_dir):
        print("\nObfuscation failed!")
        sys.exit(1)

    # Verify
    print(f"\nVerification:")
    if not verify_obfuscated(output_dir):
        print("\nVerification failed — some modules not obfuscated!")
        sys.exit(1)

    print(f"\nObfuscation complete!")
    print(f"Obfuscated code at: {output_dir}")
    print(f"\nNext: build with PyInstaller using the obfuscated source")


if __name__ == "__main__":
    main()
