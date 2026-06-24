"""Tests for report export (PDF/Markdown) and compliance gate — current pipeline."""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.report.pdf_exporter import export_report_pdf, export_report_markdown
from src.compliance.report_reviewer import (
    review_and_sanitize, sanitize_report_locally,
    validate_sanitized_report, sanitize_decision,
)
from src.compliance.phrase_checker import check_banned_phrases, has_disclaimer


def _make_sample_report() -> str:
    """Build a realistic multi-section report for testing."""
    parts = [
        "# QuantSage 研究报告",
        "**股票代码**: 600519  **股票名称**: 贵州茅台",
        "---",
        "## 📈 技术面分析",
        "这是技术面分析内容。MA5与MA10形成交叉。成交量温和放大。" * 10,
        "",
        "## 📊 基本面分析",
        "这是基本面分析内容。公司营收稳健增长，现金流健康。" * 10,
        "",
        "## 💬 投资者情绪分析",
        "市场情绪中性偏积极。散户关注度上升。" * 10,
        "",
        "## 🛡️ 风险管控与最终决策",
        "综合风险可控。多空因素交织。" * 10,
        "",
        "## 🔮 Kronos 深度学习 K 线预测",
        "Kronos模型预测方向看涨，目标价1420元，置信度73%。" * 3,
        "",
        "## 综合结论",
        "综合来看基本面良好，技术面偏多。模型信号偏积极，供研究参考。" * 5,
        "",
        "---",
        "> 本报告由 QuantSage 自动生成，仅供参考研究，不构成任何投资建议，盈亏自负。",
    ]
    return "\n\n".join(parts)


# === PDF Export Tests ===

def test_export_pdf_creates_file():
    report = _make_sample_report()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        result = export_report_pdf(report, tmp_path)
        assert result.exists()
        assert result.stat().st_size > 100
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def test_export_markdown_creates_file():
    report = _make_sample_report()
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


def test_pdf_is_valid():
    report = _make_sample_report()
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        result = export_report_pdf(report, tmp_path)
        content = result.read_bytes()
        assert content[:4] == b"%PDF", "Not a valid PDF"
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


# === Compliance Tests ===

def test_report_has_disclaimer():
    report = _make_sample_report()
    assert has_disclaimer(report), "Report missing disclaimer"


def test_no_banned_phrases():
    report = _make_sample_report()
    safe = sanitize_report_locally(report)
    violations = check_banned_phrases(safe)
    assert len(violations) == 0, f"Found banned phrases: {violations}"


def test_sanitize_preserves_sections():
    report = _make_sample_report()
    safe, method = review_and_sanitize(report, mode="local")
    assert method == "regex_local"
    for section in ["技术面分析", "基本面分析", "综合结论"]:
        assert section in safe, f"Missing section: {section}"


def test_validate_complete_report():
    report = _make_sample_report()
    safe, _ = review_and_sanitize(report, mode="local")
    ok, missing = validate_sanitized_report(report, safe)
    assert ok is True, f"Validation failed: {missing}"


def test_sanitize_decision():
    decision = {"action": "买入", "confidence": 0.8, "risk_score": 0.3}
    result = sanitize_decision(decision)
    assert result["action"] != "买入"
    assert result["confidence"] == 0.8
