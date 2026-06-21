"""Post-configuration home page.

Real stock analysis with multi-market support (A-shares, US, HK).
"""

from __future__ import annotations

import sys
import os
import json
import time
import threading
from datetime import datetime
from pathlib import Path

import streamlit as st

from src.core.config_manager import load_config, get_key_status, ProviderStatus
from src.compliance.disclaimer import get_ui_disclaimer

# Ensure TradingAgents-CN is on path (external dependency)
# When installed via pip, it's on sys.path already.
# When running from source, look in sibling directory.
_TA_PATH = Path(__file__).resolve().parent.parent.parent.parent / "TradingAgents-CN"
if _TA_PATH.is_dir() and str(_TA_PATH) not in sys.path:
    sys.path.insert(0, str(_TA_PATH))

# Check TradingAgents-CN availability
_TA_AVAILABLE = False
try:
    from tradingagents.graph.trading_graph import TradingAgentsGraph
    from tradingagents.default_config import DEFAULT_CONFIG
    _TA_AVAILABLE = True
except ImportError:
    pass

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


# Module-level mailbox for thread-safe result passing
# Python GIL makes simple assignments atomic across threads.
# This avoids Streamlit's non-thread-safe st.session_state and file I/O races.
_ANALYSIS_MAILBOX: dict | None = None


