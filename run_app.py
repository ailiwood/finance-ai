"""QuantSage Streamlit entry point (PyInstaller-friendly wrapper).

This wrapper ensures the bundle's Python path is set up correctly
before Streamlit loads the main app. Any import errors are printed
to the console so they are visible in the CMD window.
"""

import sys
from pathlib import Path

# Ensure the PyInstaller extraction directory is on sys.path
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    if sys._MEIPASS not in sys.path:
        sys.path.insert(0, sys._MEIPASS)

# Diagnostic: verify critical imports
_IMPORT_ERRORS = []

def _check(module_name: str) -> None:
    try:
        __import__(module_name)
        print(f"  [OK] {module_name}")
    except Exception as e:
        print(f"  [FAIL] {module_name}: {e}")
        _IMPORT_ERRORS.append((module_name, str(e)))

print("\n[QuantSage] Verifying imports...")
_check("streamlit")
_check("src.deployment.resource_path")
_check("src.deployment.version")
_check("src.core.config_manager")
_check("src.compliance.disclaimer")
_check("src.compliance.phrase_checker")
_check("src.report.templates")
_check("src.report.pdf_exporter")
_check("src.report.report_generator")
_check("src.ui.app")
_check("src.ui.home")
_check("src.ui.config_wizard")
_check("src.ui.disclaimer_gate")
_check("src.ui.plugin_manager")
_check("cryptography")
_check("fpdf")

if _IMPORT_ERRORS:
    print(f"\n[QuantSage] WARNING: {len(_IMPORT_ERRORS)} import(s) failed!")
    for mod, err in _IMPORT_ERRORS:
        print(f"  - {mod}: {err}")
else:
    print("[QuantSage] All imports OK.\n")

# Now load and run the actual Streamlit app
from src.ui.app import main

if __name__ == "__main__":
    main()
