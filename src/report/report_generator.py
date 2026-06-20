"""Report generator: transforms multi-agent analysis output into structured reports.

Integrates compliance scanning from src.compliance.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from datetime import datetime

from src.report.templates import (
    ReportData, SectionData, AgentOpinion,
    assemble_report,
)
from src.compliance.phrase_checker import check_banned_phrases, has_disclaimer
from src.compliance.disclaimer import get_footer_text


def generate_report(
    symbol: str,
    stock_name: str,
    analysis_output: Dict[str, Any],
    plugins_used: Optional[List[str]] = None,
    gpu_used: bool = False,
) -> tuple[str, ReportData]:
    """Generate a full QuantSage report from TradingAgents-CN output.

    Args:
        symbol: Stock symbol (e.g. "600519")
        stock_name: Stock name (e.g. "贵州茅台")
        analysis_output: Raw output from TradingAgentsGraph.propagate()
        plugins_used: List of plugin names used (e.g. ["kronos", "finbert"])
        gpu_used: Whether GPU acceleration was used

    Returns:
        (markdown_report: str, report_data: ReportData)
    """
    sections = _extract_sections(analysis_output)
    conclusion = _extract_conclusion(analysis_output)
    risk_score = _extract_risk_score(analysis_output)
    target_price = _extract_target_price(analysis_output)

    data: ReportData = {
        "symbol": symbol,
        "stock_name": stock_name,
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "sections": sections,
        "conclusion": conclusion,
        "risk_score": risk_score,
        "target_price": target_price,
        "plugins_used": plugins_used or [],
        "gpu_used": gpu_used,
        "generation_time_seconds": 0.0,
    }

    report = assemble_report(data)

    # Compliance check
    violations = check_banned_phrases(report)
    if violations:
        # Log warning but don't block — the disclaimer footer mitigates
        import warnings
        warnings.warn(f"Report contains compliance violations: {violations}")

    return report, data


def _extract_sections(output: Dict[str, Any]) -> List[SectionData]:
    """Extract the 4 analysis sections from TradingAgents-CN output."""
    sections: List[SectionData] = []

    # Try to extract from structured output
    # TradingAgents-CN output format: {decision, ...agent outputs...}

    # Section 1: 基本面分析
    fundamentals = _find_section(output, [
        "fundamental", "fundamentals", "基本面", "基本面分析",
    ])
    if fundamentals:
        sections.append(SectionData(
            title="基本面分析",
            icon="",
            summary=fundamentals.get("summary", "基于财务数据的公司基本面评估"),
            opinions=fundamentals.get("opinions", [
                AgentOpinion(
                    agent_name="基本面分析师",
                    direction="中性",
                    confidence=0.5,
                    reasoning=fundamentals.get("text", output.get("reasoning", "详见原始分析输出")),
                    key_points=fundamentals.get("key_points", []),
                ),
            ]),
            data_highlights=fundamentals.get("data_highlights", []),
        ))
    else:
        sections.append(_make_default_section("基本面分析"))

    # Section 2: 技术面分析
    technical = _find_section(output, [
        "technical", "market", "技术面", "技术分析",
    ])
    if technical:
        sections.append(SectionData(
            title="技术面分析",
            icon="",
            summary=technical.get("summary", "基于价格和成交量的技术指标分析"),
            opinions=technical.get("opinions", []),
            data_highlights=technical.get("data_highlights", []),
        ))
    else:
        sections.append(_make_default_section("技术面分析"))

    # Section 3: 情绪面分析
    sentiment = _find_section(output, [
        "sentiment", "news", "social", "情绪面", "情绪分析", "新闻",
    ])
    if sentiment:
        sections.append(SectionData(
            title="情绪面分析",
            icon="",
            summary=sentiment.get("summary", "基于新闻和社交媒体情绪的分析"),
            opinions=sentiment.get("opinions", []),
            data_highlights=sentiment.get("data_highlights", []),
        ))
    else:
        sections.append(_make_default_section("情绪面分析"))

    # Section 4: 风险管控
    risk = _find_section(output, [
        "risk", "风险管理", "风险管控", "risk_mgmt",
    ])
    if risk:
        sections.append(SectionData(
            title="风险管控",
            icon="",
            summary=risk.get("summary", "多维风险评估"),
            opinions=risk.get("opinions", []),
            data_highlights=risk.get("data_highlights", []),
        ))
    else:
        sections.append(_make_default_section("风险管控"))

    return sections


def _find_section(output: Dict[str, Any], keys: List[str]) -> Optional[Dict[str, Any]]:
    """Find a section in the output by matching keys."""
    for key in keys:
        if key in output:
            val = output[key]
            if isinstance(val, dict):
                return val
            if isinstance(val, str):
                return {"text": val, "summary": val[:200]}
    return None


def _extract_conclusion(output: Dict[str, Any]) -> AgentOpinion:
    """Extract the final conclusion from analysis output."""
    decision = output.get("decision", output)
    if isinstance(decision, dict):
        action = decision.get("action", "中性")
        direction_map = {"卖出": "看空", "买入": "看多", "持有": "中性"}
        return AgentOpinion(
            agent_name="综合决策",
            direction=direction_map.get(str(action), "中性"),
            confidence=float(decision.get("confidence", 0.5)),
            reasoning=str(decision.get("reasoning", output.get("reasoning", "详见分析报告"))),
            key_points=[],
        )
    return AgentOpinion(
        agent_name="综合决策",
        direction="中性",
        confidence=0.5,
        reasoning=str(output.get("reasoning", str(decision))) if decision else "详见分析报告",
        key_points=[],
    )


def _extract_risk_score(output: Dict[str, Any]) -> float:
    """Extract risk score from output."""
    decision = output.get("decision", output)
    if isinstance(decision, dict):
        return float(decision.get("risk_score", 0.5))
    return float(output.get("risk_score", 0.5))


def _extract_target_price(output: Dict[str, Any]) -> Optional[float]:
    """Extract target price from output."""
    decision = output.get("decision", output)
    if isinstance(decision, dict):
        tp = decision.get("target_price")
        if tp:
            return float(tp)
    tp = output.get("target_price")
    return float(tp) if tp else None


def _make_default_section(title: str) -> SectionData:
    """Create a placeholder section when data is unavailable."""
    return SectionData(
        title=title,
        icon="",
        summary=f"{title}数据暂不可用，请确认数据源配置。",
        opinions=[],
        data_highlights=[],
    )