def _run_analysis(symbol: str, stock_name: str, market: str, depth: int):
    """Run TradingAgents-CN analysis in background thread. Result goes to _ANALYSIS_MAILBOX."""
    global _ANALYSIS_MAILBOX
    if not _TA_AVAILABLE:
        _ANALYSIS_MAILBOX = {"error": "TradingAgents-CN 未安装。请在终端运行: pip install git+https://github.com/hsliuping/TradingAgents-CN.git@v1.0.1"}
        return
    try:
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,eastmoney.com,push2.eastmoney.com,gtimg.cn,sinaimg.cn,api.tushare.pro,baostock.com,api.deepseek.com")

        config = load_config()
        ds_key = config.get("deepseek_api_key", "") or os.getenv("DEEPSEEK_API_KEY", "")
        if not ds_key:
            _ANALYSIS_MAILBOX = {"error": "未配置 DeepSeek API Key"}
            return

        ta_config = DEFAULT_CONFIG.copy()
        ta_config["llm_provider"] = "deepseek"
        ta_config["backend_url"] = "https://api.deepseek.com"
        ta_config["deep_think_llm"] = "deepseek-chat"
        ta_config["quick_think_llm"] = "deepseek-chat"
        ta_config["max_debate_rounds"] = max(1, min(3, depth // 2))
        ta_config["online_tools"] = False
        ta_config["online_news"] = False
        ta_config["realtime_data"] = False
        os.environ["DEEPSEEK_API_KEY"] = ds_key

        ta = TradingAgentsGraph(debug=False, config=ta_config)
        final_state, decision = ta.propagate(symbol, "2025-06-18")

        # Extract decision fields
        safe_decision: dict = {}
        if isinstance(decision, dict):
            for k, v in decision.items():
                if isinstance(v, (str, int, float, bool, type(None))):
                    safe_decision[k] = v
                else:
                    safe_decision[k] = str(v)[:500]

        # Extract agent reports from final_state
        agent_reports = {}
        for key in ["market_report", "sentiment_report", "news_report",
                     "fundamentals_report", "trader_investment_plan",
                     "bull_history", "bear_history", "judge_decision",
                     "final_trade_decision"]:
            val = final_state.get(key, "")
            agent_reports[key] = str(val) if val else ""

        _ANALYSIS_MAILBOX = {
            "symbol": symbol,
            "stock_name": stock_name,
            "market": market,
            "decision": safe_decision,
            "agent_reports": agent_reports,
        }

    except Exception as e:
        _ANALYSIS_MAILBOX = {"error": str(e)}


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

    # ── System Status Panel ──
    with st.expander("系统状态", expanded=not _TA_AVAILABLE):
        col1, col2 = st.columns(2)
        with col1:
            # GPU
            try:
                from src.plugins.kronos_service.gpu_detector import detect_gpu, format_gpu_summary
                gpu_info = detect_gpu()
                if gpu_info.available:
                    st.markdown(f'<span style="color:#4caf50;">✅ GPU: {gpu_info.name} ({gpu_info.vram_gb:.0f}GB)</span>', unsafe_allow_html=True)
                else:
                    st.caption("⬜ GPU: 未检测到（将使用统计基线引擎）")
            except Exception:
                st.caption("⬜ GPU: 检测不可用")
            # TA engine
            if _TA_AVAILABLE:
                st.markdown(f'<span style="color:#4caf50;">✅ 分析引擎: TradingAgents-CN</span>', unsafe_allow_html=True)
            else:
                st.warning("❌ 分析引擎: 未安装 TradingAgents-CN")
                st.caption("请在终端运行: pip install git+https://github.com/hsliuping/TradingAgents-CN.git@v1.0.1")
        with col2:
            # Network
            try:
                import urllib.request
                urllib.request.urlopen("https://api.deepseek.com", timeout=3)
                st.markdown(f'<span style="color:#4caf50;">✅ 网络: DeepSeek API 可达</span>', unsafe_allow_html=True)
            except Exception:
                st.caption("⬜ 网络: 无法连接到 DeepSeek API")
            # Disk
            try:
                import shutil
                free_gb = shutil.disk_usage(Path.home()).free / (1024**3)
                st.caption(f"磁盘可用: {free_gb:.1f} GB")
            except Exception:
                st.caption("磁盘: 检测不可用")

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
    analysis_running = st.session_state.get("analysis_running", False)
    analyze_disabled = analysis_running or not symbol or not _TA_AVAILABLE
    if not _TA_AVAILABLE:
        st.caption("⚠️ 需要安装 TradingAgents-CN 才能分析。请参阅安装指南。")
    if st.button("开始分析", type="primary", disabled=analyze_disabled, use_container_width=True, key="analyze_btn"):
        if not symbol:
            st.error("请输入股票代码")
        elif not _TA_AVAILABLE:
            st.error("TradingAgents-CN 未安装。请在终端运行: pip install git+https://github.com/hsliuping/TradingAgents-CN.git@v1.0.1")
        elif not key_status.get("deepseek") == ProviderStatus.CONFIGURED:
            st.error("请先配置 DeepSeek API Key（配置向导）")
        else:
            global _ANALYSIS_MAILBOX
            _ANALYSIS_MAILBOX = None
            st.session_state.analysis_running = True
            st.session_state.analysis_result = None
            st.session_state.analysis_error = None
            thread = threading.Thread(
                target=_run_analysis,
                args=(symbol, stock_name or symbol, market_info["market"], depth),
                daemon=True,
            )
            thread.start()
            st.rerun()

    # ── Progress display ──
    if st.session_state.get("analysis_running"):
        # Check mailbox for result (written by background thread)
        if _ANALYSIS_MAILBOX is not None:
            result = _ANALYSIS_MAILBOX
            if result.get("error"):
                st.session_state.analysis_error = result["error"]
            else:
                st.session_state.analysis_result = result
            st.session_state.analysis_running = False
            st.rerun()

        st.markdown('<div class="progress-box">', unsafe_allow_html=True)
        st.info("⏳ 正在分析中...")
        st.caption("分析通常需要 3-5 分钟。页面每 5 秒自动刷新。")
        st.markdown('</div>', unsafe_allow_html=True)
        time.sleep(5)
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
        reports = result.get("agent_reports", {})

        st.success(f"✅ {result['symbol']} {result['stock_name']} 分析完成")

        from src.report.pdf_exporter import export_report_pdf, export_report_markdown

        # Build report from agent reports
        direction_map = {"卖出": "看空", "买入": "看多", "持有": "中性"}
        action = decision.get("action", "中性")
        direction = direction_map.get(str(action), "中性")
        confidence = decision.get("confidence", 0.5)
        reasoning = decision.get("reasoning", "")
        risk = decision.get("risk_score", 0.5)
        tp = decision.get("target_price")

        # Assemble full report
        parts = [
            f"# QuantSage 研究报告",
            f"**股票代码**: {result['symbol']}  **股票名称**: {result.get('stock_name', result['symbol'])}  **分析日期**: {datetime.now().strftime('%Y-%m-%d')}",
            "---",
        ]

        # Market / Technical
        if reports.get("market_report"):
            parts.append("## 技术面分析")
            parts.append(reports["market_report"])
            parts.append("")

        # Fundamentals
        if reports.get("fundamentals_report"):
            parts.append("## 基本面分析")
            parts.append(reports["fundamentals_report"])
            parts.append("")

        # Sentiment
        if reports.get("sentiment_report"):
            parts.append("## 情绪面分析")
            parts.append(reports["sentiment_report"])
            parts.append("")

        # News
        if reports.get("news_report") and len(reports["news_report"]) > 10:
            parts.append("## 新闻分析")
            parts.append(reports["news_report"])
            parts.append("")

        # Risk / Final Decision
        if reports.get("final_trade_decision") or reports.get("judge_decision"):
            parts.append("## 风险管控与最终决策")
            if reports.get("final_trade_decision"):
                parts.append(reports["final_trade_decision"])
            elif reports.get("judge_decision"):
                parts.append(reports["judge_decision"])
            parts.append("")

        # Conclusion
        parts.append("---")
        parts.append("## 综合结论")
        parts.append(f"**最终观点**: {direction}")
        parts.append(f"**置信度**: {confidence:.0%}")
        parts.append(f"**风险评分**: {risk:.1%}")
        if tp:
            parts.append(f"**参考价位**: ¥{tp:,.2f}")
        if reasoning:
            parts.append(f"**综合推理**: {reasoning}")
        parts.append("")
        parts.append("---")
        parts.append("> 本报告由 QuantSage 自动生成，仅供参考研究，不构成任何投资建议，盈亏自负。")
        parts.append("*QuantSage · 仅供参考研究 · 不构成投资建议*")

        report = "\n\n".join(parts)

        with st.expander("查看完整报告", expanded=True):
            st.markdown(report)

        col1, col2, col3 = st.columns(3)
        safe_symbol = result["symbol"].replace("/", "_")
        with col1:
            st.download_button("下载 Markdown", data=report,
                file_name=f"{safe_symbol}_报告.md", mime="text/markdown", use_container_width=True)
        with col2:
            try:
                pdf_path = export_report_pdf(report, f"reports/{safe_symbol}_report.pdf")
                with open(pdf_path, "rb") as f:
                    st.download_button("下载 PDF", data=f.read(),
                        file_name=f"{safe_symbol}_报告.pdf", mime="application/pdf", use_container_width=True)
            except Exception as e:
                st.caption(f"PDF 导出暂不可用: {e}")
        with col3:
            if st.button("清除结果", key="clear_result", use_container_width=True):
                st.session_state.analysis_result = None
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Plugin Manager Toggle ──
    if st.session_state.get("show_plugin_manager", False):
        from src.ui.plugin_manager import show_plugin_manager
        show_plugin_manager()
        st.markdown(f'<div class="disclaimer-footer">{get_ui_disclaimer()}</div>', unsafe_allow_html=True)
        if st.button("← 返回首页", use_container_width=True, key="back_home_btn"):
            st.session_state.show_plugin_manager = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

    # ── Bottom actions ──
    col1, col2, col3, col4 = st.columns(4)
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
        if st.button("插件管理", use_container_width=True, key="plugin_mgr_btn"):
            st.session_state.show_plugin_manager = True
            st.rerun()
    with col4:
        if st.button("重置配置", type="secondary", use_container_width=True, key="reset_btn"):
            from src.core.config_manager import clear_config
            clear_config()
            st.session_state.config_complete = False
            st.rerun()

    # Footer disclaimer
    st.markdown(f'<div class="disclaimer-footer">{get_ui_disclaimer()}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
