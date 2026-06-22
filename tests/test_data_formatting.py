"""Tests for src/data/market_data.py — formatting and data integrity."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.market_data import format_market_data_for_llm, calc_ma


def _sample_df(rows: int = 100, source: str = "BaoStock", adjust: str = "前复权(qfq)") -> pd.DataFrame:
    """Build a realistic sample kline DataFrame with known values."""
    dates = pd.date_range(end=datetime.now(), periods=rows, freq="B")
    closes = [100.0 + i * 0.5 for i in range(rows)]  # Trending up: 100 → 149.5
    df = pd.DataFrame({
        "date": dates,
        "open": [c - 0.3 for c in closes],
        "high": [c + 0.5 for c in closes],
        "low": [c - 0.5 for c in closes],
        "close": closes,
        "volume": [1000000 + i * 1000 for i in range(rows)],
    })
    df.attrs["source"] = source
    df.attrs["adjust"] = adjust
    return df


class TestFormatMarketDataForLLM:
    """Tests for format_market_data_for_llm — the DataFrame-to-text formatter."""

    def test_returns_string_with_latest_close(self):
        """Output must contain the correct latest closing price."""
        df = _sample_df(50)
        result = format_market_data_for_llm(df, symbol="TEST")
        # Latest close = 100 + 49*0.5 = 124.5
        assert "124.50" in result, f"Expected 124.50 in output, got: {result[:300]}"

    def test_returns_string_with_ma5(self):
        """Output must contain MA5 value."""
        df = _sample_df(30)
        result = format_market_data_for_llm(df)
        assert "MA5=" in result, "Output must contain MA5"

    def test_returns_string_with_source_info(self):
        """Output must contain data source metadata."""
        df = _sample_df(10, source="BaoStock", adjust="前复权(qfq)")
        result = format_market_data_for_llm(df)
        assert "BaoStock" in result
        assert "前复权" in result

    def test_empty_df_returns_warning(self):
        """Empty DataFrame must return a Chinese warning, not crash."""
        df = pd.DataFrame()
        result = format_market_data_for_llm(df)
        assert "无可用" in result or "warning" in result.lower()

    def test_none_returns_warning(self):
        """None input must return warning, not crash."""
        result = format_market_data_for_llm(None)
        assert "无可用" in result

    def test_not_tuple_repr(self):
        """Output must NOT contain tuple repr like '(\"baostock\",'."""
        df = _sample_df(20)
        result = format_market_data_for_llm(df)
        assert "('" not in result
        assert "tuple" not in result.lower()

    def test_output_contains_table_header(self):
        """Output must contain markdown table headers."""
        df = _sample_df(10)
        result = format_market_data_for_llm(df)
        assert "日期" in result  # 日期
        assert "开盘" in result  # 开盘
        assert "收盘" in result  # 收盘

    def test_small_df_no_error(self):
        """Very small DataFrames (<5 rows) should not crash on MA calculation."""
        df = _sample_df(3)
        result = format_market_data_for_llm(df)
        # MA5 requires 5 rows — should gracefully omit
        assert isinstance(result, str)
        assert len(result) > 0


class TestCalcMA:
    """Tests for calc_ma helper."""

    def test_ma_values_correct(self):
        df = _sample_df(10)
        ma5 = calc_ma(df, 5)
        # First 4 values are partial, last value should be near 102+103+103.5+104+104.5 = avg
        assert len(ma5) == 10
        # Last value: avg of closes[5:10] = [102.5, 103.0, 103.5, 104.0, 104.5]
        expected = sum(100 + i * 0.5 for i in range(5, 10)) / 5  # = 103.0
        assert abs(ma5.iloc[-1] - expected) < 0.01


class TestDfAttrs:
    """Tests for df.attrs metadata from get_kline."""

    def test_get_kline_has_attrs(self):
        """get_kline must populate df.attrs with source and adjust."""
        from src.data.market_data import get_kline
        df = get_kline("600519", lookback_days=30)
        assert hasattr(df, "attrs"), "DataFrame must have attrs dict"
        assert "source" in df.attrs, f"attrs missing 'source': {df.attrs}"
        assert "adjust" in df.attrs, f"attrs missing 'adjust': {df.attrs}"
        assert len(str(df.attrs["source"])) > 0
