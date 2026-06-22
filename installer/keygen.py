"""QuantSage License Key Generator — simple, reliable, offline.

Usage: python keygen.py [count] [start_index]
Key format: QS-XXXX-YYYY-ZZZZ-WWWW

Validation (in both Python and Inno Setup Pascal):
  Checksum = ((XXXX_val XOR 0xA3C5) + (YYYY_val XOR 0x7E29) + 0x5E9D) % 65536
  Then ZZZZ must equal Checksum (as 4 hex chars), WWWW = inverse of Checksum
  Verification: ZZZZ == Checksum AND WWWW == (0xFFFF - Checksum)

This uses only 16-bit integer math — safe for both Python and Pascal.
"""

import sys


def make_key(seed: int) -> str:
    """Generate one valid license key from a seed."""
    # Derive P1, P2 from seed with simple mixing
    p1 = ((seed * 17137 + 14943) ^ 0xA3C5) & 0xFFFF
    p2 = ((seed * 31397 + 31805) ^ 0x7E29) & 0xFFFF

    # Checksum: simple 16-bit add
    cs = (p1 + p2 + 0x5E9D) % 65536
    cs_inv = (0xFFFF - cs) & 0xFFFF

    return f"QS-{p1:04X}-{p2:04X}-{cs:04X}-{cs_inv:04X}"


def validate_key(key: str) -> bool:
    """Verify a license key (same algorithm as Inno Setup Pascal)."""
    key = key.strip().upper().replace(" ", "").replace("-", "")
    if len(key) != 18 or not key.startswith("QS"):
        return False
    try:
        p1 = int(key[2:6], 16)
        p2 = int(key[6:10], 16)
        cs = int(key[10:14], 16)
        cs_inv = int(key[14:18], 16)

        expected_cs = (p1 + p2 + 0x5E9D) % 65536
        expected_inv = (0xFFFF - expected_cs) & 0xFFFF

        return cs == expected_cs and cs_inv == expected_inv
    except ValueError:
        return False


if __name__ == "__main__":
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    start = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    print(f"QuantSage License Key Generator")
    print(f"Generating {count} key(s) (index {start}-{start+count-1}):\n")
    for i in range(count):
        key = make_key(start + i)
        ok = validate_key(key)
        print(f"  {key}  {'[OK]' if ok else '[FAIL]'}")
    print(f"\nGive one key per paying user (19.90 RMB).")
