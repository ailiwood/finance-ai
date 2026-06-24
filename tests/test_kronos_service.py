"""Tests for Kronos model engine (direct API — no FastAPI)."""

import sys
import random
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from src.plugins.kronos_service.model_engine import (
    StatsEngine, KronosEngine, get_engine, reset_engine,
    BaseEngine, PredictionResult,
)
from src.plugins.kronos_service.gpu_detector import detect_gpu


def _make_ohlcv(n: int = 30, base_price: float = 100.0) -> list[dict]:
    """Generate synthetic OHLCV data."""
    random.seed(123)
    price = base_price
    data = []
    for i in range(n):
        change = random.uniform(-0.02, 0.02)
        close = round(price * (1 + change), 2)
        high = round(close * (1 + random.uniform(0, 0.015)), 2)
        low = round(close * (1 - random.uniform(0, 0.015)), 2)
        open_p = round(low + random.uniform(0, high - low), 2)
        data.append({
            "date": f"2025-06-{i+1:02d}",
            "open": open_p, "high": high, "low": low,
            "close": close, "volume": random.randint(10000, 100000),
        })
        price = close
    return data


# === StatsEngine Tests ===

class TestStatsEngine:
    def test_name(self):
        engine = StatsEngine()
        assert engine.name == "stats_baseline"
        assert engine.uses_gpu is False

    def test_predict_basic(self):
        engine = StatsEngine()
        ohlcv = _make_ohlcv(30)
        result = engine.predict(ohlcv, horizon_days=5)
        assert result["direction"] in ("up", "down", "neutral")
        assert 0.0 <= result["confidence"] <= 1.0
        assert result["target_price"] > 0
        assert result["current_price"] > 0
        assert "disclaimer" in result

    def test_predict_insufficient_data(self):
        engine = StatsEngine()
        with pytest.raises(ValueError):
            engine.predict(_make_ohlcv(5), horizon_days=5)

    def test_predict_result_structure(self):
        engine = StatsEngine()
        result = engine.predict(_make_ohlcv(30), horizon_days=10)
        for field in ("direction", "confidence", "target_price", "current_price",
                       "lower_bound", "upper_bound", "horizon_days", "method", "disclaimer"):
            assert field in result, f"Missing: {field}"


# === Engine Factory Tests ===

class TestEngineFactory:
    def test_get_engine_returns_engine(self):
        reset_engine()
        engine = get_engine()
        assert engine is not None
        assert isinstance(engine, BaseEngine)

    def test_get_engine_is_singleton(self):
        reset_engine()
        e1 = get_engine()
        e2 = get_engine()
        assert e1 is e2

    def test_kronos_engine_predict(self):
        reset_engine()
        engine = get_engine()
        ohlcv = _make_ohlcv(120)
        result = engine.predict(ohlcv, horizon_days=10)
        assert result["direction"] in ("up", "down", "neutral")
        assert "method" in result
        assert "disclaimer" in result


# === GPU Detector Tests ===

class TestGpuDetector:
    def test_detect_gpu_returns_result(self):
        info = detect_gpu()
        assert info is not None
        assert hasattr(info, "available")
        assert hasattr(info, "name")

    def test_detect_gpu_fields(self):
        info = detect_gpu()
        for field in ("available", "name", "vram_gb", "fp8_supported"):
            assert hasattr(info, field), f"Missing: {field}"
