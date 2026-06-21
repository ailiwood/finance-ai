"""Data inspection page — raw kline + MA verification for user reconciliation.

Shows: recent OHLCV table, MA values, data source metadata.
Users can compare directly with 同花顺/东方财富.
"""

from __future__ import annotations

import streamlit as st

from src.data.market_data import get_kline
from src.analysis.indicators import calc_ma


def show_data_inspection() -> None:
    st.header("数据体检")
    st.caption("核对原始数据，与同花顺/东方财富逐行对账")

    symbol = st.text_input("股票代码", value="600519", key="inspect_symbol").strip()
    if not symbol:
        return

    if st.button("开始体检", key="inspect_btn"):
        with st.spinner("正在获取数据..."):
            try:
                df = get_kline(symbol, adjust="qfq", include_today_intraday=False)
            except Exception as e:
                st.error(f"获取数据失败: {e}")
                return

        if df.empty:
            st.warning("无数据")
            return

        closes = df["close"].tolist()

        # Recent 10 days table
        st.markdown("### 最近10个交易日 OHLCV")
        display = df.tail(10)[["date", "open", "high", "low", "close", "volume"]].copy()
        display["date"] = display["date"].dt.strftime("%Y-%m-%d")
        for c in ["open", "high", "low", "close"]:
            display[c] = display[c].round(2)
        st.dataframe(display, use_container_width=True, hide_index=True)

        # MA values
        st.markdown("### 技术指标检验")
        cols = st.columns(3)
        for i, w in enumerate([5, 10, 20]):
            if len(closes) >= w:
                val = round(float(calc_ma(df, w).iloc[-1]), 2)
                cols[i].metric(f"MA{w}", f"{val:.2f}")

        # Metadata
        st.markdown("### 数据元信息")
        try:
            from src.data.market_data import get_last_source, get_last_adjust
            src_label = get_last_source() or "未知"
            adj_label = get_last_adjust() or "前复权(qfq)"
        except Exception:
            src_label, adj_label = "未知", "前复权(qfq)"
        st.caption(f"数据来源: **{src_label}** | 复权方式: **{adj_label}** — 与同花顺/东方财富默认一致")
        st.caption(f"数据行数: {len(df)}")
        st.caption(f"数据区间: {df['date'].iloc[0].strftime('%Y-%m-%d')} ~ {df['date'].iloc[-1].strftime('%Y-%m-%d')}")
