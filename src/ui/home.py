"""Post-configuration home page.

Shows config summary, key status, and placeholder for future analysis UI.
"""

from __future__ import annotations

import streamlit as st

from src.core.config_manager import load_config, get_key_status, ProviderStatus
from src.compliance.disclaimer import get_ui_disclaimer


CSS_HOME = """
<style>
.home-container {
    max-width: 800px;
    margin: 2vh auto;
    padding: 1.5rem 2rem;
    background: #1a1a2e;
    border-radius: 12px;
    border: 1px solid #333;
}
.home-title {
    text-align: center;
    color: #e0e0e0;
    font-size: 1.8rem;
    margin-bottom: 0.5rem;
}
.config-card {
    background: #0f0f1a;
    border: 1px solid #2a2a3e;
    border-radius: 8px;
    padding: 1.2rem;
    margin-bottom: 1rem;
}
.card-title {
    color: #ccc;
    font-size: 1.1rem;
    margin-bottom: 0.8rem;
}
.status-ok { color: #4caf50; font-size: 1.2rem; }
.status-warn { color: #ff9800; font-size: 1.2rem; }
.status-error { color: #f44336; font-size: 1.2rem; }
.placeholder-card {
    background: #1a2744;
    border: 1px dashed #4a90d9;
    border-radius: 8px;
    padding: 1.5rem;
    text-align: center;
    margin: 1.5rem 0;
}
.disclaimer-footer {
    text-align: center;
    color: #888;
    font-size: 0.8rem;
    margin-top: 2rem;
    border-top: 1px solid #333;
    padding-top: 1rem;
}
</style>
"""


