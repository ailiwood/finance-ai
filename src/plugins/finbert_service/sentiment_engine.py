"""Financial sentiment analysis engine.

Primary: ProsusAI/finbert (Apache 2.0) via HuggingFace transformers.
Fallback: Rule-based keyword matching (always available, zero dependencies).
"""

from __future__ import annotations

import re
import math
from abc import ABC, abstractmethod
from typing import TypedDict, List, Dict, Optional, Any
import warnings


class SentimentScore(TypedDict):
    """Single text sentiment result."""
    text: str
    label: str           # "positive", "negative", "neutral"
    score: float         # 0.0 (most negative) to 1.0 (most positive)
    confidence: float    # model confidence 0.0-1.0


class SentimentIndex(TypedDict):
    """Aggregated sentiment index for a batch of texts."""
    daily_index: float           # 0-10 scale (5 = neutral)
    positive_ratio: float        # 0.0-1.0
    negative_ratio: float        # 0.0-1.0
    neutral_ratio: float         # 0.0-1.0
    total_texts: int
    avg_confidence: float
    sentiment_label: str         # "乐观", "中性", "悲观"
    individual_scores: List[SentimentScore]
    method: str
    disclaimer: str


# === Abstract Base ===

class BaseSentimentEngine(ABC):
    """Abstract sentiment analysis engine."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def uses_gpu(self) -> bool: ...

    @abstractmethod
    def analyze(self, text: str) -> SentimentScore: ...

    def batch_analyze(self, texts: List[str]) -> SentimentIndex:
        """Analyze multiple texts and produce a daily sentiment index."""
        scores = [self.analyze(t) for t in texts]

        if not scores:
            return _empty_index(texts, self.name)

        positive = sum(1 for s in scores if s["label"] == "positive")
        negative = sum(1 for s in scores if s["label"] == "negative")
        n = len(scores)

        # Sentiment index on 0-10 scale
        # positive=1, negative=-1, neutral=0 per item → map to 0-10
        raw = sum(
            1 if s["label"] == "positive" else (-1 if s["label"] == "negative" else 0)
            for s in scores
        ) / n  # -1 to 1
        daily_index = round(5.0 + raw * 5.0, 2)  # map to 0-10

        avg_confidence = round(sum(s["confidence"] for s in scores) / n, 3)

        idx = raw
        if idx > 0.15:
            sentiment_label = "乐观"
        elif idx < -0.15:
            sentiment_label = "悲观"
        else:
            sentiment_label = "中性"

        return SentimentIndex(
            daily_index=daily_index,
            positive_ratio=round(positive / n, 3),
            negative_ratio=round(negative / n, 3),
            neutral_ratio=round(1 - (positive + negative) / n, 3),
            total_texts=n,
            avg_confidence=avg_confidence,
            sentiment_label=sentiment_label,
            individual_scores=scores,
            method=self.name,
            disclaimer="本软件仅供参考研究，不构成任何投资建议，盈亏自负。",
        )


# === Rule-based Fallback Engine ===

# Financial sentiment keywords (Chinese)
_POSITIVE_WORDS = [
    "增长", "盈利", "上涨", "突破", "利好", "反弹", "复苏",
    "创新高", "超预期", "分红", "回购", "扩张", "升级",
    "买入", "增持", "跑赢", "景气", "产能释放", "订单增长",
    "毛利率提升", "净利增长", "营收增长", "市场份额提升",
    "bullish", "upgrade", "beat", "outperform", "growth",
]

_NEGATIVE_WORDS = [
    "下跌", "亏损", "衰退", "风险", "利空", "暴跌", "下滑",
    "创新低", "低于预期", "减持", "收缩", "裁员", "违约",
    "卖出", "减仓", "跑输", "低迷", "产能过剩", "订单下滑",
    "毛利率下降", "净利下滑", "营收下降", "市场份额下降",
    "bearish", "downgrade", "miss", "underperform", "decline",
]

# Weak modifiers that reduce confidence
_WEAK_MODIFIERS = ["可能", "或许", "预计", "预期", "有望", "或将", "估计"]


class RuleBasedEngine(BaseSentimentEngine):
    """Keyword-based sentiment analysis engine.

    Always available. No GPU or external dependencies required.
    Good baseline and fallback when FinBERT model is unavailable.
    """

    def __init__(self) -> None:
        self._name = "rule_based"

    @property
    def name(self) -> str:
        return self._name

    @property
    def uses_gpu(self) -> bool:
        return False

    def analyze(self, text: str) -> SentimentScore:
        if not text or not text.strip():
            return SentimentScore(
                text=text, label="neutral", score=0.5, confidence=0.0
            )

        text_lower = text.lower()

        pos_count = sum(1 for w in _POSITIVE_WORDS if w.lower() in text_lower)
        neg_count = sum(1 for w in _NEGATIVE_WORDS if w.lower() in text_lower)

        # Detect weak modifiers
        has_weak = any(w in text for w in _WEAK_MODIFIERS)

        if pos_count > neg_count:
            label = "positive"
            raw_score = min(1.0, 0.5 + 0.1 * (pos_count - neg_count))
            confidence = min(0.8, 0.4 + 0.1 * pos_count)
        elif neg_count > pos_count:
            label = "negative"
            raw_score = max(0.0, 0.5 - 0.1 * (neg_count - pos_count))
            confidence = min(0.8, 0.4 + 0.1 * neg_count)
        else:
            label = "neutral"
            raw_score = 0.5
            confidence = 0.3

        if has_weak:
            confidence *= 0.7

        # Map 0-1 score to 0-1 (where 1 = very positive, 0 = very negative)
        score = round(0.5 + (raw_score - 0.5) * (pos_count + neg_count) * 0.3, 3)
        score = max(0.0, min(1.0, score))

        return SentimentScore(
            text=text[:200],
            label=label,
            score=round(score, 3),
            confidence=round(min(confidence, 0.95), 3),
        )


# === FinBERT Engine (GPU, optional) ===

_HAS_FINBERT = False
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    _HAS_FINBERT = True
except ImportError:
    pass


class FinBERTEngine(BaseSentimentEngine):
    """FinBERT-based sentiment engine.

    Uses ProsusAI/finbert from HuggingFace (Apache 2.0).
    GPU-accelerated via PyTorch when available.
    Falls back to RuleBasedEngine on load failure.
    """

    _MODEL_ID = "ProsusAI/finbert"
    _LABEL_MAP = {0: "negative", 1: "neutral", 2: "positive"}

    def __init__(self, device: str = "cpu") -> None:
        self._device = device
        self._loaded = False
        self._name = "finbert"
        self._model: Any = None
        self._tokenizer: Any = None

        if not _HAS_FINBERT:
            return

        try:
            self._load_model()
        except Exception as e:
            warnings.warn(f"FinBERT model loading failed: {e}. Using rule-based fallback.")

    def _load_model(self) -> None:
        """Load FinBERT model from HuggingFace."""
        self._tokenizer = AutoTokenizer.from_pretrained(self._MODEL_ID)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self._MODEL_ID,
        )
        if self._device != "cpu":
            try:
                self._model = self._model.to(self._device)
            except Exception:
                pass  # stay on CPU
        self._loaded = True

    @property
    def name(self) -> str:
        return self._name if self._loaded else "finbert_unavailable"

    @property
    def uses_gpu(self) -> bool:
        return self._loaded and self._device.startswith("cuda")

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    def analyze(self, text: str) -> SentimentScore:
        """Analyze sentiment using FinBERT."""
        import torch

        if not self._loaded or self._tokenizer is None or self._model is None:
            fallback = RuleBasedEngine()
            result = fallback.analyze(text)
            result["method"] = "finbert_fallback_rule"
            return result  # type: ignore[typeddict-item]

        if not text or not text.strip():
            return SentimentScore(text=text, label="neutral", score=0.5, confidence=0.0)

        truncated = text[:self._tokenizer.model_max_length] if self._tokenizer.model_max_length < 10000 else text[:512]

        inputs = self._tokenizer(
            truncated,
            return_tensors="pt",
            truncation=True,
            max_length=512,
        )
        if self._device != "cpu":
            inputs = {k: v.to(self._device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self._model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)[0]

        label_id = int(torch.argmax(probs).item())
        label = self._LABEL_MAP.get(label_id, "neutral")
        confidence = round(float(probs[label_id].item()), 3)

        # Map to 0-1 score: negative→0.0, neutral→0.5, positive→1.0
        if label == "positive":
            score = 0.5 + 0.5 * confidence
        elif label == "negative":
            score = 0.5 - 0.5 * confidence
        else:
            score = 0.5

        return SentimentScore(
            text=text[:200],
            label=label,
            score=round(score, 3),
            confidence=confidence,
        )


# === Engine Factory ===

def get_sentiment_engine(prefer_gpu: bool = True) -> BaseSentimentEngine:
    """Return the best available sentiment engine."""
    try:
        from src.plugins.kronos_service.gpu_detector import detect_gpu
        gpu_info = detect_gpu()
        device = "cuda:0" if (prefer_gpu and gpu_info.available) else "cpu"
    except ImportError:
        device = "cpu"

    engine = FinBERTEngine(device=device)
    if engine.is_loaded:
        return engine
    return RuleBasedEngine()


def get_sentiment_summary() -> Dict[str, Any]:
    """Return engine status for health checks."""
    try:
        from src.plugins.kronos_service.gpu_detector import detect_gpu
        gpu = detect_gpu()
    except ImportError:
        gpu = None

    engine = get_sentiment_engine(prefer_gpu=True)
    return {
        "engine_name": engine.name,
        "gpu_available": gpu.available if gpu else False,
        "gpu_name": gpu.name if gpu and gpu.available else "N/A",
        "uses_gpu": engine.uses_gpu,
    }


def _empty_index(texts: List[str], method: str) -> SentimentIndex:
    return SentimentIndex(
        daily_index=5.0,
        positive_ratio=0.0,
        negative_ratio=0.0,
        neutral_ratio=1.0,
        total_texts=0,
        avg_confidence=0.0,
        sentiment_label="中性",
        individual_scores=[],
        method=method,
        disclaimer="本软件仅供参考研究，不构成任何投资建议，盈亏自负。",
    )
