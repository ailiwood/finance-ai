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

# TradingAgents-CN is bundled directly in the exe — always available
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG
_TA_AVAILABLE = True

# Inline SVG icons (vector, any scale)
_ICON_FUNDAMENTALS = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#22d3ee" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="24" height="24"><path d="M4 20h16M5.5 18.5V11h13v7.5M3.5 11 12 5l8.5 6M8 18.5v-5h2.5v5M13.5 18.5v-5H16v5"/><path d="M15.5 8.5v-3h4v5"/><path d="M15.5 8.5h4"/></svg>'
_ICON_TECHNICAL = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#2f81f7" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="24" height="24"><path d="M3.5 3.5v17h17"/><path d="M5.5 16.5 9 12.5l3 2.2 5.5-7.2 2 1.5"/><rect x="6.25" y="11" width="2.5" height="3" rx=".5"/><rect x="10.25" y="10" width="2.5" height="2.5" rx=".5"/><rect x="14.25" y="11" width="2.5" height="2.5" rx=".5"/><rect x="17.75" y="7" width="2.5" height="2" rx=".5"/></svg>'
_ICON_SENTIMENT = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#39d0d8" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="24" height="24"><path d="M4 5.5h16v10.2a2 2 0 0 1-2 2H10l-4 3v-3.1a2 2 0 0 1-2-2V7.5a2 2 0 0 1 2-2Z"/><path d="M6.5 12h2l1.5-3 2.2 6 1.8-4h3.5"/></svg>'
_ICON_RISK = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#f87171" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" width="24" height="24"><path d="M12 3.5 19 6v5.3c0 4.4-2.9 7.6-7 9.2-4.1-1.6-7-4.8-7-9.2V6l7-2.5Z"/><path d="M12 7v5.3M12 16.2h.01" stroke-width="2.1"/></svg>'

def _card(title: str, icon_svg: str, content: str) -> str:
    """Render a styled card with SVG icon."""
    return f'<div class="quantsage-card"><div class="quantsage-card-header">{icon_svg} {title}</div>{content}</div>'

