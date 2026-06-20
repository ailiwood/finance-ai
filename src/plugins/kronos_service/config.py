"""Kronos service configuration.

Reads plugin settings from environment variables and QuantSage config.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KronosConfig:
    """Kronos plugin configuration."""

    enabled: bool = False
    gpu_device: str = "auto"       # "auto", "cuda:0", "cpu"
    model: str = "kronos_mini"     # model variant
    host: str = "0.0.0.0"
    port: int = 8100
    max_horizon_days: int = 30
    min_ohlcv_rows: int = 20

    @classmethod
    def from_env(cls) -> "KronosConfig":
        """Load configuration from environment variables."""
        import os

        return cls(
            enabled=_parse_bool(os.getenv("KRONOS_ENABLED", "false")),
            gpu_device=os.getenv("KRONOS_GPU_DEVICE", "auto"),
            model=os.getenv("KRONOS_MODEL", "kronos_mini"),
            host=os.getenv("KRONOS_HOST", "0.0.0.0"),
            port=int(os.getenv("KRONOS_PORT", "8100")),
            max_horizon_days=int(os.getenv("KRONOS_MAX_HORIZON", "30")),
            min_ohlcv_rows=int(os.getenv("KRONOS_MIN_ROWS", "20")),
        )

    @classmethod
    def from_quantage_config(cls, config: dict) -> "KronosConfig":
        """Load from QuantSage config dict."""
        return cls(
            enabled=config.get("kronos_enabled", False),
            gpu_device=config.get("kronos_gpu_device", "auto"),
            model=config.get("kronos_model", "kronos_mini"),
        )


def _parse_bool(val: str) -> bool:
    """Parse boolean from string."""
    return val.lower() in ("true", "1", "yes", "on")
