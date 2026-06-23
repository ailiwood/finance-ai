"""Standalone device code tool — prints 8-char fingerprint to stdout.
Bundled with installer so the Purchase page can show the real device code.
"""
import hashlib
import uuid
import sys

parts = []
# MachineGuid (Windows registry)
try:
    import winreg
    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
    guid, _ = winreg.QueryValueEx(key, "MachineGuid")
    winreg.CloseKey(key)
    parts.append(str(guid))
except Exception:
    pass
# MAC address
try:
    parts.append(f"{uuid.getnode():012x}")
except Exception:
    pass
if not parts:
    import platform
    parts.append(platform.node() or "unknown")

code = hashlib.sha256("|".join(parts).encode()).hexdigest()[:8].upper()
print(code, end="")  # No newline — installer captures this
