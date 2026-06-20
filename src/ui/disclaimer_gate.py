"""First-launch disclaimer gate.

Blocks all interaction until user explicitly agrees to the disclaimer.
Red Line 2 compliance: every user must see and accept the disclaimer.
"""

from __future__ import annotations

import streamlit as st

from src.compliance.disclaimer import load_disclaimer, get_ui_disclaimer
from src.core.config_manager import check_disclaimer_accepted, set_disclaimer_accepted


CSS_GATE = """
<style>
.disclaimer-container {
    max-width: 700px;
    margin: 5vh auto;
    padding: 2rem;
    background: #1a1a2e;
    border-radius: 12px;
    border: 1px solid #333;
    box-shadow: 0 4px 24px rgba(0,0,0,0.3);
}
.disclaimer-title {
    text-align: center;
    color: #e0e0e0;
    font-size: 1.8rem;
    margin-bottom: 1rem;
}
.disclaimer-text {
    background: #0f0f1a;
    border: 1px solid #2a2a3e;
    border-radius: 8px;
    padding: 1.2rem;
    color: #ccc;
    font-size: 0.9rem;
    line-height: 1.7;
    max-height: 350px;
    overflow-y: auto;
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


def show_disclaimer_gate() -> None:
    """Render the full-screen disclaimer gate.

    Blocks via st.stop() until the user checks the box and clicks agree.
    """
    st.markdown(CSS_GATE, unsafe_allow_html=True)

    st.markdown('<div class="disclaimer-container">', unsafe_allow_html=True)

    # Title
    st.markdown(
        '<h1 class="disclaimer-title">QuantSage 免责声明</h1>',
        unsafe_allow_html=True
    )

    # Disclaimer text in a scrollable container
    disclaimer_text = load_disclaimer()
    st.markdown(
        f'<div class="disclaimer-text">{disclaimer_text}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Agreement checkbox
    agreed = st.checkbox(
        "我已阅读并同意上述免责声明",
        key="disclaimer_checkbox",
    )

    # Agree button
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button(
            "同意并继续",
            type="primary",
            disabled=not agreed,
            use_container_width=True,
        ):
            set_disclaimer_accepted()
            st.rerun()

    if not agreed:
        st.caption("请阅读并勾选同意后方可继续使用")

    # Footer
    st.markdown(
        f'<div class="disclaimer-footer">{get_ui_disclaimer()}</div>',
        unsafe_allow_html=True,
    )

    st.markdown("</div>", unsafe_allow_html=True)

    # Block if not yet accepted
    if not check_disclaimer_accepted():
        st.stop()
