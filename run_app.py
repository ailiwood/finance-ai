"""QuantSage Streamlit entry point (PyInstaller-friendly wrapper)."""
import sys, os
from pathlib import Path

# Write a marker file to prove this script was executed
_marker = Path(os.environ.get("TEMP", "/tmp")) / "quantsage_run_app_executed.txt"
_marker.write_text("run_app.py WAS executed\nsys.argv: " + repr(sys.argv) + "\n__name__: " + repr(__name__) + "\nfrozen: " + str(getattr(sys, "frozen", False)) + "\nMEIPASS: " + str(getattr(sys, "_MEIPASS", "N/A")))

# Ensure the PyInstaller extraction directory is on sys.path
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    if sys._MEIPASS not in sys.path:
        sys.path.insert(0, sys._MEIPASS)

# Load the actual Streamlit app
from src.ui.app import main

if __name__ == "__main__":
    main()
