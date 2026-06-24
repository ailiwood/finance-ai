"""Structured report assembler — chapter-by-chapter with completeness validation.

Replaces the flat string concatenation in home.py with a structured builder
that ensures all mandatory sections are present and the disclaimer is always last.
"""

from __future__ import annotations

from typing import List, Tuple, Optional

MANDATORY_SECTIONS = [
    "技术面分析",
    "基本面分析",
    "投资者情绪分析",
    "风险管控与最终研究决策",
    "Kronos 深度学习 K线预测",
    "综合结论",
    "免责声明",
]

_REQUIRED_KEYWORDS = [
    "技术面分析",
    "基本面分析",
    "情绪",
    "风险",
    "Kronos",
    "综合结论",
    "本软件仅供参考研究",
]


def assemble_report_sections(sections: List[Tuple[str, str]]) -> str:
    """Build a full report from labeled sections.

    Args:
        sections: List of (title, content) tuples in display order.

    Returns:
        Complete markdown report string with all sections present.
    """
    parts = ["# QuantSage 研究报告", ""]
    for title, content in sections:
        if not content or not content.strip():
            continue
        parts.append(f"---")
        parts.append(f"## {title}")
        parts.append("")
        parts.append(content.strip())
        parts.append("")

    # Disclaimer always last
    parts.append("---")
    parts.append("> 本报告由 QuantSage 自动生成，仅供参考研究，不构成任何投资建议，盈亏自负。")
    return "\n\n".join(parts)


def sanitize_report_sections(report: str) -> str:
    """Remove any buy/sell/trade instructions from report text.

    Uses local regex rules — no LLM dependency.
    """
    import re

    # Remove trading directive patterns
    patterns = [
        (r'(?:建议|推荐|强烈建议)(?:买入|卖出|做多|做空|加仓|减仓|满仓|清仓)', '[合规过滤]'),
        (r'(?:止损|止盈)(?:位|价|点)[：:]\s*\d+\.?\d*', '[合规过滤]'),
        (r'(?:目标价|目标位)[：:]\s*\d+\.?\d*', '[合规过滤]'),
    ]
    for pattern, replacement in patterns:
        report = re.sub(pattern, replacement, report, flags=re.IGNORECASE)
    return report


def validate_report_completeness(report: str) -> Tuple[bool, List[str]]:
    """Check that all required sections are present.

    Returns:
        (is_complete, missing_sections) tuple.
    """
    missing = []
    # Check for key structural markers
    if "技术面分析" not in report and "技术面" not in report:
        missing.append("技术面分析")
    if "基本面分析" not in report and "基本面" not in report:
        missing.append("基本面分析")
    if "情绪" not in report:
        missing.append("投资者情绪分析")
    if "风险" not in report:
        missing.append("风险管控")
    if "Kronos" not in report:
        missing.append("Kronos 深度学习 K线预测")
    if "综合结论" not in report and "结论" not in report:
        missing.append("综合结论")
    if "仅供参考研究" not in report and "不构成任何投资建议" not in report:
        missing.append("免责声明")

    return len(missing) == 0, missing


def detect_truncation(report: str, min_chars: int = 500) -> bool:
    """Heuristic: check if report appears truncated.

    A complete report should end with a disclaimer or proper closing.
    """
    report = report.strip()
    if len(report) < min_chars:
        return True
    # Check ending — should contain disclaimer
    last_200 = report[-200:]
    if "免责" not in last_200 and "仅供参考" not in last_200:
        return True
    # Check for obvious mid-sentence cutoff
    if report[-1] not in ".。！？\n*>)":
        return True
    return False


def render_markdown(sections: List[Tuple[str, str]]) -> str:
    """Main entry point: assemble, sanitize, validate, return complete report.

    This is a LOCAL-ONLY pipeline — no LLM rewriting.
    For LLM-based compliance review, use src/compliance/report_reviewer.py
    on individual sections, not the full report.
    """
    report = assemble_report_sections(sections)
    report = sanitize_report_sections(report)
    is_complete, missing = validate_report_completeness(report)
    if not is_complete:
        missing_str = ", ".join(missing)
        report += f"\n\n---\n> ⚠️ 报告完整性警告：缺少章节 — {missing_str}"
    return report
