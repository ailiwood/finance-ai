"""FinBERT service configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class FinBERTConfig:
    """FinBERT plugin configuration."""

    enabled: bool = False
    model: str = "ProsusAI/finbert"
    gpu_device: str = "auto"
    host: str = "0.0.0.0"
    port: int = 8101
    max_text_length: int = 512
    batch_size: int = 32

    @classmethod
    def from_env(cls) -> "FinBERTConfig":
        """Load from environment variables."""
        import os
        return cls(
            enabled=_parse(os.getenv("FINBERT_ENABLED", "false")),
            model=os.getenv("FINBERT_MODEL", "ProsusAI/finbert"),
            gpu_device=os.getenv("FINBERT_GPU_DEVICE", "auto"),
            host=os.getenv("FINBERT_HOST", "0.0.0.0"),
            port=int(os.getenv("FINBERT_PORT", "8101")),
            max_text_length=int(os.getenv("FINBERT_MAX_LENGTH", "512")),
            batch_size=int(os.getenv("FINBERT_BATCH_SIZE", "32")),
        )

    @classmethod
    def from_quantage_config(cls, config: dict) -> "FinBERTConfig":
        """Load from QuantSage config dict."""
        return cls(
            enabled=config.get("finbert_enabled", False),
            gpu_device=config.get("finbert_gpu_device", "auto"),
            model=config.get("finbert_model", "ProsusAI/finbert"),
        )


def _parse(val: str) -> bool:
    return val.lower() in ("true", "1", "yes", "on")
