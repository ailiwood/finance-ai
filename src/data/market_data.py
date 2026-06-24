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

# ── In-memory K-line cache (prevents native library crashes on re-login) ──
# Key: (symbol, adjust, trade_date), Value: (timestamp, DataFrame)
# TTL: 30 minutes — financial data must not go stale
# This also fixes the test machine crash where bs.login() segfaults on second call.
_kline_cache: dict = {}
_KLINE_CACHE_TTL = 30 * 60  # seconds

# ── Fundamentals cache ──
# Key: symbol, Value: (timestamp, result_string)
_fundamentals_cache: dict = {}
_FUNDAMENTALS_CACHE_TTL = 30 * 60  # seconds


def clear_kline_cache(symbol: str = "") -> None:
    """Clear kline cache for a symbol, or all if empty. For 'force refresh' button."""
    global _kline_cache
    if symbol:
        _kline_cache = {k: v for k, v in _kline_cache.items() if k[0] != symbol}
    else:
        _kline_cache.clear()


def clear_fundamentals_cache(symbol: str = "") -> None:
    """Clear fundamentals cache for a symbol, or all if empty."""
    global _fundamentals_cache
    if symbol:
        _fundamentals_cache.pop(symbol, None)
    else:
        _fundamentals_cache.clear()


def _log(msg: str) -> None:
    # Use ASCII-safe replacement to avoid GBK/UnicodeEncodeError on Windows terminals
    safe = msg.encode("ascii", errors="replace").decode("ascii")
    try:
        print(f"[data] {safe}", flush=True)
    except Exception:
        pass


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
            _log(f"BaoStock [OK]: {len(df)}行, {df['close'].iloc[0]:.2f}~{df['close'].iloc[-1]:.2f}")
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
            _log(f"AkShare(Sina) [OK]: {len(df)}行, {df['close'].iloc[0]:.2f}~{df['close'].iloc[-1]:.2f}")
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
            _log(f"Tushare [OK]: {len(df)}行, {df['close'].iloc[0]:.2f}~{df['close'].iloc[-1]:.2f}")
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
            _log(f"AkShare(EM) [OK]: {len(df)}行, {df['close'].iloc[0]:.2f}~{df['close'].iloc[-1]:.2f}")
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

    # ── Cache check: TTL + date key, prevents stale prices + native re-login crash ──
    _today = datetime.now().strftime("%Y%m%d")
    _cache_key = (symbol, adjust, lookback_days, _today)
    if _cache_key in _kline_cache:
        _ts, _cached = _kline_cache[_cache_key]
        _age = time.time() - _ts
        if _age < _KLINE_CACHE_TTL:
            _log(f"get_kline({symbol}) → 缓存命中 ({len(_cached)}行, {_age:.0f}s前)")
            from src.monitor import log_data_shape
            log_data_shape(f"get_kline({symbol}) cached", _cached)
            # Return slice with requested lookback
            _cutoff = pd.Timestamp.now() - pd.Timedelta(days=lookback_days + 10)
            _sliced = _cached[_cached["date"] >= _cutoff].copy()
            if len(_sliced) >= 3:
                _sliced.attrs = dict(_cached.attrs)
                return _sliced
            return _cached.copy()
        else:
            _log(f"get_kline({symbol}) → 缓存过期({_age:.0f}s > {_KLINE_CACHE_TTL}s), 重新获取")
            _kline_cache.pop(_cache_key, None)

    end = datetime.now()
    start = end - timedelta(days=lookback_days + 10)
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    # ── Checkpoint: get_kline entry ──
    from src.monitor import log_data_shape
    log_data_shape(f"get_kline({symbol}) entry", {"symbol": symbol, "start": start_str, "end": end_str, "adjust": adjust})

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
            # Attach metadata so downstream can display source/adjust info
            df.attrs["source"] = _source_used or "unknown"
            df.attrs["adjust"] = _adjust_used or "qfq"
            # Store in cache for subsequent calls (TTL + date key)
            _kline_cache[_cache_key] = (time.time(), df.copy())
            # Remove legacy global state to prevent stale reads
            _source_used, _adjust_used = "", ""
            # ── Checkpoint: get_kline return ──
            log_data_shape("get_kline return", df)
            return df

    raise RuntimeError(
        f"获取 {symbol} K线数据失败。已尝试: BaoStock、AKShare(Sina)、Tushare、AKShare(东财)。\n"
        "建议: 检查网络连接，或在配置向导填写 Tushare Token（tushare.pro 免费注册）。"
    )


