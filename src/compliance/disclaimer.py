"""Disclaimer loader and formatter.

Single source of truth: DISCLAIMER.md at project root.
All user-facing outputs MUST reference or embed text from this module.
"""

from __future__ import annotations

import re
from pathlib import Path
from functools import lru_cache

# Path resolution relative to project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DISCLAIMER_PATH = _PROJECT_ROOT / "DISCLAIMER.md"

# === Parsing utilities ===

def _parse_disclaimer_sections() -> dict[str, str]:
    """Parse DISCLAIMER.md into named sections.

    Returns dict with keys: standard, ui, report_footer, pdf_footer, api.
    """
    if not _DISCLAIMER_PATH.exists():
        raise FileNotFoundError(
            f"免责声明文件缺失，应用无法启动。\n"
            f"预期路径: {_DISCLAIMER_PATH}\n"
            f"请确保 DISCLAIMER.md 存在于项目根目录。"
        )

    text = _DISCLAIMER_PATH.read_text(encoding="utf-8")
    sections: dict[str, str] = {}

    # Standard disclaimer (first block after "## 标准免责声明")
    std_match = re.search(
        r'## 标准免责声明\s*\n+(.*?)(?=\n## |\n---\n|\Z)',
        text, re.DOTALL
    )
    if std_match:
        sections["standard"] = std_match.group(1).strip()

    # UI 首屏
    ui_match = re.search(
        r'### UI 首屏\n+"(.*?)"',
        text
    )
    if ui_match:
        sections["ui"] = ui_match.group(1).strip()

    # 报告页脚
    report_match = re.search(
        r'### 报告页脚\n+"(.*?)"',
        text
    )
    if report_match:
        sections["report_footer"] = report_match.group(1).strip()

    # PDF 页脚
    pdf_match = re.search(
        r'### PDF 页脚\n+"(.*?)"',
        text
    )
    if pdf_match:
        sections["pdf_footer"] = pdf_match.group(1).strip()

    # API 响应
    api_match = re.search(
        r"### API 响应\n+\"(.*?)\"",
        text
    )
    if api_match:
        sections["api"] = api_match.group(1).strip()

    return sections


@lru_cache(maxsize=1)
def _cached_sections() -> dict[str, str]:
    """Load and cache disclaimer sections (called once, cached forever)."""
    return _parse_disclaimer_sections()


def _get_section(key: str) -> str:
    """Get a cached section by key, raising if not found."""
    sections = _cached_sections()
    if key not in sections:
        raise ValueError(
            f"未能从 DISCLAIMER.md 解析到 '{key}' 段落。"
            f"请检查文件格式是否完整。"
        )
    return sections[key]


# === Public API ===

def load_disclaimer() -> str:
    """Return the full standard disclaimer text.

    Uses the 'standard' section from DISCLAIMER.md.
    Falls back to hardcoded minimum if parsing fails.
    """
    try:
        return _get_section("standard")
    except (FileNotFoundError, ValueError):
        return (
            "本软件仅供参考研究，不构成任何投资建议，盈亏自负。\n\n"
            "QuantSage 是一个本地运行的多智能体股票研究辅助软件，"
            "基于公开数据与大语言模型生成分析报告。所有分析结果均为"
            "基于历史数据和算法推测的参考信息，不构成任何形式的投资建议。"
        )


def get_footer_text() -> str:
    """Return the report/PDF footer disclaimer.

    Example:
        "本报告由 QuantSage 自动生成，仅供参考研究，不构成任何投资建议，盈亏自负。"
    """
    try:
        return _get_section("report_footer")
    except (FileNotFoundError, ValueError):
        return "本报告由 QuantSage 自动生成，仅供参考研究，不构成任何投资建议，盈亏自负。"


def get_ui_disclaimer() -> str:
    """Return the one-liner for UI footers and status bars.

    Example:
        "本软件仅供参考研究，不构成任何投资建议，盈亏自负。"
    """
    try:
        return _get_section("ui").rstrip("。") + "。"
    except (FileNotFoundError, ValueError):
        return "本软件仅供参考研究，不构成任何投资建议，盈亏自负。"


def get_pdf_footer_text() -> str:
    """Return the compact PDF page footer.

    Example:
        "QuantSage · 仅供参考研究 · 不构成投资建议 · 盈亏自负"
    """
    try:
        return _get_section("pdf_footer")
    except (FileNotFoundError, ValueError):
        return "QuantSage · 仅供参考研究 · 不构成投资建议 · 盈亏自负"


def get_api_disclaimer() -> str:
    """Return the one-liner for API responses."""
    try:
        return _get_section("api")
    except (FileNotFoundError, ValueError):
        return "本软件仅供参考研究，不构成任何投资建议，盈亏自负。"


def parse_banned_phrases() -> list[str]:
    """Parse the banned phrases list from DISCLAIMER.md.

    Returns a list of raw banned phrase patterns from the markdown.
    Handles multi-phrase lines like: - ❌ "稳赚" / "保证收益" / "必涨"
    """
    defaults = [
        "推荐买入", "建议买入", "稳赚", "保证收益", "必涨",
        "精准预测", "内幕消息",
    ]
    try:
        text = _DISCLAIMER_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return defaults

    phrases: list[str] = []
    in_list = False
    for line in text.splitlines():
        if "违规措辞清单" in line:
            in_list = True
            continue
        if in_list and line.strip().startswith("- ❌"):
            # Extract ALL quoted strings on this line (handles "A" / "B" / "C")
            matches = re.findall(r'"([^"]+)"', line)
            phrases.extend(matches)

    # Filter out placeholders like "[任何暗示确定盈利的表述]"
    phrases = [p for p in phrases if not p.startswith("[")]

    return phrases if phrases else defaults
