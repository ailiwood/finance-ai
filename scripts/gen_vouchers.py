#!/usr/bin/env python3
"""Generate batch voucher codes for QuantSage activation.

Generates N random voucher codes, outputs them in formats suitable for:
  1. Uploading to a payment platform (CSV/TXT)
  2. Inserting into Cloudflare D1 via SQL file

Usage:
  python scripts/gen_vouchers.py --count 100
  python scripts/gen_vouchers.py --count 50 --prefix QS
  python scripts/gen_vouchers.py --count 50 --output-dir ./vouchers

Outputs:
  vouchers.csv        — For uploading to payment platform (code per line)
  vouchers_sql.sql    — SQL file to insert into D1
  vouchers_all.txt    — Plain text list (one per line)

After generation:
  1. Upload vouchers.csv to your payment platform
  2. Insert into D1: wrangler d1 execute quantsage_db --file=vouchers_sql.sql --remote
"""

from __future__ import annotations

import argparse
import csv
import os
import secrets
import sys
from datetime import datetime
from pathlib import Path


def generate_voucher_code(prefix: str = "") -> str:
    """Generate a single voucher code: prefix + 24 random hex chars."""
    suffix = secrets.token_hex(12)  # 24 hex chars
    if prefix:
        return f"{prefix}-{suffix}"
    return f"QS-{suffix}"


def generate_batch(count: int, prefix: str = "") -> list[str]:
    """Generate a batch of unique voucher codes."""
    codes = []
    seen = set()
    for _ in range(count):
        code = generate_voucher_code(prefix)
        # Ensure uniqueness (extremely unlikely collision, but guard anyway)
        while code in seen:
            code = generate_voucher_code(prefix)
        seen.add(code)
        codes.append(code)
    return codes


def write_csv(codes: list[str], path: Path) -> None:
    """Write voucher codes as CSV (one column, suitable for payment platforms)."""
    path.write_text("\n".join(codes), encoding="utf-8")
    print(f"  CSV: {path} ({len(codes)} codes)")


def write_txt(codes: list[str], path: Path) -> None:
    """Write voucher codes as plain text (one per line)."""
    path.write_text("\n".join(codes), encoding="utf-8")
    print(f"  TXT: {path} ({len(codes)} codes)")


def write_sql(codes: list[str], path: Path) -> None:
    """Write SQL INSERT statements for D1."""
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"-- QuantSage Voucher Codes — Generated {timestamp}",
        f"-- Count: {len(codes)}",
        f"-- Execute: wrangler d1 execute quantsage_db --file={path.name} --remote",
        "",
    ]
    for code in codes:
        lines.append(
            f"INSERT INTO vouchers (voucher_code, status) "
            f"VALUES ('{code}', 'unused');"
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  SQL: {path} ({len(codes)} INSERT statements)")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate batch voucher codes for QuantSage activation"
    )
    parser.add_argument(
        "--count", "-n", type=int, default=100,
        help="Number of voucher codes to generate (default: 100)"
    )
    parser.add_argument(
        "--prefix", "-p", type=str, default="QS",
        help="Voucher code prefix (default: QS)"
    )
    parser.add_argument(
        "--output-dir", "-o", type=str, default=".",
        help="Output directory (default: current directory)"
    )
    parser.add_argument(
        "--no-sql", action="store_true",
        help="Skip SQL file generation"
    )
    args = parser.parse_args()

    if args.count < 1:
        print("Error: --count must be >= 1", file=sys.stderr)
        sys.exit(1)
    if args.count > 100000:
        print("Error: --count must be <= 100000", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.count} voucher codes (prefix: '{args.prefix}' → '{args.prefix}-XXXX...')...")
    codes = generate_batch(args.count, args.prefix)
    print(f"Generated {len(codes)} unique codes.\n")

    # Write output files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"vouchers_{timestamp}"

    csv_path = out_dir / f"{base_name}.csv"
    write_csv(codes, csv_path)

    txt_path = out_dir / f"{base_name}.txt"
    write_txt(codes, txt_path)

    if not args.no_sql:
        sql_path = out_dir / f"{base_name}.sql"
        write_sql(codes, sql_path)

    print(f"\nSample codes:")
    for code in codes[:5]:
        print(f"  {code}")
    if len(codes) > 5:
        print(f"  ... and {len(codes) - 5} more")

    print(f"\nNext steps:")
    print(f"  1. Upload {csv_path.name} to your payment platform")
    if not args.no_sql:
        print(f"  2. Insert into D1: cd cloudflare && npx wrangler d1 execute quantsage_db --file=../{sql_path} --remote")
    print(f"  3. Keep {txt_path.name} as your master record (store securely)")


if __name__ == "__main__":
    main()
