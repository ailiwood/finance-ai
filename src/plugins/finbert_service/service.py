"""FinBERT Sentiment Analysis FastAPI Microservice.

Endpoints:
- GET  /health            — service status + GPU info
- POST /analyze           — single text sentiment analysis
- POST /batch_analyze     — batch analysis + daily sentiment index

Start: uvicorn src.plugins.finbert_service.service:app --port 8101
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from typing import List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .config import FinBERTConfig
from .sentiment_engine import (
    get_sentiment_engine,
    get_sentiment_summary,
    RuleBasedEngine,
)

app = FastAPI(
    title="FinBERT Sentiment Analysis Service",
    description="GPU-optional financial text sentiment analysis",
    version="0.1.0",
)

config = FinBERTConfig.from_env()
engine = get_sentiment_engine(prefer_gpu=True)
summary = get_sentiment_summary()


# === Request/Response Models ===

class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000, description="Financial text to analyze")


class AnalyzeResponse(BaseModel):
    text: str
    label: str
    score: float
    confidence: float
    method: str
    gpu_used: bool
    disclaimer: str


class BatchAnalyzeRequest(BaseModel):
    texts: List[str] = Field(..., min_length=1, max_length=500, description="List of texts to analyze")


class BatchAnalyzeResponse(BaseModel):
    daily_index: float
    positive_ratio: float
    negative_ratio: float
    neutral_ratio: float
    total_texts: int
    avg_confidence: float
    sentiment_label: str
    method: str
    gpu_used: bool
    scores: List[AnalyzeResponse]
    disclaimer: str


class HealthResponse(BaseModel):
    status: str
    service: str
    engine_name: str
    gpu_available: bool
    gpu_name: str
    uses_gpu: bool
    config_enabled: bool


# === Endpoints ===

@app.get("/health", response_model=HealthResponse)
async def health():
    """Service health check."""
    return HealthResponse(
        status="ok" if config.enabled else "disabled",
        service="finbert-sentiment-analysis",
        engine_name=summary["engine_name"],
        gpu_available=summary["gpu_available"],
        gpu_name=summary["gpu_name"],
        uses_gpu=summary["uses_gpu"],
        config_enabled=config.enabled,
    )


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(request: AnalyzeRequest):
    """Analyze sentiment of a single text."""
    if not config.enabled:
        return _disabled_single(request.text)

    try:
        result = engine.analyze(request.text)
        return AnalyzeResponse(
            text=result["text"],
            label=result["label"],
            score=result["score"],
            confidence=result["confidence"],
            method=result.get("method", engine.name),
            gpu_used=summary["gpu_available"] and engine.uses_gpu,
            disclaimer="本软件仅供参考研究，不构成任何投资建议，盈亏自负。",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/batch_analyze", response_model=BatchAnalyzeResponse)
async def batch_analyze(request: BatchAnalyzeRequest):
    """Batch analyze multiple texts and return a daily sentiment index."""
    if not config.enabled:
        return _disabled_batch(request.texts)

    try:
        index = engine.batch_analyze(request.texts)
        scores = [
            AnalyzeResponse(
                text=s["text"],
                label=s["label"],
                score=s["score"],
                confidence=s["confidence"],
                method=index["method"],
                gpu_used=summary["gpu_available"] and engine.uses_gpu,
                disclaimer="本软件仅供参考研究，不构成任何投资建议，盈亏自负。",
            )
            for s in index["individual_scores"]
        ]
        return BatchAnalyzeResponse(
            daily_index=index["daily_index"],
            positive_ratio=index["positive_ratio"],
            negative_ratio=index["negative_ratio"],
            neutral_ratio=index["neutral_ratio"],
            total_texts=index["total_texts"],
            avg_confidence=index["avg_confidence"],
            sentiment_label=index["sentiment_label"],
            method=index["method"],
            gpu_used=summary["gpu_available"] and engine.uses_gpu,
            scores=scores,
            disclaimer=index["disclaimer"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _disabled_single(text: str) -> AnalyzeResponse:
    return AnalyzeResponse(
        text=text[:200],
        label="neutral",
        score=0.5,
        confidence=0.0,
        method="disabled",
        gpu_used=False,
        disclaimer="FinBERT 情绪分析服务未启用。本软件仅供参考研究，不构成任何投资建议，盈亏自负。",
    )


def _disabled_batch(texts: List[str]) -> BatchAnalyzeResponse:
    return BatchAnalyzeResponse(
        daily_index=5.0,
        positive_ratio=0.0,
        negative_ratio=0.0,
        neutral_ratio=1.0,
        total_texts=len(texts),
        avg_confidence=0.0,
        sentiment_label="中性",
        method="disabled",
        gpu_used=False,
        scores=[],
        disclaimer="FinBERT 情绪分析服务未启用。本软件仅供参考研究，不构成任何投资建议，盈亏自负。",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.host, port=config.port)
