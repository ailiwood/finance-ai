"""QuantSage Desktop Launcher.

Entry point for PyInstaller-packaged (onedir) executable.

Architecture:
  Parent process spawns a child (itself with --_server flag).
  Child runs Streamlit. Parent monitors health, opens browser,
  and relays child output. All output is mirrored to a log file
  at ~/.quantsage/logs/quantsage.log for post-crash diagnosis.
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from src.deployment.version import __version__

DEFAULT_PORT = 8501
HEALTH_CHECK_TIMEOUT = 120
POLL_INTERVAL = 1.5

# ── Global log file path ──
_LOG_DIR = Path.home() / ".quantsage" / "logs"
_LOG_FILE = _LOG_DIR / "quantsage.log"


def _setup_file_logging() -> logging.Logger:
    """Configure rotating file logger for crash diagnosis.

    Returns a logger that writes to both the log file and stderr.
    Max 10 MB per file, keeps 3 backups.
    """
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("quantsage")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # Don't duplicate to root logger

    # Clear existing handlers (prevent duplicates on re-entry)
    logger.handlers.clear()

    # File handler with rotation
    fh = logging.handlers.RotatingFileHandler(
        str(_LOG_FILE),
        maxBytes=10 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    logger.addHandler(fh)

    # Stream handler (to stderr so it doesn't conflict with subprocess PIPE)
    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(sh)

    return logger


log = _setup_file_logging()


def _log_and_print(msg: str, level: int = logging.INFO, **kwargs) -> None:
    """Log to file and print to stdout. Extra kwargs passed to print()."""
    log.log(level, msg)
    print(msg, flush=True, **kwargs)


def _open_browser_windows(url: str) -> bool:
    """Try 4 methods to open the browser. Returns True if any succeeds."""
    methods = [
        ("webbrowser", lambda: webbrowser.open(url)),
        ("os.startfile", lambda: (_os_startfile_impl(url) is not False)),
        ("ShellExecuteW", lambda: _shell_execute_impl(url)),
        ("cmd start", lambda: _cmd_start_impl(url)),
    ]
    for method, fn in methods:
        try:
            if fn():
                log.info("Browser opened via %s", method)
                return True
        except Exception as e:
            log.debug("Browser method %s failed: %s", method, e)
    return False


def _os_startfile_impl(url: str):
    """os.startfile returns None on success, raises on failure."""
    os.startfile(url)
    return True


def _shell_execute_impl(url: str) -> bool:
    import ctypes
    ret = ctypes.windll.shell32.ShellExecuteW(None, "open", url, None, None, 1)
    # ShellExecuteW returns HINSTANCE > 32 on success
    return ret > 32


def _cmd_start_impl(url: str) -> bool:
    try:
        subprocess.run(["cmd", "/c", "start", "", url], capture_output=True, timeout=10, check=False)
        return True
    except Exception:
        return False


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_available_port(start: int = DEFAULT_PORT, max_attempts: int = 100) -> int:
    for offset in range(max_attempts):
        port = start + offset
        if is_port_available(port):
            return port
    raise RuntimeError(f"No available ports from {start}")


def wait_for_server(port: int, timeout: int = HEALTH_CHECK_TIMEOUT) -> bool:
    url = f"http://127.0.0.1:{port}/_stcore/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = urllib.request.urlopen(url, timeout=2)
            if resp.status == 200:
                return True
        except urllib.error.HTTPError:
            pass
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)
    return False


def handle_reset_config() -> None:
    config_dir = Path.home() / ".quantsage"
    if config_dir.exists():
        for item in config_dir.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                import shutil
                shutil.rmtree(item)
    _log_and_print("[QuantSage] Configuration reset complete.")


def _get_app_script() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidate = Path(sys._MEIPASS) / "src" / "ui" / "app.py"
        if candidate.exists():
            return str(candidate)
    candidate = Path(__file__).resolve().parent.parent / "ui" / "app.py"
    if candidate.exists():
        return str(candidate)
    raise FileNotFoundError("Cannot find src/ui/app.py")


def _run_server_mode(script_path: str, port: int) -> None:
    """Child process: start Streamlit server (all output to log)."""
    import streamlit.web.bootstrap as bootstrap
    from streamlit import config as _config

    main_script = os.path.abspath(script_path)
    _config._main_script_path = main_script

    # Suppress repetitive CORS/XSRF warning
    _config.set_option("server.enableCORS", True)
    _config.set_option("server.enableXsrfProtection", False)
    _config.set_option("global.developmentMode", False)
    _config.set_option("server.port", port)
    _config.set_option("server.address", "127.0.0.1")
    _config.set_option("server.headless", True)
    _config.set_option("browser.serverAddress", "127.0.0.1")
    _config.set_option("browser.serverPort", port)
    _config.set_option("browser.gatherUsageStats", False)
    _config.set_option("server.websocketPingInterval", 60)
    # Frozen mode: disable file watcher to prevent torchvision scanning errors
    _config.set_option("server.fileWatcherType", "none")
    _config.set_option("server.runOnSave", False)

    flag_options = {
        "global_development_mode": False,
        "server_port": port,
        "server_address": "127.0.0.1",
        "server_headless": True,
        "enable_cors": True,
        "enable_xsrf_protection": False,
        "browser_server_address": "127.0.0.1",
        "browser_server_port": port,
        "gather_usage_stats": False,
        "websocket_ping_interval": 60,
    }

    try:
        bootstrap.run(
            main_script_path=main_script,
            is_hello=False,
            args=[],
            flag_options=flag_options,
        )
    except SystemExit:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=f"QuantSage v{__version__}")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--reset-config", action="store_true")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--version", action="version", version=f"QuantSage v{__version__}")
    parser.add_argument("--diagnose-kronos", action="store_true",
                        help="Run Kronos model diagnostic (offline, no Streamlit)")
    parser.add_argument("--_server", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_script", type=str, help=argparse.SUPPRESS)
    return parser.parse_args()



# ── Kronos Diagnostic CLI ────────────────────────────────────────────────────

def _run_kronos_diagnostic() -> int:
    """Run Kronos model diagnostic offline. No Streamlit, no network."""
    import json as _json
    diag = {
        "timestamp": datetime.now().isoformat(),
        "frozen": getattr(sys, "frozen", False),
        "python_version": sys.version,
    }

    for pkg in ["torch", "transformers", "einops", "huggingface_hub", "safetensors"]:
        try:
            mod = __import__(pkg)
            diag[f"{pkg}_version"] = getattr(mod, "__version__", "unknown")
        except ImportError:
            diag[f"{pkg}_version"] = "NOT INSTALLED"

    try:
        import torch
        diag["torch_cuda_available"] = torch.cuda.is_available()
    except Exception:
        diag["torch_cuda_available"] = False

    diag["cpu_count"] = os.cpu_count()

    cache_paths = []
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        cp = Path(sys._MEIPASS) / "src" / "plugins" / "kronos_service" / "kronos_model" / "hf_cache"
        cache_paths.append({"source": "frozen", "path": str(cp), "exists": cp.exists()})
    dev_cp = Path(__file__).resolve().parent.parent / "plugins" / "kronos_service" / "kronos_model" / "hf_cache"
    cache_paths.append({"source": "dev", "path": str(dev_cp), "exists": dev_cp.exists()})
    diag["weight_cache_paths"] = cache_paths

    diag["prediction_method"] = None
    diag["model_loaded"] = False
    diag["fallback_used"] = False
    diag["error"] = None
    diag["advice"] = None

    try:
        from src.plugins.kronos_service.model_engine import get_engine
        engine = get_engine()
        diag["engine_name"] = engine.name
        diag["engine_loaded"] = getattr(engine, "is_loaded", None) if hasattr(engine, "is_loaded") else None

        import random
        random.seed(42)
        base = 100.0
        sample_ohlcv = []
        for i in range(120):
            chg = (random.random() - 0.48) * 0.03
            close = base * (1 + chg)
            high = close * (1 + random.random() * 0.01)
            low = close * (1 - random.random() * 0.01)
            open_p = low + random.random() * (high - low)
            sample_ohlcv.append({
                "date": f"2024-{(i//20+1):02d}-{(i%20+1):02d}",
                "open": round(open_p, 2), "high": round(high, 2),
                "low": round(low, 2), "close": round(close, 2),
                "volume": random.randint(1000000, 5000000),
            })
            base = close

        result = engine.predict(sample_ohlcv, horizon_days=10)
        diag["prediction_method"] = str(result.get("method", ""))
        diag["prediction_direction"] = str(result.get("direction", ""))
        diag["prediction_target"] = float(result.get("target_price", 0))
        diag["prediction_confidence"] = float(result.get("confidence", 0))

        is_kronos = "Kronos-base" in diag["prediction_method"] and "fallback" not in diag["prediction_method"].lower()
        diag["model_loaded"] = is_kronos
        diag["fallback_used"] = not is_kronos

        if is_kronos:
            diag["advice"] = "Kronos-base model loaded and running successfully."
        else:
            diag["advice"] = "Kronos-base not loaded — statistical fallback used. Check hf_cache weights and dependencies."
    except Exception as e:
        diag["error"] = str(e)
        diag["advice"] = f"Exception during prediction: {e}"

    print(_json.dumps(diag, indent=2, ensure_ascii=False))
    log.info("Kronos diagnostic: %s", _json.dumps(diag, indent=2, ensure_ascii=False))

    if diag.get("fallback_used") or not diag.get("model_loaded"):
        print("\n[DIAGNOSE] Kronos-base deep model NOT loaded — using statistical fallback.")
        return 1
    print("\n[DIAGNOSE] Kronos-base model loaded successfully.")
    return 0

def main() -> int:
    args = parse_args()

    # ── CHILD: Streamlit server ──
    if args._server:
        script = args._script or _get_app_script()
        log.info("Server starting on 127.0.0.1:%s, script=%s", args.port, script)
        try:
            _run_server_mode(script, args.port)
        except SystemExit:
            pass
        except BaseException:
            tb = traceback.format_exc()
            log.critical("FATAL ERROR in server:\n%s", tb)
            print(f"\n[QuantSage Server] FATAL ERROR:\n{tb}", flush=True)
            print(f"[QuantSage Server] Log file: {_LOG_FILE}", flush=True)
            return 1
        log.info("Server stopped normally")
        return 0

    # ── Kronos diagnostic (offline, no Streamlit) ──
    if args.diagnose_kronos:
        return _run_kronos_diagnostic()

    # ── PARENT: launcher ──
    log.info("QuantSage v%s starting", __version__)
    _log_and_print(f"\n{'='*60}")
    _log_and_print(f"  QuantSage v{__version__}")
    _log_and_print(f"  {'='*60}\n")

    if args.reset_config:
        handle_reset_config()

    script_path = _get_app_script()
    port = args.port

    if not is_port_available(port):
        alt = find_available_port(port + 1)
        log.warning("Port %s in use, switching to %s", port, alt)
        port = alt

    url = f"http://127.0.0.1:{port}"

    log.info("Spawning server subprocess")
    _log_and_print("[QuantSage] Starting server...")

    cmd = [sys.executable, "--_server", "--_script", script_path, "--port", str(port)]

    # Let the child inherit stdout/stderr directly — capturing via PIPE
    # breaks Streamlit's click.echo() on Windows (OSError: Invalid argument).
    # The child's output goes to the same console; logging is done via the
    # file logger configured in _setup_file_logging().
    proc = subprocess.Popen(
        cmd,
        # Inherit stdout/stderr so Streamlit can use click.echo normally
        stdout=None,
        stderr=None,
    )

    _log_and_print("[QuantSage] Waiting for server...", end="")
    if not wait_for_server(port):
        log.error("Server failed to start within %ss", HEALTH_CHECK_TIMEOUT)
        _log_and_print(" FAILED")
        proc.terminate()
        _log_and_print(f"[QuantSage] Check log: {_LOG_FILE}")
        return 1
    _log_and_print(" OK")

    if not args.no_browser:
        _log_and_print(f"[QuantSage] Opening {url}")
        if not _open_browser_windows(url):
            _log_and_print(f"[QuantSage] Please visit: {url}")
            try:
                _url_file = _LOG_DIR / "last_server_url.txt"
                _url_file.write_text(url)
                _log_and_print(f"[QuantSage] Server URL saved to: {_url_file}")
            except Exception:
                pass

    _log_and_print(f"[QuantSage] Running at {url}. Press Ctrl+C to stop.\n")

    retcode = None
    try:
        retcode = proc.wait()
    except KeyboardInterrupt:
        _log_and_print("\n[QuantSage] Shutting down...")
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    if retcode is not None and retcode != 0:
        log.error("Server exited with code %s", retcode)
        _log_and_print(f"[QuantSage] Server exited with code {retcode}.")
        _log_and_print(f"[QuantSage] Log: {_LOG_FILE}")

    log.info("QuantSage stopped")
    _log_and_print("[QuantSage] Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
