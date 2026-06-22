"""QuantSage main entry point.

Orchestrates: Disclaimer Gate -> Config Wizard -> Home.

Launch: streamlit run src/ui/app.py
"""

from __future__ import annotations

import os as _os, sys as _sys, time as _time
from pathlib import Path as _Path

# ═══════════════════════════════════════════════════════════════
# Step 0: Set up sys.path BEFORE any project imports
# ═══════════════════════════════════════════════════════════════
# When running `streamlit run src/ui/app.py`, the project root is the cwd.
# For PyInstaller builds, sys._MEIPASS points to the extraction dir.
_FROZEN = getattr(_sys, "frozen", False)
if _FROZEN and hasattr(_sys, "_MEIPASS"):
    _PROJECT_ROOT = _Path(_sys._MEIPASS)
else:
    _PROJECT_ROOT = _Path(__file__).resolve().parent.parent.parent

_TA_CN_DIR = _PROJECT_ROOT / "TradingAgents-CN"
for _p in (str(_PROJECT_ROOT), str(_TA_CN_DIR)):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)

# Execution marker for frozen-mode debugging
_marker = _Path(_os.environ.get("TEMP", "/tmp")) / "quantsage_app_executed.txt"
try:
    _marker.write_text(
        f"{_time.strftime('%H:%M:%S')} app.py EXECUTED\n"
        f"frozen={_FROZEN}\n"
        f"python={_sys.executable}\n"
        f"root={_PROJECT_ROOT}\n"
    )
except Exception:
    pass

# ── Logging: file + console ──
from src.core.logging_config import setup_logging
_log = setup_logging()

import streamlit as st

# Page config MUST be the first Streamlit command
st.set_page_config(
    page_title="QuantSage",
    page_icon="\U0001f4ca",
    layout="wide",
    initial_sidebar_state="collapsed",
)

from src.ui.disclaimer_gate import show_disclaimer_gate
from src.ui.config_wizard import show_wizard
from src.ui.home import show_home
from src.core.config_manager import (
    is_configured, check_disclaimer_accepted, CONFIG_DIR, load_config,
)
from src.compliance.disclaimer import get_ui_disclaimer, get_ui_footer


CSS_GLOBAL = """
<style>
/* ── Streamlit branding ── */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* ── Dark tech theme palette ──
   bg-primary:    #0a0e1a  (deep navy)
   bg-secondary:  #111827  (card bg)
   bg-tertiary:   #1a2236  (hover)
   text-primary:  #e8eaed  (white-ish)
   text-secondary:#9ca3af  (gray)
   accent-cyan:   #22d3ee  (highlights)
   accent-green:  #34d399  (success)
   accent-red:    #f87171  (warnings)
   accent-gold:   #fbbf24  (emphasis)
   border:        #1f2937  (subtle)
*/

.stApp {
    background: radial-gradient(ellipse at 50% 0%, #1a1040 0%, #0d1117 50%, #0a0e1a 100%);
    color: #e8eaed;
}

/* ── Typography ── */
h1, h2, h3, h4, h5, h6 { color: #e8eaed !important; font-family: 'Segoe UI', 'Microsoft YaHei', system-ui, sans-serif; }
h1 { font-size: 2rem; font-weight: 700; }
h2 { font-size: 1.5rem; font-weight: 600; border-bottom: 1px solid #1f2937; padding-bottom: 0.5rem; }
p, li, span, div { color: #d1d5db; font-family: 'Segoe UI', 'Microsoft YaHei', system-ui, sans-serif; }
.stCaption { color: #9ca3af !important; }

/* ── Cards ── */
.quantsage-card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 10px;
    padding: 1.25rem;
    margin-bottom: 1rem;
}
.quantsage-card-header {
    display: flex; align-items: center; gap: 0.5rem;
    margin-bottom: 0.75rem;
    font-weight: 600; font-size: 1.1rem; color: #e8eaed;
}
.quantsage-card-header img { width: 24px; height: 24px; }
.quantsage-card-number { font-size: 1.4rem; font-weight: 700; color: #22d3ee; }

/* ── Buttons ── */
.stButton > button {
    border-radius: 6px;
    border: 1px solid #1f2937;
    background-color: #111827;
    color: #e8eaed;
    transition: all 0.2s ease;
}
.stButton > button:hover {
    border-color: #22d3ee;
    background-color: #1a2236;
}
.stButton > button:disabled {
    opacity: 0.4;
}

/* ── Text inputs ── */
.stTextInput > div > div > input {
    background-color: #111827;
    color: #e8eaed;
    border: 1px solid #1f2937;
    border-radius: 6px;
}
.stSelectbox > div > div {
    background-color: #111827;
    color: #e8eaed;
}

/* ── Expanders ── */
.streamlit-expanderHeader {
    background-color: #111827;
    border: 1px solid #1f2937;
    border-radius: 6px;
    color: #e8eaed;
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 8px; }
::-webkit-scrollbar-track { background: #0a0e1a; }
::-webkit-scrollbar-thumb { background: #374151; border-radius: 4px; }
::-webkit-scrollbar-thumb:hover { background: #4b5563; }

/* ── Disclaimer banner (strong red) ── */
.quantsage-disclaimer-banner {
    background: linear-gradient(135deg, #1f0a0a 0%, #2d0f0f 100%);
    border: 2px solid #f87171;
    border-radius: 8px;
    padding: 14px 18px;
    margin: 12px 0;
    color: #fca5a5;
    font-size: 1.05rem;
    font-weight: 700;
    text-align: center;
}

/* ── Community banner ── */
.quantsage-community {
    background: linear-gradient(135deg, #1a1040 0%, #162040 100%);
    border: 1.5px solid #22d3ee;
    border-radius: 10px;
    padding: 16px 20px;
    margin: 16px 0;
    text-align: center;
}
.quantsage-community a {
    color: #22d3ee;
    font-size: 1rem;
    font-weight: 600;
    text-decoration: none;
    display: inline-block;
    padding: 8px 24px;
    border: 1px solid #22d3ee;
    border-radius: 6px;
    transition: all 0.2s;
}
.quantsage-community a:hover {
    background: #22d3ee;
    color: #0a0e1a;
}
.quantsage-community-label {
    color: #e8eaed;
    font-size: 0.95rem;
    font-weight: 600;
    margin-bottom: 6px;
}

/* ── Copyright footer ── */
.quantsage-copyright {
    text-align: center;
    color: #6b7280;
    font-size: 0.78rem;
    margin-top: 1.5rem;
    padding-top: 1rem;
    border-top: 1px solid #1f2937;
}
.quantsage-copyright a {
    color: #9ca3af;
    text-decoration: none;
}
.quantsage-copyright a:hover {
    color: #22d3ee;
}
</style>
"""

