"""PyInstaller runtime hook: Fix Streamlit static directory path in frozen mode.

In PyInstaller bundles, streamlit.file_util.get_static_dir() returns a path
based on __file__, which points into the PYZ archive rather than the real
filesystem. This causes create_streamlit_static_assets_routes() to return []
because os.path.isdir() fails on the archive path.

This hook replaces get_static_dir() with a version that uses sys._MEIPASS.
It runs early in the PyInstaller bootstrap process.
"""

import os
import sys

# Fix GBK encoding: Chinese Windows console can't handle emoji in log messages.
# This MUST run before any TradingAgents-CN code that logs emoji (🔧🔍⚠️).
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.stdout.encoding and sys.stdout.encoding.lower() in ("gbk", "cp936", "cp950"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def _patch() -> None:
    if not getattr(sys, "frozen", False) or not hasattr(sys, "_MEIPASS"):
        return

    static_dir = os.path.join(sys._MEIPASS, "streamlit", "static")
    if not os.path.isdir(static_dir):
        return

    import streamlit.file_util as file_util
    file_util.get_static_dir = lambda: static_dir


_patch()
