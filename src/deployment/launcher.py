"""QuantSage Desktop Launcher.

Entry point for PyInstaller-packaged executable.

Architecture:
  Parent process launches a child process (itself with --_server flag).
  The child runs Streamlit. The parent monitors health, opens browser,
  and relays child output to the console.
"""

from __future__ import annotations

import argparse
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


def _open_browser_windows(url: str) -> bool:
    """Open URL in default browser. Returns True if successful.

    Tries 4 methods in order of reliability on Windows:
    1. webbrowser.open()
    2. os.startfile()
    3. ShellExecuteW via ctypes (most reliable Windows API)
    4. cmd /c start
    """
    # Method 1: webbrowser
    try:
        if webbrowser.open(url):
            return True
    except Exception:
        pass

    # Method 2: os.startfile
    try:
        os.startfile(url)
        return True
    except Exception:
        pass

    # Method 3: ShellExecuteW via ctypes (works even without default browser set)
    try:
        import ctypes
        SW_SHOWNORMAL = 1
        ctypes.windll.shell32.ShellExecuteW(
            None, "open", url, None, None, SW_SHOWNORMAL
        )
        return True
    except Exception:
        pass

    # Method 4: cmd /c start
    try:
        subprocess.run(
            ["cmd", "/c", "start", "", url],
            capture_output=True, timeout=10,
        )
        return True
    except Exception:
        pass

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
    raise RuntimeError(f"No available ports from {start} to {start + max_attempts}")


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
    print("[QuantSage] Configuration reset complete.")


def _write_crash_log(error: str, script: str) -> str:
    """Write crash information to a log file. Returns the log file path."""
    log_dir = Path.home() / ".quantsage"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "crash.log"
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_path.write_text(
        f"[{timestamp}] QUANTSAGE CRASH\n"
        f"Script: {script}\n"
        f"Error:\n{error}\n"
        f"---\n",
        encoding="utf-8",
    )
    return str(log_path)


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
    """Child process: start Streamlit server."""
    import streamlit.web.bootstrap as bootstrap
    from streamlit import config as _config

    main_script = os.path.abspath(script_path)
    _config._main_script_path = main_script

    _config.set_option("global.developmentMode", False)
    _config.set_option("server.port", port)
    _config.set_option("server.address", "127.0.0.1")
    _config.set_option("server.headless", True)
    _config.set_option("server.enableXsrfProtection", False)
    _config.set_option("browser.serverAddress", "127.0.0.1")
    _config.set_option("browser.serverPort", port)
    _config.set_option("browser.gatherUsageStats", False)
    _config.set_option("server.websocketPingInterval", 60)

    flag_options = {
        "global_development_mode": False,
        "server_port": port,
        "server_address": "127.0.0.1",
        "server_headless": True,
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
    parser.add_argument("--_server", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_script", type=str, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # ── CHILD PROCESS: Streamlit server ──
    if args._server:
        script = args._script or _get_app_script()
        print(f"[QuantSage Server] Starting on 127.0.0.1:{args.port}", flush=True)
        try:
            _run_server_mode(script, args.port)
        except SystemExit:
            pass
        except BaseException:
            tb = traceback.format_exc()
            print(f"[QuantSage Server] FATAL ERROR:\n{tb}", flush=True)
            log_path = _write_crash_log(tb, script)
            print(f"[QuantSage Server] Crash log: {log_path}", flush=True)
            return 1
        print("[QuantSage Server] Stopped.", flush=True)
        return 0

    # ── PARENT PROCESS: launcher ──
    print(f"\n{'='*60}")
    print(f"  QuantSage v{__version__}")
    print(f"  {'='*60}\n")

    if args.reset_config:
        handle_reset_config()

    script_path = _get_app_script()
    port = args.port

    if not is_port_available(port):
        print(f"[QuantSage] Port {port} is in use. Trying next available...", flush=True)
        port = find_available_port(port + 1)

    url = f"http://127.0.0.1:{port}"

    print(f"[QuantSage] Starting server...", flush=True)

    cmd = [
        sys.executable,
        "--_server",
        "--_script", script_path,
        "--port", str(port),
    ]

    creationflags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )

    def _stream_output():
        if proc.stdout:
            for line in proc.stdout:
                stripped = line.rstrip()
                if stripped:
                    print(f"  {stripped}", flush=True)

    output_thread = threading.Thread(target=_stream_output, daemon=True)
    output_thread.start()

    print("[QuantSage] Waiting for server...", end="", flush=True)
    if not wait_for_server(port):
        print(" FAILED")
        print("[QuantSage] Server did not start. Check the crash log at:", flush=True)
        log_path = Path.home() / ".quantsage" / "crash.log"
        if log_path.exists():
            print(f"  {log_path}", flush=True)
            print(log_path.read_text(encoding="utf-8"), flush=True)
        proc.terminate()
        return 1
    print(" OK")

    # Open browser
    if not args.no_browser:
        print(f"[QuantSage] Opening {url}", flush=True)
        if not _open_browser_windows(url):
            print(f"[QuantSage] Please open your browser and visit:", flush=True)
            print(f"  {url}", flush=True)

    print(f"[QuantSage] Running at {url}. Press Ctrl+C to stop.\n", flush=True)

    # Monitor child process; detect crashes
    retcode = None
    try:
        retcode = proc.wait()
    except KeyboardInterrupt:
        print("\n[QuantSage] Shutting down...", flush=True)
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    if retcode is not None and retcode != 0:
        print(f"[QuantSage] Server exited with code {retcode}.", flush=True)
        log_path = Path.home() / ".quantsage" / "crash.log"
        if log_path.exists():
            print(f"[QuantSage] Crash log: {log_path}", flush=True)

    print("[QuantSage] Stopped.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
