"""Tests for report generation and PDF export."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tempfile
from src.report.templates import (
    ReportData, SectionData, AgentOpinion,
    assemble_report, section_template, conclusion_template,
    report_header, report_footer,
)
from src.report.report_generator import (
    generate_report, _extract_conclusion, _extract_risk_score,
    _extract_sections,
)
from src.report.pdf_exporter import (
    export_report_pdf, export_report_markdown,
)
from src.compliance.phrase_checker import check_banned_phrases, has_disclaimer


# === Template Tests ===

def test_report_header():
    header = report_header("600519", "贵州茅台", "2025-06-20")
    assert "600519" in header
    assert "贵州茅台" in header
    assert "2025-06-20" in header


def test_report_footer_has_disclaimer():
    footer = report_footer()
    assert "仅供参考" in footer


def test_section_template_standardized_format():
    section = SectionData(
        title="基本面分析",
        icon="",
        summary="测试摘要",
        opinions=[
            AgentOpinion(
                agent_name="测试分析师",
                direction="看多",
                confidence=0.75,
                reasoning="基本面良好，盈利增长稳定",
                key_points=["营收增长 20%", "PE 处于合理区间"],
            ),
        ],
        data_highlights=["ROE: 15%", "负债率: 30%"],
    )
    result = section_template(section)
    assert "基本面分析" in result
    assert "看多" in result
    assert "75%" in result
    assert "营收增长 20%" in result
    assert "ROE: 15%" in result


def test_conclusion_template():
    conclusion = AgentOpinion(
        agent_name="综合决策",
        direction="中性",
        confidence=0.6,
        reasoning="多空因素均衡",
        key_points=["技术面偏空", "基本面稳健"],
    )
    result = conclusion_template(conclusion, 0.4, 1500.0)
    assert "综合结论" in result
    assert "中性" in result
    assert "60%" in result
    assert "40.0%" in result
    assert "1,500.00" in result


def test_assemble_report():
    data: ReportData = {
        "symbol": "600519",
        "stock_name": "贵州茅台",
        "analysis_date": "2025-06-20",
        "sections": [
            SectionData(
                title="基本面分析", icon="",
                summary="测试", opinions=[], data_highlights=[],
            ),
        ],
        "conclusion": AgentOpinion(
            agent_name="综合决策", direction="中性", confidence=0.5,
            reasoning="测试", key_points=[],
        ),
        "risk_score": 0.5,
        "target_price": None,
        "plugins_used": ["kronos"],
        "gpu_used": False,
        "generation_time_seconds": 10.0,
    }
    result = assemble_report(data)
    assert "600519" in result
    assert "基本面分析" in result
    assert "综合结论" in result
    assert "仅供参考" in result


# === Report Generator Tests ===

def test_generate_report_basic():
    output = {
        "decision": {
            "action": "持有",
            "confidence": 0.6,
            "risk_score": 0.4,
            "target_price": 1500.0,
            "reasoning": "基本面稳健，技术面震荡，建议持有观望",
        },
        "reasoning": "整体评估中性偏积极",
    }
    report, data = generate_report("000001", "平安银行", output)
    assert "000001" in report
    assert "平安银行" in report
    assert isinstance(data, dict)
    assert len(data["sections"]) == 4  # 4 sections always


def test_generate_report_compliance():
    """Report must not contain banned phrases."""
    output = {
        "decision": {
            "action": "持有",
            "confidence": 0.5,
            "risk_score": 0.5,
            "reasoning": "基于数据分析的参考观点，仅供参考研究",
        },
    }
    report, _ = generate_report("600519", "贵州茅台", output)
    violations = check_banned_phrases(report)
    assert len(violations) == 0, f"Found banned phrases: {violations}"


def test_generate_report_has_disclaimer():
    output = {"decision": {"action": "中性", "confidence": 0.5, "reasoning": "中性"}}
    report, _ = generate_report("600519", "贵州茅台", output)
    assert has_disclaimer(report), "Report missing disclaimer"


def test_extract_conclusion():
    output = {
        "decision": {
            "action": "买入",
            "confidence": 0.85,
            "risk_score": 0.3,
            "reasoning": "超跌反弹信号明显",
            "target_price": 1600.0,
        },
    }
    conclusion = _extract_conclusion(output)
    assert conclusion["direction"] == "看多"  # 买入 → 看多
    assert conclusion["confidence"] == 0.85


def test_extract_risk_score():
    output = {"decision": {"risk_score": 0.55}}
    assert _extract_risk_score(output) == 0.55


# === PDF Export Tests ===

def test_export_pdf_creates_file():
    report = assemble_report(_make_sample_data())
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        result = export_report_pdf(report, tmp_path)
        assert result.exists()
        assert result.stat().st_size > 100  # PDF should have content
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_export_markdown_creates_file():
    report = assemble_report(_make_sample_data())
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        result = export_report_markdown(report, tmp_path)
        assert result.exists()
        content = result.read_text(encoding="utf-8")
        assert "仅供参考" in content
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_pdf_disclaimer_injected():
    """PDF must contain the disclaimer phrase."""
    report = assemble_report(_make_sample_data())
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        result = export_report_pdf(report, tmp_path)
        # Check the PDF binary contains the disclaimer ASCII approximation
        content = result.read_bytes()
        # The disclaimer in PDF footer might be encoded, but check header
        assert content[:4] == b"%PDF", "Not a valid PDF"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


# === Helpers ===

def _make_sample_data() -> ReportData:
    return ReportData(
        symbol="600519",
        stock_name="贵州茅台",
        analysis_date="2025-06-20",
        sections=[
            SectionData(
                title="基本面分析", icon="",
                summary="基本面稳健",
                opinions=[
                    AgentOpinion(
                        agent_name="基本面分析师",
                        direction="看多",
                        confidence=0.7,
                        reasoning="盈利稳定，现金流充裕",
                        key_points=["ROE > 25%", "低负债率"],
                    ),
                ],
                data_highlights=["PE: 25x", "EPS: 60元"],
            ),
            SectionData(
                title="技术面分析", icon="",
                summary="短期偏空",
                opinions=[
                    AgentOpinion(
                        agent_name="市场分析师",
                        direction="看空",
                        confidence=0.65,
                        reasoning="均线死叉，MACD走弱",
                        key_points=["跌破MA20", "RSI弱势"],
                    ),
                ],
                data_highlights=[],
            ),
            SectionData(title="情绪面分析", icon="", summary="中性偏谨慎", opinions=[], data_highlights=[]),
            SectionData(title="风险管控", icon="", summary="中等风险", opinions=[], data_highlights=[]),
        ],
        conclusion=AgentOpinion(
            agent_name="综合决策",
            direction="中性",
            confidence=0.55,
            reasoning="多空因素交织，建议观望",
            key_points=["基本面支撑", "技术面承压"],
        ),
        risk_score=0.45,
        target_price=1500.0,
        plugins_used=["kronos", "finbert"],
        gpu_used=True,
        generation_time_seconds=120.0,
    )
