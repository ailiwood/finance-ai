"""QuantSage Desktop Launcher.

Entry point for PyInstaller-packaged executable. Starts the Streamlit
server and opens the default browser.

Two execution modes:
  - PyInstaller (frozen):  Runs Streamlit in-process via its bootstrap API
  - Source (python):        Spawns Streamlit as a subprocess

Usage:
    QuantSage.exe                    # Start server + open browser
    QuantSage.exe --no-browser       # Server only
    QuantSage.exe --reset-config     # Clear config before starting
    QuantSage.exe --port 8502        # Custom port
"""

from __future__ import annotations

import argparse
import os
import signal
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
DEFAULT_ADDR = "127.0.0.1"  # localhost-only binding for security
HEALTH_CHECK_TIMEOUT = 90    # max seconds to wait (longer for PyInstaller cold start)
POLL_INTERVAL = 1.5          # seconds between health polls


def is_port_available(port: int, host: str = DEFAULT_ADDR) -> bool:
    """Check if a TCP port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def find_available_port(start: int = DEFAULT_PORT, max_attempts: int = 100) -> int:
    """Find the first available port starting from `start`."""
    for offset in range(max_attempts):
        port = start + offset
        if is_port_available(port):
            return port
    raise RuntimeError(f"No available ports from {start} to {start + max_attempts}")


def wait_for_server(port: int, timeout: int = HEALTH_CHECK_TIMEOUT) -> bool:
    """Poll Streamlit health endpoint until server is fully initialized.

    Only HTTP 200 from /_stcore/health confirms the server is ready.
    Connection refused / timeout means still starting — keep polling.
    HTTP 404 or other errors mean the server is partially up but the
    Streamlit app hasn't loaded yet — keep polling.
    """
    url = f"http://{DEFAULT_ADDR}:{port}/_stcore/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            resp = urllib.request.urlopen(url, timeout=2)
            if resp.status == 200:
                return True
            # Any non-200 means server is not fully ready yet
        except urllib.error.HTTPError:
            # Server responding but /_stcore/health not ready — keep polling
            pass
        except Exception:
            # Connection refused or timeout — server not listening yet
            pass
        time.sleep(POLL_INTERVAL)
    return False


def handle_reset_config() -> None:
    """Clear all QuantSage configuration and local state."""
    config_dir = Path.home() / ".quantsage"
    if config_dir.exists():
        for item in config_dir.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                import shutil
                shutil.rmtree(item)
    print("[QuantSage] Configuration reset complete.")


def kill_process_on_port(port: int) -> bool:
    """Attempt to kill whatever is listening on the given port (Windows)."""
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True, text=True, timeout=10,
        )
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                pid = line.strip().split()[-1]
                subprocess.run(
                    ["taskkill", "/PID", pid, "/F"],
                    capture_output=True, timeout=10,
                )
                return True
    except Exception:
        pass
    return False


def _wait_and_open_browser(port: int, no_browser: bool) -> None:
    """Wait for Streamlit to be ready, then open the browser.

    Runs in a daemon thread so the main thread can host Streamlit's
    event loop (which requires signal.signal() in the main thread).
    """
    print("[QuantSage] Waiting for server...", end="", flush=True)
    if not wait_for_server(port):
        print(" FAILED")
        print(f"[QuantSage] Server did not start within {HEALTH_CHECK_TIMEOUT}s.")
        return
    print(" OK")

    # Use 127.0.0.1 (not localhost) to avoid IPv4/IPv6 resolution issues
    url = f"http://127.0.0.1:{port}"
    if not no_browser:
        print(f"[QuantSage] Opening {url}")
        webbrowser.open(url)
    else:
        print(f"[QuantSage] Server at {url} (browser suppressed)")

    print("[QuantSage] Running. Press Ctrl+C to stop.\n")


def _get_streamlit_script() -> str:
    """Find the Streamlit entry script, respecting PyInstaller bundles.

    In frozen mode, prefers run_app.py (diagnostic wrapper) over app.py directly.
    In source mode, uses app.py directly.
    """
    # PyInstaller bundle: prefer run_app.py wrapper, fallback to app.py
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        for relpath in ["run_app.py", os.path.join("src", "ui", "app.py")]:
            candidate = Path(sys._MEIPASS) / relpath
            if candidate.exists():
                return str(candidate)

    # Source mode: app.py relative to launcher
    for relpath in [
        Path(__file__).resolve().parent.parent / "ui" / "app.py",
        Path(__file__).resolve().parent.parent.parent / "run_app.py",
    ]:
        if relpath.exists():
            return str(relpath)

    raise FileNotFoundError(
        "Cannot find Streamlit entry script. "
        "Make sure run_app.py or src/ui/app.py exists."
    )


def _run_streamlit_inprocess(script_path: str, port: int) -> None:
    """Run Streamlit server in-process (used in PyInstaller mode).

    This runs Streamlit's tornado server in the current thread.
    It blocks until the server exits.
    """
    import streamlit.web.bootstrap as bootstrap
    from streamlit import config as _config

    # Configure Streamlit programmatically
    _config.set_option("server.port", port)
    _config.set_option("server.address", DEFAULT_ADDR)
    _config.set_option("server.headless", True)
    _config.set_option("server.enableCORS", True)
    _config.set_option("server.enableXsrfProtection", False)
    _config.set_option("browser.serverAddress", "127.0.0.1")
    _config.set_option("browser.serverPort", port)
    _config.set_option("browser.gatherUsageStats", False)

    # Build args for bootstrap.run()
    # Signature: run(main_script_path, is_hello, args, flag_options)
    cli_args = [
        "--server.port", str(port),
        "--server.address", DEFAULT_ADDR,
        "--server.headless", "true",
        "--server.enableCORS", "true",
        "--server.enableXsrfProtection", "false",
        "--browser.serverAddress", "127.0.0.1",
        "--browser.serverPort", str(port),
        "--browser.gatherUsageStats", "false",
    ]

    try:
        bootstrap.run(
            main_script_path=script_path,
            is_hello=False,
            args=cli_args,
            flag_options={},
        )
    except SystemExit:
        pass  # Server stopped normally


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=f"QuantSage v{__version__}",
    )
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--reset-config", action="store_true")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--version", action="version", version=f"QuantSage v{__version__}")
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    args = parse_args()

    print(f"\n{'='*60}")
    print(f"  QuantSage v{__version__}")
    print(f"  {'='*60}\n")

    if args.reset_config:
        handle_reset_config()

    # Resolve port
    port = args.port
    if not is_port_available(port):
        print(f"[QuantSage] Port {port} is in use.", end=" ")
        killed = kill_process_on_port(port)
        if killed:
            print("Previous instance terminated.")
            time.sleep(1)
        else:
            port = find_available_port(port)
            print(f"Using port {port} instead.")

    # Find the Streamlit script
    try:
        script_path = _get_streamlit_script()
    except FileNotFoundError as e:
        print(f"[QuantSage] ERROR: {e}")
        return 1

    # Check DISCLAIMER.md
    from src.deployment.resource_path import get_disclaimer_path
    disclaimer = get_disclaimer_path()
    if not disclaimer.exists():
        print(f"[QuantSage] WARNING: DISCLAIMER.md not found at {disclaimer}")

    url = f"http://localhost:{port}"

    # Decide run mode: PyInstaller frozen → in-process, source → subprocess
    is_frozen = getattr(sys, "frozen", False)

    if is_frozen:
        # In-process mode:
        # - Streamlit MUST run in the main thread (needs signal.signal())
        # - Health check + browser open runs in a daemon thread
        print(f"[QuantSage] Starting server (bundled mode)...")

        # Start browser opener in background thread
        browser_thread = threading.Thread(
            target=_wait_and_open_browser,
            args=(port, args.no_browser),
            daemon=True,
        )
        browser_thread.start()

        # Run Streamlit in the MAIN thread (blocks until server exits)
        _run_streamlit_inprocess(script_path, port)

    else:
        # Source mode: spawn Streamlit as a subprocess
        cmd = [
            sys.executable, "-m", "streamlit", "run",
            script_path,
            f"--server.port={port}",
            f"--server.address={DEFAULT_ADDR}",
            "--server.headless=true",
            "--server.enableCORS=false",
            "--server.enableXsrfProtection=false",
            f"--browser.serverAddress=localhost",
            f"--browser.serverPort={port}",
            "--browser.gatherUsageStats=false",
        ]

        print(f"[QuantSage] Starting server (source mode)...")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        print("[QuantSage] Waiting for server...", end="", flush=True)
        if not wait_for_server(port):
            print(" FAILED")
            proc.terminate()
            return 1
        print(" OK")

        if not args.no_browser:
            print(f"[QuantSage] Opening {url}")
            webbrowser.open(url)
        else:
            print(f"[QuantSage] Server at {url} (browser suppressed)")

        print("[QuantSage] Running. Press Ctrl+C to stop.\n")

        # Stream output
        def _stream():
            if proc.stdout:
                for line in proc.stdout:
                    stripped = line.rstrip()
                    if stripped:
                        print(f"  [streamlit] {stripped}")

        output_thread = threading.Thread(target=_stream, daemon=True)
        output_thread.start()

        try:
            while True:
                try:
                    proc.wait(1)
                    break
                except subprocess.TimeoutExpired:
                    continue
                except KeyboardInterrupt:
                    print("\n[QuantSage] Shutting down...")
                    break
        finally:
            try:
                proc.terminate()
                proc.wait(timeout=10)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    print("[QuantSage] Stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