CSS_HOME = """
<style>
.home-container { max-width: 960px; margin: 2vh auto; padding: 1.5rem 2rem; }
.home-title { text-align: center; color: #e8eaed; font-size: 2rem; font-weight: 700; margin-bottom: 0.25rem; }
.home-subtitle { text-align: center; color: #9ca3af; font-size: 0.9rem; margin-bottom: 1.5rem; }
.config-card { background: #111827; border: 1px solid #1f2937; border-radius: 10px; padding: 1rem; margin-bottom: 0.75rem; }
.card-title { color: #e8eaed; font-size: 1rem; font-weight: 600; margin-bottom: 0.5rem; }
.status-ok { color: #34d399; }
.status-warn { color: #fbbf24; }
.status-error { color: #f87171; }
.analysis-card { background: #111827; border: 1px solid #1f2937; border-radius: 10px; padding: 1.25rem; margin-bottom: 1rem; }
.disclaimer-footer { text-align: center; color: #6b7280; font-size: 0.78rem; margin-top: 2rem; border-top: 1px solid #1f2937; padding-top: 1rem; }
.progress-box { background: #111827; border: 1px solid #fbbf24; border-radius: 8px; padding: 1.25rem; margin: 1rem 0; text-align: center; }
.quantsage-card { background: #111827; border: 1px solid #1f2937; border-radius: 10px; padding: 1.25rem; margin-bottom: 1rem; }
.quantsage-card-header { display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem; font-weight: 600; font-size: 1.1rem; color: #e8eaed; }
.quantsage-card-number { font-size: 1.4rem; font-weight: 700; color: #22d3ee; }
.quantsage-card-label { color: #9ca3af; font-size: 0.8rem; }
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

    # ── Generate trace ID for this analysis ──
    from src.monitor import new_trace, get_logger, mask_secret, log_data_shape
    trace = new_trace(symbol)
    log = get_logger("analysis")
    log.info("[START] analysis: symbol=%s, market=%s, depth=%d", symbol, market, depth)

    try:
        os.environ.setdefault("PYTHONIOENCODING", "utf-8")
        os.environ.setdefault("NO_PROXY", "localhost,127.0.0.1,eastmoney.com,push2.eastmoney.com,gtimg.cn,sinaimg.cn,api.tushare.pro,baostock.com,api.deepseek.com")

        config = load_config()
        ds_key = (config.get("deepseek_api_key", "") or os.getenv("DEEPSEEK_API_KEY", "")).strip()
        log.info("[KEY] deepseek key: %s", mask_secret(ds_key))
        if not ds_key:
            _ANALYSIS_MAILBOX = {"error": "未配置 DeepSeek API Key"}
            log.warning("[ABORT] no DeepSeek key configured")
            return
        ds_masked = ds_key[:4] + "****" + ds_key[-4:] if len(ds_key) > 8 else "****"
        print(f"[DEBUG] _run_analysis: DEEPSEEK_API_KEY len={len(ds_key)}, masked={ds_masked}")

        ta_config = DEFAULT_CONFIG.copy()
        ta_config["llm_provider"] = "deepseek"
        ta_config["backend_url"] = "https://api.deepseek.com"
        ta_config["deep_think_llm"] = "deepseek-chat"
        ta_config["quick_think_llm"] = "deepseek-chat"
        ta_config["max_debate_rounds"] = max(1, min(3, depth // 2))
        # Ensure LLM has enough output tokens for complete reports
        ta_config["deep_model_config"] = {"max_tokens": 8000, "temperature": 0.3, "timeout": 300}
        ta_config["quick_model_config"] = {"max_tokens": 8000, "temperature": 0.7, "timeout": 180}
        ta_config["online_tools"] = False
        ta_config["online_news"] = False
        ta_config["realtime_data"] = False
        os.environ["DEEPSEEK_API_KEY"] = ds_key

        # Tushare as primary A-share source when token available (more stable than AkShare)
        tushare_token = config.get("tushare_token", "")
        if tushare_token and not tushare_token.startswith("your_"):
            os.environ["TUSHARE_TOKEN"] = tushare_token
            ta_config["tushare_token"] = tushare_token
            ta_config["preferred_data_source"] = "tushare"
            os.environ["TA_PREFERRED_DATA_SOURCE"] = "tushare"

        # Disable curl_cffi to avoid eastmoney connection issues
        os.environ["AKSHARE_CURL_CFFI_DISABLED"] = "1"

        # Use most recent trading day (handle weekends/holidays)
        try:
            from src.data.market_data import get_kline as _get_kline_for_date
            _df = _get_kline_for_date(symbol, adjust="qfq", lookback_days=10)
            analysis_date = _df["date"].max().strftime("%Y-%m-%d")
        except Exception:
            # Fallback: if today is weekend, roll back to Friday
            from datetime import timedelta
            today = datetime.now()
            weekday = today.weekday()
            if weekday == 5:  # Saturday
                today = today - timedelta(days=1)
            elif weekday == 6:  # Sunday
                today = today - timedelta(days=2)
            analysis_date = today.strftime("%Y-%m-%d")

        # P0-A: Validate data BEFORE LLM analysis — never allow fabricated data
        try:
            from src.data.market_data import get_kline as _validate_kline
            _kline = _validate_kline(symbol, adjust="qfq", lookback_days=10)
            if _kline is None or _kline.empty or len(_kline) < 3:
                _ANALYSIS_MAILBOX = {
                    "error": (
                        f"数据获取失败：{symbol} 无有效K线数据。"
                        "可能原因：网络不通、非交易日、或代码错误。"
                        "请检查网络后重试，或在配置向导中填写 Tushare Token 作为备用数据源。"
                        "本次分析已终止以确保数据真实性。"
                    )
                }
                return
        except Exception as _e:
            _ANALYSIS_MAILBOX = {
                "error": f"数据获取失败: {str(_e)[:200]}。本次分析已终止。请检查网络或数据源配置。"
            }
            return

        ta = TradingAgentsGraph(debug=False, config=ta_config)
        final_state, decision = ta.propagate(symbol, analysis_date)

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
    st.markdown('<p class="home-subtitle">多智能体股票研究辅助平台</p>', unsafe_allow_html=True)

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
        # Sentiment sources
        try:
            from src.config.sentiment_sources import get_source_list
            st.caption(f"情绪源: {', '.join(s['label'][:12] for s in get_source_list()[:3])} ...")
        except Exception:
            pass

    # ── System Status Panel ──
    with st.expander("系统状态", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            # GPU / Hardware detection (三层方案: CPU默认→检测引导→用户升级)
            try:
                from src.deployment.gpu_upgrade import get_upgrade_info
                hw_info = get_upgrade_info()
                mode = hw_info["compute_mode"]
                gpu = hw_info["gpu_name"]

                if mode == "gpu_enabled":
                    st.markdown(
                        f'<span style="color:#4caf50;">GPU 加速已启用 ({gpu})</span>',
                        unsafe_allow_html=True,
                    )
                elif mode == "cpu_upgradable":
                    st.markdown(
                        f'<span style="color:#fbbf24;">检测到 {gpu}</span>'
                        f'<br><span style="color:#9ca3af;font-size:0.8rem;">当前: CPU 模式。可升级 GPU 版获得更快 K线预测速度</span>',
                        unsafe_allow_html=True,
                    )
                    # Upgrade button
                    if st.button("升级 GPU 版", type="secondary", key="gpu_upgrade_btn",
                                 help="安装 CUDA 版 PyTorch，下载约 2.5GB，需要 NVIDIA 驱动"):
                        st.session_state.show_gpu_upgrade = True
                        st.rerun()
                else:
                    st.caption("CPU 模式（适用于所有电脑）")
            except Exception:
                st.caption("CPU 模式")

            # TA engine (bundled)
            st.markdown(f'<span style="color:#4caf50;">分析引擎: TradingAgents-CN</span>', unsafe_allow_html=True)
            # Data source
            ds = config.get("default_china_data_source", "akshare")
            ds_names = {"akshare": "AkShare（免费，免注册）", "tushare": "Tushare", "baostock": "BaoStock"}
            ds_label = ds_names.get(ds, ds)
            if config.get("tushare_token"):
                st.markdown(f'<span style="color:#4caf50;">数据源: {ds_label}</span>', unsafe_allow_html=True)
            else:
                st.markdown(f'<span style="color:#4caf50;">数据源: {ds_label}</span>', unsafe_allow_html=True)
            st.caption("默认使用 AkShare 免费数据，覆盖A股/指数/基金。非交易日数据为空属正常。")
        with col2:
            # Network
            try:
                import urllib.request
                urllib.request.urlopen("https://api.deepseek.com", timeout=3)
                st.markdown(f'<span style="color:#4caf50;">网络: DeepSeek API 可达</span>', unsafe_allow_html=True)
            except Exception:
                st.caption("网络: 无法连接到 DeepSeek API")
            # Disk
            try:
                import shutil
                free_gb = shutil.disk_usage(Path.home()).free / (1024**3)
                st.caption(f"磁盘可用: {free_gb:.1f} GB")
            except Exception:
                st.caption("磁盘: 检测不可用")

    # ── GPU Upgrade Dialog ──
    if st.session_state.get("show_gpu_upgrade", False):
        st.markdown("---")
        st.markdown("### GPU 升级向导")
        try:
            from src.deployment.gpu_upgrade import check_upgrade_prerequisites, _DOWNLOAD_SIZE_GB, _CUDA_TAG

            ready, pre_msg = check_upgrade_prerequisites()
            st.info(pre_msg.replace("\n", "\n\n"))

            if ready:
                st.warning(
                    f"即将下载 CUDA 版 PyTorch（约 {_DOWNLOAD_SIZE_GB} GB），"
                    f"需要稳定的网络连接和较新的 NVIDIA 驱动。\n\n"
                    f"升级过程中请勿关闭应用。"
                )

                col_a, col_b, col_c = st.columns([1, 1, 2])
                with col_a:
                    if st.button("确认升级", type="primary", key="confirm_gpu_upgrade"):
                        st.session_state.gpu_upgrading = True
                        st.rerun()
                with col_b:
                    if st.button("取消", key="cancel_gpu_upgrade"):
                        st.session_state.show_gpu_upgrade = False
                        st.rerun()
            else:
                if st.button("关闭", key="close_gpu_info"):
                    st.session_state.show_gpu_upgrade = False
                    st.rerun()
        except Exception as e:
            st.error(f"硬件检测失败: {e}")
            if st.button("关闭", key="close_gpu_error"):
                st.session_state.show_gpu_upgrade = False
                st.rerun()

        st.markdown("---")

    # ── GPU Upgrade Execution ──
    if st.session_state.get("gpu_upgrading", False):
        st.markdown("### GPU 升级进行中...")
        progress_bar = st.progress(0.0)
        status_text = st.empty()

        def _ui_progress(msg: str, fraction: float):
            status_text.text(msg)
            progress_bar.progress(min(fraction, 1.0))

        try:
            from src.deployment.gpu_upgrade import upgrade_to_gpu
            success, message = upgrade_to_gpu(progress_callback=_ui_progress)

            if success:
                st.success(message)
                st.info("请重启应用以启用 GPU 加速。")
            else:
                st.error(message)
                st.info("CPU 版功能不受影响，可以继续使用。")
        except Exception as e:
            st.error(f"升级过程出现异常: {e}")
        finally:
            st.session_state.gpu_upgrading = False
            st.session_state.show_gpu_upgrade = False
            if st.button("确定", key="dismiss_gpu_result"):
                st.rerun()

        st.markdown("---")

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
    st.caption("ℹ️ A股交易日: 周一至周五 9:30-15:00（节假日无数据属正常现象）")

    # Auto-detect stock name
    stock_name = STOCK_NAMES.get(symbol, "")
    if not stock_name and symbol:
        st.caption("股票名称未知，将使用代码进行分析")

    # Analyze button
    analysis_running = st.session_state.get("analysis_running", False)
    analyze_disabled = analysis_running or not symbol
    if st.button("开始分析", type="primary", disabled=analyze_disabled, use_container_width=True, key="analyze_btn"):
        if not symbol:
            st.error("请输入股票代码")
        elif not key_status.get("deepseek") == ProviderStatus.CONFIGURED:
            ds_status = key_status.get("deepseek")
            if ds_status == ProviderStatus.INVALID:
                st.error("API Key 配置存在问题（空值或仍为占位符）。请通过配置向导重新填写。")
                if st.button("重置配置并重新设置", key="reset_config_btn"):
                    from src.core.config_manager import clear_config
                    clear_config()
                    st.session_state.config_complete = False
                    st.rerun()
            elif ds_status == ProviderStatus.NOT_CONFIGURED:
                st.error("未配置 DeepSeek API Key。请通过配置向导设置。")
            else:
                st.error(f"DeepSeek API Key 状态异常: {ds_status}")
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
        st.caption("分析通常需要 3-5 分钟。页面每 2 秒自动刷新。")
        st.markdown('</div>', unsafe_allow_html=True)
        time.sleep(2)
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

        # Sanitize decision dict
        try:
            from src.compliance.report_reviewer import sanitize_decision
            decision = sanitize_decision(decision)
        except Exception:
            pass

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
            parts.append(_card("📈 技术面分析", _ICON_TECHNICAL, reports["market_report"]))
            parts.append("")

        # Fundamentals
        if reports.get("fundamentals_report"):
            parts.append(_card("📊 基本面分析", _ICON_FUNDAMENTALS, reports["fundamentals_report"]))
            parts.append("")

        # Sentiment
        if reports.get("sentiment_report"):
            parts.append(_card("💬 情绪面分析", _ICON_SENTIMENT, reports["sentiment_report"]))
            parts.append("")

        # News
        if reports.get("news_report") and len(reports["news_report"]) > 10:
            parts.append("## 新闻分析")
            parts.append(reports["news_report"])
            parts.append("")

        # Risk / Final Decision
        if reports.get("final_trade_decision") or reports.get("judge_decision"):
            parts.append(_card("🛡️ 风险管控与最终决策", _ICON_RISK,
                reports.get("final_trade_decision") or reports.get("judge_decision", "")))
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

        # ── Multi-period tech indicators ──
        try:
            from src.data.market_data import get_kline as _kline_ind
            from src.analysis.indicators import compute_all_indicators
            _ind_df = _kline_ind(symbol, lookback_days=1100)
            indicators = compute_all_indicators(_ind_df)
            parts.append("## 📐 多周期技术指标汇总")
            for period, vals in indicators.items():
                if vals:
                    items = [f"**{period}**: " + " | ".join(f"{k}={v}" for k, v in list(vals.items())[:6])]
                    parts.extend(items)
            parts.append("")
            parts.append(f"*复权方式: 前复权(qfq) | 与同花顺/东方财富一致*")
            parts.append("")
        except Exception:
            pass

        report = "\n\n".join(parts)

        # ── Compliance review gate ──
        review_method = "skipped"
        try:
            from src.compliance.report_reviewer import review_and_sanitize
            report, review_method = review_and_sanitize(report)
        except Exception:
            pass  # Never block report output on compliance failure

        review_label = {
            "llm": "✅ 已通过 LLM 合规审查",
            "regex": "⚠️ LLM 审查不可用，已通过本地规则过滤",
            "skipped": "⚠️ 合规审查跳过",
        }.get(review_method, "")
        with st.expander(f"查看完整报告  {review_label}", expanded=True):
            st.markdown(report)

        col1, col2, col3 = st.columns(3)
        safe_symbol = result["symbol"].replace("/", "_")
        with col1:
            try:
                from src.report.pdf_exporter import export_report_markdown
                st.download_button("下载 Markdown", data=report,
                    file_name=f"{safe_symbol}_报告.md", mime="text/markdown", use_container_width=True)
            except Exception:
                st.download_button("下载 Markdown", data=report,
                    file_name=f"{safe_symbol}_报告.md", mime="text/markdown", use_container_width=True)
        with col2:
            try:
                from src.report.pdf_exporter import export_report_pdf
                pdf_path = export_report_pdf(report, f"reports/{safe_symbol}_report.pdf")
                with open(pdf_path, "rb") as f:
                    st.download_button("下载 PDF", data=f.read(),
                        file_name=f"{safe_symbol}_报告.pdf", mime="application/pdf", use_container_width=True)
            except Exception:
                st.caption("⚠️ PDF 导出组件暂不可用，请使用 Markdown 格式下载")
        with col3:
            if st.button("清除结果", key="clear_result", use_container_width=True):
                st.session_state.analysis_result = None
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Data Inspection Toggle ──
    if st.session_state.get("show_data_inspection", False):
        from src.ui.data_inspection import show_data_inspection
        show_data_inspection()
        st.markdown(f'<div class="disclaimer-footer">{get_ui_disclaimer()}</div>', unsafe_allow_html=True)
        if st.button("← 返回首页", key="back_home_inspect"):
            st.session_state.show_data_inspection = False
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
        return

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
    col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
    with col1:
        if st.button("重新配置", use_container_width=True, key="reconfig_btn"):
            st.session_state.config_complete = False
            st.session_state.wizard_step = 0
            st.rerun()
    with col2:
        if st.button("数据体检", use_container_width=True, key="data_inspect_btn"):
            st.session_state.show_data_inspection = True
            st.rerun()
    with col3:
        if st.button("合规扫描", use_container_width=True, key="compliance_btn"):
            from src.compliance.phrase_checker import scan_project
            violations = scan_project()
            if violations:
                st.warning(f"发现 {len(violations)} 个合规问题")
                for v in violations:
                    st.caption(f"- {v.phrase}")
            else:
                st.success("合规扫描通过")
    with col4:
        if st.button("插件管理", use_container_width=True, key="plugin_mgr_btn"):
            st.session_state.show_plugin_manager = True
            st.rerun()
    with col5:
        if st.button("重置配置", type="secondary", use_container_width=True, key="reset_btn"):
            from src.core.config_manager import clear_config
            clear_config()
            st.session_state.config_complete = False
            st.rerun()
    with col6:
        if st.button("金融学习", use_container_width=True, key="learn_btn"):
            st.session_state.show_learning = not st.session_state.get("show_learning", False)
            st.rerun()
    with col7:
        if st.button("诊断日志", use_container_width=True, key="diag_btn"):
            from src.monitor.diagnostics import export_diagnostics
            try:
                zip_path = export_diagnostics()
                with open(zip_path, "rb") as f:
                    st.download_button(
                        "下载诊断包 (ZIP)", data=f.read(),
                        file_name=zip_path.split("/")[-1].split("\\")[-1],
                        mime="application/zip",
                        use_container_width=True,
                    )
                st.success(f"诊断包已生成：{zip_path}")
            except Exception as e:
                st.error(f"生成诊断包失败：{e}")

    # ── Financial Learning Hub ──
    if st.session_state.get("show_learning", False):
        st.markdown("---")
        st.markdown("## 金融知识学习中心")
        st.caption(
            "以下学习资源仅供参考，不构成任何投资建议。"
            "请结合自身情况独立判断，盈亏自负。"
        )

        tab1, tab2, tab3, tab4 = st.tabs(["入门基础", "进阶分析", "高级量化", "常用术语速查"])

        # ── Tab 1: 入门基础 ──
        with tab1:
            st.markdown("### 中国官方投资者教育资源（推荐首选）")
            st.markdown("""
