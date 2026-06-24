#!/usr/bin/env python3
"""Issue permanent QuantSage license codes via cloud API.

Calls POST /admin/issue-permanent on the activation Worker.
Requires ADMIN_SECRET (set as environment variable or passed via --secret).

Usage:
  # Set env var first: export QUANTSAGE_ADMIN_SECRET="..."
  python scripts/issue_permanent.py --device DEV001DEV001DEV0 --note "ops-alice"

  # Batch: issue 8 device-bound + 2 MASTER permanent codes
  python scripts/issue_permanent.py --batch

  # Custom API URL (default: production workers.dev)
  python scripts/issue_permanent.py --device DEV001DEV001DEV0 --api-url https://custom.example.com
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

DEFAULT_API_URL = "https://quantsage-activation.lk166564317.workers.dev"


def get_admin_secret(args_secret: str | None = None) -> str:
    """Get admin secret from args, env var, or prompt."""
    if args_secret:
        return args_secret

    env_val = os.environ.get("QUANTSAGE_ADMIN_SECRET", "")
    if env_val:
        return env_val

    # Try reading from a local file (not in git)
    secret_file = Path.home() / ".quantsage" / "admin_secret.txt"
    if secret_file.exists():
        return secret_file.read_text(encoding="utf-8").strip()

    print("Admin secret not found. Set one of:", file=sys.stderr)
    print("  1. export QUANTSAGE_ADMIN_SECRET='...'", file=sys.stderr)
    print(f"  2. Save to {secret_file}", file=sys.stderr)
    print("  3. Pass --secret '...'", file=sys.stderr)
    sys.exit(1)


def issue_permanent(
    device_code: str,
    note: str,
    api_url: str,
    admin_secret: str,
) -> dict[str, Any]:
    """Issue a single permanent license via the cloud API."""
    try:
        resp = requests.post(
            f"{api_url}/admin/issue-permanent",
            headers={
                "X-Admin-Secret": admin_secret,
                "Content-Type": "application/json",
            },
            json={
                "device_code": device_code,
                "note": note,
            },
            timeout=30,
        )
        data = resp.json()
        data["_status_code"] = resp.status_code
        return data
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": str(e), "_status_code": 0}


def issue_batch(api_url: str, admin_secret: str) -> None:
    """Issue the standard batch: 8 device-bound + 2 MASTER keys."""
    print("=" * 70)
    print("QuantSage Permanent License Batch Issuance")
    print(f"API: {api_url}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    results: list[dict[str, Any]] = []

    # ── 8 device-bound permanent codes ──
    print("\n── 8 Device-Bound Permanent Codes ──\n")
    device_bound = [
        ("DEV001", "ops-alice"),
        ("DEV002", "ops-bob"),
        ("DEV003", "ops-charlie"),
        ("DEV004", "ops-diana"),
        ("DEV005", "ops-eve"),
        ("DEV006", "ops-frank"),
        ("DEV007", "ops-grace"),
        ("DEV008", "ops-henry"),
    ]

    for dev, note in device_bound:
        print(f"\n> Issuing for {note} (device: {dev})...")
        print(f"  NOTE: Replace '{dev}' with the ACTUAL device code from the user's QuantSage client!")
        print(f"  Skipping automatic issuance for placeholder device codes.")
        print(f"  To issue: python scripts/issue_permanent.py --device <REAL_DEVICE_CODE> --note '{note}'")
        results.append({
            "device_code": dev,
            "note": note,
            "skipped": True,
            "reason": "placeholder_device_code",
        })

    # ── 2 MASTER universal codes ──
    print("\n── 2 MASTER Universal Codes ──\n")
    for i in range(1, 3):
        note = f"master-key-{i:02d}"
        print(f"Issuing MASTER key #{i}...")
        result = issue_permanent("MASTER", note, api_url, admin_secret)

        status = result.get("_status_code", 0)
        if result.get("success"):
            print(f"  [OK] License: {result['license_key']}")
            results.append(result)
        else:
            print(f"  [FAIL] Status {status}: {result.get('error', 'unknown')}")
            results.append({"device_code": "MASTER", "note": note, "success": False, "error": result.get("error")})

    # ── Summary ──
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    success_count = sum(1 for r in results if r.get("success"))
    skip_count = sum(1 for r in results if r.get("skipped"))
    fail_count = sum(1 for r in results if not r.get("success") and not r.get("skipped"))
    print(f"  Total: {len(results)}")
    print(f"  Success: {success_count}")
    print(f"  Skipped (placeholder device codes): {skip_count}")
    print(f"  Failed: {fail_count}")

    if success_count > 0:
        print(f"\n  Successful licenses:")
        for r in results:
            if r.get("success"):
                is_master = r.get("is_master", False)
                tag = "[MASTER - UNIVERSAL]" if is_master else "[Device-bound]"
                print(f"    {tag} {r.get('note', '')}: {r.get('license_key', '')}")

    if skip_count > 0:
        print(f"\n  Skipped (need real device codes):")
        for r in results:
            if r.get("skipped"):
                print(f"    {r.get('note', '')}: python scripts/issue_permanent.py --device <REAL_DEVICE_CODE> --note '{r.get('note', '')}'")

    # Save results
    out_file = Path(f"permanent_licenses_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nResults saved to: {out_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Issue permanent QuantSage license codes via cloud API"
    )
    parser.add_argument(
        "--device", "-d", type=str,
        help="Device code (16 hex chars) or 'MASTER' for universal key"
    )
    parser.add_argument(
        "--note", "-n", type=str, default="",
        help="Note/description for this license (e.g., who it's for)"
    )
    parser.add_argument(
        "--secret", "-s", type=str, default=None,
        help="Admin secret (or set QUANTSAGE_ADMIN_SECRET env var)"
    )
    parser.add_argument(
        "--api-url", type=str, default=DEFAULT_API_URL,
        help=f"API base URL (default: {DEFAULT_API_URL})"
    )
    parser.add_argument(
        "--batch", "-b", action="store_true",
        help="Issue standard batch: 8 device-bound + 2 MASTER codes"
    )
    args = parser.parse_args()

    admin_secret = get_admin_secret(args.secret)

    if args.batch:
        issue_batch(args.api_url, admin_secret)
        return

    if not args.device:
        parser.error("Either --device or --batch is required")

    # Single issuance
    print(f"Issuing permanent license for device: {args.device}")
    result = issue_permanent(args.device, args.note, args.api_url, admin_secret)

    status = result.pop("_status_code", 0)
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if result.get("success"):
        print(f"\nLicense key:")
        print(f"  {result['license_key']}")
        if result.get("is_master"):
            print(f"\n  [WARNING] This is a MASTER universal key — valid on ANY device!")
            print(f"  Store it securely and only share with core team members.")
    else:
        print(f"\nFailed (HTTP {status}): {result.get('error', 'unknown')}")
        sys.exit(1)


if __name__ == "__main__":
    main()
