"""GPU detection utility for Kronos plugin.

Detects CUDA GPU availability, VRAM, and FP8 support.
Works without torch installed (returns not-available).
"""

from __future__ import annotations

from typing import NamedTuple, Optional


class GpuInfo(NamedTuple):
    """GPU capability information."""
    available: bool
    name: str
    vram_gb: float
    fp8_supported: bool
    cuda_version: str
    pytorch_version: str


def detect_gpu() -> GpuInfo:
    """Detect GPU availability and capabilities.

    Returns GpuInfo with detailed GPU specs if available.
    Gracefully returns not-available if torch not installed or no GPU found.
    """
    try:
        import torch
    except ImportError:
        return GpuInfo(
            available=False,
            name="N/A",
            vram_gb=0.0,
            fp8_supported=False,
            cuda_version="N/A",
            pytorch_version="N/A",
        )

    if not torch.cuda.is_available():
        return GpuInfo(
            available=False,
            name="N/A",
            vram_gb=0.0,
            fp8_supported=False,
            cuda_version="N/A",
            pytorch_version=torch.__version__,
        )

    device = torch.cuda.current_device()
    props = torch.cuda.get_device_properties(device)

    # VRAM in GB (total_memory for PyTorch 2.11+, total_mem for older versions)
    total_mem = getattr(props, "total_memory", getattr(props, "total_mem", 0))
    vram_gb = total_mem / (1024 ** 3)

    # FP8 support: Blackwell (SM 12.x) natively supports FP8
    # Ada Lovelace (SM 8.9) also supports FP8 via transformer engine
    fp8_supported = (props.major >= 9) or (props.major == 8 and props.minor >= 9)

    cuda_version = torch.version.cuda or "unknown"

    return GpuInfo(
        available=True,
        name=props.name,
        vram_gb=round(vram_gb, 2),
        fp8_supported=fp8_supported,
        cuda_version=cuda_version,
        pytorch_version=torch.__version__,
    )


def get_optimal_device(prefer_gpu: bool = True) -> str:
    """Get the optimal PyTorch device string.

    Args:
        prefer_gpu: If True, try to use GPU first.

    Returns:
        "cuda:0" if GPU available and preferred, otherwise "cpu".
    """
    if not prefer_gpu:
        return "cpu"

    gpu_info = detect_gpu()
    return "cuda:0" if gpu_info.available else "cpu"


def pick_device() -> str:
    """Auto-detect the best available compute device.

    Returns one of: "cuda", "mps", "cpu"
    - CUDA: NVIDIA GPU (30/40/50 series)
    - MPS: Apple Silicon (M1/M2/M3/M4)
    - CPU: Everyone else (AMD, Intel iGPU, no GPU)
    """
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def format_gpu_summary() -> str:
    """Return a human-readable GPU summary string."""
    info = detect_gpu()
    if not info.available:
        return "GPU: 不可用 (CPU only)"

    fp8_note = " (支持 FP8)" if info.fp8_supported else ""
    return (
        f"GPU: {info.name} | "
        f"VRAM: {info.vram_gb:.1f} GB | "
        f"CUDA: {info.cuda_version} | "
        f"PyTorch: {info.pytorch_version}"
        f"{fp8_note}"
    )


def gpu_enabled() -> bool:
    """Quick check: is a usable GPU available?"""
    return detect_gpu().available
