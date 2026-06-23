"""Device identity — persistent random UUID, 100% reliable.

Does NOT depend on wmic, registry, subprocess, or admin rights.
Works on any Windows, VM, or packaged environment.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path


def get_device_code() -> str:
    """Get or create a persistent device code (16 hex chars).

    First call: generates random UUID, saves to %LOCALAPPDATA%\QuantSage\device.id
    Subsequent calls: reads from that file.
    Survives app reinstall (file is in user profile, not app dir).
    NEVER fails — always returns a non-empty string.
    """
    try:
        _id_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "QuantSage"
        _id_dir.mkdir(parents=True, exist_ok=True)
        _id_file = _id_dir / "device.id"

        # Read persisted code
        if _id_file.exists():
            _code = _id_file.read_text(encoding="utf-8").strip()
            if _code and len(_code) >= 8:
                return _code[:16].upper()

        # First run: generate and persist
        _code = uuid.uuid4().hex[:16].upper()
        _id_file.write_text(_code, encoding="utf-8")
        return _code
    except Exception:
        # Ultimate fallback — in-memory only, but NEVER returns empty
        return uuid.uuid4().hex[:16].upper()
