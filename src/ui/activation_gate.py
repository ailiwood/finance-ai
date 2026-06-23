"""Activation gate — shown on first launch before main functionality.

Flow: Disclaimer → Activation Gate → Config Wizard → Home
If already activated (valid license on disk), pass through immediately.
"""

from __future__ import annotations

import streamlit as st

from src.core.device_id import get_device_code
from src.core.license import verify_license
from src.deployment.license import save_license, load_license


def is_activated() -> bool:
    """Check if the current installation has a valid, device-bound license."""
    info = load_license()
    if not info:
        return False
    key = info.get("key", "")
    if not key:
        return False
    result = verify_license(key, get_device_code())
    return result.get("valid", False)


def show_activation_gate() -> None:
    """Show activation page and block until activated. st.stop() if not activated."""
    if is_activated():
        return  # Already activated, pass through

    if st.session_state.get("activation_skipped", False):
        return  # User chose to skip, pass through

    st.markdown("""
    <style>
    .activation-box {
        max-width: 520px; margin: 4vh auto; padding: 2rem;
        background: #111827; border: 1px solid #1f2937; border-radius: 12px;
    }
    .activation-title { text-align: center; color: #e8eaed; font-size: 1.4rem; font-weight: 700; margin-bottom: 0.5rem; }
    .activation-subtitle { text-align: center; color: #9ca3af; font-size: 0.9rem; margin-bottom: 1.5rem; }
    .device-code-box {
        background: #0a0e1a; border: 2px solid #22d3ee; border-radius: 8px;
        padding: 14px 18px; margin: 12px 0; text-align: center;
    }
    .device-code-label { color: #9ca3af; font-size: 0.85rem; }
    .device-code-value { color: #22d3ee; font-size: 1.6rem; font-weight: 700; font-family: 'Consolas', monospace; letter-spacing: 2px; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="activation-box">', unsafe_allow_html=True)
    st.markdown('<div class="activation-title">激活 QuantSage</div>', unsafe_allow_html=True)
    st.markdown('<div class="activation-subtitle">购买许可证密钥以解锁全部功能</div>', unsafe_allow_html=True)

    # Device code display
    dev_code = get_device_code()
    st.markdown(f"""
    <div class="device-code-box">
        <div class="device-code-label">📟 本机设备码</div>
        <div class="device-code-value">{dev_code}</div>
    </div>
    """, unsafe_allow_html=True)

    # Copy button
    st.button("📋 复制设备码", key="copy_dev_code", use_container_width=True,
              on_click=lambda: _copy_to_clipboard(dev_code))

    # Purchase info
    with st.expander("💳 如何购买？", expanded=True):
        st.markdown("""
        **购买步骤：**
        1. 复制上方的**设备码**
        2. 联系开发者并提供设备码
           - 抖音号：**23230218947**
        3. 支付 **19.90 RMB**
        4. 开发者会发送给您一个**许可证密钥**
        5. 在下方输入密钥完成激活

        ⚠️ 一个密钥仅绑定一台设备，重装系统后设备码可能变化需重新激活。
        """)

    # Key input
    st.markdown("---")
    key_input = st.text_input(
        "许可证密钥",
        placeholder="QS.XXXX.XXXX.XXXX...",
        key="activation_key_input",
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("🔑 激活", type="primary", use_container_width=True, key="activate_btn"):
            _handle_activation(key_input, dev_code)
    with col2:
        if st.button("🔄 稍后激活", use_container_width=True, key="skip_activation"):
            st.warning("未激活状态下部分功能可能受限。您可以稍后在设置中完成激活。")
            st.session_state.activation_skipped = True
            st.rerun()

    # Error display
    if st.session_state.get("activation_error"):
        st.error(st.session_state.activation_error)
        st.session_state.activation_error = None

    st.markdown('</div>', unsafe_allow_html=True)

    # Block further execution
    st.stop()


def _handle_activation(key_input: str, dev_code: str) -> None:
    """Validate and persist license key."""
    key = key_input.strip()
    if not key:
        st.session_state.activation_error = "请输入许可证密钥。"
        return

    result = verify_license(key, dev_code)
    if not result.get("valid"):
        st.session_state.activation_error = f"激活失败：{result.get('reason', '未知错误')}"
        return

    # Save activation state
    save_license(key, dev_code)
    st.session_state.activation_skipped = False
    st.rerun()


def _copy_to_clipboard(text: str) -> None:
    """Copy text using Streamlit's built-in mechanism."""
    st.code(text, language=None)
    st.toast("设备码已显示在上方，请手动复制（Ctrl+C）", icon="📋")
