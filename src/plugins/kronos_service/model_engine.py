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


# === Kronos Engine (Deep Learning, MIT) ===

# ── Lazy import of vendored Kronos model ──
_KronosPredictor = None
_HAS_KRONOS_CODE = False

def _try_import_kronos():
    """Lazy-import Kronos model classes from vendored code."""
    global _KronosPredictor, _HAS_KRONOS_CODE
    if _HAS_KRONOS_CODE:
        return True
    try:
        from src.plugins.kronos_service.kronos_model.kronos import (
            Kronos, KronosTokenizer, KronosPredictor
        )
        _KronosPredictor = KronosPredictor
        _HAS_KRONOS_CODE = True
        return True
    except ImportError as e:
        warnings.warn(f"Kronos model code unavailable: {e}")
        return False
    except Exception as e:
        warnings.warn(f"Kronos import failed: {e}")
        return False


class KronosEngine(BaseEngine):
    """Kronos deep-learning prediction engine (MIT license, AAAI 2026).

    Uses Kronos-base (102.3M params) — a Transformer model pre-trained on
    OHLCV data for probabilistic K-line forecasting.
    Loads from HuggingFace: NeoQuasar/Kronos-base + Kronos-Tokenizer-base.

    Lazy-loading: model is downloaded on first predict() call, not at import time.
    Falls back to StatsEngine on any loading/inference failure.
    """

    _MODEL_NAME = "NeoQuasar/Kronos-base"                # hardcoded, no mini/small
    _TOKENIZER_NAME = "NeoQuasar/Kronos-Tokenizer-base"  # hardcoded
    _MAX_CONTEXT = 512

    def __init__(self) -> None:
        self._device = None
        self._loaded = False
        self._predictor = None
        self._load_error = None

    # ── Lazy load ──

    def _lazy_load(self) -> bool:
        """Download and initialize Kronos model on first use. Returns True if ready."""
        if self._loaded:
            return True
        if not _try_import_kronos():
            self._load_error = "Kronos model code not importable (missing einops/huggingface_hub?)"
            return False

        try:
            from .gpu_detector import pick_device
            self._device = pick_device()

            # Redirect HF cache to vendored weights (works in both dev and frozen)
            import os as _os, sys as _sys
            from pathlib import Path as _Path

            # Try to find vendored weights relative to this file
            _this_dir = _Path(__file__).resolve().parent
            _cache_candidates = [
                _this_dir / "kronos_model" / "hf_cache",           # Dev: kronos_service/
                _Path(_sys._MEIPASS) / "src" / "plugins" / "kronos_service" / "kronos_model" / "hf_cache" if getattr(_sys, "frozen", False) else None,
            ]
            for _cache_path in _cache_candidates:
                if _cache_path and _cache_path.exists():
                    _os.environ["HF_HOME"] = str(_cache_path)
                    _os.environ["HF_HUB_OFFLINE"] = "1"
                    _os.environ.pop("SSL_CERT_FILE", None)  # Prevent httpx SSL errors in offline mode
                    break

            # Allow user to set HF mirror for China mainland
            _hf_endpoint = _os.environ.get("HF_ENDPOINT", "")
            if _hf_endpoint:
                _os.environ.setdefault("HF_ENDPOINT", _hf_endpoint)

            # Download & load from HuggingFace Hub
            from src.plugins.kronos_service.kronos_model.kronos import (
                Kronos, KronosTokenizer
            )
            tokenizer = KronosTokenizer.from_pretrained(
                self._TOKENIZER_NAME, local_files_only=True
            )
            model = Kronos.from_pretrained(
                self._MODEL_NAME, local_files_only=True
            )
            self._predictor = _KronosPredictor(
                model, tokenizer,
                device=self._device,
                max_context=self._MAX_CONTEXT,
            )
            self._loaded = True
            return True
        except Exception as e:
            self._load_error = str(e)[:200]
            warnings.warn(f"Kronos loading failed: {e}. Will use StatsEngine fallback.")
            return False

    # ── Properties ──

    @property
    def name(self) -> str:
        if self._loaded:
            gpu = "GPU" if (self._device and self._device.startswith("cuda")) else "CPU"
            return f"Kronos-base (深度学习模型, {gpu}模式)"
        if self._load_error:
            return f"Kronos-base (未加载: {self._load_error[:60]})"
        return "Kronos-base (未加载)"

    @property
    def uses_gpu(self) -> bool:
        return self._loaded and bool(self._device and self._device.startswith("cuda"))

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # ── Predict ──

    def predict(
        self,
        ohlcv: List[OhlcvRow],
        horizon_days: int = 5,
    ) -> PredictionResult:
        """Generate probabilistic K-line forecast using Kronos-base.

        Uses Monte Carlo sampling (sample_count=30) for uncertainty intervals.
        Automatically clips lookback to _MAX_CONTEXT (512).

        Returns PredictionResult with direction, confidence, target_price,
        lower_bound, upper_bound, and mandatory disclaimer.
        """
        # Lazy load on first call
        if not self._lazy_load():
            return StatsEngine().predict(ohlcv, horizon_days)

        try:
            import pandas as pd

            # Build OHLCV DataFrame from input rows
            df = pd.DataFrame(ohlcv)
            if "date" in df.columns:
                df["date"] = pd.to_datetime(df["date"])
            for col in ("open", "high", "low", "close"):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            df = df.dropna(subset=["open", "high", "low", "close"])

            if len(df) < 20:
                return self._fallback_result(ohlcv, horizon_days, "data too short (<20 rows)")

            # Clip to max context
            if len(df) > self._MAX_CONTEXT:
                df = df.tail(self._MAX_CONTEXT)

            # Build timestamps for Kronos predictor
            x_timestamp = df["date"] if "date" in df.columns else pd.Series(range(len(df)))
            freq = pd.infer_freq(x_timestamp) or pd.tseries.frequencies.to_offset("B")
            last_ts = x_timestamp.iloc[-1]
            y_timestamp = pd.date_range(
                start=last_ts + pd.Timedelta(days=1),
                periods=horizon_days,
                freq=freq,
            )

            # Run Monte Carlo prediction
            pred_len = min(horizon_days, 30)
            sample_count = max(10, min(30, horizon_days * 3))

            pred_df = self._predictor.predict(
                df=df[["open", "high", "low", "close"]],
                x_timestamp=x_timestamp,
                y_timestamp=y_timestamp,
                pred_len=pred_len,
                T=1.0,
                top_p=0.9,
                sample_count=sample_count,
            )

            # Extract prediction from Monte Carlo samples
            if pred_df is None or pred_df.empty:
                return self._fallback_result(ohlcv, horizon_days, "prediction returned empty")

            # pred_df columns after sample_count>1: open_0, high_0, ..., open_1, high_1, ...
            close_cols = [c for c in pred_df.columns if c.startswith("close")]
            if not close_cols:
                return self._fallback_result(ohlcv, horizon_days, "no close predictions")

            closes = pred_df[close_cols].values  # shape: (horizon, sample_count)
            mean_close = float(closes.mean())
            std_close = float(closes.std())

            current_price = float(df["close"].iloc[-1])
            target_price = round(mean_close, 2)
            lower_bound = round(mean_close - 2 * std_close, 2)
            upper_bound = round(mean_close + 2 * std_close, 2)

            # Direction
            if target_price > current_price * 1.005:
                direction = "up"
                confidence = min(0.95, 0.5 + abs(target_price / current_price - 1) * 10)
            elif target_price < current_price * 0.995:
                direction = "down"
                confidence = min(0.95, 0.5 + abs(1 - target_price / current_price) * 10)
            else:
                direction = "neutral"
                confidence = 0.5 + (1 - abs(target_price / current_price - 1) * 20)

            return PredictionResult(
                direction=direction,
                confidence=round(confidence, 3),
                target_price=target_price,
                current_price=current_price,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                horizon_days=pred_len,
                method=self.name,
                disclaimer=(
                    "基于深度学习模型 (Kronos-base) 的概率性预测，非确定性结论，"
                    "仅供参考研究，不构成任何投资建议。"
                ),
            )
        except Exception as e:
            warnings.warn(f"Kronos prediction failed: {e}")
            return self._fallback_result(ohlcv, horizon_days, f"prediction error: {str(e)[:100]}")

    def _fallback_result(
        self, ohlcv: List[OhlcvRow], horizon_days: int, reason: str = ""
    ) -> PredictionResult:
        """Graceful fallback to StatsEngine."""
        result = StatsEngine().predict(ohlcv, horizon_days)
        result["method"] = f"kronos_fallback_stats ({reason})" if reason else "kronos_fallback_stats"
        return result


