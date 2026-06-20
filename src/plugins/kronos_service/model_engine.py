"""Prediction engine abstraction for K-line forecasting.

Provides:
- BaseEngine: abstract interface
- StatsEngine: lightweight statistical baseline (always available)
- get_engine: factory that selects best available engine
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from typing import TypedDict, List, Optional, Dict, Any
import warnings


class OhlcvRow(TypedDict):
    """Single OHLCV data point."""
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class PredictionResult(TypedDict):
    """Standardized prediction output."""
    direction: str          # "up", "down", "neutral"
    confidence: float       # 0.0 - 1.0
    target_price: float     # predicted price at horizon
    current_price: float    # last known close price
    lower_bound: float      # uncertainty lower bound
    upper_bound: float      # uncertainty upper bound
    horizon_days: int       # forecast horizon in days
    method: str             # engine name
    disclaimer: str         # mandatory disclaimer


# === Abstract Base ===

class BaseEngine(ABC):
    """Abstract prediction engine interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable engine name."""
        ...

    @property
    @abstractmethod
    def uses_gpu(self) -> bool:
        """Whether this engine uses GPU acceleration."""
        ...

    @abstractmethod
    def predict(
        self,
        ohlcv: List[OhlcvRow],
        horizon_days: int = 5,
    ) -> PredictionResult:
        """Generate a price prediction.

        Args:
            ohlcv: List of OHLCV data points, most recent last. Minimum 20 rows.
            horizon_days: Number of days to forecast ahead (1-30).

        Returns:
            PredictionResult with direction, confidence, target price, bounds.
        """
        ...


# === Statistical Baseline Engine ===

class StatsEngine(BaseEngine):
    """Lightweight statistical engine using rolling statistics.

    Uses:
    - EMA crossover for direction
    - Historical volatility for confidence bounds
    - Zero external dependencies beyond stdlib

    Always available. No GPU required.
    """

    def __init__(self) -> None:
        self._name = "stats_baseline"

    @property
    def name(self) -> str:
        return self._name

    @property
    def uses_gpu(self) -> bool:
        return False

    def predict(
        self,
        ohlcv: List[OhlcvRow],
        horizon_days: int = 5,
    ) -> PredictionResult:
        """Generate prediction using statistical methods."""
        if len(ohlcv) < 10:
            raise ValueError("Need at least 10 OHLCV data points")

        closes = [row["close"] for row in ohlcv]
        highs = [row["high"] for row in ohlcv]
        lows = [row["low"] for row in ohlcv]
        current_price = closes[-1]

        # 1. Direction: short EMA vs long EMA crossover
        short_ema = _calc_ema(closes, span=5)
        long_ema = _calc_ema(closes, span=20)

        if short_ema > long_ema * 1.01:
            direction = "up"
            base_confidence = 0.55
        elif short_ema < long_ema * 0.99:
            direction = "down"
            base_confidence = 0.55
        else:
            direction = "neutral"
            base_confidence = 0.50

        # 2. Volatility: average true range normalized
        atr_pct = _calc_atr_pct(highs, lows, closes)
        daily_vol = atr_pct * current_price  # absolute daily volatility

        # 3. Price target: extrapolate recent momentum with mean reversion
        returns = [_log_return(closes[i-1], closes[i]) for i in range(1, len(closes))]
        recent_momentum = sum(returns[-5:])  # last 5 days return
        # Mean reversion: pull toward long-term mean
        long_term_mean = sum(closes) / len(closes)
        mean_reversion_strength = 0.3  # weight for mean reversion

        # Predicted return over horizon
        momentum_contribution = recent_momentum * (horizon_days / 5)
        mean_rev_contribution = (
            (long_term_mean - current_price) / current_price
        ) * mean_reversion_strength * (horizon_days / 20)

        predicted_return = momentum_contribution + mean_rev_contribution

        # Clamp to reasonable range (-30% to +30%)
        predicted_return = max(-0.30, min(0.30, predicted_return))
        target_price = current_price * (1 + predicted_return)

        # 4. Confidence bounds using volatility
        # 68% confidence if 1 std, 95% if 2 std
        horizon_vol = daily_vol * math.sqrt(horizon_days)
        lower_bound = target_price - 1.64 * horizon_vol  # 90% CI lower
        upper_bound = target_price + 1.64 * horizon_vol  # 90% CI upper

        # Ensure bounds don't go negative
        lower_bound = max(lower_bound, target_price * 0.7)
        upper_bound = min(upper_bound, target_price * 1.3)

        # 5. Confidence score
        trend_strength = abs(short_ema - long_ema) / long_ema
        confidence = min(0.85, base_confidence + trend_strength * 5)
        confidence = round(confidence, 2)

        return PredictionResult(
            direction=direction,
            confidence=confidence,
            target_price=round(target_price, 2),
            current_price=current_price,
            lower_bound=round(lower_bound, 2),
            upper_bound=round(upper_bound, 2),
            horizon_days=horizon_days,
            method=self.name,
            disclaimer="本软件仅供参考研究，不构成任何投资建议，盈亏自负。",
        )


# === Statistical helpers ===

def _calc_ema(values: List[float], span: int) -> float:
    """Calculate Exponential Moving Average."""
    if len(values) < span:
        return sum(values) / len(values)
    alpha = 2.0 / (span + 1.0)
    ema = sum(values[:span]) / span
    for v in values[span:]:
        ema = alpha * v + (1 - alpha) * ema
    return ema


def _calc_atr_pct(highs: List[float], lows: List[float], closes: List[float]) -> float:
    """Calculate Average True Range as percentage of price."""
    tr_values = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1]),
        )
        tr_pct = tr / closes[i-1] if closes[i-1] > 0 else 0
        tr_values.append(tr_pct)
    if not tr_values:
        return 0.02  # default 2%
    return sum(tr_values[-14:]) / min(14, len(tr_values))  # 14-period ATR


def _log_return(p0: float, p1: float) -> float:
    """Calculate log return."""
    if p0 <= 0:
        return 0.0
    return math.log(p1 / p0)


# === Kronos Engine (GPU, optional) ===

# Try importing Kronos dependencies at module level
_HAS_KRONOS = False
_KronosModel = None
_KronosTokenizer = None

try:
    from transformers import AutoModel, AutoTokenizer
    _HAS_KRONOS = True
except ImportError:
    pass


class KronosEngine(BaseEngine):
    """Kronos-based prediction engine.

    Uses the Kronos K-line foundation model (MIT) for OHLCV-native forecasting.
    Loads from HuggingFace: NeoQuasar/Kronos-mini

    Falls back to StatsEngine if model loading fails.
    """

    _MODEL_ID = "NeoQuasar/Kronos-mini"

    def __init__(self, device: str = "cpu") -> None:
        self._device = device
        self._loaded = False
        self._name = "kronos_mini"
        self._model = None
        self._tokenizer = None

        if not _HAS_KRONOS:
            return

        try:
            self._load_model()
        except Exception as e:
            warnings.warn(f"Kronos model loading failed: {e}. Using stats fallback.")

    def _load_model(self) -> None:
        """Load Kronos model from HuggingFace."""
        # This is a forward-compatible loader.
        # When the Kronos model is available on HF, this will load it.
        # For now, the StatsEngine provides the actual predictions.
        #
        # Future: self._model = AutoModel.from_pretrained(self._MODEL_ID)
        #         self._tokenizer = AutoTokenizer.from_pretrained(self._MODEL_ID)
        #
        # For now, mark as not loaded so get_engine falls back to StatsEngine.
        self._loaded = False

    @property
    def name(self) -> str:
        return self._name if self._loaded else "kronos_unavailable"

    @property
    def uses_gpu(self) -> bool:
        return self._loaded and self._device.startswith("cuda")

    @property
    def is_loaded(self) -> bool:
        """Whether the Kronos model is successfully loaded."""
        return self._loaded

    def predict(
        self,
        ohlcv: List[OhlcvRow],
        horizon_days: int = 5,
    ) -> PredictionResult:
        """Generate prediction using Kronos model.

        Falls back to statistical baseline since Kronos model
        is not yet loaded from HuggingFace (awaiting model release).
        """
        fallback = StatsEngine()
        result = fallback.predict(ohlcv, horizon_days)
        # Override method name to indicate attempted Kronos
        result["method"] = "kronos_fallback_stats"
        return result


# === Engine Factory ===

def get_engine(prefer_gpu: bool = True) -> BaseEngine:
    """Factory: return the best available prediction engine.

    Resolution order:
    1. Kronos (GPU) — if GPU available and Kronos loads successfully
    2. Kronos (CPU) — if no GPU but Kronos loads
    3. StatsEngine — always available baseline

    Args:
        prefer_gpu: If True, try GPU-accelerated engines first.

    Returns:
        Best available BaseEngine instance.
    """
    # Try Kronos first
    try:
        from .gpu_detector import detect_gpu
        gpu_info = detect_gpu()
        device = "cuda:0" if (prefer_gpu and gpu_info.available) else "cpu"
    except ImportError:
        device = "cpu"

    kronos = KronosEngine(device=device)
    if kronos.is_loaded:
        return kronos

    # Fallback: Statistical baseline (always works)
    return StatsEngine()


def get_engine_summary() -> Dict[str, Any]:
    """Return engine status summary for health checks."""
    try:
        from .gpu_detector import detect_gpu
        gpu_info = detect_gpu()
    except ImportError:
        gpu_info = None

    engine = get_engine(prefer_gpu=True)

    return {
        "engine_name": engine.name,
        "gpu_available": gpu_info.available if gpu_info else False,
        "gpu_name": gpu_info.name if gpu_info and gpu_info.available else "N/A",
        "gpu_vram_gb": gpu_info.vram_gb if gpu_info and gpu_info.available else 0,
        "fp8_supported": gpu_info.fp8_supported if gpu_info and gpu_info.available else False,
        "uses_gpu": engine.uses_gpu,
    }
