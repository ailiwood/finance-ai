"""QuantSage Desktop Launcher.

Entry point for PyInstaller-packaged executable. Starts the Streamlit
server and opens the default browser.

Architecture (PyInstaller mode):
  The launcher spawns a SECOND instance of itself with --_server flag.
  That child instance runs Streamlit directly as a subprocess using
  the embedded Python interpreter. The parent monitors health and opens
  the browser.

  This subprocess approach avoids ALL in-process Streamlit compatibility
  issues in the PyInstaller frozen environment.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from src.deployment.version import __version__

DEFAULT_PORT = 8501
HEALTH_CHECK_TIMEOUT = 120  # generous for PyInstaller cold start
POLL_INTERVAL = 1.5


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def wait_for_server(port: int, timeout: int = HEALTH_CHECK_TIMEOUT) -> bool:
    """Poll /_stcore/health until HTTP 200."""
    url = f"http://127.0.0.1:{port}/_stcore/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = urllib.request.urlopen(url, timeout=2)
            if resp.status == 200:
                return True
        except urllib.error.HTTPError:
            pass  # Keep polling — server partially up
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


def _get_app_script() -> str:
    """Find src/ui/app.py, respecting PyInstaller bundles."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidate = Path(sys._MEIPASS) / "src" / "ui" / "app.py"
        if candidate.exists():
            return str(candidate)
    candidate = Path(__file__).resolve().parent.parent / "ui" / "app.py"
    if candidate.exists():
        return str(candidate)
    raise FileNotFoundError("Cannot find src/ui/app.py")


def _run_server_mode(script_path: str, port: int) -> None:
    """Run as a Streamlit server (called from subprocess with --_server).

    This is the CHILD process. It starts Streamlit and blocks until stopped.

    """
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

    flag_options = {
        "global_development_mode": False,
        "server_port": port,
        "server_address": "127.0.0.1",
        "server_headless": True,
        "enable_xsrf_protection": False,
        "browser_server_address": "127.0.0.1",
        "browser_server_port": port,
        "gather_usage_stats": False,
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
    # Internal flags for subprocess mode
    parser.add_argument("--_server", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_script", type=str, help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    # ── Subprocess server mode (child process) ──
    if args._server:
        script = args._script or _get_app_script()
        print(f"[QuantSage Server] Starting on 127.0.0.1:{args.port}", flush=True)
        _run_server_mode(script, args.port)
        print("[QuantSage Server] Stopped.", flush=True)
        return 0

    # ── Launcher mode (parent process) ──
    print(f"\n{'='*60}")
    print(f"  QuantSage v{__version__}")
    print(f"  {'='*60}\n")

    if args.reset_config:
        handle_reset_config()

    script_path = _get_app_script()
    port = args.port

    if not is_port_available(port):
        print(f"[QuantSage] Port {port} is in use. Trying next available...", flush=True)
        port += 1
        while not is_port_available(port) and port < 8600:
            port += 1

    url = f"http://127.0.0.1:{port}"

    # In frozen mode: spawn child EXE as Streamlit server
    print(f"[QuantSage] Starting server...", flush=True)

    # Build command: QuantSage.exe --_server --_script <path> --port <port>
    cmd = [
        sys.executable,
        "--_server",
        "--_script", script_path,
        "--port", str(port),
    ]

    # On Windows, hide the child's console window
    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NO_WINDOW

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
    )

    # Stream child's stdout to our stdout
    def _stream_output():
        if proc.stdout:
            for line in proc.stdout:
                stripped = line.rstrip()
                if stripped:
                    print(f"  {stripped}", flush=True)

    output_thread = threading.Thread(target=_stream_output, daemon=True)
    output_thread.start()

    # Wait for server to be ready
    print("[QuantSage] Waiting for server...", end="", flush=True)
    if not wait_for_server(port):
        print(" FAILED")
        proc.terminate()
        return 1
    print(" OK")

    # Open browser
    if not args.no_browser:
        print(f"[QuantSage] Opening {url}", flush=True)
        webbrowser.open(url)

    print(f"[QuantSage] Running at {url}. Press Ctrl+C to stop.\n", flush=True)

    # Wait for child process or Ctrl+C
    try:
        proc.wait()
    except KeyboardInterrupt:
        print("\n[QuantSage] Shutting down...", flush=True)
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()

    print("[QuantSage] Stopped.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