def calc_ma(df: pd.DataFrame, window: int, column: str = "close") -> pd.Series:
    return df[column].rolling(window=window, min_periods=1).mean()


def format_market_data_for_llm(df: pd.DataFrame, symbol: str = "", max_rows: int = 50) -> str:
    """Format a kline DataFrame into structured text for LLM consumption.

    Produces a markdown table with recent OHLCV + MA5/MA10/MA20 values.
    Never fabricates — all numbers come directly from the DataFrame.

    Args:
        df: DataFrame from get_kline() with columns (date, open, high, low, close, volume)
        symbol: Stock code for the header
        max_rows: Max recent rows to include

    Returns:
        Markdown-formatted string suitable for LLM context.
    """
    if df is None or df.empty:
        return "⚠️ 无可用K线数据"

    source = str(df.attrs.get("source", "未知"))
    adjust = str(df.attrs.get("adjust", "前复权"))

    # Work on a copy limited to recent rows
    work = df.tail(max_rows).copy()
    work["date"] = work["date"].dt.strftime("%Y-%m-%d")
    for col in ("open", "high", "low", "close"):
        if col in work.columns:
            work[col] = work[col].round(2)

    # Calculate MAs
    latest = df.iloc[-1]
    ma5 = round(float(calc_ma(df, 5).iloc[-1]), 2) if len(df) >= 5 else None
    ma10 = round(float(calc_ma(df, 10).iloc[-1]), 2) if len(df) >= 10 else None
    ma20 = round(float(calc_ma(df, 20).iloc[-1]), 2) if len(df) >= 20 else None
    ma60 = round(float(calc_ma(df, 60).iloc[-1]), 2) if len(df) >= 60 else None

    header = f"# {symbol or '股票'} 市场数据\n"
    header += f"数据来源: {source} | 复权: {adjust} | 总行数: {len(df)}\n\n"

    summary = "## 最新收盘\n"
    summary += f"- 日期: {latest['date'].strftime('%Y-%m-%d')}\n"
    summary += f"- 开盘: {latest['open']:.2f} | 最高: {latest['high']:.2f} | 最低: {latest['low']:.2f} | 收盘: {latest['close']:.2f}\n"
    summary += f"- 成交量: {int(latest['volume']):,}\n"
    mas = []
    if ma5 is not None:
        mas.append(f"MA5={ma5}")
    if ma10 is not None:
        mas.append(f"MA10={ma10}")
    if ma20 is not None:
        mas.append(f"MA20={ma20}")
    if ma60 is not None:
        mas.append(f"MA60={ma60}")
    if mas:
        summary += f"- 均线: {' | '.join(mas)}\n"

    # Recent data table
    table = f"\n## 最近{len(work)}个交易日 OHLCV\n"
    table += "| 日期 | 开盘 | 最高 | 最低 | 收盘 | 成交量 |\n"
    table += "|------|------|------|------|------|--------|\n"
    for _, row in work.iterrows():
        table += (
            f"| {row['date']} "
            f"| {row['open']:.2f} "
            f"| {row['high']:.2f} "
            f"| {row['low']:.2f} "
            f"| {row['close']:.2f} "
            f"| {int(row['volume']):,} |\n"
        )

    result = header + summary + table
    result += "\n---\n*数据由 QuantSage 自动获取，仅供参考研究，不构成投资建议*\n"

    # DEBUG: log first 500 chars
    _log(f"format_market_data_for_llm: {len(result)} chars total")
    preview = result[:500].replace("\n", "\\n")
    _log(f"LLM 数据前500字: {preview}")

    return result


def clear_cache():
    import shutil
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════
# Free news fetcher (AKShare → EastMoney stock_news_em)
# ═══════════════════════════════════════════════════════════════

