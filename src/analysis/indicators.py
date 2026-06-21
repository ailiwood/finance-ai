"""Technical indicators — MA, MACD, RSI, KDJ, BOLL.

All indicators expect a DataFrame with at minimum 'close' column.
Multi-period support: pass sliced data for different lookbacks.
"""

from __future__ import annotations

import pandas as pd
import numpy as np


# ── Multi-period config ──
PERIODS = {
    "近1周":  {"days": 7,    "granularity": "daily"},
    "近1月":  {"days": 30,   "granularity": "daily"},
    "近3月":  {"days": 90,   "granularity": "daily"},
    "近6月":  {"days": 180,  "granularity": "daily"},
    "近1年":  {"days": 365,  "granularity": "daily"},
    "近3年":  {"days": 1095, "granularity": "weekly"},
}


def calc_ma(df: pd.DataFrame, window: int, column: str = "close") -> pd.Series:
    """Simple Moving Average."""
    return df[column].rolling(window=window, min_periods=1).mean()


def calc_macd(df: pd.DataFrame, column: str = "close",
              fast: int = 12, slow: int = 26, signal: int = 9):
    """MACD: returns (dif, dea, histogram)."""
    ema_fast = df[column].ewm(span=fast, adjust=False).mean()
    ema_slow = df[column].ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    hist = (dif - dea) * 2
    return dif, dea, hist


def calc_rsi(df: pd.DataFrame, window: int = 14, column: str = "close") -> pd.Series:
    """Relative Strength Index (SMA-based, China standard)."""
    delta = df[column].diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=window - 1, adjust=True).mean()
    avg_loss = loss.ewm(com=window - 1, adjust=True).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3):
    """KDJ indicator: returns (k, d, j)."""
    low_n = df["low"].rolling(window=n, min_periods=1).min()
    high_n = df["high"].rolling(window=n, min_periods=1).max()
    rsv = (df["close"] - low_n) / (high_n - low_n).replace(0, np.nan) * 100
    k = rsv.ewm(com=m1 - 1, adjust=True).mean()
    d = k.ewm(com=m2 - 1, adjust=True).mean()
    j = 3 * k - 2 * d
    return k, d, j


def calc_boll(df: pd.DataFrame, window: int = 20, column: str = "close"):
    """Bollinger Bands: returns (mid, upper, lower)."""
    mid = df[column].rolling(window=window, min_periods=1).mean()
    std = df[column].rolling(window=window, min_periods=1).std()
    upper = mid + 2 * std
    lower = mid - 2 * std
    return mid, upper, lower


def slice_period(df: pd.DataFrame, days: int) -> pd.DataFrame:
    """Slice the last N days from kline data."""
    if len(df) <= days:
        return df.copy()
    return df.iloc[-days:].copy()


def compute_all_indicators(df: pd.DataFrame,
                           periods: dict = None) -> dict:
    """Compute indicators for all configured periods.

    Returns dict: period_name → {ma5, ma10, ma20, ma60, macd_dif, rsi14, ...}
    """
    if periods is None:
        periods = PERIODS

    result = {}
    for name, cfg in periods.items():
        sliced = slice_period(df, cfg["days"])

        # Resample long periods to weekly
        if cfg.get("granularity") == "weekly" and len(sliced) > 20:
            sliced = sliced.set_index("date").resample("W").agg({
                "open": "first", "high": "max", "low": "min",
                "close": "last", "volume": "sum",
            }).dropna().reset_index()

        indicators = {}
        close = sliced["close"]

        if len(close) >= 5:
            indicators["ma5"] = round(float(calc_ma(sliced, 5).iloc[-1]), 2)
        if len(close) >= 10:
            indicators["ma10"] = round(float(calc_ma(sliced, 10).iloc[-1]), 2)
        if len(close) >= 20:
            indicators["ma20"] = round(float(calc_ma(sliced, 20).iloc[-1]), 2)
        if len(close) >= 60:
            indicators["ma60"] = round(float(calc_ma(sliced, 60).iloc[-1]), 2)

        if len(close) >= 26:
            dif, dea, hist = calc_macd(sliced)
            indicators["macd_dif"] = round(float(dif.iloc[-1]), 4)
            indicators["macd_dea"] = round(float(dea.iloc[-1]), 4)
            indicators["macd_hist"] = round(float(hist.iloc[-1]), 4)
        if len(close) >= 14:
            indicators["rsi14"] = round(float(calc_rsi(sliced).iloc[-1]), 1)
        if "high" in sliced.columns and len(close) >= 9:
            k, d, j = calc_kdj(sliced)
            indicators["kdj_k"] = round(float(k.iloc[-1]), 1)
            indicators["kdj_d"] = round(float(d.iloc[-1]), 1)
            indicators["kdj_j"] = round(float(j.iloc[-1]), 1)
        if len(close) >= 20:
            mid, upper, lower = calc_boll(sliced)
            indicators["boll_mid"] = round(float(mid.iloc[-1]), 2)
            indicators["boll_upper"] = round(float(upper.iloc[-1]), 2)
            indicators["boll_lower"] = round(float(lower.iloc[-1]), 2)

        result[name] = indicators

    return result