def show_home() -> None:
    """Render the post-configuration home page."""
    st.markdown(CSS_HOME, unsafe_allow_html=True)

    st.markdown('<div class="home-container">', unsafe_allow_html=True)

    # Title
    st.markdown(
        '<h1 class="home-title">QuantSage</h1>',
        unsafe_allow_html=True,
    )
    st.caption("多智能体股票研究辅助平台")

    # Config summary card
    config = load_config()
    key_status = get_key_status()

    st.markdown('<div class="config-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">配置概览</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        # LLM Status
        st.markdown("**LLM 提供商**")
        for provider, status in key_status.items():
            provider_name = {
                "deepseek": "DeepSeek",
                "dashscope": "阿里百炼",
            }.get(provider, provider)

            if status == ProviderStatus.CONFIGURED:
                st.markdown(f'<span class="status-ok">✅</span> {provider_name}', unsafe_allow_html=True)
            elif status == ProviderStatus.NOT_CONFIGURED:
                st.markdown(f'<span class="status-warn">⬜</span> {provider_name} (未配置)', unsafe_allow_html=True)
            else:
                st.markdown(f'<span class="status-error">❌</span> {provider_name} (配置有误)', unsafe_allow_html=True)

    with col2:
        # Data & Risk
        st.markdown("**数据源**")
        sources = []
        if config.get("default_china_data_source") == "akshare":
            sources.append("AkShare (免费)")
        if config.get("tushare_token"):
            sources.append("Tushare (已配置)")
        st.markdown(", ".join(sources) if sources else "未配置")

        st.markdown("**风险偏好**")
        risk_map = {"conservative": "保守", "moderate": "平衡", "aggressive": "积极"}
        st.markdown(risk_map.get(config.get("risk_level", "moderate"), "未知"))

        st.markdown("**分析深度**")
        st.markdown(f"等级 {config.get('analysis_depth', 3)}/5")

    st.markdown("</div>", unsafe_allow_html=True)

    # Plugin status
    st.markdown('<div class="config-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">插件状态</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        kronos_on = config.get("kronos_enabled", False)
        if kronos_on:
            st.markdown('<span class="status-ok">✅</span> Kronos K线预测: 已启用', unsafe_allow_html=True)
            st.caption(f"设备: {config.get('kronos_gpu_device', 'auto')}")
        else:
            st.markdown('<span class="status-warn">⬜</span> Kronos K线预测: 未启用', unsafe_allow_html=True)

    with col2:
        finbert_on = config.get("finbert_enabled", False)
        if finbert_on:
            st.markdown('<span class="status-ok">✅</span> FinBERT 情绪分析: 已启用', unsafe_allow_html=True)
        else:
            st.markdown('<span class="status-warn">⬜</span> FinBERT 情绪分析: 未启用 (M4)', unsafe_allow_html=True)

    # Check if Kronos service is reachable
    if kronos_on:
        try:
            from src.plugins.kronos_service.client import KronosClient
            client = KronosClient()
            if client.is_available():
                health = client.health()
                if health:
                    gpu_note = f"GPU: {health.get('gpu_name', 'N/A')}" if health.get('gpu_available') else "CPU only"
                    st.caption(f"Kronos 服务运行中 ({health.get('engine_name', '?')}, {gpu_note})")
            else:
                st.caption("⚠️ Kronos 服务未启动 (运行: uvicorn src.plugins.kronos_service.service:app --port 8100)")
        except Exception:
            st.caption("⚠️ 无法连接 Kronos 服务")

    st.markdown("</div>", unsafe_allow_html=True)

    # Report Demo section
    st.markdown('<div class="config-card">', unsafe_allow_html=True)
    st.markdown('<div class="card-title">报告与导出</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("生成示例报告", use_container_width=True):
            st.session_state.show_demo_report = True
    with col2:
        if st.button("合规扫描自检", use_container_width=True, type="secondary"):
            st.session_state.show_compliance_check = True

    # Demo report
    if st.session_state.get("show_demo_report"):
        with st.spinner("正在生成报告..."):
            from src.report.report_generator import generate_report
            from src.report.pdf_exporter import export_report_pdf, export_report_markdown

            # Sample analysis output from M1 test result
            sample_output = {
                "decision": {
                    "action": "卖出",
                    "target_price": 1100.0,
                    "confidence": 0.8,
                    "risk_score": 0.65,
                    "reasoning": "贵州茅台面临技术面、基本面、情绪面三重共振下行。批价下跌反映需求萎缩，高毛利放大风险。建议等待情绪指数降至3分以下、批价企稳后再考虑。",
                },
                "reasoning": "基本面：批价持续下跌、渠道库存压力；技术面：RSI超卖、均线空头排列；情绪面：散户乐观度6.5分说明抛压未充分释放。综合判断短期看空。",
            }

            report, data = generate_report(
                symbol="600519",
                stock_name="贵州茅台",
                analysis_output=sample_output,
                plugins_used=["kronos", "finbert"],
                gpu_used=True,
            )

            st.markdown("### 研究报告预览")
            with st.expander("查看完整报告", expanded=True):
                st.markdown(report)

            # Export buttons
            col1, col2 = st.columns(2)
            with col1:
                md_path = export_report_markdown(report, "reports/600519_report.md")
                st.download_button(
                    "下载 Markdown 报告",
                    data=report,
                    file_name="600519_报告.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with col2:
                pdf_path = export_report_pdf(report, "reports/600519_report.pdf")
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        "下载 PDF 报告",
                        data=f.read(),
                        file_name="600519_报告.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                    )

    # Compliance check
    if st.session_state.get("show_compliance_check"):
        from src.compliance.phrase_checker import scan_project

        violations = scan_project()
        if violations:
            st.warning(f"发现 {len(violations)} 个合规问题:")
            for v in violations:
                st.caption(f"  - {v.phrase} ({v.category})")
        else:
            st.success("合规扫描通过 — 未发现违规措辞")
        st.caption(f"免责声明: {get_ui_disclaimer()}")

    st.markdown("</div>", unsafe_allow_html=True)

    # Config actions
    col1, col2 = st.columns(2)
    with col1:
        if st.button("重新配置", use_container_width=True):
            st.session_state.config_complete = False
            st.session_state.wizard_step = 0
            st.rerun()
    with col2:
        if st.button("重置所有配置", type="secondary", use_container_width=True):
            from src.core.config_manager import clear_config
            clear_config()
            st.session_state.config_complete = False
            st.session_state.wizard_step = 0
            st.rerun()

    # Footer disclaimer
    st.markdown(
        f'<div class="disclaimer-footer">{get_ui_disclaimer()}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)