def fetch_china_news(symbol: str, max_news: int = 10) -> str:
    """Fetch real A-share news via EastMoney API directly. FREE, no API key.

    Bypasses akshare.stock_news_em which has a pyarrow bug in v1.18.x.
    Uses raw HTTP to EastMoney's JSON API.

    Returns formatted news text, or empty string on failure.
    """
    # Method 1: EastMoney direct API (no akshare, no pyarrow dependency)
    try:
        import requests
        # EastMoney stock notice/announcement API
        url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
        params = {
            "sr": -1, "page_size": max_news, "page_index": 1,
            "ann_type": "A", "client_source": "web",
            "stock_list": symbol,
        }
        r = requests.get(url, params=params, timeout=15,
                        headers={"User-Agent": "Mozilla/5.0"})
        data = r.json()
        items = data.get("data", {}).get("list", [])
        if items:
            lines = [
                f"## {symbol} 个股新闻 (来源: 东方财富公告, 免费)",
                f"共获取 {len(items)} 条公告/新闻：\n"
            ]
            for item in items[:max_news]:
                title = item.get("title", "") or item.get("announcementTitle", "")
                date_str = item.get("notice_date", "") or item.get("publishDate", "")
                if title:
                    lines.append(f"- [{date_str}] {title}")
            result = "\n".join(lines)
            _log(f"fetch_china_news({symbol}): EastMoney直接API → {len(items)} 条")
            if len(items) > 0:
                return result
    except Exception as e:
        _log(f"fetch_china_news EastMoney直接API失败: {e}")

    # Method 2: Fallback to akshare (may fail on pyarrow bug)
    try:
        import akshare as ak
        df = ak.stock_news_em(symbol=symbol)
        if df is not None and not df.empty:
            df = df.head(max_news)
            lines = [
                f"## {symbol} 个股新闻 (来源: AKShare/东方财富, 免费)",
                f"共获取 {len(df)} 条新闻：\n"
            ]
            for _, row in df.iterrows():
                title = str(row.get("新闻标题", row.get("title", "")))
                time_str = str(row.get("发布时间", row.get("time", "")))
                if title and title != "nan":
                    lines.append(f"- [{time_str}] {title}")
            result = "\n".join(lines)
            _log(f"fetch_china_news({symbol}): AKShare fallback → {len(df)} 条")
            return result
    except ImportError:
        _log("fetch_china_news: akshare 未安装")
    except Exception as e:
        _log(f"fetch_china_news AKShare备用也失败: {e}")

    return ""


# ═══════════════════════════════════════════════════════════════
# Free fundamentals fetcher (BaoStock query_stock_basic)
# ═══════════════════════════════════════════════════════════════

def _fetch_akshare_financials(symbol: str) -> dict:
    """Try AKShare free financial indicators (PE/PB/ROE/EPS).

    Uses stock_a_indicator_lg which provides the latest financial ratios.
    Returns empty dict on any failure — never fabricates.
    """
    try:
        import akshare as ak
        df = ak.stock_a_indicator_lg(symbol=symbol)
        if df is None or df.empty:
            return {}
        # Get the most recent row with valid data
        latest = df.iloc[-1]
        result = {}
        # Map common column names to our keys
        for ak_col, our_key in [
            ("pe", "pe"), ("pe_ttm", "pe"),
            ("pb", "pb"), ("pb_mrq", "pb"),
            ("roe", "roe"), ("roe_ttm", "roe"),
            ("eps", "eps"), ("basic_eps", "eps"),
        ]:
            if ak_col in df.columns:
                val = latest[ak_col]
                if pd.notna(val) and float(val) != 0:
                    result[our_key] = f"{float(val):.2f}"
                    # Don't overwrite if already set
                    if our_key not in result:
                        result[our_key] = f"{float(val):.2f}"
        return result
    except Exception:
        return {}


