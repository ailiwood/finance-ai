"""GPU detection utility for Kronos plugin + hardware detection.

Detects NVIDIA GPU (via nvidia-smi + torch.cuda), VRAM, FP8 support.
Works with both CPU-torch and CUDA-torch builds.

Three compute modes:
- "cpu_only"      — no NVIDIA GPU (just CPU, works everywhere)
- "cpu_upgradable" — NVIDIA GPU detected but CPU-torch installed (can upgrade)
- "gpu_enabled"   — NVIDIA GPU + CUDA-torch (full acceleration)
"""

from __future__ import annotations

import subprocess
from typing import NamedTuple, Optional


class GpuInfo(NamedTuple):
    """GPU capability information."""
    available: bool
    name: str
    vram_gb: float
    fp8_supported: bool
    cuda_version: str
    pytorch_version: str


class HardwareInfo(NamedTuple):
    """Full hardware detection result — combines nvidia-smi + torch info."""
    has_nvidia: bool                          # Physical NVIDIA GPU present
    gpu_name: str                             # From nvidia-smi (best effort)
    torch_build: str                          # "cpu", "cuda", or "not_installed"
    torch_version: str                        # PyTorch version string
    cuda_version: str                         # CUDA version from torch, if any
    vram_gb: float                            # VRAM if CUDA-torch available
    fp8_supported: bool                       # FP8 if GPU available
    compute_mode: str                         # "cpu_only" | "cpu_upgradable" | "gpu_enabled"


# ── nvidia-smi probe (works even without torch/CUDA installed) ──

def _probe_nvidia_smi() -> tuple[bool, str]:
    """Probe for NVIDIA GPU via nvidia-smi CLI.

    Returns (has_nvidia, gpu_name). Works regardless of torch build.
    """
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=8,
            creationflags=0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        if r.returncode == 0 and r.stdout.strip():
            name = r.stdout.strip().splitlines()[0].strip()
            return True, name
    except FileNotFoundError:
        pass  # nvidia-smi not on PATH
    except Exception:
        pass
    return False, ""


# ── Full hardware detection ──

def detect_hardware() -> HardwareInfo:
    """Full hardware detection: nvidia-smi + torch CUDA.

    Returns HardwareInfo with complete hardware snapshot.
    Never throws — handles all missing deps gracefully.
    """
    has_nvidia, gpu_name = _probe_nvidia_smi()
    torch_build = "not_installed"
    torch_version = "N/A"
    cuda_version = "N/A"
    vram_gb = 0.0
    fp8_supported = False

    try:
        import torch
        torch_version = torch.__version__

        if torch.cuda.is_available():
            torch_build = "cuda"
            cuda_version = torch.version.cuda or "unknown"
            try:
                device = torch.cuda.current_device()
                props = torch.cuda.get_device_properties(device)
                total_mem = getattr(props, "total_memory", getattr(props, "total_mem", 0))
                vram_gb = round(total_mem / (1024 ** 3), 2)
                fp8_supported = (props.major >= 9) or (props.major == 8 and props.minor >= 9)
                if not gpu_name:
                    gpu_name = props.name
            except Exception:
                pass
        else:
            torch_build = "cpu"
    except ImportError:
        pass

    # Determine compute mode
    if torch_build == "cuda":
        compute_mode = "gpu_enabled"
    elif has_nvidia:
        compute_mode = "cpu_upgradable"
    else:
        compute_mode = "cpu_only"

    return HardwareInfo(
        has_nvidia=has_nvidia,
        gpu_name=gpu_name or "N/A",
        torch_build=torch_build,
        torch_version=torch_version,
        cuda_version=cuda_version,
        vram_gb=vram_gb,
        fp8_supported=fp8_supported,
        compute_mode=compute_mode,
    )


def get_compute_mode() -> str:
    """Quick check: return the current compute mode string."""
    return detect_hardware().compute_mode


# ── Legacy detect_gpu (still used by Kronos) ──

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
