"""Tests for src/plugins/kronos_service/model_engine.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.plugins.kronos_service.model_engine import (
    StatsEngine,
    KronosEngine,
    get_engine,
    get_engine_summary,
    PredictionResult,
    OhlcvRow,
)


def _make_ohlcv(n: int = 30, base_price: float = 100.0) -> list[OhlcvRow]:
    """Generate synthetic OHLCV data for testing."""
    import random
    random.seed(42)
    data = []
    price = base_price
    for i in range(n):
        change = random.uniform(-0.03, 0.03)
        close = price * (1 + change)
        high = close * (1 + random.uniform(0, 0.02))
        low = close * (1 - random.uniform(0, 0.02))
        open_price = price
        data.append(OhlcvRow(
            date=f"2025-{((i // 30) + 1):02d}-{(i % 28 + 1):02d}",
            open=round(open_price, 2),
            high=round(high, 2),
            low=round(low, 2),
            close=round(close, 2),
            volume=random.randint(10000, 100000),
        ))
        price = close
    return data


def test_stats_engine_name():
    """StatsEngine should have a name."""
    engine = StatsEngine()
    assert engine.name == "stats_baseline"


def test_stats_engine_uses_gpu():
    """StatsEngine should not use GPU."""
    engine = StatsEngine()
    assert engine.uses_gpu is False


def test_stats_engine_predict_returns_valid_result():
    """StatsEngine.predict should return a valid PredictionResult."""
    engine = StatsEngine()
    ohlcv = _make_ohlcv(30)
    result = engine.predict(ohlcv, horizon_days=5)

    assert isinstance(result, dict)
    assert result["direction"] in ("up", "down", "neutral")
    assert 0.0 <= result["confidence"] <= 1.0
    assert result["target_price"] > 0
    assert result["current_price"] > 0
    assert result["lower_bound"] <= result["target_price"] <= result["upper_bound"]
    assert result["horizon_days"] == 5
    assert "disclaimer" in result
    assert "仅供参考" in result["disclaimer"]


def test_stats_engine_needs_min_data():
    """StatsEngine should raise ValueError with insufficient data."""
    engine = StatsEngine()
    ohlcv = _make_ohlcv(5)
    try:
        engine.predict(ohlcv)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_stats_engine_horizon_affects_bounds():
    """Longer horizon should produce wider uncertainty bounds."""
    engine = StatsEngine()
    ohlcv = _make_ohlcv(60)

    r1 = engine.predict(ohlcv, horizon_days=5)
    r2 = engine.predict(ohlcv, horizon_days=20)

    spread5 = r1["upper_bound"] - r1["lower_bound"]
    spread20 = r2["upper_bound"] - r2["lower_bound"]

    assert spread20 >= spread5 * 0.9  # longer horizon should generally widen


def test_get_engine_returns_base_engine():
    """get_engine should always return a working engine."""
    engine = get_engine(prefer_gpu=True)
    assert engine is not None
    # Try a prediction to verify
    ohlcv = _make_ohlcv(30)
    result = engine.predict(ohlcv, horizon_days=5)
    assert result["direction"] in ("up", "down", "neutral")


def test_get_engine_summary():
    """get_engine_summary should return a dict with expected keys."""
    summary = get_engine_summary()
    assert "engine_name" in summary
    assert "gpu_available" in summary
    assert "uses_gpu" in summary


def test_kronos_engine_fallback():
    """KronosEngine should fallback to stats when model not loaded."""
    engine = KronosEngine(device="cpu")
    assert not engine.is_loaded  # Kronos model not yet available
    ohlcv = _make_ohlcv(30)
    result = engine.predict(ohlcv, horizon_days=5)
    # Should still produce valid results via fallback
    assert result["direction"] in ("up", "down", "neutral")