def get_fundamentals(symbol: str) -> str:
    """Fetch A-share fundamental data via BaoStock (free, no registration).

    Returns markdown-formatted string with stock basic info (industry, area, listing date).
    Financial indicators (PE/PB/ROE) require Tushare for complete data.
    Never fabricates — missing fields are clearly marked.
    """
    # Check cache with TTL (prevents bs.login() segfault + ensures fresh data)
    if symbol in _fundamentals_cache:
        _ts, _result = _fundamentals_cache[symbol]
        if time.time() - _ts < _FUNDAMENTALS_CACHE_TTL:
            return _result
        else:
            _fundamentals_cache.pop(symbol, None)

    try:
        import baostock as bs
        lg = bs.login()
        if lg.error_code != "0":
            return ""

        bs_code = _baostock_symbol(symbol)

        # 1) Stock basic info
        rs_basic = bs.query_stock_basic(code=bs_code)
        basic_info = {}
        if rs_basic.error_code == "0":
            while rs_basic.next():
                row = rs_basic.get_row_data()
                basic_info["name"] = row[1] if len(row) > 1 else ""
                basic_info["ipo_date"] = row[2] if len(row) > 2 else ""

        # 2) Industry classification
        try:
            rs_ind = bs.query_stock_industry(code=bs_code)
            industry = ""
            if rs_ind.error_code == "0":
                while rs_ind.next():
                    row = rs_ind.get_row_data()
                    industry = row[3] if len(row) > 3 else ""
            basic_info["industry"] = industry
        except Exception:
            basic_info["industry"] = ""

        bs.logout()

        if not basic_info.get("name"):
            return ""

        # 3) AKShare financial indicators (PE/PB/ROE/EPS — free, no token needed)
        fin_data = _fetch_akshare_financials(symbol)

        # Build financial indicator rows
        fin_rows = []
        fin_source = ""
        if fin_data:
            fin_source = " (来源: AKShare, 免费接口)"
            pe_val = fin_data.get("pe", "")
            pb_val = fin_data.get("pb", "")
            roe_val = fin_data.get("roe", "")
            eps_val = fin_data.get("eps", "")
            fin_rows = [
                f"| PE (市盈率) | {pe_val if pe_val else '⚠️ 暂不可用'} | {'' if pe_val else 'AKShare接口未返回'} |",
                f"| PB (市净率) | {pb_val if pb_val else '⚠️ 暂不可用'} | {'' if pb_val else 'AKShare接口未返回'} |",
                f"| ROE | {roe_val if roe_val else '⚠️ 暂不可用'} | {'' if roe_val else 'AKShare接口未返回'} |",
                f"| EPS | {eps_val if eps_val else '⚠️ 暂不可用'} | {'' if eps_val else 'AKShare接口未返回'} |",
                "| 股息率 | ⚠️ 暂不可用 | 需 Tushare Token (tushare.pro 免费注册) |",
            ]
        else:
            fin_rows = [
                "| PE (市盈率) | ⚠️ 暂不可用 | AKShare/BaoStock免费接口均未返回 |",
                "| PB (市净率) | ⚠️ 暂不可用 | 同上 |",
                "| ROE | ⚠️ 暂不可用 | 同上 |",
                "| EPS | ⚠️ 暂不可用 | 同上 |",
                "| 股息率 | ⚠️ 暂不可用 | 需 Tushare Token |",
            ]

        lines = [
            f"## {symbol} 基本面信息 (来源: BaoStock, 免费接口){fin_source}",
            "",
            "### 公司基本信息",
            f"- 股票名称: {basic_info.get('name', '未知')}",
            f"- 所属行业: {basic_info.get('industry', '未知')}",
            f"- 上市日期: {basic_info.get('ipo_date', '未知')}",
            "",
            "### 财务指标",
            "| 指标 | 数值 | 说明 |",
            "|------|------|------|",
        ] + fin_rows + [
            "",
            "*BaoStock 免费接口提供基本信息，AKShare 补充 PE/PB/ROE/EPS。*",
            "*本报告不编造任何数据。标注'暂不可用'的指标为真实数据缺失。*",
        ]
        result = "\n".join(lines)
        # Cache to avoid BaoStock re-login crashes on subsequent calls
        _fundamentals_cache[symbol] = (time.time(), result)
        return result
    except ImportError:
        return ""
    except Exception as e:
        _log(f"get_fundamentals({symbol}) 失败: {e}")
        return ""
