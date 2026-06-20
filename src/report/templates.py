"""Report structure templates.

Defines the standard 4-section report format:
1. 基本面分析 (Fundamentals)
2. 技术面分析 (Technical)
3. 情绪面分析 (Sentiment)
4. 风险管控 (Risk Management)
+ 综合结论 (Comprehensive Conclusion)
"""

from __future__ import annotations

from typing import TypedDict, List, Optional
from datetime import datetime
from src.compliance.disclaimer import get_footer_text, get_ui_disclaimer


class AgentOpinion(TypedDict):
    """Single agent's output in standardized format."""
    agent_name: str        # e.g. "基本面分析师", "多头研究员"
    direction: str         # "看多" / "看空" / "中性"
    confidence: float      # 0.0 - 1.0
    reasoning: str         # Full reasoning text
    key_points: List[str]  # 3-5 key bullet points


class SectionData(TypedDict):
    """Data for one report section."""
    title: str
    icon: str
    summary: str            # 1-2 sentence section summary
    opinions: List[AgentOpinion]
    data_highlights: List[str]  # key data points


class ReportData(TypedDict):
    """Complete report data structure."""
    symbol: str
    stock_name: str
    analysis_date: str
    sections: List[SectionData]
    conclusion: AgentOpinion      # final combined verdict
    risk_score: float             # 0.0 - 1.0
    target_price: Optional[float]
    plugins_used: List[str]       # e.g. ["kronos", "finbert"]
    gpu_used: bool
    generation_time_seconds: float


def report_header(symbol: str, stock_name: str, date: str) -> str:
    """Generate report header."""
    return f"""# QuantSage 研究报告

**股票代码**: {symbol}
**股票名称**: {stock_name}
**分析日期**: {date}

---
"""


def report_footer() -> str:
    """Generate report footer with disclaimer."""
    return f"""

---

> {get_footer_text()}

*QuantSage · 仅供参考研究 · 不构成投资建议*
"""


def section_template(section: SectionData) -> str:
    """Render a single report section as markdown.

    Includes each agent's {方向, 置信度, 理由} in standardized format.
    """
    lines = [
        f"## {section['icon']} {section['title']}",
        "",
        f"**摘要**: {section['summary']}",
        "",
    ]

    # Data highlights
    if section.get("data_highlights"):
        lines.append("**关键数据**:")
        for dh in section["data_highlights"]:
            lines.append(f"- {dh}")
        lines.append("")

    # Agent opinions with standardized {方向, 置信度, 理由}
    for opinion in section.get("opinions", []):
        lines.append(f"### {opinion['agent_name']}")
        lines.append("")
        lines.append(f"**研究观点**: {opinion['direction']}")
        lines.append(f"**置信度**: {opinion['confidence']:.0%}")
        lines.append(f"**理由**: {opinion['reasoning']}")
        lines.append("")
        if opinion.get("key_points"):
            for kp in opinion["key_points"]:
                lines.append(f"- {kp}")
            lines.append("")

    return "\n".join(lines)


def conclusion_template(conclusion: AgentOpinion, risk_score: float, target_price: Optional[float]) -> str:
    """Render the comprehensive conclusion section."""
    lines = [
        "---",
        "",
        "## 综合结论",
        "",
        f"**最终观点**: {conclusion['direction']}",
        f"**置信度**: {conclusion['confidence']:.0%}",
        f"**风险评分**: {risk_score:.1%}",
    ]

    if target_price:
        lines.append(f"**参考价位**: ¥{target_price:,.2f}")

    lines.extend([
        "",
        f"**综合推理**: {conclusion['reasoning']}",
        "",
    ])

    if conclusion.get("key_points"):
        lines.append("**关键要点**:")
        for kp in conclusion["key_points"]:
            lines.append(f"- {kp}")

    return "\n".join(lines)


def assemble_report(data: ReportData) -> str:
    """Assemble a complete report from structured data.

    Args:
        data: Complete ReportData with all sections filled.

    Returns:
        Full markdown report string with header, sections, conclusion, and footer.
    """
    parts = [report_header(data["symbol"], data["stock_name"], data["analysis_date"])]

    for section in data["sections"]:
        parts.append(section_template(section))

    if data.get("conclusion"):
        parts.append(conclusion_template(
            data["conclusion"],
            data.get("risk_score", 0.5),
            data.get("target_price"),
        ))

    # Plugin status
    if data.get("plugins_used"):
        plugins_str = ", ".join(data["plugins_used"])
        gpu_note = " (GPU 加速)" if data.get("gpu_used") else ""
        parts.append(f"\n**分析插件**: {plugins_str}{gpu_note}\n")

    parts.append(report_footer())

    return "\n".join(parts)
