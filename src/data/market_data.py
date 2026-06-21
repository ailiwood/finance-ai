"""Unified market data — 4-source fallback chain, all free.

Chain: BaoStock(qfq,free) → AKShare Sina(qfq) → Tushare → AKShare EM → Error
Every source failure logs detail; no fabrication (red line).
"""

from __future__ import annotations
import sys, os, warnings, time
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
    "pre_close": "preclose", "pct_chg": "pct_change",
}

# Track which source was used
_source_used: str = ""
_adjust_used: str = ""


def _log(msg: str) -> None:
    print(f"[数据] {msg}", flush=True)
    print(f"[数据] {msg}", file=sys.stderr, flush=True)


def get_last_source() -> str:
    return _source_used


def get_last_adjust() -> str:
    return _adjust_used


# ═══════════════════════════════════════════════════════════════
# Source 1: BaoStock (前复权，免费，无需积分)
# ═══════════════════════════════════════════════════════════════

def _baostock_symbol(symbol: str) -> str:
    """600519 → sh.600519, 000001 → sz.000001"""
    if symbol.startswith("6"):
        return f"sh.{symbol}"
    elif symbol.startswith(("0", "3")):
        return f"sz.{symbol}"
    elif symbol.startswith(("8", "4")):
        return f"bj.{symbol}"
    return symbol


def _fetch_baostock(symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """BaoStock: free qfq, no credits needed. PRIMARY choice."""
    try:
        import baostock as bs
        lg = bs.login()
        if lg.error_code != "0":
            _log(f"BaoStock 登录失败: {lg.error_msg}")
            return None

        bs_code = _baostock_symbol(symbol)
        _log(f"BaoStock: {bs_code} qfq ...")

        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount",
            start_date=start.replace("-", "-"),
            end_date=end.replace("-", "-"),
            frequency="d",
            adjustflag="2",  # 前复权
        )

        rows = []
        while rs.next():
            rows.append(rs.get_row_data())
        bs.logout()

        if not rows:
            _log(f"BaoStock: {bs_code} 返回空")
            return None

        df = pd.DataFrame(rows, columns=["date", "open", "high", "low", "close", "volume", "amount"])
        for c in ["open", "high", "low", "close", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)

        if len(df) >= 3:
            global _source_used, _adjust_used
            _source_used, _adjust_used = "BaoStock", "前复权(qfq)"
            _log(f"BaoStock ✅: {len(df)}行, {df['close'].iloc[0]:.2f}~{df['close'].iloc[-1]:.2f}")
            return df
        _log(f"BaoStock: 有效数据不足({len(df)}行)")
        return None
    except Exception as e:
        _log(f"BaoStock 失败: {e}")
        try:
            import baostock as bs
            bs.logout()
        except Exception:
            pass
        return None


# ═══════════════════════════════════════════════════════════════
# Source 2: AKShare Sina (前复权，免费，质量高)
# ═══════════════════════════════════════════════════════════════

