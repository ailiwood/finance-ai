"""Resource path abstraction for PyInstaller-packaged and source-mode execution.

When running from a PyInstaller bundle, resources are extracted to a temp
directory (sys._MEIPASS). When running from source, resources are relative
to the project root.

Centralizing this here avoids scattering _MEIPASS checks across the codebase.
"""

from __future__ import annotations

import sys
from pathlib import Path


def get_base_path() -> Path:
    """Return the base directory for resource files.

    - PyInstaller bundle: sys._MEIPASS (temp extraction directory)
    - Source execution: project root (E:/AI_projects/fin or equivalent)
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    # Running from source: this file is at src/packaging/resource_path.py
    # so .resolve().parent.parent.parent = project root
    return Path(__file__).resolve().parent.parent.parent


def get_config_dir() -> Path:
    """Return the user's configuration directory (~/.quantsage/).

    This path is always in the user's home directory, regardless of
    whether we are running from source or a PyInstaller bundle.
    """
    return Path.home() / ".quantsage"


def get_plugin_dir() -> Path:
    """Return the directory where optional plugins are installed.

    %APPDATA%/QuantSage/plugins/ on Windows,
    ~/.quantsage/plugins/ on Linux/macOS.
    """
    return get_config_dir() / "plugins"


def get_disclaimer_path() -> Path:
    """Return the path to DISCLAIMER.md, accounting for bundle extraction."""
    return get_base_path() / "DISCLAIMER.md"


def get_logs_dir() -> Path:
    """Return the logs directory path."""
    return get_base_path() / "logs"


def get_reports_dir() -> Path:
    """Return the reports directory path."""
    return get_base_path() / "reports"


def get_cache_dir() -> Path:
    """Return the data cache directory path."""
    return get_base_path() / "cache"
