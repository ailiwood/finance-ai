"""3-step graphical configuration wizard.

Steps:
1. LLM Key: provider selection + API key entry + connection test
2. Data Source: AkShare (free/default) + Tushare (optional)
3. Risk Preference: risk level + analysis depth
"""

from __future__ import annotations

import streamlit as st
from typing import Optional

from src.core.config_manager import (
    QuantSageConfig, LLMProvider, RiskLevel, ProviderStatus,
    save_config, validate_api_key, test_llm_connection, get_key_status,
    is_configured,
)
from src.compliance.disclaimer import get_ui_disclaimer

TOTAL_STEPS = 3


CSS_WIZARD = """
<style>
.wizard-container {
    max-width: 700px;
    margin: 2vh auto;
    padding: 1.5rem 2rem;
    background: #1a1a2e;
    border-radius: 12px;
    border: 1px solid #333;
}
.wizard-title {
    text-align: center;
    color: #e0e0e0;
    font-size: 1.6rem;
    margin-bottom: 0.5rem;
}
.step-indicator {
    text-align: center;
    color: #aaa;
    font-size: 0.9rem;
    margin-bottom: 1.5rem;
}
.form-section {
    background: #0f0f1a;
    border: 1px solid #2a2a3e;
    border-radius: 8px;
    padding: 1.2rem;
    margin-bottom: 1rem;
}
.nav-buttons {
    display: flex;
    gap: 1rem;
    justify-content: center;
    margin-top: 1.5rem;
}
.info-box {
    background: #1a2744;
    border-left: 3px solid #4a90d9;
    padding: 0.8rem 1rem;
    border-radius: 4px;
    font-size: 0.85rem;
    color: #b0c8e8;
    margin: 1rem 0;
}
.status-ok { color: #4caf50; font-weight: bold; }
.status-warn { color: #ff9800; font-weight: bold; }
.status-error { color: #f44336; font-weight: bold; }
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


def _init_wizard_state() -> None:
    """Initialize wizard session state if not set."""
    if "wizard_step" not in st.session_state:
        st.session_state.wizard_step = 0
    if "wizard_config" not in st.session_state:
        st.session_state.wizard_config = {
            "deepseek_api_key": "",
            "deepseek_base_url": "https://api.deepseek.com",
            "deepseek_enabled": True,
            "dashscope_api_key": "",
            "default_china_data_source": "akshare",
            "tushare_token": "",
            "risk_level": "moderate",
            "analysis_depth": 3,
            "kronos_enabled": False,
            "kronos_gpu_device": "auto",
            "kronos_model": "kronos_mini",
            "finbert_enabled": False,
            "finbert_gpu_device": "auto",
            "finbert_model": "ProsusAI/finbert",
            "cache_dir": "./cache",
            "cache_ttl": 3600,
            "log_level": "INFO",
        }
    if "wizard_key_status" not in st.session_state:
        st.session_state.wizard_key_status = None


def _render_progress() -> None:
    """Render the progress bar at the top of the wizard."""
    step = st.session_state.wizard_step
    progress = step / (TOTAL_STEPS - 1) if step > 0 else 0.0
    if step == 0:
        progress = 0.0
    elif step == 1:
        progress = 0.5
    else:
        progress = 1.0

    st.progress(progress)
    step_labels = ["LLM 密钥", "数据源", "风险偏好"]
    labels_html = ""
    for i, label in enumerate(step_labels):
        if i < step:
            style = "color: #4caf50;"
        elif i == step:
            style = "color: #fff; font-weight: bold;"
        else:
            style = "color: #666;"
        labels_html += f'<span style="{style} margin: 0 24px;">{label}</span>'

    st.markdown(
        f'<div style="text-align:center; margin: 0.5rem 0 1.5rem 0;">{labels_html}</div>',
        unsafe_allow_html=True,
    )
    st.caption(f"步骤 {step + 1}/{TOTAL_STEPS}")


# === Step 1: LLM Key ===

def _show_step_llm() -> None:
    """Step 1: LLM provider selection and API key entry."""
    st.markdown("### 步骤 1: 配置大模型 API Key")

    config = st.session_state.wizard_config

    # Provider selection
    provider = st.selectbox(
        "LLM 提供商",
        options=["deepseek", "dashscope"],
        format_func=lambda x: {
            "deepseek": "DeepSeek (推荐，性价比高)",
            "dashscope": "阿里百炼 (国产稳定)",
        }.get(x, x),
        key="wizard_provider",
    )

    # API key input
    api_key_field = "deepseek_api_key" if provider == "deepseek" else "dashscope_api_key"
    current_key = config.get(api_key_field, "")

    api_key = st.text_input(
        "API Key",
        type="password",
        placeholder="sk-..." if provider == "deepseek" else "sk-...",
        key=f"wizard_key_{provider}",
    )

    # Show masked key hint
    if api_key and len(api_key) > 8:
        masked = api_key[:3] + "*" * (len(api_key) - 8) + api_key[-4:]
        st.caption(f"已输入: {masked}")

    # Info expander
    with st.expander("如何获取 API Key?"):
        if provider == "deepseek":
            st.markdown("""
            **DeepSeek API Key 获取步骤：**
            1. 访问 [platform.deepseek.com](https://platform.deepseek.com/)
            2. 注册账号并登录
            3. 进入 API Keys 页面
            4. 创建新的 API Key，复制保存
            """)
        else:
            st.markdown("""
            **阿里百炼 API Key 获取步骤：**
            1. 访问 [dashscope.aliyun.com](https://dashscope.aliyun.com/)
            2. 注册阿里云账号并开通百炼服务
            3. 进入 API-KEY 管理页面
            4. 创建新的 API Key，复制保存
            """)

    # Test connection button
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("测试连接", type="secondary", key="test_conn"):
            if not api_key:
                st.error("请先输入 API Key")
            elif not validate_api_key(provider, api_key):
                st.error("API Key 为空或仍为占位符，请填写真实密钥")
            else:
                with st.spinner("正在测试连接..."):
                    success, msg = test_llm_connection(provider, api_key)
                    if success:
                        st.session_state.wizard_key_status = "ok"
                        st.success(f"✅ {msg}")
                    else:
                        st.session_state.wizard_key_status = "error"
                        st.error(f"❌ {msg}")

    # Status display
    if st.session_state.wizard_key_status == "ok":
        st.markdown('<span class="status-ok">✅ 连接验证通过</span>', unsafe_allow_html=True)
    elif st.session_state.wizard_key_status == "error":
        st.markdown('<span class="status-warn">⚠️ 连接失败，您可以跳过测试直接继续</span>', unsafe_allow_html=True)

    # Save to config on next
    if api_key:
        config[api_key_field] = api_key
        if provider == "deepseek":
            config["deepseek_enabled"] = True
        else:
            config["dashscope_enabled"] = True


# === Step 2: Data Source ===

def _show_step_data() -> None:
    """Step 2: Data source configuration."""
    st.markdown("### 步骤 2: 配置数据源")

    config = st.session_state.wizard_config

    # AkShare (free, default)
    st.markdown('<div class="form-section">', unsafe_allow_html=True)
    st.markdown("#### AkShare (免费数据源)")

    use_akshare = st.checkbox(
        "启用 AkShare（免费，无需 API Key，默认推荐）",
        value=config.get("default_china_data_source", "akshare") == "akshare",
        key="use_akshare",
    )
    st.caption("AkShare 提供免费的中国A股数据，包括实时行情、历史K线、财务数据等。")

    if use_akshare:
        config["default_china_data_source"] = "akshare"
        st.markdown('<span class="status-ok">✅ AkShare 已启用</span>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Tushare (optional)
    st.markdown('<div class="form-section">', unsafe_allow_html=True)
    st.markdown("#### Tushare (专业数据源，可选)")

    tushare_expander = st.expander("Tushare 配置（进阶用户可选）", expanded=False)
    with tushare_expander:
        tushare_token = st.text_input(
            "Tushare Token",
            type="password",
            placeholder="输入你的 Tushare Token",
            value=config.get("tushare_token", ""),
            key="wizard_tushare",
        )
        if tushare_token:
            config["tushare_token"] = tushare_token
            st.caption("Token 已保存，将在分析时使用。")

        st.markdown("""
        **获取 Tushare Token：**
        1. 访问 [tushare.pro](https://tushare.pro/)
        2. 注册账号并邮箱验证
        3. 在个人中心获取 Token
        4. 免费用户有调用频率限制
        """)
    st.markdown("</div>", unsafe_allow_html=True)


# === Step 3: Risk Preference ===

def _show_step_risk() -> None:
    """Step 3: Risk preference and analysis depth."""
    st.markdown("### 步骤 3: 风险偏好设置")

    config = st.session_state.wizard_config

    st.markdown('<div class="form-section">', unsafe_allow_html=True)

    # Risk level
    risk_options = {
        "conservative": "保守 — 侧重基本面深度分析，谨慎评估风险",
        "moderate": "平衡 — 综合基本面与技术面，均衡判断",
        "aggressive": "积极 — 广泛扫描市场信号，侧重动量方向",
    }
    risk_level = st.radio(
        "风险偏好",
        options=list(risk_options.keys()),
        format_func=lambda x: risk_options[x],
        index=list(risk_options.keys()).index(config.get("risk_level", "moderate")),
        key="wizard_risk",
    )
    config["risk_level"] = risk_level

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="form-section">', unsafe_allow_html=True)

    # Analysis depth
    depth = st.slider(
        "分析深度 (1-5)",
        min_value=1,
        max_value=5,
        value=config.get("analysis_depth", 3),
        step=1,
        key="wizard_depth",
        help="""
        1: 快速扫描 (约1分钟)
        3: 标准分析 (约3-5分钟)
        5: 深度研究 (约5-10分钟)
        """,
    )
    config["analysis_depth"] = depth

    # Depth descriptions
    depth_descriptions = {
        1: "基础技术指标 + 简要基本面",
        2: "技术分析 + 基本面概览 + 新闻情绪",
        3: "全面技术分析 + 详细基本面 + 新闻 + 多轮辩论",
        4: "深度分析 + 社交媒体情绪 + 历史对比",
        5: "全维度深度研究 + 最大辩论轮次 + 风险情景分析",
    }
    st.caption(f"当前深度: {depth_descriptions[depth]}")

    st.markdown("</div>", unsafe_allow_html=True)

    # Kronos plugin toggle
    st.markdown('<div class="form-section">', unsafe_allow_html=True)
    kronos_enabled = st.checkbox(
        "启用 Kronos K线预测 (GPU 加速，可选)",
        value=config.get("kronos_enabled", False),
        key="wizard_kronos",
        help="需要 NVIDIA GPU + PyTorch。无 GPU 时自动降级为统计基线模型。",
    )
    config["kronos_enabled"] = kronos_enabled
    if kronos_enabled:
        st.caption("✅ 将在分析时调用 Kronos 预测服务 (需单独启动微服务)")
        config["kronos_gpu_device"] = st.selectbox(
            "GPU 设备",
            options=["auto", "cuda:0", "cpu"],
            index=0,
            key="wizard_kronos_device",
        )
    else:
        st.caption("K线预测功能未启用。可在后续设置中开启。")
    st.markdown("</div>", unsafe_allow_html=True)

    # FinBERT plugin toggle
    st.markdown('<div class="form-section">', unsafe_allow_html=True)
    finbert_enabled = st.checkbox(
        "启用 FinBERT 情绪分析 (GPU 加速，可选)",
        value=config.get("finbert_enabled", False),
        key="wizard_finbert",
        help="使用 FinBERT 模型分析财经新闻情绪。需要 transformers + PyTorch。",
    )
    config["finbert_enabled"] = finbert_enabled
    if finbert_enabled:
        st.caption("✅ 将在分析时调用 FinBERT 情绪分析服务 (需单独启动微服务)")
        config["finbert_model"] = st.selectbox(
            "模型",
            options=["ProsusAI/finbert", "rule_based"],
            index=0,
            key="wizard_finbert_model",
        )
    else:
        st.caption("情绪分析功能未启用。可在后续设置中开启。")
    st.markdown("</div>", unsafe_allow_html=True)


# === Main Wizard Entry ===

def show_wizard() -> Optional[QuantSageConfig]:
    """Main wizard entry point.

    Renders the 3-step configuration wizard with progress indicator.
    Returns completed config dict when wizard finishes, or None.
    """
    _init_wizard_state()
    st.markdown(CSS_WIZARD, unsafe_allow_html=True)

    st.markdown('<div class="wizard-container">', unsafe_allow_html=True)

    # Title
    st.markdown(
        '<h1 class="wizard-title">QuantSage 配置向导</h1>',
        unsafe_allow_html=True,
    )

    # Info box for first-time users
    if st.session_state.wizard_step == 0:
        st.markdown(
            '<div class="info-box">'
            '至少需要配置一个 LLM 提供商才能使用 QuantSage。<br>'
            '如果您还没有 API Key，请前往对应平台注册获取。'
            '</div>',
            unsafe_allow_html=True,
        )

    # Progress indicator
    _render_progress()

    # Render current step
    step = st.session_state.wizard_step
    if step == 0:
        _show_step_llm()
    elif step == 1:
        _show_step_data()
    elif step == 2:
        _show_step_risk()

    # Navigation buttons
    st.markdown('<div class="nav-buttons">', unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if step > 0:
            if st.button("上一步", use_container_width=True):
                st.session_state.wizard_step -= 1
                st.rerun()

    with col3:
        if step < TOTAL_STEPS - 1:
            if st.button("下一步", type="primary", use_container_width=True):
                # Validate before proceeding
                if step == 0:
                    config = st.session_state.wizard_config
                    has_key = (
                        (config.get("deepseek_api_key") and validate_api_key("deepseek", config["deepseek_api_key"]))
                        or (config.get("dashscope_api_key") and validate_api_key("dashscope", config["dashscope_api_key"]))
                    )
                    if not has_key:
                        st.error("请至少输入一个有效的 API Key 后再继续")
                        st.stop()
                st.session_state.wizard_step += 1
                st.rerun()
        else:
            if st.button("完成配置", type="primary", use_container_width=True):
                config = st.session_state.wizard_config
                save_config(config)
                st.session_state.config_complete = True
                st.success("配置已保存！正在跳转...")
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    # Footer disclaimer
    st.markdown(
        f'<div class="disclaimer-footer">{get_ui_disclaimer()}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    return None
