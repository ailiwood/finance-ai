"""Activation gate — shown on first launch before main functionality.

Flow: Disclaimer → Activation Gate → Config Wizard → Home
If already activated (valid license on disk), pass through immediately.

Self-built payment flow (no third-party payment platform):
  1. User copies device code from this page
  2. User scans Alipay QR code, pays, puts device code in payment note
  3. User opens activation web page → submits device code as order
  4. Developer confirms payment → issues license via admin backend
  5. User queries activation web page with device code → gets license key
  6. User pastes license key here → client verifies with public key → activated!

The private key NEVER leaves the cloud. The client only verifies.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

import streamlit as st

from src.core.device_id import get_device_code
from src.core.license import verify_license
from src.deployment.license import save_license, load_license

# Cloud activation page URL (Cloudflare Workers *.workers.dev)
ACTIVATION_PAGE_URL = "https://quantsage-activation.lk166564317.workers.dev/"


def _get_qr_base64() -> str:
    """Load pay_img.jpg and return as base64 data URI.

    Searches: project root, next to exe (PyInstaller _MEIPASS), and CWD.
    Falls back to empty string if not found.
    """
    candidates = []
    # PyInstaller frozen build
    if getattr(__import__("sys"), "frozen", False):
        import sys as _sys
        if hasattr(_sys, "_MEIPASS"):
            candidates.append(Path(_sys._MEIPASS) / "pay_img.jpg")
    # Development: project root
    candidates.append(Path(__file__).resolve().parent.parent.parent / "pay_img.jpg")
    # Fallback: CWD
    candidates.append(Path("pay_img.jpg"))

    for p in candidates:
        if p.exists():
            try:
                data = p.read_bytes()
                return f"data:image/jpeg;base64,{base64.b64encode(data).decode('ascii')}"
            except Exception:
                pass
    return ""


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
        max-width: 580px; margin: 2vh auto; padding: 1.5rem 2rem;
        background: #111827; border: 1px solid #1f2937; border-radius: 12px;
    }
    .activation-title { text-align: center; color: #e8eaed; font-size: 1.4rem; font-weight: 700; margin-bottom: 0.3rem; }
    .activation-subtitle { text-align: center; color: #9ca3af; font-size: 0.85rem; margin-bottom: 1rem; }
    .device-code-box {
        background: #0a0e1a; border: 2px solid #22d3ee; border-radius: 8px;
        padding: 12px 16px; margin: 10px 0; text-align: center;
    }
    .device-code-label { color: #9ca3af; font-size: 0.85rem; }
    .device-code-value { color: #22d3ee; font-size: 1.5rem; font-weight: 700; font-family: 'Consolas', monospace; letter-spacing: 2px; }
    .activate-btn-link {
        display: inline-block; width: 100%; padding: 11px;
        background: linear-gradient(135deg, #0891b2, #06b6d4);
        border: none; border-radius: 8px;
        color: white; font-size: 0.95rem; font-weight: 600;
        text-align: center; text-decoration: none;
        cursor: pointer; transition: all 0.2s;
    }
    .activate-btn-link:hover {
        background: linear-gradient(135deg, #06b6d4, #22d3ee);
        transform: translateY(-1px);
    }
    .qr-container { text-align: center; margin: 0.75rem 0; }
    .qr-container img { max-width: 220px; border-radius: 8px; border: 2px solid #1f2937; }
    .price-tag { color: #fbbf24; font-size: 1.2rem; font-weight: 700; text-align: center; margin: 0.25rem 0; }
    .steps-list { color: #9ca3af; font-size: 0.85rem; line-height: 1.6; }
    .steps-list strong { color: #e8eaed; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="activation-box">', unsafe_allow_html=True)
    st.markdown('<div class="activation-title">激活 QuantSage</div>', unsafe_allow_html=True)
    st.markdown('<div class="activation-subtitle">支付宝扫码付款 → 提交设备码 → 获取激活码</div>', unsafe_allow_html=True)

    # Device code display
    dev_code = get_device_code()
    st.markdown(f"""
    <div class="device-code-box">
        <div class="device-code-label">📟 本机设备码（付款时请备注此码）</div>
        <div class="device-code-value">{dev_code}</div>
    </div>
    """, unsafe_allow_html=True)

    # Copy device code
    col_copy, _ = st.columns([1, 2])
    with col_copy:
        st.code(dev_code, language=None)

    st.markdown("---")
    st.markdown("### 📋 激活步骤")

    st.markdown("""
    <div class="steps-list">
    <strong>第1步：支付宝扫码付款</strong><br>
    扫描下方支付宝商家收款码，<strong>付款时务必在备注中填写您的设备码</strong>（上方16位码）。<br><br>
    <strong>第2步：提交订单</strong><br>
    点击下方按钮打开激活网页，在「付款激活」标签页输入设备码，点击「提交订单」。<br><br>
    <strong>第3步：获取激活码</strong><br>
    等待开发者确认收款（通常5分钟内），然后在激活网页的「查询激活码」标签页获取激活码。<br><br>
    <strong>第4步：激活软件</strong><br>
    将激活码粘贴到下方输入框，点击「激活」按钮。
    </div>
    """, unsafe_allow_html=True)

    # Alipay QR code
    qr_b64 = _get_qr_base64()
    if qr_b64:
        st.markdown(f"""
        <div class="qr-container">
            <p class="price-tag">💰 ￥19.90</p>
            <img src="{qr_b64}" alt="支付宝收款码">
            <p style="color:#fca5a5;font-size:0.8rem;margin-top:0.3rem;">⚠️ 付款备注务必填写设备码</p>
        </div>
        """, unsafe_allow_html=True)

    # Link to activation page
    st.markdown(
        f'<a href="{ACTIVATION_PAGE_URL}" target="_blank" class="activate-btn-link">'
        f'🌐 打开激活网页（提交订单 / 查询激活码）</a>',
        unsafe_allow_html=True,
    )

    # Key input
    st.markdown("---")
    key_input = st.text_input(
        "许可证密钥",
        placeholder="粘贴从激活网页获取的密钥（QS 开头）",
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

    # Disclaimer
    st.caption("⚠️ 本软件仅供参考研究，不构成任何投资建议，盈亏自负。激活码绑定设备，一码一机。")

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
