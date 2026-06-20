"""Post-configuration home page.

Real stock analysis with multi-market support (A-shares, US, HK).
"""

from __future__ import annotations

import sys
import os
import threading
from pathlib import Path

import streamlit as st

from src.core.config_manager import load_config, get_key_status, ProviderStatus
from src.compliance.disclaimer import get_ui_disclaimer

# Ensure TradingAgents-CN is on path
_TA_PATH = Path(__file__).resolve().parent.parent.parent.parent / "TradingAgents-CN"
if str(_TA_PATH) not in sys.path:
    sys.path.insert(0, str(_TA_PATH))

CSS_HOME = """
<style>
.home-container { max-width: 900px; margin: 2vh auto; padding: 1.5rem 2rem; background: #1a1a2e; border-radius: 12px; border: 1px solid #333; }
.home-title { text-align: center; color: #e0e0e0; font-size: 1.8rem; margin-bottom: 0.5rem; }
.config-card { background: #0f0f1a; border: 1px solid #2a2a3e; border-radius: 8px; padding: 1.2rem; margin-bottom: 1rem; }
.card-title { color: #ccc; font-size: 1.1rem; margin-bottom: 0.8rem; }
.status-ok { color: #4caf50; font-size: 1.2rem; }
.status-warn { color: #ff9800; font-size: 1.2rem; }
.status-error { color: #f44336; font-size: 1.2rem; }
.analysis-card { background: #0a1a2e; border: 1px solid #2a4a6e; border-radius: 8px; padding: 1.2rem; margin-bottom: 1rem; }
.disclaimer-footer { text-align: center; color: #888; font-size: 0.8rem; margin-top: 2rem; border-top: 1px solid #333; padding-top: 1rem; }
.progress-box { background: #0f1a2e; border: 1px solid #2a3a5e; border-radius: 6px; padding: 1rem; margin: 1rem 0; }
</style>
"""

MARKET_CONFIG = {
    "A股 (上海/深圳)": {"market": "A股", "placeholder": "600519", "examples": "600519 贵州茅台, 000001 平安银行, 300750 宁德时代"},
    "美股 (NASDAQ/NYSE)": {"market": "美股", "placeholder": "AAPL", "examples": "AAPL Apple, TSLA Tesla, NVDA NVIDIA, MSFT Microsoft"},
    "港股 (HKEX)": {"market": "港股", "placeholder": "00700", "examples": "00700 腾讯, 09988 阿里巴巴, 00388 港交所"},
}

STOCK_NAMES = {
    "600519": "贵州茅台", "000001": "平安银行", "300750": "宁德时代",
    "601318": "中国平安", "000858": "五粮液", "600036": "招商银行",
    "AAPL": "Apple Inc.", "TSLA": "Tesla Inc.", "NVDA": "NVIDIA Corp.",
    "MSFT": "Microsoft Corp.", "GOOGL": "Alphabet Inc.", "AMZN": "Amazon.com Inc.",
    "00700": "腾讯控股", "09988": "阿里巴巴", "00388": "香港交易所",
    "01810": "小米集团", "02318": "中国平安(港)", "00941": "中国移动",
}


