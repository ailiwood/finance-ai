"""Centralized logging — file + console, UTF-8 safe.

Logs go to:
- Console (stderr): real-time monitoring in the Streamlit terminal
- File: ~/.quantsage/logs/quantsage_{date}.log (persistent, for post-mortem)

Usage: call setup_logging() once at app startup.
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

LOG_DIR = Path.home() / ".quantsage" / "logs"
_MAX_LOG_FILES = 30  # Keep last 30 daily logs


_LOGGING_INITIALIZED = False


def setup_logging(level: int = logging.INFO, to_console: bool = True) -> logging.Logger:
    """Configure root logger with file + console handlers.

    File handler: daily rotating log in ~/.quantsage/logs/
    Console handler: stderr (UTF-8 safe wrapper on Windows)

    Idempotent: skips re-initialization if already configured (avoids log spam on Streamlit reruns).

    Returns the root logger configured for the application.
    """
    global _LOGGING_INITIALIZED
    if _LOGGING_INITIALIZED:
        return logging.getLogger("quantsage")

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Clean up old logs
    _rotate_logs()

    today = datetime.now().strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"quantsage_{today}.log"

    root = logging.getLogger()
    root.setLevel(level)

    # Clear existing handlers to avoid duplicates on Streamlit reruns
    root.handlers.clear()

    # --- File handler (UTF-8) ---
    try:
        fh = logging.FileHandler(str(log_file), encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)-7s] %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(fh)
    except Exception:
        pass  # File logging is best-effort

    # --- Console handler (stderr, UTF-8 safe) ---
    if to_console:
        ch = _Utf8StderrHandler()
        ch.setLevel(level)
        ch.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)-4s] %(message)s",
            datefmt="%H:%M:%S",
        ))
        root.addHandler(ch)

    # Quiet noisy third-party loggers
    for noisy in ("urllib3", "httpx", "matplotlib", "PIL", "asyncio",
                  "chromadb", "watchfiles", "numexpr"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logger = logging.getLogger("quantsage")
    logger.info("=" * 50)
    logger.info("QuantSage started — log file: %s", log_file)
    logger.info("=" * 50)

    global _LOGGING_INITIALIZED
    _LOGGING_INITIALIZED = True
    return logger


class _Utf8StderrHandler(logging.StreamHandler):
    """StreamHandler that replaces unencodable chars instead of crashing."""

    def __init__(self):
        super().__init__(stream=sys.stderr)

    def emit(self, record):
        try:
            super().emit(record)
        except UnicodeEncodeError:
            # Replace emoji/non-GBK chars with '?' instead of crashing
            msg = record.getMessage().encode("ascii", errors="replace").decode("ascii")
            record = logging.makeLogRecord(vars(record) | {"msg": msg, "message": msg})
            super().emit(record)


def _rotate_logs() -> None:
    """Keep only the _MAX_LOG_FILES most recent log files."""
    try:
        logs = sorted(LOG_DIR.glob("quantsage_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in logs[_MAX_LOG_FILES:]:
            old.unlink()
    except Exception:
        pass


def get_logger(name: str) -> logging.Logger:
    """Get a child logger for a specific module."""
    return logging.getLogger(f"quantsage.{name}")
