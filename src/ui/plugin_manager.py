"""Plugin Manager Streamlit UI.

Accessible from the home page. Shows installed and available plugins,
GPU status, and provides one-click download/install.

Compliance: includes disclaimer footer.
"""

from __future__ import annotations

import streamlit as st

from src.compliance.disclaimer import get_ui_disclaimer
from src.deployment.plugin_manager import (
    get_plugin_manager, PluginInfo, PluginManager,
)

CSS_PLUGIN = """
<style>
.plugin-container { max-width: 900px; margin: 0 auto; }
.plugin-card { background: #1a1a2e; border: 1px solid #333; border-radius: 8px; padding: 1.2rem; margin-bottom: 1rem; }
.plugin-name { color: #e0e0e0; font-size: 1.2rem; }
.plugin-desc { color: #999; font-size: 0.9rem; margin-top: 0.5rem; }
.plugin-status-installed { color: #4caf50; font-size: 0.85rem; }
.plugin-status-available { color: #2196f3; font-size: 0.85rem; }
.plugin-status-incompatible { color: #f44336; font-size: 0.85rem; }
.gpu-card { background: #0f1a2e; border: 1px solid #2a3a5e; border-radius: 8px; padding: 1rem; margin-bottom: 1.5rem; }
.gpu-label { color: #888; font-size: 0.85rem; }
.gpu-value { color: #ccc; font-size: 0.95rem; }
</style>
"""


def show_plugin_manager() -> None:
    """Render the plugin manager page."""
    st.markdown(CSS_PLUGIN, unsafe_allow_html=True)
    st.markdown('<div class="plugin-container">', unsafe_allow_html=True)

    st.header("插件管理")
    st.caption("管理 GPU 加速插件。无 GPU 时将自动使用基线引擎，无需安装插件。")

    manager = get_plugin_manager()

    # ── GPU Status ──
    _show_gpu_status(manager)

    # ── Available Plugins ──
    st.markdown("---")
    st.subheader("可用插件")

    plugins = manager.get_available_plugins()

    if not plugins:
        st.info("无法获取插件清单。请检查网络连接后刷新页面。")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    for plugin in plugins:
        _show_plugin_card(manager, plugin)

    # ── Footer ──
    st.markdown("---")
    st.caption(f"⚠️ {get_ui_disclaimer()}")

    st.markdown("</div>", unsafe_allow_html=True)


def _show_gpu_status(manager: PluginManager) -> None:
    """Display GPU hardware status."""
    gpu = manager.get_gpu_status()
    st.markdown('<div class="gpu-card">', unsafe_allow_html=True)
    st.markdown("**系统状态**")

    col1, col2 = st.columns(2)
    with col1:
        if gpu["available"]:
            st.markdown(
                f'<span class="gpu-label">GPU</span><br>'
                f'<span style="color:#4caf50;">✅ {gpu["name"]}</span>',
                unsafe_allow_html=True,
            )
            st.markdown(
                f'<span class="gpu-label">显存</span><br>'
                f'<span class="gpu-value">{gpu["vram_gb"]:.1f} GB</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<span class="gpu-label">GPU</span><br>'
                f'<span style="color:#888;">❌ 未检测到</span>',
                unsafe_allow_html=True,
            )

    with col2:
        st.markdown(
            f'<span class="gpu-label">CUDA 版本</span><br>'
            f'<span class="gpu-value">{gpu.get("cuda_version") or "N/A"}</span>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<span class="gpu-label">FP8 支持</span><br>'
            f'<span class="gpu-value">{"✅ 支持" if gpu["fp8_supported"] else "❌ 不支持"}</span>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def _show_plugin_card(manager: PluginManager, plugin: PluginInfo) -> None:
    """Render a single plugin card with action button."""
    compatible, reason = manager.is_plugin_compatible(plugin)

    st.markdown('<div class="plugin-card">', unsafe_allow_html=True)

    col1, col2 = st.columns([3, 1])

    with col1:
        st.markdown(f'<div class="plugin-name">{plugin.name}</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="plugin-desc">{plugin.description}</div>', unsafe_allow_html=True)

        if plugin.installed:
            st.markdown(
                f'<span class="plugin-status-installed">✅ 已安装 v{plugin.installed_version}</span>'
                f' &nbsp; <span class="gpu-label">~{plugin.required_disk_mb / 1024:.1f} GB</span>',
                unsafe_allow_html=True,
            )
        elif not compatible:
            st.markdown(
                f'<span class="plugin-status-incompatible">❌ {reason}</span>'
                f' &nbsp; <span class="gpu-label">~{plugin.required_disk_mb / 1024:.1f} GB</span>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f'<span class="plugin-status-available">⬇️ 可安装</span>'
                f' &nbsp; <span class="gpu-label">~{plugin.required_disk_mb / 1024:.1f} GB</span>',
                unsafe_allow_html=True,
            )

    with col2:
        if plugin.installed:
            if st.button("卸载", key=f"uninstall_{plugin.plugin_id}", use_container_width=True):
                with st.spinner(f"正在卸载 {plugin.name}..."):
                    manager.deactivate_plugin(plugin.plugin_id)
                    manager.uninstall_plugin(plugin.plugin_id)
                st.success(f"{plugin.name} 已卸载")
                st.rerun()

        elif compatible:
            if st.button("安装", key=f"install_{plugin.plugin_id}", type="primary", use_container_width=True):
                _do_install(manager, plugin)

        else:
            st.button("不可用", disabled=True, key=f"incompat_{plugin.plugin_id}", use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)


def _do_install(manager: PluginManager, plugin: PluginInfo) -> None:
    """Execute plugin download + install with progress display."""
    progress_placeholder = st.empty()
    status_placeholder = st.empty()

    def progress_cb(ratio: float, msg: str) -> None:
        with progress_placeholder.container():
            st.progress(min(ratio, 1.0))
        status_placeholder.caption(msg)

    with st.spinner(f"正在准备下载 {plugin.name}..."):
        success = manager.download_plugin(plugin.plugin_id, progress_cb)

    if success:
        manager.activate_plugin(plugin.plugin_id)
        st.success(f"{plugin.name} 安装并激活成功！分析时需重启 Kronos/FinBERT 服务。")
        st.rerun()
    else:
        st.error(f"{plugin.name} 安装失败。请检查网络连接或稍后重试。")
