"""Unified logging + trace ID + data shape checkpointing.

Dual output:
  - Console: INFO and above (clean, for terminal monitoring)
  - File: DEBUG full trace (for post-mortem analysis)

Log directory: %LOCALAPPDATA%/QuantSage/logs/ (or ~/.quantsage/logs/ on non-Windows)
RotatingFileHandler: 10 MB x 7 files, auto-clean old logs.

Usage:
    from src.monitor import setup_logging, new_trace, get_logger, log_data_shape
    setup_logging()
    trace = new_trace()
    log = get_logger(__name__)
    log.info("analysis started")
    log_data_shape("get_kline output", df, trace=trace)
"""

from __future__ import annotations

import hashlib
import logging
import os
import sys
import time
import traceback
from contextvars import ContextVar
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from secrets import token_hex
from typing import Any, Optional

# ── Trace context (thread-safe for Streamlit's threaded analysis) ──
_trace_var: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)

# ── Power-up guard ──
_INITIALIZED = False

# ── Log directory ──
if os.name == "nt":
    _LOG_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "QuantSage" / "logs"
else:
    _LOG_DIR = Path.home() / ".quantsage" / "logs"

_MAX_LOG_FILES = 30


# ── Secret masking ──

def mask_secret(value: Any) -> str:
    """Return a safe-for-log representation. Never prints full API keys."""
    s = str(value) if value is not None else ""
    n = len(s)
    if n == 0:
        return "<empty>"
    if n <= 6:
        return "****"
    return f"{s[:4]}****{s[-2:]}(len={n})"


# ── Trace ID ──

