"""Unified market data access — Tushare primary, AkShare fallback.

All errors are printed to console AND written to crash log for diagnosis.
"""

from __future__ import annotations
import warnings, sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd

CACHE_DIR = Path.home() / ".quantsage" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

COL_MAP = {
    "日期": "date", "开盘": "open", "收盘": "close",
    "最高": "high", "最低": "low", "成交量": "volume",
    "成交额": "amount", "trade_date": "date", "vol": "volume",
}


def _log(msg: str) -> None:
    """Print to both stdout and stderr to ensure visibility."""
    print(f"[数据] {msg}", flush=True)
    print(f"[数据] {msg}", file=sys.stderr, flush=True)


def _get_token() -> Optional[str]:
    """Get Tushare token from env or config manager."""
    import os
    # Env var (set at app startup or during analysis)
    token = os.getenv("TUSHARE_TOKEN", "") or os.getenv("tushare_token", "")
    if token and not token.startswith("your_"):
        return token
    # Config manager (encrypted storage)
    try:
        from src.core.config_manager import load_config
        cfg = load_config()
        token = cfg.get("tushare_token", "")
        if token and not token.startswith("your_"):
            return token
    except Exception:
        pass
    return None


def _fetch_via_tushare(symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """Fetch kline via Tushare. Returns None on any failure."""
    token = _get_token()
    if not token:
        _log("Tushare: 未配置 Token（请在配置向导中填写）")
        return None
    try:
        import tushare as ts
        # CRITICAL: must call set_token BEFORE pro_api()
        ts.set_token(token)
        pro = ts.pro_api()

        # ts_code format: 600519 → 600519.SH
        if symbol.startswith("6"):
            ts_code = f"{symbol}.SH"
        elif symbol.startswith(("0", "3")):
            ts_code = f"{symbol}.SZ"
        elif symbol.startswith(("8", "4")):
            ts_code = f"{symbol}.BJ"
        else:
            ts_code = symbol

        _log(f"Tushare: 正在获取 {ts_code} {start}→{end} ...")

        df = pro.daily(
            ts_code=ts_code,
            start_date=start.replace("-", ""),
            end_date=end.replace("-", ""),
        )

        if df is None or df.empty:
            _log(f"Tushare: {ts_code} 返回空数据（可能非交易日或无权限）")
            return None

        df = df.rename(columns={"trade_date": "date", "vol": "volume"})
        df["date"] = pd.to_datetime(df["date"])
        for c in ["open", "high", "low", "close", "volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)

        if len(df) >= 3:
            _log(f"Tushare 成功: {len(df)}行, 收盘区间 {df['close'].iloc[0]:.2f}~{df['close'].iloc[-1]:.2f}")
            return df
        _log(f"Tushare: 有效数据不足 ({len(df)}行)")
        return None

    except Exception as e:
        _log(f"Tushare 失败: {type(e).__name__}: {e}")
        return None


def _fetch_via_akshare(symbol: str, start: str, end: str, adjust: str) -> Optional[pd.DataFrame]:
    """Fetch kline via AkShare. Returns None on any failure."""
    try:
        import akshare as ak
        _log(f"AkShare: 正在获取 {symbol} qfq ...")
        df = ak.stock_zh_a_hist(
            symbol=symbol, period="daily",
            start_date=start.replace("-", ""),
            end_date=end.replace("-", ""),
            adjust=adjust,
        )
        if df is None or df.empty:
            _log(f"AkShare: {symbol} 返回空数据")
            return None

        df = df.rename(columns=COL_MAP)
        keep = [c for c in ["date", "open", "high", "low", "close", "volume"] if c in df.columns]
        df = df[keep].copy()
        for c in ["open", "high", "low", "close", "volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)

        if len(df) >= 3:
            _log(f"AkShare 成功: {len(df)}行, 收盘区间 {df['close'].iloc[0]:.2f}~{df['close'].iloc[-1]:.2f}")
            return df
        _log(f"AkShare: 有效数据不足 ({len(df)}行)")
        return None

    except Exception as e:
        _log(f"AkShare 失败: {type(e).__name__}: {e}")
        return None


def get_kline(
    symbol: str,
    period: str = "daily",
    adjust: str = "qfq",
    lookback_days: int = 1100,
    include_today_intraday: bool = False,
) -> pd.DataFrame:
    """Get standardized A-share kline. Priority: Tushare → AkShare → error."""
    end = datetime.now()
    start = end - timedelta(days=lookback_days + 10)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    _log(f"get_kline({symbol}, lookback={lookback_days}d)")

    # 1. Tushare
    df = _fetch_via_tushare(symbol, start_str, end_str)
    if df is not None:
        return _finalize(df, symbol, adjust, include_today_intraday)

    # 2. AkShare fallback
    df = _fetch_via_akshare(symbol, start_str, end_str, adjust)
    if df is not None:
        return _finalize(df, symbol, adjust, include_today_intraday)

    raise RuntimeError(
        f"获取 {symbol} K线数据失败。已尝试: Tushare、AkShare。\n"
        "建议：在配置向导填写 Tushare Token（tushare.pro 免费注册），"
        "或检查网络是否能访问 eastmoney.com"
    )


def _finalize(df, symbol, adjust, exclude_today):
    if exclude_today and len(df) > 0:
        today = pd.Timestamp.now().normalize()
        df = df[df["date"] < today].copy()
    return df


def calc_ma(df: pd.DataFrame, window: int, column: str = "close") -> pd.Series:
    return df[column].rolling(window=window, min_periods=1).mean()


def clear_cache():
    import shutil
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