def _run_analysis(symbol: str, stock_name: str, market: str, depth: int):
    """Run TradingAgents-CN analysis in a background thread."""
    try:
        # Fix encoding and proxy for background thread
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,eastmoney.com,push2.eastmoney.com,gtimg.cn,sinaimg.cn,api.tushare.pro,baostock.com,api.deepseek.com")

        st.session_state.analysis_running = True
        st.session_state.analysis_progress = "正在初始化分析引擎..."
        st.session_state.analysis_error = None

        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG

        # Build config from user settings
        config = load_config()
        ta_config = DEFAULT_CONFIG.copy()

        # DeepSeek
        ds_key = config.get("deepseek_api_key", "") or os.getenv("DEEPSEEK_API_KEY", "")
        if not ds_key:
            st.session_state.analysis_error = "未配置 DeepSeek API Key。请先完成配置向导。"
            st.session_state.analysis_running = False
            return

        ta_config["llm_provider"] = "deepseek"
        ta_config["backend_url"] = "https://api.deepseek.com"
        ta_config["deep_think_llm"] = "deepseek-chat"
        ta_config["quick_think_llm"] = "deepseek-chat"
        ta_config["max_debate_rounds"] = max(1, min(3, depth // 2))
        ta_config["online_tools"] = False
        ta_config["online_news"] = False
        ta_config["realtime_data"] = False

        os.environ["DEEPSEEK_API_KEY"] = ds_key

        st.session_state.analysis_progress = "正在获取数据并启动多智能体分析..."
        ta = TradingAgentsGraph(debug=False, config=ta_config)

        st.session_state.analysis_progress = f"正在分析 {symbol} {stock_name}（{market}）..."

        _, decision = ta.propagate(symbol, "2025-06-18")

        st.session_state.analysis_result = {
            "symbol": symbol,
            "stock_name": stock_name,
            "market": market,
            "decision": decision if isinstance(decision, dict) else {},
            "raw": str(decision) if not isinstance(decision, dict) else "",
        }
        st.session_state.analysis_progress = "分析完成"

    except Exception as e:
        st.session_state.analysis_error = str(e)
    finally:
        st.session_state.analysis_running = False


def show_home() -> None:
    """Render the post-configuration home page with real analysis capability."""
    st.markdown(CSS_HOME, unsafe_allow_html=True)
    st.markdown('<div class="home-container">', unsafe_allow_html=True)

    st.markdown('<h1 class="home-title">QuantSage</h1>', unsafe_allow_html=True)
    st.caption("多智能体股票研究辅助平台")

    config = load_config()
    key_status = get_key_status()

    # ── Config Summary (collapsed by default) ──
    with st.expander("配置概览", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**LLM 提供商**")
            for provider, status in key_status.items():
                name = {"deepseek": "DeepSeek", "dashscope": "阿里百炼"}.get(provider, provider)
                if status == ProviderStatus.CONFIGURED:
                    st.markdown(f'<span class="status-ok">✅</span> {name}', unsafe_allow_html=True)
                elif status == ProviderStatus.NOT_CONFIGURED:
                    st.markdown(f'<span class="status-warn">⬜</span> {name} (未配置)', unsafe_allow_html=True)
                else:
                    st.markdown(f'<span class="status-error">❌</span> {name} (配置有误)', unsafe_allow_html=True)
        with col2:
            st.markdown("**数据源**")
            srcs = []
            if config.get("default_china_data_source") == "akshare":
                srcs.append("AkShare")
            if config.get("tushare_token"):
                srcs.append("Tushare")
            st.markdown(", ".join(srcs) if srcs else "未配置")
            risk_map = {"conservative": "保守", "moderate": "平衡", "aggressive": "积极"}
            st.markdown(f"**风险**: {risk_map.get(config.get('risk_level', 'moderate'), '?')} | **深度**: {config.get('analysis_depth', 3)}/5")

        # Plugin status
        k_on = config.get("kronos_enabled", False)
        f_on = config.get("finbert_enabled", False)
        st.caption(f"插件: {'Kronos ✅' if k_on else 'Kronos ⬜'} | {'FinBERT ✅' if f_on else 'FinBERT ⬜'}")

    # ── Stock Analysis Section ──
    st.markdown('<div class="analysis-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">股票分析</div>', unsafe_allow_html=True)

    # Market selector
    market_label = st.selectbox(
        "选择市场",
        options=list(MARKET_CONFIG.keys()),
        key="market_select",
    )
    market_info = MARKET_CONFIG[market_label]

    # Stock input
    col1, col2 = st.columns([3, 1])
    with col1:
        symbol = st.text_input(
            "股票代码",
            placeholder=f"例如: {market_info['placeholder']}",
            key="symbol_input",
        ).strip().upper()
    with col2:
        depth = st.selectbox("分析深度", options=[1, 2, 3, 4, 5], index=2, key="depth_select")

    st.caption(f"常用: {market_info['examples']}")

    # Auto-detect stock name
    stock_name = STOCK_NAMES.get(symbol, "")
    if not stock_name and symbol:
        st.caption("股票名称未知，将使用代码进行分析")

    # Analyze button
    analyze_disabled = st.session_state.get("analysis_running", False) or not symbol
    if st.button("开始分析", type="primary", disabled=analyze_disabled, use_container_width=True, key="analyze_btn"):
        if not symbol:
            st.error("请输入股票代码")
        elif not key_status.get("deepseek") == ProviderStatus.CONFIGURED:
            st.error("请先配置 DeepSeek API Key（配置向导）")
        else:
            # Start background analysis
            thread = threading.Thread(
                target=_run_analysis,
                args=(symbol, stock_name or symbol, market_info["market"], depth),
                daemon=True,
            )
            thread.start()
            st.rerun()

    # ── Progress display ──
    if st.session_state.get("analysis_running"):
        st.markdown('<div class="progress-box">', unsafe_allow_html=True)
        progress_text = st.session_state.get("analysis_progress", "分析中...")
        st.info(f"⏳ {progress_text}")
        st.caption("分析通常需要 3-5 分钟，请耐心等待...")
        st.markdown('</div>', unsafe_allow_html=True)
        import time; time.sleep(3)
        st.rerun()

    # Auto-detect: analysis just finished but results not yet shown
    if st.session_state.get("analysis_result") and not st.session_state.get("analysis_running"):
        if not st.session_state.get("_results_shown"):
            st.session_state._results_shown = True
            st.rerun()

    # ── Error display ──
    if st.session_state.get("analysis_error"):
        st.error(f"分析失败: {st.session_state.analysis_error}")
        if st.button("清除错误", key="clear_error"):
            st.session_state.analysis_error = None
            st.rerun()

    # ── Results display ──
    if st.session_state.get("analysis_result") and not st.session_state.get("analysis_running"):
        result = st.session_state.analysis_result
        decision = result.get("decision", {})

        st.success(f"✅ {result['symbol']} {result['stock_name']} 分析完成")

        from src.report.report_generator import generate_report
        from src.report.pdf_exporter import export_report_pdf, export_report_markdown

        # Build analysis output for report generator
        analysis_output = {
            "decision": decision if isinstance(decision, dict) else {},
        }
        if result.get("raw"):
            analysis_output["reasoning"] = result["raw"]

        plugins = []
        if config.get("kronos_enabled"):
            plugins.append("kronos")
        if config.get("finbert_enabled"):
            plugins.append("finbert")

        try:
            report, data = generate_report(
                symbol=result["symbol"],
                stock_name=result.get("stock_name", result["symbol"]),
                analysis_output=analysis_output,
                plugins_used=plugins,
                gpu_used=False,
            )
        except Exception:
            # Fallback: build report manually
            direction_map = {"卖出": "看空", "买入": "看多", "持有": "中性"}
            action = decision.get("action", "中性") if isinstance(decision, dict) else "中性"
            direction = direction_map.get(str(action), "中性")
            confidence = decision.get("confidence", 0.5) if isinstance(decision, dict) else 0.5
            reasoning = decision.get("reasoning", str(decision)) if isinstance(decision, dict) else str(decision)
            risk = decision.get("risk_score", 0.5) if isinstance(decision, dict) else 0.5
            tp = decision.get("target_price") if isinstance(decision, dict) else None

            report = f"""# QuantSage 研究报告

**股票代码**: {result['symbol']}
**股票名称**: {result.get('stock_name', result['symbol'])}
**分析日期**: 2026-06-21

---

## 综合结论

**最终观点**: {direction}
**置信度**: {confidence:.0%}
**风险评分**: {risk:.1%}"""
            if tp:
                report += f"\n**参考价位**: ¥{tp:,.2f}"
            report += f"""

**综合推理**: {reasoning}

---

> 本报告由 QuantSage 自动生成，仅供参考研究，不构成任何投资建议，盈亏自负。
*QuantSage · 仅供参考研究 · 不构成投资建议*
"""

        with st.expander("查看完整报告", expanded=True):
            st.markdown(report)

        col1, col2, col3 = st.columns(3)
        with col1:
            safe_symbol = result["symbol"].replace("/", "_")
            st.download_button("下载 Markdown", data=report,
                file_name=f"{safe_symbol}_报告.md", mime="text/markdown", use_container_width=True)
        with col2:
            try:
                pdf_path = export_report_pdf(report, f"reports/{safe_symbol}_report.pdf")
                with open(pdf_path, "rb") as f:
                    st.download_button("下载 PDF", data=f.read(),
                        file_name=f"{safe_symbol}_报告.pdf", mime="application/pdf", use_container_width=True)
            except Exception:
                st.caption("PDF 导出暂不可用")
        with col3:
            if st.button("清除结果", key="clear_result", use_container_width=True):
                st.session_state.analysis_result = None
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Bottom actions ──
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("重新配置", use_container_width=True, key="reconfig_btn"):
            st.session_state.config_complete = False
            st.session_state.wizard_step = 0
            st.rerun()
    with col2:
        if st.button("合规扫描", use_container_width=True, key="compliance_btn"):
            from src.compliance.phrase_checker import scan_project
            violations = scan_project()
            if violations:
                st.warning(f"发现 {len(violations)} 个合规问题")
                for v in violations:
                    st.caption(f"- {v.phrase}")
            else:
                st.success("合规扫描通过")
    with col3:
        if st.button("重置配置", type="secondary", use_container_width=True, key="reset_btn"):
            from src.core.config_manager import clear_config
            clear_config()
            st.session_state.config_complete = False
            st.rerun()

    # Footer disclaimer
    st.markdown(f'<div class="disclaimer-footer">{get_ui_disclaimer()}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