_COPYRIGHT_HTML = """
<div class="quantsage-copyright">
本软件由 <strong>ailiwood</strong> 开发 |
<a href="https://github.com/ailiwood" target="_blank">GitHub</a> |
抖音号: 23230218947
</div>
"""


_COMMUNITY_HTML = """
<div class="quantsage-community">
  <div class="quantsage-community-label">软件支持与量化技术交流</div>
  <a href="https://applink.feishu.cn/client/chat/chatter/add_by_link?link_token=b7bg64d8-3f24-42ac-8361-ffec9a9c682f" target="_blank">加入飞书群聊</a>
</div>
"""


def _show_disclaimer_footer() -> None:
    """Always-visible strong disclaimer + community + copyright at bottom."""
    st.divider()
    st.markdown(
        f'<div class="quantsage-disclaimer-banner">'
        f'⚠️ {get_ui_footer()}'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown(_COMMUNITY_HTML, unsafe_allow_html=True)
    st.markdown(_COPYRIGHT_HTML, unsafe_allow_html=True)


def _init_session() -> None:
    """Initialize session state defaults."""
    defaults = {
        "disclaimer_accepted": False,
        "config_complete": False,
        "wizard_step": 0,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


def main() -> None:
    """Main application flow.

    Flow:
    1. Initialize session state
    2. Check disclaimer gate
    3. Check configuration
    4. Route to wizard or home
    """
    # Ensure config directory exists
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Pre-load Tushare token into env for all pages (data inspection, analysis)
    try:
        _cfg = load_config()
        _tt = _cfg.get("tushare_token", "")
        if _tt and not _tt.startswith("your_"):
            _os.environ["TUSHARE_TOKEN"] = _tt
    except Exception:
        pass

    # Inject global CSS + auto-reconnect JavaScript
    st.markdown(CSS_GLOBAL, unsafe_allow_html=True)

    # Auto-reconnect on WebSocket disconnect (long analyses can trigger timeout)
    reconnect_js = """
    <script>
    let reconnectAttempts = 0;
    const MAX_RECONNECT = 30;

    function tryReconnect() {
        if (reconnectAttempts >= MAX_RECONNECT) {
            console.log('[QuantSage] Max reconnect attempts reached. Please refresh manually.');
            return;
        }
        reconnectAttempts++;
        fetch(window.location.href, {method: 'HEAD'})
            .then(r => {
                if (r.ok) {
                    console.log('[QuantSage] Server available. Reloading...');
                    window.location.reload();
                } else {
                    setTimeout(tryReconnect, 3000);
                }
            })
            .catch(() => setTimeout(tryReconnect, 3000));
    }

    // Listen for WebSocket errors (Streamlit uses WebSocket for state sync)
    window.addEventListener('error', function(e) {
        if (e.target && (e.target instanceof WebSocket || e.message?.includes('WebSocket'))) {
            console.log('[QuantSage] WebSocket error detected. Will attempt reconnect...');
            setTimeout(tryReconnect, 2000);
        }
    });

    // Also poll: if page becomes unresponsive, check server
    setInterval(function() {
        if (document.hidden) return;
        fetch(window.location.href, {method: 'HEAD'})
            .catch(() => setTimeout(tryReconnect, 2000));
    }, 30000);
    </script>
    """
    st.markdown(reconnect_js, unsafe_allow_html=True)

    _init_session()

    # Gate 1: Disclaimer
    if not check_disclaimer_accepted():
        show_disclaimer_gate()
        return  # st.stop() called inside show_disclaimer_gate

    # Gate 2: Configuration
    config_complete = st.session_state.get("config_complete", False)
    if not config_complete and not is_configured():
        show_wizard()
        return

    # If config exists but session flag isn't set (e.g., from M1), set it
    if is_configured():
        st.session_state.config_complete = True

    # Main app
    show_home()
    _show_disclaimer_footer()


if __name__ == "__main__":
    main()
