"""Tests for FinBERT sentiment analysis service."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient


# Import service
from src.plugins.finbert_service.service import app
from src.plugins.finbert_service.sentiment_engine import (
    RuleBasedEngine, FinBERTEngine, get_sentiment_engine,
    SentimentScore, SentimentIndex,
)

client = TestClient(app)


# === RuleBasedEngine Tests ===

def test_rule_based_engine_name():
    engine = RuleBasedEngine()
    assert engine.name == "rule_based"
    assert engine.uses_gpu is False


def test_rule_based_analyze_empty_text():
    engine = RuleBasedEngine()
    result = engine.analyze("")
    assert result["label"] == "neutral"
    assert result["confidence"] == 0.0


def test_rule_based_analyze_positive():
    engine = RuleBasedEngine()
    result = engine.analyze("公司业绩大幅增长，盈利超预期，市场份额提升")
    assert result["label"] == "positive"
    assert result["score"] > 0.5


def test_rule_based_analyze_negative():
    engine = RuleBasedEngine()
    result = engine.analyze("公司业绩大幅下滑，亏损严重，裁员收缩，风险加剧")
    assert result["label"] == "negative"
    assert result["score"] < 0.5


def test_rule_based_analyze_neutral():
    engine = RuleBasedEngine()
    result = engine.analyze("公司召开了年度会议")
    assert result["label"] == "neutral"


def test_rule_based_batch_analyze():
    engine = RuleBasedEngine()
    texts = [
        "业绩大幅增长，盈利超预期",
        "业绩大幅增长，盈利超预期",
        "业绩大幅下滑，亏损严重",
        "普通公告，无特别内容",
    ]
    index = engine.batch_analyze(texts)
    assert index["total_texts"] == 4
    assert 0.0 <= index["daily_index"] <= 10.0
    assert "positive_ratio" in index
    assert "sentiment_label" in index
    assert len(index["individual_scores"]) == 4


def test_rule_based_dict_keys():
    engine = RuleBasedEngine()
    result = engine.analyze("增长")
    for key in ("text", "label", "score", "confidence"):
        assert key in result


# === Engine factory ===

def test_get_engine_returns_engine():
    engine = get_sentiment_engine(prefer_gpu=True)
    assert engine is not None
    assert engine.name in ("rule_based", "finbert", "finbert_unavailable")


def test_finbert_engine_fallback():
    engine = FinBERTEngine(device="cpu")
    if not engine.is_loaded:
        # Should still produce valid results via fallback
        result = engine.analyze("增长")
        assert result["label"] in ("positive", "negative", "neutral")


# === FastAPI endpoints ===

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "service" in data
    assert "engine_name" in data


def test_analyze_endpoint_disabled():
    response = client.post("/analyze", json={"text": "公司业绩增长"})
    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "disabled"


def test_analyze_structure():
    response = client.post("/analyze", json={"text": "业绩增长，盈利超预期"})
    data = response.json()
    for field in ("text", "label", "score", "confidence", "method", "disclaimer"):
        assert field in data, f"Missing: {field}"


def test_batch_analyze_disabled():
    texts = ["业绩增长", "亏损下滑", "中性消息"]
    response = client.post("/batch_analyze", json={"texts": texts})
    assert response.status_code == 200
    data = response.json()
    assert data["method"] == "disabled"
    assert data["total_texts"] == 3


def test_analyze_empty_text_validation():
    response = client.post("/analyze", json={"text": ""})
    assert response.status_code == 422  # Pydantic min_length=1


def test_batch_analyze_structure():
    texts = ["消息A", "消息B", "消息C"]
    response = client.post("/batch_analyze", json={"texts": texts})
    data = response.json()
    for field in ("daily_index", "positive_ratio", "negative_ratio", "sentiment_label", "total_texts"):
        assert field in data, f"Missing: {field}"
    assert 0.0 <= data["daily_index"] <= 10.0
