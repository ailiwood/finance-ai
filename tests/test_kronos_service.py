"""Tests for Kronos FastAPI service endpoints."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient


# Import the FastAPI app
from src.plugins.kronos_service.service import app

client = TestClient(app)


def _make_ohlcv_payload(n: int = 30) -> list[dict]:
    """Generate synthetic OHLCV data."""
    import random
    random.seed(123)
    price = 100.0
    data = []
    for i in range(n):
        change = random.uniform(-0.02, 0.02)
        close = price * (1 + change)
        high = close * (1 + random.uniform(0, 0.015))
        low = close * (1 - random.uniform(0, 0.015))
        data.append({
            "date": f"2025-06-{i+1:02d}",
            "open": round(price, 2),
            "high": round(high, 2),
            "low": round(low, 2),
            "close": round(close, 2),
            "volume": random.randint(10000, 100000),
        })
        price = close
    return data


def test_health_endpoint():
    """GET /health should return 200 with expected fields."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert "gpu_available" in data
    assert "engine_name" in data
    assert "config_enabled" in data


def test_gpu_endpoint():
    """GET /gpu should return GPU info."""
    response = client.get("/gpu")
    assert response.status_code == 200
    data = response.json()
    assert "gpu_available" in data
    assert "summary" in data


def test_predict_missing_data():
    """POST /predict with insufficient data should return 422 (pydantic validation)."""
    payload = {
        "symbol": "600519",
        "ohlcv": [{"date": "2025-06-01", "open": 100, "high": 102, "low": 99, "close": 101, "volume": 1000}],
        "horizon_days": 5,
    }
    response = client.post("/predict", json=payload)
    # Pydantic validates min_length=10 before our handler runs
    assert response.status_code == 422


def test_predict_disabled_service():
    """When service is disabled, predict returns zeroed result."""
    payload = {
        "symbol": "600519",
        "ohlcv": _make_ohlcv_payload(30),
        "horizon_days": 5,
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["symbol"] == "600519"
    assert "disclaimer" in data


def test_batch_predict_disabled():
    """Batch predict when disabled returns empty predictions."""
    payload = {
        "symbols": [
            {"symbol": "600519", "ohlcv": _make_ohlcv_payload(30), "horizon_days": 5},
        ]
    }
    response = client.post("/batch_predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "disabled"
    assert len(data["predictions"]) == 0


def test_predict_endpoint_structure():
    """Verify the predict response has all required fields."""
    payload = {
        "symbol": "000001",
        "ohlcv": _make_ohlcv_payload(30),
        "horizon_days": 10,
    }
    response = client.post("/predict", json=payload)
    data = response.json()

    expected_fields = [
        "symbol", "direction", "confidence", "target_price",
        "current_price", "lower_bound", "upper_bound",
        "horizon_days", "method", "gpu_used", "disclaimer",
    ]
    for field in expected_fields:
        assert field in data, f"Missing field: {field}"
