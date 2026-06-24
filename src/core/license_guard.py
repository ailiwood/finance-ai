"""Unified license guard — single point for checking activation status.

Import and call at every high-value execution entry point.
Modules must use this guard; do NOT duplicate verification logic.
"""

from __future__ import annotations

from src.core.license import verify_license
from src.core.device_id import get_device_code
from src.deployment.license import load_license


class ActivationStatus:
    """Cached activation check result (checked once, reused for 60s)."""
    def __init__(self):
        self._last_check = 0.0
        self._cached_valid = False
        self._cached_msg = ""

    def check(self) -> tuple[bool, str]:
        """Check if activated. Caches result for 60 seconds."""
        import time
        now = time.time()
        if now - self._last_check < 60:
            return self._cached_valid, self._cached_msg

        info = load_license()
        if not info:
            self._cached_valid = False
            self._cached_msg = "未找到许可证。请在激活页面完成激活后使用此功能。"
        else:
            key = info.get("key", "")
            if not key:
                self._cached_valid = False
                self._cached_msg = "许可证密钥为空。请重新激活。"
            else:
                result = verify_license(key, get_device_code())
                self._cached_valid = result.get("valid", False)
                self._cached_msg = result.get("reason", "未知错误") if not self._cached_valid else ""

        self._last_check = now
        return self._cached_valid, self._cached_msg

    def invalidate(self):
        self._last_check = 0.0


_guard = ActivationStatus()


def require_activation(feature_name: str = "") -> tuple[bool, str]:
    """Check activation status. Returns (is_activated, error_message).

    Usage:
        ok, err = require_activation("Kronos预测")
        if not ok:
            return err  # or raise / show to user
    """
    ok, msg = _guard.check()
    if not ok:
        label = f"「{feature_name}」" if feature_name else "此功能"
        return False, f"{label}需要有效许可证。{msg}"
    return True, ""


def is_activated() -> bool:
    """Quick boolean check."""
    ok, _ = _guard.check()
    return ok
