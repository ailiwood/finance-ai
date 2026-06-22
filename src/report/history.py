"""Report history storage — save & retrieve past analysis reports.

Stores each report as:
  ~/.quantsage/reports/{symbol}/{timestamp}.json
Plus an index file:
  ~/.quantsage/reports/index.json
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

REPORTS_DIR = Path.home() / ".quantsage" / "reports"
INDEX_FILE = REPORTS_DIR / "index.json"


def save_report(symbol: str, stock_name: str, market: str, report: str,
                decision: dict, trace_id: str = "") -> Optional[Path]:
    """Save a completed analysis report to local storage.

    Args:
        symbol: Stock code (e.g., "600519")
        stock_name: Company name
        market: Market label
        report: Full markdown report text
        decision: Decision dict (action, confidence, risk_score, etc.)
        trace_id: Analysis trace ID

    Returns:
        Path to saved report file, or None on failure.
    """
    try:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_sym = symbol.replace("/", "_").replace("\\", "_")
        report_dir = REPORTS_DIR / safe_sym
        report_dir.mkdir(parents=True, exist_ok=True)

        report_file = report_dir / f"{ts}.json"
        data = {
            "symbol": symbol,
            "stock_name": stock_name,
            "market": market,
            "analyzed_at": datetime.now().isoformat(),
            "trace_id": trace_id,
            "decision": {
                "action": decision.get("action", "未知"),
                "confidence": decision.get("confidence", 0),
                "risk_score": decision.get("risk_score", 0),
                "target_price": decision.get("target_price"),
                "reasoning": str(decision.get("reasoning", ""))[:500],
            },
            "report": report,
        }
        report_file.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Update index
        _update_index(symbol, safe_sym, stock_name, market, ts, decision, str(report_file))
        return report_file
    except Exception:
        return None


def _update_index(symbol: str, safe_sym: str, stock_name: str, market: str,
                  ts: str, decision: dict, filepath: str) -> None:
    """Append entry to the report index."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
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
        "analyzed_at": f"{ts[:4]}-{ts[4:6]}-{ts[6:8]} {ts[9:11]}:{ts[11:13]}:{ts[13:15]}",
        "action": decision.get("action", "未知"),
        "confidence": decision.get("confidence", 0),
        "file": filepath,
    })

    # Keep last 100 entries
    index = index[:100]
    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def load_history() -> list[dict]:
    """Load the report history index, newest first."""
    try:
        if INDEX_FILE.exists():
            return json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def load_report(filepath: str) -> Optional[dict]:
    """Load a specific report by file path."""
    try:
        p = Path(filepath)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def clear_history() -> None:
    """Delete all saved reports."""
    import shutil
    if REPORTS_DIR.exists():
        shutil.rmtree(REPORTS_DIR)
