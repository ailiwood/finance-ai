"""One-click diagnostic export — for developer troubleshooting and customer support.

Usage:
    path = export_diagnostics()
    # Returns path to a zip file containing logs + sanitized system info.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

def _get_log_dir() -> Path:
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "QuantSage" / "logs"
    return Path.home() / ".quantsage" / "logs"


def _sanitize_sys_info() -> dict:
    """Collect system info with all secrets stripped."""
    info = {
        "export_time": datetime.now().isoformat(),
        "os": platform.platform(),
        "python": sys.version,
        "cpu_count": os.cpu_count(),
    }
    # PyTorch
    try:
        import torch
        info["torch"] = torch.__version__
        info["torch_cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            info["cuda_version"] = torch.version.cuda
            info["gpu_name"] = torch.cuda.get_device_name(0)
    except ImportError:
        info["torch"] = "not_installed"

    # Detect hardware
    try:
        from src.plugins.kronos_service.gpu_detector import detect_hardware
        hw = detect_hardware()
        info["hardware"] = {
            "compute_mode": hw.compute_mode,
            "has_nvidia": hw.has_nvidia,
            "torch_build": hw.torch_build,
        }
    except Exception:
        pass

    # Config (NO keys — only enabled/disabled and source names)
    try:
        from src.core.config_manager import load_config
        cfg = load_config()
        info["config_summary"] = {
            "deepseek_enabled": bool(cfg.get("deepseek_api_key")),
            "dashscope_enabled": bool(cfg.get("dashscope_api_key")),
            "data_source": cfg.get("default_china_data_source", "unknown"),
            "kronos_enabled": cfg.get("kronos_enabled", False),
            "finbert_enabled": cfg.get("finbert_enabled", False),
            "risk_level": cfg.get("risk_level", "moderate"),
            "analysis_depth": cfg.get("analysis_depth", 3),
        }
    except Exception:
        info["config_summary"] = {"error": "failed to load"}

    return info


def _scan_for_secrets(text: str) -> list[str]:
    """Quick scan for obvious API key patterns. Returns list of findings."""
    import re
    findings = []
    patterns = [
        r'sk-[a-zA-Z0-9]{20,}',        # OpenAI/DeepSeek style
        r'fp_[a-zA-Z0-9]{20,}',        # Custom
        r'ak-[a-zA-Z0-9]{20,}',        # AK style
        r'[a-f0-9]{32,}',              # Generic hex tokens
    ]
    for pat in patterns:
        matches = re.findall(pat, text)
        if matches:
            findings.extend(matches[:3])
    return findings


def export_diagnostics() -> str:
    """Package recent logs + sanitized system info into a zip file.

    Returns the path to the zip file. The caller (Streamlit) can offer it as a download.
    """
    log_dir = _get_log_dir()
    tmp = Path(tempfile.gettempdir()) / "quantsage_diag"
    tmp.mkdir(exist_ok=True)

    # Collect log files (last 7 days)
    zip_path = str(Path.home() / "Desktop" / f"quantsage_diag_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip")

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add log files
        for f in sorted(log_dir.glob("quantsage_*.log*"), key=lambda p: p.stat().st_mtime, reverse=True)[:14]:
            content = f.read_text(encoding="utf-8", errors="replace")
            # Scan for secrets
            secrets = _scan_for_secrets(content)
            if secrets:
                # Mask them
                for s in secrets:
                    content = content.replace(s, f"<REDACTED:{s[:4]}***>")
            zf.writestr(f"logs/{f.name}", content)

        # Add sanitized system info
        sys_info = _sanitize_sys_info()
        zf.writestr("system_info.json", json.dumps(sys_info, indent=2, ensure_ascii=False))

    return zip_path
