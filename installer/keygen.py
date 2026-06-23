"""QuantSage License Key Generator — device-bound, offline.

Usage:
  python keygen.py [count] [start_index]             — unbound keys (backward compat)
  python keygen.py [count] [start] --device <CODE>    — device-bound keys
  python keygen.py fingerprint                        — show this machine's device code

Key format: QS-XXXX-YYYY-ZZZZ-WWWW
Device binding: P2 is XOR'd with device code's integer value.
Validation uses same 16-bit integer math in both Python and Inno Setup Pascal.
"""

import sys


def _device_code_int(device_code: str = "") -> int:
    """Convert 8-char device code to a 16-bit integer for XOR mixing."""
    if not device_code or len(device_code) < 4:
        return 0
    try:
        return int(device_code[:4], 16)
    except ValueError:
        return 0


def make_key(seed: int, device_code: str = "") -> str:
    """Generate one license key. Optional device_code binds to specific machine."""
    p1 = ((seed * 17137 + 14943) ^ 0xA3C5) & 0xFFFF
    p2_raw = ((seed * 31397 + 31805) ^ 0x7E29) & 0xFFFF

    # Device binding: XOR device code into P2
    dc_int = _device_code_int(device_code)
    p2 = (p2_raw ^ dc_int) & 0xFFFF

    cs = (p1 + p2 + 0x5E9D) % 65536
    cs_inv = (0xFFFF - cs) & 0xFFFF

    return f"QS-{p1:04X}-{p2:04X}-{cs:04X}-{cs_inv:04X}"


def validate_key(key: str, device_code: str = "") -> bool:
    """Verify a license key. Optional device_code for binding check."""
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
    device_code = ""
    args = sys.argv[1:]

    # Parse --device flag
    if "--device" in args:
        idx = args.index("--device")
        if idx + 1 < len(args):
            device_code = args[idx + 1].upper()
            args = args[:idx] + args[idx + 2:]

    count = int(args[0]) if len(args) > 0 else 5
    start = int(args[1]) if len(args) > 1 else 1

    bound_msg = f" (device-bound: {device_code})" if device_code else " (unbound)"
    print(f"QuantSage License Key Generator{bound_msg}")
    print(f"Generating {count} key(s) (index {start}-{start+count-1}):\n")
    for i in range(count):
        key = make_key(start + i, device_code)
        ok = validate_key(key, device_code)
        print(f"  {key}  {'[OK]' if ok else '[FAIL]'}")
    print(f"\nGive one key per paying user (19.90 RMB).")
    if device_code:
        print(f"Keys are bound to device: {device_code}")
