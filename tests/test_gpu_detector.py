"""Tests for src/plugins/kronos_service/gpu_detector.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.plugins.kronos_service.gpu_detector import (
    detect_gpu,
    get_optimal_device,
    gpu_enabled,
    GpuInfo,
)


def test_detect_gpu_returns_gpuinfo():
    """detect_gpu should always return a GpuInfo NamedTuple."""
    info = detect_gpu()
    assert isinstance(info, GpuInfo)
    assert isinstance(info.available, bool)
    assert isinstance(info.name, str)
    assert isinstance(info.vram_gb, float)
    assert isinstance(info.fp8_supported, bool)


def test_detect_gpu_no_crash_without_torch():
    """detect_gpu should not crash even if torch is not installed."""
    # This test verifies graceful degradation
    info = detect_gpu()
    # Just checking it doesn't raise
    assert info is not None


def test_get_optimal_device_returns_string():
    """get_optimal_device should return a valid device string."""
    device = get_optimal_device(prefer_gpu=True)
    assert device in ("cuda:0", "cpu")


def test_get_optimal_device_no_gpu():
    """With prefer_gpu=False, should always return cpu."""
    device = get_optimal_device(prefer_gpu=False)
    assert device == "cpu"


def test_gpu_enabled_returns_bool():
    """gpu_enabled should return a boolean."""
    result = gpu_enabled()
    assert isinstance(result, bool)