# === Engine Singleton (process-level cache with thread safety) ===

_ENGINE_INSTANCE: BaseEngine | None = None
_ENGINE_LOCK = __import__("threading").Lock()


def get_engine() -> BaseEngine:
    """Return the singleton prediction engine (thread-safe).

    Kronos-base is preferred but loaded lazily on first predict().
    The engine is cached globally — subsequent calls return the same instance.
    This prevents double-loading of the 406MB model weights.

    Returns:
        KronosEngine (singleton, lazy-load) — falls back to StatsEngine.
    """
    global _ENGINE_INSTANCE
    if _ENGINE_INSTANCE is not None:
        return _ENGINE_INSTANCE
    with _ENGINE_LOCK:
        if _ENGINE_INSTANCE is not None:
            return _ENGINE_INSTANCE
        try:
            _ENGINE_INSTANCE = KronosEngine()
        except Exception:
            _ENGINE_INSTANCE = StatsEngine()
        return _ENGINE_INSTANCE


def reset_engine() -> None:
    """Reset the engine singleton (for testing)."""
    global _ENGINE_INSTANCE
    with _ENGINE_LOCK:
        _ENGINE_INSTANCE = None


def get_engine_summary() -> Dict[str, Any]:
    """Return engine status summary for health checks."""
    try:
        from .gpu_detector import detect_gpu
        gpu_info = detect_gpu()
    except ImportError:
        gpu_info = None

    engine = get_engine()

    return {
        "engine_name": engine.name,
        "gpu_available": gpu_info.available if gpu_info else False,
        "gpu_name": gpu_info.name if gpu_info and gpu_info.available else "N/A",
        "gpu_vram_gb": gpu_info.vram_gb if gpu_info and gpu_info.available else 0,
        "fp8_supported": gpu_info.fp8_supported if gpu_info and gpu_info.available else False,
        "uses_gpu": engine.uses_gpu,
    }
