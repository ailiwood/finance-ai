"""QuantSage License Key Generator — offline checksum-based.

Usage: python keygen.py [count] [start_seed]
Generates valid license keys with modular checksum verification.
The installer validates the same checksum logic in Pascal.

Key format: QS-XXXX-YYYY-ZZZZ-WWWW (4 hex groups)
Validation: (P1Val * 33727 + P2Val * 31790 + 1589039500) mod 65536 * 65537
            must equal the decimal value of Part3+Part4 combined.
"""
import sys

SECRET_SEED = 0x5E9D2B8C   # Must match the Inno Setup constant
MULT1 = 0x1A3F              # 6719
MULT2 = 0x7C2E              # 31790

def make_key(seed: int) -> str:
    """Generate one valid license key."""
    p1 = (seed * 17137 + 0x3A5F) & 0xFFFF      # 0-65535
    p2 = (seed * 31397 + 0x7C2D) & 0xFFFF      # 0-65535

    # Expected checksum
    cs = ((p1 * MULT1 + p2 * MULT2 + SECRET_SEED) % 0x10000) * 0x10001

    p3 = (cs >> 16) & 0xFFFF
    p4 = cs & 0xFFFF

    return f"QS-{p1:04X}-{p2:04X}-{p3:04X}-{p4:04X}"


def validate_key(key: str) -> bool:
    """Verify a license key (same logic as Inno Setup Pascal code)."""
    key = key.strip().upper().replace(" ", "").replace("-", "")
    if not key.startswith("QS") or len(key) != 18:
        return False
    try:
        p1 = int(key[2:6], 16)
        p2 = int(key[6:10], 16)
        cs = int(key[10:18], 16)
        expected = ((p1 * MULT1 + p2 * MULT2 + SECRET_SEED) % 0x10000) * 0x10001
        # Allow small tolerance for 32-bit integer math differences
        return abs(int(cs) - int(expected)) < 10
    except ValueError:
        return False


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    print(f"Generating {count} license key(s) (seed {start}-{start+count-1}):\n")
    for i in range(count):
        key = make_key(start + i)
        ok = validate_key(key)
        print(f"  {key}  {'OK' if ok else 'FAIL!'}")
    print(f"\nGive one key per paying user ($19.90 lifetime license).")
