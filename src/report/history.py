"""Report history storage — save & retrieve past analysis reports.

Saves each report as:
  ~/.quantsage/reports/YYYY-MM-DD_600519.txt (plain text)
Plus an index file:
  ~/.quantsage/reports/index.json (metadata only, no report content)

Limits: 100 most recent reports in index; old .txt files auto-cleaned.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

REPORTS_DIR = Path.home() / ".quantsage" / "reports"
INDEX_FILE = REPORTS_DIR / "index.json"
MAX_REPORTS = 100  # Keep at most this many reports


def save_report(symbol: str, stock_name: str, market: str, report: str,
                decision: dict, trace_id: str = "") -> Optional[Path]:
    """Save report as 日期-股票代码.txt in ~/.quantsage/reports/.

    Returns path to saved file, or None on failure.
    """
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        safe_sym = symbol.replace("/", "_").replace("\\", "_")
        filename = f"{date_str}_{safe_sym}.txt"
        report_file = REPORTS_DIR / filename

        report_file.write_text(report, encoding="utf-8")

        # Update index (metadata only, no report content)
        _update_index(symbol, stock_name, market, decision, str(report_file), trace_id)
        return report_file
    except Exception:
        return None


def _update_index(symbol: str, stock_name: str, market: str,
                  decision: dict, filepath: str, trace_id: str) -> None:
    """Append metadata-only entry to index. Clean up old .txt files beyond MAX_REPORTS."""
    try:
        if INDEX_FILE.exists():
            index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        else:
            index = []
    except Exception:
        index = []

    index.insert(0, {
        "symbol": symbol,
        "stock_name": stock_name,
        "market": market,
        "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "action": decision.get("action", "未知"),
        "confidence": decision.get("confidence", 0),
        "file": filepath,
        "trace_id": trace_id,
    })

    # Trim and clean up old files
    if len(index) > MAX_REPORTS:
        for entry in index[MAX_REPORTS:]:
            old_file = Path(entry.get("file", ""))
            if old_file.exists():
                try:
                    old_file.unlink()
                except Exception:
                    pass
        index = index[:MAX_REPORTS]

    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def load_history() -> list[dict]:
    """Load the report history index (metadata only)."""
    try:
        if INDEX_FILE.exists():
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def clear_history() -> None:
    """Delete all saved reports and index."""
    import shutil
    if REPORTS_DIR.exists():
        shutil.rmtree(REPORTS_DIR)