def _fetch_akshare_sina(symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """AKShare Sina interface: stock_zh_a_daily, qfq, higher quality."""
    try:
        import akshare as ak
        sina_code = _baostock_symbol(symbol)  # same format: sh.600519
        _log(f"AkShare(Sina): {sina_code} qfq ...")

        for attempt in range(3):
            try:
                df = ak.stock_zh_a_daily(
                    symbol=sina_code, adjust="qfq",
                    start_date=start.replace("-", ""),
                    end_date=end.replace("-", ""),
                )
                break
            except Exception:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                else:
                    raise

        if df is None or df.empty:
            _log(f"AkShare(Sina): 返回空")
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
            global _source_used, _adjust_used
            _source_used, _adjust_used = "AKShare(Sina)", "前复权(qfq)"
            _log(f"AkShare(Sina) ✅: {len(df)}行, {df['close'].iloc[0]:.2f}~{df['close'].iloc[-1]:.2f}")
            return df
        return None
    except Exception as e:
        _log(f"AkShare(Sina) 失败: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# Source 3: Tushare (120 credits = basic daily access, no qfq)
# ═══════════════════════════════════════════════════════════════

def _fetch_tushare(symbol: str, start: str, end: str) -> Optional[pd.DataFrame]:
    """Tushare: basic daily access (no qfq at 120 credits)."""
    token = _get_token()
    if not token:
        _log("Tushare: 未配置 Token")
        return None
    try:
        import tushare as ts
        ts.set_token(token)
        pro = ts.pro_api()

        if symbol.startswith("6"):
            ts_code = f"{symbol}.SH"
        elif symbol.startswith(("0", "3")):
            ts_code = f"{symbol}.SZ"
        elif symbol.startswith(("8", "4")):
            ts_code = f"{symbol}.BJ"
        else:
            ts_code = symbol

        _log(f"Tushare: {ts_code} (不复权) ...")
        df = pro.daily(
            ts_code=ts_code,
            start_date=start.replace("-", ""),
            end_date=end.replace("-", ""),
        )
        if df is None or df.empty:
            _log(f"Tushare: 返回空")
            return None

        df = df.rename(columns={"trade_date": "date", "vol": "volume"})
        df["date"] = pd.to_datetime(df["date"])
        for c in ["open", "high", "low", "close", "volume"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["close"]).sort_values("date").reset_index(drop=True)

        if len(df) >= 3:
            global _source_used, _adjust_used
            _source_used, _adjust_used = "Tushare", "不复权"
            _log(f"Tushare ✅: {len(df)}行, {df['close'].iloc[0]:.2f}~{df['close'].iloc[-1]:.2f}")
            return df
        return None
    except Exception as e:
        _log(f"Tushare 失败: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# Source 4: AKShare EastMoney (free, may be blocked)
# ═══════════════════════════════════════════════════════════════

def _fetch_akshare_em(symbol: str, start: str, end: str, adjust: str) -> Optional[pd.DataFrame]:
    """AKShare eastmoney fallback (last resort)."""
    try:
        import akshare as ak
        _log(f"AkShare(EM): {symbol} qfq ...")
        df = ak.stock_zh_a_hist(
            symbol=symbol, period="daily",
            start_date=start.replace("-", ""),
            end_date=end.replace("-", ""),
            adjust=adjust,
        )
        if df is None or df.empty:
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
            global _source_used, _adjust_used
            _source_used, _adjust_used = "AKShare(东财)", "前复权(qfq)"
            _log(f"AkShare(EM) ✅: {len(df)}行, {df['close'].iloc[0]:.2f}~{df['close'].iloc[-1]:.2f}")
            return df
        return None
    except Exception as e:
        _log(f"AkShare(EM) 失败: {e}")
        return None


# ═══════════════════════════════════════════════════════════════
# Unified entry
# ═══════════════════════════════════════════════════════════════

def _get_token() -> Optional[str]:
    for key in ("TUSHARE_TOKEN", "tushare_token"):
        t = os.getenv(key, "")
        if t and not t.startswith("your_"):
            return t
    try:
        from src.core.config_manager import load_config
        t = load_config().get("tushare_token", "")
        if t and not t.startswith("your_"):
            return t
    except Exception:
        pass
    return None


def get_kline(
    symbol: str,
    period: str = "daily",
    adjust: str = "qfq",
    lookback_days: int = 1100,
    include_today_intraday: bool = False,
) -> pd.DataFrame:
    """Get A-share kline via 4-source fallback chain.

    Chain: BaoStock → AKShare(Sina) → Tushare → AKShare(EM) → Error
    """
    global _source_used, _adjust_used
    _source_used = _adjust_used = ""

    end = datetime.now()
    start = end - timedelta(days=lookback_days + 10)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    _log(f"get_kline({symbol}) → 4源链: BaoStock→Sina→Tushare→东财")

    # Chain of sources — try each, first success wins
    for fetcher in [
        lambda: _fetch_baostock(symbol, start_str, end_str),
        lambda: _fetch_akshare_sina(symbol, start_str, end_str),
        lambda: _fetch_tushare(symbol, start_str, end_str),
        lambda: _fetch_akshare_em(symbol, start_str, end_str, adjust),
    ]:
        df = fetcher()
        if df is not None:
            if include_today_intraday is False and len(df) > 0:
                today = pd.Timestamp.now().normalize()
                df = df[df["date"] < today].copy()
            return df

    raise RuntimeError(
        f"获取 {symbol} K线数据失败。已尝试: BaoStock、AKShare(Sina)、Tushare、AKShare(东财)。\n"
        "建议: 检查网络连接，或在配置向导填写 Tushare Token（tushare.pro 免费注册）。"
    )


def calc_ma(df: pd.DataFrame, window: int, column: str = "close") -> pd.Series:
    return df[column].rolling(window=window, min_periods=1).mean()


def clear_cache():
    import shutil
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