| 资源 | 说明 | 难度 | 语言 |
|------|------|------|------|
| [中国投资者网](https://www.investor.org.cn) | 证监会主办，投资者教育权威平台。涵盖市场规则、维权、基础知识 | 🟢入门 | 中 |
| [上交所投资者教育](https://edu.sse.com.cn) | 上海证券交易所官方出品。A股交易规则、信息披露、风险提示 | 🟢入门 | 中 |
| [深交所投教基地](http://investor.szse.cn) | 深圳证券交易所投资者教育中心。国家级互联网投教基地 | 🟢入门 | 中 |
| [中证中小投服中心](http://www.isc.com.cn) | 证监会直属，投资者保护机构。持股行权、纠纷调解、投教活动 | 🟢入门 | 中 |
| [华泰证券投教](https://www.htsc.com.cn/htscedu/) | 券商投教基地范例。课程体系完整，适合系统学习A股知识 | 🟢入门 | 中 |
| [东方财富投教](http://edu.18.cn/) | 互联网券商投教基地。结合行情软件讲解，实战导向 | 🟢入门 | 中 |
""")
            st.caption("以上均为证监会体系的官方或持牌投教平台，完全免费，内容适合A股散户入门。比通用金融课程更贴合中国市场规则。")

            st.markdown("### 国际通用金融入门")
            st.markdown("""
| 资源 | 说明 | 难度 | 语言 |
|------|------|------|------|
| [可汗学院 · 金融与资本市场](https://www.khanacademy.org/economics-finance-domain/core-finance) | 免费、零基础友好，解释股票/债券/市场基本运作原理 | 🟢入门 | 中/英 |
| [Investopedia 金融百科](https://www.investopedia.com/) | 全球最全面的金融词典，每个术语都有详细解释和案例 | 🟢入门 | 英 |
| [雪球 · 新手入门](https://xueqiu.com/topic/newbie) | 中文投资社区，大量A股实战经验分享 | 🟢入门 | 中 |

**价值投资经典入门**
| 资源 | 说明 | 难度 | 语言 |
|------|------|------|------|
| [聪明的投资者 (格雷厄姆)](https://book.douban.com/subject/5243775/) | 价值投资奠基之作，"安全边际"概念的源头 | 🟡进阶 | 中 |
| [彼得·林奇的成功投资](https://book.douban.com/subject/1052698/) | 最通俗易懂的选股逻辑，适合散户阅读 | 🟢入门 | 中 |
""")

        # ── Tab 2: 进阶分析 ──
        with tab2:
            st.markdown("### 基本面分析")
            st.markdown("""
| 资源 | 说明 | 难度 | 语言 |
|------|------|------|------|
| [东方财富 · 财务数据](https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html) | A股财报、PE/PB/ROE 免费查询，数据最全 | 🟡进阶 | 中 |
| [同花顺 · 个股F10](https://www.10jqka.com.cn/) | 完整的基本面数据面板，A股标配 | 🟡进阶 | 中 |
| [晨星中国](https://www.morningstar.cn/) | 专业基金/股票评级和分析，价值投资常用 | 🟡进阶 | 中 |
| [GuruFocus](https://www.gurufocus.com/) | 全球价值投资筛选工具，支持中文 | 🟡进阶 | 中/英 |
""")

            st.markdown("### 技术分析")
            st.markdown("""
| 资源 | 说明 | 难度 | 语言 |
|------|------|------|------|
| [TradingView 图表](https://www.tradingview.com/chart/) | 全球最大图表社区，实时K线、指标叠加、社区策略分享 | 🟡进阶 | 中/英 |
| [通达信公式教程](https://help.tdx.com.cn/) | A股最常用的技术分析软件，自定义公式编写 | 🟡进阶 | 中 |
| [技术面分析入门 (Investopedia)](https://www.investopedia.com/terms/t/technicalanalysis.asp) | MA/MACD/RSI/KDJ/BOLL 等核心指标的英文详解 | 🟡进阶 | 英 |
""")

            st.markdown("### 市场情绪与行为金融")
            st.markdown("""
| 资源 | 说明 | 难度 | 语言 |
|------|------|------|------|
| [思考，快与慢 (卡尼曼)](https://book.douban.com/subject/10785583/) | 诺贝尔奖得主的行为经济学经典 | 🔴高级 | 中 |
""")

        # ── Tab 3: 高级量化 ──
        with tab3:
            st.markdown("### 量化交易学习路径")
            st.markdown("""
| 资源 | 说明 | 难度 | 语言 |
|------|------|------|------|
| [JoinQuant 聚宽 · 课堂](https://www.joinquant.com/help) | 国内最大量化平台，中文教程 + 在线回测 | 🟡进阶 | 中 |
| [BigQuant · AI量化](https://bigquant.com/) | AI赋能量化投资，可视化策略搭建 | 🟡进阶 | 中 |
| [QuantConnect 学习中心](https://www.quantconnect.com/learning/) | 免费的量化交易课程，含Python示例代码 | 🔴高级 | 英 |
""")

            st.markdown("### Python 金融编程")
            st.markdown("""
| 资源 | 说明 | 难度 | 语言 |
|------|------|------|------|
| [QuantSage 开源项目](https://github.com/ailiwood/finance-ai) | 本项目代码仓库。基于 TradingAgents-CN 的本地股票分析工具 | 🔴高级 | 中 |
| [pandas 时间序列教程](https://pandas.pydata.org/docs/getting_started/intro_tutorials/09_timeseries.html) | Python数据处理库的金融时序分析基础 | 🟡进阶 | 英 |
""")

            st.markdown("### 数学与统计基础")
            st.markdown("""
| 资源 | 说明 | 难度 | 语言 |
|------|------|------|------|
| [3Blue1Brown · 线性代数 (B站)](https://space.bilibili.com/88461692) | 最直观的数学可视化，量化入门必看 | 🟢入门 | 中 |
| [MIT 18.06 线性代数](https://ocw.mit.edu/courses/18-06sc-linear-algebra-fall-2011/) | MIT经典公开课，量化交易数学基础 | 🔴高级 | 英 |
""")

        # ── Tab 4: 常用术语速查（就地可读） ──
        with tab4:
            st.markdown("### 现代金融体系基础")
            st.markdown("""
> **股票** — 公司所有权的小碎片。你买1股茅台，就是茅台的微型股东，公司赚钱你可能分红、股价涨你卖出赚差价。

> **债券** — 借条的正规说法。买国债 = 借钱给国家，到期还本付息，收益比银行存款高一点，风险低。

> **基金** — 把钱交给专业经理帮你投资。买一只基金等于同时持有几十上百只股票/债券，分散风险，适合没时间研究个股的人。

> **一级市场** — 公司首次发行股票（IPO）卖给投资人的市场。普通人一般参与不了，是机构的主场。

> **二级市场** — 就是我们每天交易的股市。股票在投资人之间买卖，公司不直接收钱。你打开同花顺看到的就是二级市场。

> **指数** — 用一篮子股票价格算出来的一个数，代表市场整体涨跌。沪深300 = 最大的300只A股，上证50 = 最大的50只沪市蓝筹，平常说的"大盘"通常指上证综指。
""")

            st.markdown("### 股市常见术语")
            st.markdown("""
> **开盘价** — 每天9:30集合竞价撮合出的第一笔成交价。**收盘价** — 15:00最后一笔成交价，也是计算涨跌幅的基准。

> **涨跌停** — A股每天最多涨/跌多少的硬限制。主板±10%，科创/创业板±20%，ST股±5%。达到涨跌停后当天不能再交易。

> **成交量** — 今天有多少股被买卖了。量放大说明市场关注度高，量萎缩说明冷清。一根大阳线配巨量比配缩量更有说服力。

> **换手率** — 成交量 ÷ 流通股本。5%以上算活跃，10%以上算热门。换手率太高可能有人在炒作，太低说明没人关注。

> **市值 / 流通市值** — 总市值 = 股价 × 全部股票数。流通市值 = 股价 × 市场上可交易的那部分。茅台总市值超万亿，是典型的"大市值"股。

> **除权除息** — 分红或送股后股价会调低（你手里多了股票或拿到了现金，总资产不变）。比如股价10元分红了1元，除息后交易日开盘参考价就是9元。

> **复权** — 把除权除息的缺口补回去，让你看到股票"真正的"历史涨幅。前复权以当前价为基准回溯，是同花顺/东方财富默认方式。

> **T+1** — A股今天买入，最早明天才能卖出（T是交易日，+1是下一个交易日）。这是硬规则，不是你可以选的。

> **做多** — 低买高卖，赚差价。绝大多数散户做的就是这个。**做空** — 借股票先卖出，等跌了再买回来还，赚下跌的钱。A股融券做空门槛高，普通人一般不做。

> **止损** — 亏到某个点就强制卖出，防止亏更多。比如买入100元，设止损95元，跌到95就卖。**止盈** — 反过来的，赚到目标价就锁定利润。

> **集合竞价** — 9:15-9:25之间，所有买卖委托汇集到一起，用最大成交量原则撮合出一个统一的开盘价。这是每天最重要的价格形成机制。
""")

            st.markdown("### 估值指标 — 怎么判断股票贵不贵？")
            st.markdown("""
> **PE（市盈率）** = 股价 ÷ 每股收益。意思是"按现在的盈利能力，多少年能回本"。PE=10意味着10年回本。同一行业PE越低越便宜，但高成长公司PE通常更高——因为市场预期未来利润会大增。不能跨行业比PE（银行和科技股的PE天生不同）。

> **PB（市净率）** = 股价 ÷ 每股净资产。意思是"市场给出的价格是公司实际资产的几倍"。PB<1叫"破净"，说明股价比公司净资产还低——可能是机会也可能是陷阱（资产质量差）。银行股PB常年低于1。

> **ROE（净资产收益率）** = 净利润 ÷ 净资产。衡量"公司用股东的钱创造了多少回报"。长期ROE>15%的公司属于"印钞机"级别（茅台的ROE长期30%+），<5%说明公司赚钱效率很低。

> **股息率** = 每股分红 ÷ 股价。有人买股票就是为了稳定收股息（像收房租），股息率越高"现金流回报"越好。银行、电力、高速路等成熟行业股息率普遍较高。

> **PEG** = PE ÷ 盈利增长率。把成长性纳入估值考量：PEG<1可能被低估，PEG>2可能偏贵。但前提是公司利润增长确实可持续——预测未来增长率是最大的不确定因素。
""")

            st.markdown("### 技术指标 — 大白话解释")
            st.markdown("""
> **MA（均线）** — 过去N天收盘价的平均值连成一条线。MA5反映短期趋势，MA20反映中期趋势，MA60反映长期趋势。股价在均线上方说明"站上均线"（偏强），在下方说明"跌破均线"（偏弱）。多条均线向上发散是典型的多头排列。

> **MACD** — 快线和慢线的关系图。快线上穿慢线 = "金叉"（通常看涨信号），快线下穿慢线 = "死叉"（通常看跌信号）。柱状图变长说明趋势在加强，变短说明趋势在衰减。本质上是在告诉你要不要跟趋势。

> **RSI（相对强弱）** — 一只股票最近是涨得太猛还是跌得太狠。0到100之间，高于70叫"超买"（可能该回调了），低于30叫"超卖"（可能该反弹了）。但强势股可以长期在70以上，弱势股也可以长期在30以下——不能只看这一个指标。

> **KDJ** — 和RSI类似，也是判断短期是否"涨过头"或"跌过头"的指标。K线上穿D线是金叉看涨，下穿是死叉看跌。KDJ比RSI更灵敏所以假信号也更多，通常配合趋势指标（如MACD）一起用。

> **BOLL（布林带）** — 在均线上下各画两条"轨道线"，股价大部分时间在轨道内波动。触及上轨 → 短期可能涨多了要回调，触及下轨 → 短期可能跌多了要反弹。带口收窄说明变盘在即（大波动要来），带口张开说明趋势正在展开。

> **成交量** — 价格的"燃料"。涨的时候放量说明买盘进场信心足（真实性高），涨的时候缩量说明没人跟（可能是假突破）。跌的时候放量说明恐慌盘在出（杀伤力大），跌的时候缩量说明抛压在减少（可能快见底）。量价配合是技术分析最基础也是最核心的判断标准。
""")

            st.markdown("### 交易常用词")
            st.markdown("""
> **仓位** — 你投入股市的资金占总资金的比例。满仓 = 全部买入、空仓 = 全部现金、半仓 = 一半股票一半现金。控制仓位就是控制风险暴露。

> **知行合一** — 知道该做什么就真的去做。很多人分析得头头是道但一开盘就冲动操作——这行最难的其实是执行纪律。

> **波段操作** — 在相对低点买、相对高点卖，赚中间"波段"的差价。介于长线持有和短线快进快出之间，是A股散户最常见的操作方式。

> **追涨杀跌** — 涨了才冲进去买、跌了就恐慌卖出——这是亏损之源。大资金最喜欢这类散户，因为他们提供流动性。
""")

        if st.button("收起学习中心", key="hide_learning"):
            st.session_state.show_learning = False
            st.rerun()

    # Footer disclaimer
    from src.compliance.disclaimer import get_ui_footer
    st.markdown(f'<div class="disclaimer-footer">{get_ui_footer()}</div>', unsafe_allow_html=True)

    # ── Live Log Monitor ──
    with st.expander("实时日志监控", expanded=False):
        st.caption("应用运行日志（文件: ~/.quantsage/logs/）。分析进行中时点击刷新查看进度。")

        col_r1, col_r2 = st.columns([1, 4])
        with col_r1:
            lines = st.selectbox("显示行数", [30, 50, 100, 200], index=1, key="log_lines")
            if st.button("刷新日志", key="refresh_log"):
                st.rerun()

        log_file = Path.home() / ".quantsage" / "logs" / f"quantsage_{datetime.now().strftime('%Y-%m-%d')}.log"
        if log_file.exists():
            try:
                content = log_file.read_text(encoding="utf-8")
                tail_lines = content.strip().splitlines()[-lines:]
                st.code("\n".join(tail_lines), language="text", line_numbers=False)
            except Exception:
                st.caption("(无法读取日志文件)")
        else:
            st.caption("(日志文件尚未生成)")

    st.markdown("</div>", unsafe_allow_html=True)
