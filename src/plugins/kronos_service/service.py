"""Kronos K-line Prediction FastAPI Microservice.

Endpoints:
- GET  /health         — service status + GPU info
- POST /predict        — single-stock OHLCV prediction
- POST /batch_predict  — multi-stock batch prediction

Start: uvicorn src.plugins.kronos_service.service:app --port 8100
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root on sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import KronosConfig
from .gpu_detector import detect_gpu, format_gpu_summary
from .model_engine import get_engine, get_engine_summary, OhlcvRow

# === FastAPI App ===

app = FastAPI(
    title="Kronos K-line Prediction Service",
    description="GPU-optional OHLCV candlestick price forecasting microservice",
    version="0.1.0",
)

# Load config at startup
config = KronosConfig.from_env()
engine = get_engine(prefer_gpu=True)
engine_summary = get_engine_summary()


# === Request/Response Models ===

class OhlcvPoint(BaseModel):
    """Single OHLCV data point."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int = 0


class PredictRequest(BaseModel):
    """Prediction request."""
    symbol: str = Field(..., description="Stock symbol (e.g., 600519)")
    ohlcv: List[OhlcvPoint] = Field(..., min_length=10, description="OHLCV data points, most recent last")
    horizon_days: int = Field(5, ge=1, le=30, description="Forecast horizon in days")


class BatchPredictRequest(BaseModel):
    """Batch prediction request."""
    symbols: List[PredictRequest]


class PredictResponse(BaseModel):
    """Prediction response."""
    symbol: str
    direction: str
    confidence: float
    target_price: float
    current_price: float
    lower_bound: float
    upper_bound: float
    horizon_days: int
    method: str
    gpu_used: bool
    disclaimer: str


class HealthResponse(BaseModel):
    """Service health status."""
    status: str
    service: str
    version: str
    gpu_available: bool
    gpu_name: str
    gpu_vram_gb: float
    fp8_supported: bool
    engine_name: str
    uses_gpu: bool
    config_enabled: bool


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: str


# === Endpoints ===

@app.get("/health", response_model=HealthResponse)
async def health():
    """Service health check with GPU and engine status."""
    gpu_info = detect_gpu()
    return HealthResponse(
        status="ok" if config.enabled else "disabled",
        service="kronos-kline-prediction",
        version="0.1.0",
        gpu_available=gpu_info.available,
        gpu_name=gpu_info.name,
        gpu_vram_gb=gpu_info.vram_gb,
        fp8_supported=gpu_info.fp8_supported,
        engine_name=engine_summary["engine_name"],
        uses_gpu=engine_summary["uses_gpu"],
        config_enabled=config.enabled,
    )


@app.post("/predict", response_model=PredictResponse)
async def predict(request: PredictRequest):
    """Generate K-line price prediction for a single stock.

    Returns direction, confidence, target price, and uncertainty bounds.
    """
    if not config.enabled:
        return _disabled_response(request.symbol, request.horizon_days)

    if len(request.ohlcv) < config.min_ohlcv_rows:
        raise HTTPException(
            status_code=400,
            detail=f"Need at least {config.min_ohlcv_rows} OHLCV data points, got {len(request.ohlcv)}",
        )

    if request.horizon_days > config.max_horizon_days:
        raise HTTPException(
            status_code=400,
            detail=f"Horizon days cannot exceed {config.max_horizon_days}",
        )

    try:
        ohlcv_rows: List[OhlcvRow] = [
            {
                "date": p.date,
                "open": p.open,
                "high": p.high,
                "low": p.low,
                "close": p.close,
                "volume": p.volume,
            }
            for p in request.ohlcv
        ]

        result = engine.predict(ohlcv_rows, request.horizon_days)
        gpu_info = detect_gpu()

        return PredictResponse(
            symbol=request.symbol,
            direction=result["direction"],
            confidence=result["confidence"],
            target_price=result["target_price"],
            current_price=result["current_price"],
            lower_bound=result["lower_bound"],
            upper_bound=result["upper_bound"],
            horizon_days=result["horizon_days"],
            method=result["method"],
            gpu_used=gpu_info.available,
            disclaimer=result["disclaimer"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@app.post("/batch_predict")
async def batch_predict(request: BatchPredictRequest):
    """Batch prediction for multiple stocks.

    Returns list of predictions, one per symbol.
    """
    if not config.enabled:
        return {
            "status": "disabled",
            "reason": "Kronos service is not enabled. Set KRONOS_ENABLED=true.",
            "predictions": [],
        }

    results = []
    errors = []
    for req in request.symbols:
        try:
            # Reuse single predict logic
            inner_request = PredictRequest(
                symbol=req.symbol,
                ohlcv=req.ohlcv,
                horizon_days=req.horizon_days,
            )
            result = await predict(inner_request)
            results.append(result.dict())
        except HTTPException as e:
            errors.append({"symbol": req.symbol, "error": e.detail})
        except Exception as e:
            errors.append({"symbol": req.symbol, "error": str(e)})

    return {
        "count": len(results),
        "predictions": results,
        "errors": errors,
    }


@app.get("/gpu")
async def gpu_status():
    """Detailed GPU status endpoint."""
    gpu_info = detect_gpu()
    return {
        "gpu_available": gpu_info.available,
        "gpu_name": gpu_info.name,
        "vram_gb": gpu_info.vram_gb,
        "fp8_supported": gpu_info.fp8_supported,
        "cuda_version": gpu_info.cuda_version,
        "pytorch_version": gpu_info.pytorch_version,
        "summary": format_gpu_summary(),
    }


# === Helpers ===

def _disabled_response(symbol: str, horizon_days: int) -> PredictResponse:
    """Return a disabled-service response."""
    return PredictResponse(
        symbol=symbol,
        direction="neutral",
        confidence=0.0,
        target_price=0.0,
        current_price=0.0,
        lower_bound=0.0,
        upper_bound=0.0,
        horizon_days=horizon_days,
        method="disabled",
        gpu_used=False,
        disclaimer="Kronos 预测服务未启用。本软件仅供参考研究，不构成任何投资建议，盈亏自负。",
    )


# === Main (for direct execution) ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.host, port=config.port)