def new_trace(symbol: str = "") -> str:
    """Generate a new trace ID and set it as the current context.

    If symbol is provided, also creates a per-analysis log file:
      quantsage_YY-MM-DD_HH-MM_{symbol}_{trace}.log
    """
    tid = token_hex(4)  # 8 hex chars
    _trace_var.set(tid)

    if symbol:
        try:
            now = datetime.now().strftime("%Y-%m-%d_%H-%M")
            safe_sym = symbol.replace("/", "_").replace("\\", "_")[:12]
            trace_log = _LOG_DIR / f"quantsage_{now}_{safe_sym}_{tid}.log"

            # Add a file handler dedicated to this trace
            root = logging.getLogger("quantsage")
            th = logging.FileHandler(str(trace_log), encoding="utf-8")
            th.setLevel(logging.DEBUG)
            th.setFormatter(logging.Formatter(
                "%(asctime)s | %(levelname)-5s | %(trace)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            th.addFilter(_TraceFilter())
            root.addHandler(th)

            # Store reference so we can clean up later
            if not hasattr(root, "_trace_handlers"):
                root._trace_handlers = []
            root._trace_handlers.append(th)

            log = logging.getLogger("quantsage")
            log.info("Trace log file: %s", trace_log)
        except Exception:
            pass

    return tid


def get_trace_id() -> str:
    """Get the current trace ID, or '--------' if not set."""
    return _trace_var.get() or "--------"


class _TraceFilter(logging.Filter):
    """Inject trace_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace = get_trace_id()  # type: ignore[attr-defined]
        return True


# ── Logging setup ──

def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    """Configure the QuantSage root logger. Idempotent — safe to call repeatedly."""
    global _INITIALIZED
    if _INITIALIZED:
        return logging.getLogger("quantsage")

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("quantsage")
    root.setLevel(level)

    # Double-check: skip if handlers already exist (Streamlit reruns)
    if root.handlers:
        _INITIALIZED = True
        return root

    # ── Console handler: INFO+ only (clean) ──
    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.INFO)
    ch.setFormatter(_ColoredFormatter("%(asctime)s [%(levelname)-4s] %(message)s", datefmt="%H:%M:%S"))

    # ── File handler: DEBUG full trace (for post-mortem) ──
    # File name includes hour-minute so each session has its own log
    now = datetime.now().strftime("%Y-%m-%d_%H-%M")
    fh = RotatingFileHandler(
        str(_LOG_DIR / f"quantsage_{now}.log"),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=14,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(trace)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))

    for h in (ch, fh):
        h.addFilter(_TraceFilter())
        root.addHandler(h)

    # Silence noisy third-party loggers
    for lib in ("urllib3", "httpx", "matplotlib", "PIL", "asyncio",
                "chromadb", "watchfiles", "numexpr", "openai", "langchain"):
        logging.getLogger(lib).setLevel(logging.WARNING)

    _INITIALIZED = True

    log = logging.getLogger("quantsage")
    log.info("Logger initialized — dir=%s", _LOG_DIR)
    _rotate_old_logs()
    return log


def get_logger(name: str) -> logging.Logger:
    """Get a namespaced child logger."""
    return logging.getLogger(f"quantsage.{name}")


# ── Data shape checkpoint ──

def log_data_shape(stage: str, obj: Any, trace: Optional[str] = None) -> None:
    """Record the shape/type of data at a pipeline checkpoint.

    Args:
        stage: Human description of the checkpoint, e.g. "get_kline return"
        obj: The data object to inspect
        trace: Optional trace ID override
    """
    log = logging.getLogger("quantsage.monitor")
    if trace:
        old = _trace_var.get()
        _trace_var.set(trace)
    try:
        import pandas as pd
        if obj is None:
            log.warning("[NONE] %s: object is None", stage)
        elif isinstance(obj, pd.DataFrame):
            attrs = dict(getattr(obj, "attrs", {}))
            latest = ""
            if not obj.empty and "close" in obj.columns:
                try:
                    latest = f", latest_close={float(obj['close'].iloc[-1]):.2f}"
                except Exception:
                    pass
            log.info("[DF] %s: rows=%d, cols=%s, attrs=%s%s",
                     stage, len(obj), list(obj.columns)[:8], attrs, latest)
        elif isinstance(obj, str):
            preview = obj[:120].replace("\n", " ").replace("\r", "")
            log.info("[STR] %s: len=%d, preview='%s'", stage, len(obj), preview)
        elif isinstance(obj, (list, tuple)):
            log.info("[SEQ] %s: type=%s, len=%d", stage, type(obj).__name__, len(obj))
        elif isinstance(obj, dict):
            keys = list(obj.keys())[:10]
            log.info("[DICT] %s: keys=%s", stage, keys)
        else:
            log.info("[OBJ] %s: type=%s, repr=%s",
                     stage, type(obj).__name__, repr(obj)[:120])
    except Exception:
        log.info("[?] %s: type=%s", stage, type(obj).__name__)
    finally:
        if trace:
            _trace_var.set(old)


# ── Unhandled exception hook ──

def install_excepthook() -> None:
    """Install global handler that logs any unhandled exception before crashing."""
    log = logging.getLogger("quantsage")

    def _hook(extype, value, tb):
        log.critical(
            "UNHANDLED EXCEPTION: %s: %s\n%s",
            extype.__name__, str(value),
            "".join(traceback.format_tb(tb)),
        )
        # Also call original hook so it prints to stderr
        sys.__excepthook__(extype, value, tb)

    sys.excepthook = _hook


# ── Helpers ──

class _ColoredFormatter(logging.Formatter):
    """Minimal color formatter — no external deps."""
    COLORS = {
        "DEBUG": "\033[36m",     # cyan
        "INFO": "\033[0m",       # default
        "WARNING": "\033[33m",   # yellow
        "ERROR": "\033[31m",    # red
        "CRITICAL": "\033[1;31m",  # bold red
    }
    RESET = "\033[0m"

    def format(self, record):
        color = self.COLORS.get(record.levelname, "")
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        record.msg = f"{color}{record.msg}{self.RESET}"
        return super().format(record)


def _rotate_old_logs() -> None:
    """Keep only the _MAX_LOG_FILES most recent logs."""
    try:
        logs = sorted(
            _LOG_DIR.glob("quantsage_*.log*"),
            key=lambda p: p.stat().st_mtime, reverse=True,
        )
        for old in logs[_MAX_LOG_FILES:]:
            old.unlink()
    except Exception:
        pass
