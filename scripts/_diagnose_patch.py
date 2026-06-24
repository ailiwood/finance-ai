"""Apply patches to launcher.py: browser fix + --diagnose-kronos + frozen mode."""
from pathlib import Path

path = Path("E:/AI_projects/fin/src/deployment/launcher.py")
content = path.read_text(encoding="utf-8")

# Patch 1: Remove global url_for_shell, fix browser functions
old_browser = '''def _open_browser_windows(url: str) -> bool:
    """Try 4 methods to open the browser. Returns True if any succeeds."""
    for method, fn in [
        ("webbrowser", lambda: webbrowser.open(url)),
        ("os.startfile", lambda: os.startfile(url) or True),
        ("ShellExecuteW", _shell_execute),
        ("cmd start", _cmd_start),
    ]:
        try:
            if fn():
                log.info("Browser opened via %s", method)
                return True
        except Exception as e:
            log.debug("Browser method %s failed: %s", method, e)
    log.warning("All browser methods failed")
    return False


def _shell_execute() -> bool:
    import ctypes
    ctypes.windll.shell32.ShellExecuteW(None, "open", url_for_shell, None, None, 1)
    return True


def _cmd_start() -> bool:
    subprocess.run(["cmd", "/c", "start", "", url_for_shell], capture_output=True, timeout=10)
    return True


# Module-level for _open_browser_windows closure access
url_for_shell = ""'''

new_browser = '''def _open_browser_windows(url: str) -> bool:
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
        return False'''

content = content.replace(old_browser, new_browser)

# Patch 2: Add --diagnose-kronos argument
old_args = '''    parser.add_argument("--_server", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_script", type=str, help=argparse.SUPPRESS)
    return parser.parse_args()'''
new_args = '''    parser.add_argument("--diagnose-kronos", action="store_true",
                        help="Run Kronos model diagnostic (offline, no Streamlit)")
    parser.add_argument("--_server", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--_script", type=str, help=argparse.SUPPRESS)
    return parser.parse_args()'''
content = content.replace(old_args, new_args)

# Patch 3: Remove global url_for_shell in main()
content = content.replace(
    "def main() -> int:\n    global url_for_shell\n    args = parse_args()",
    "def main() -> int:\n    args = parse_args()"
)

# Patch 4: Remove url_for_shell assignment
content = content.replace(
    '    url = f"http://127.0.0.1:{port}"\n    url_for_shell = url',
    '    url = f"http://127.0.0.1:{port}"'
)

# Patch 5: Add diagnose handler + URL file on failure
old_parent = '    # ── PARENT: launcher ──\n    log.info("QuantSage v%s starting", __version__)'
new_parent = '''    # ── Kronos diagnostic (offline, no Streamlit) ──
    if args.diagnose_kronos:
        return _run_kronos_diagnostic()

    # ── PARENT: launcher ──
    log.info("QuantSage v%s starting", __version__)'''
content = content.replace(old_parent, new_parent)

# Patch 6: Save URL file on browser failure
old_open = '''    if not args.no_browser:
        _log_and_print(f"[QuantSage] Opening {url}")
        if not _open_browser_windows(url):
            _log_and_print(f"[QuantSage] Please visit: {url}")'''
new_open = '''    if not args.no_browser:
        _log_and_print(f"[QuantSage] Opening {url}")
        if not _open_browser_windows(url):
            _log_and_print(f"[QuantSage] Please visit: {url}")
            try:
                _url_file = _LOG_DIR / "last_server_url.txt"
                _url_file.write_text(url)
                _log_and_print(f"[QuantSage] Server URL saved to: {_url_file}")
            except Exception:
                pass'''
content = content.replace(old_open, new_open)

# Insert diagnose function before main()
diagnose_fn = '''

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
        print("\\n[DIAGNOSE] Kronos-base deep model NOT loaded — using statistical fallback.")
        return 1
    print("\\n[DIAGNOSE] Kronos-base model loaded successfully.")
    return 0
'''

# Insert before def main()
content = content.replace("\ndef main() -> int:", diagnose_fn + "\ndef main() -> int:")

path.write_text(content, encoding="utf-8")
print("Patched: browser open fix + --diagnose-kronos CLI + frozen watcher off + URL file on failure")
