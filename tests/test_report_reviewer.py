"""Tests for report_reviewer compliance gate — updated for local-first architecture."""
import pytest
from src.compliance.report_reviewer import (
    review_and_sanitize,
    sanitize_decision,
    sanitize_report_locally,
    validate_sanitized_report,
    find_prohibited_instruction_patterns,
)


class TestLocalSanitize:
    """Test sanitize_report_locally (public API, deterministic regex)."""

    def test_removes_buy_recommendation(self):
        result = sanitize_report_locally("建议买入该股票，目标价1380元")
        assert "建议买入" not in result

    def test_removes_sell_recommendation(self):
        result = sanitize_report_locally("建议卖出该股票，止损位15元")
        assert "建议卖出" not in result

    def test_removes_guarantee_phrases(self):
        result = sanitize_report_locally("稳赚不赔的好机会，必涨无疑")
        assert "稳赚" not in result
        assert "必涨" not in result

    def test_removes_precise_prediction(self):
        result = sanitize_report_locally("精准预测明日涨停")
        assert "精准预测" not in result

    def test_preserves_neutral_content(self):
        original = "公司营收同比增长15%，现金流健康"
        result = sanitize_report_locally(original)
        assert "营收同比增长15%" in result
        assert "现金流健康" in result

    def test_removes_target_price(self):
        result = sanitize_report_locally("目标价: 200元")
        assert "200元" not in result or "参考" in result

    def test_preserves_neutral_positive(self):
        """'中性偏积极' must not be corrupted."""
        result = sanitize_report_locally("市场情绪：中性偏积极")
        assert "中性偏积极" in result

    def test_preserves_markdown_headings(self):
        text = "## 技术面分析\n这是技术面内容\n## 基本面分析\n这是基本面内容"
        result = sanitize_report_locally(text)
        assert "## 技术面分析" in result
        assert "## 基本面分析" in result

    def test_long_report_not_truncated(self):
        """12000+ char report must not be shortened by local sanitization."""
        long_text = ("## 技术面分析\n" + "这是技术面分析内容。\n" * 50 +
                     "## 基本面分析\n" + "这是基本面分析内容。\n" * 50 +
                     "## 综合结论\n" + "这是综合结论内容。\n" * 20 +
                     "本软件仅供参考研究，不构成任何投资建议，盈亏自负。")
        result = sanitize_report_locally(long_text)
        assert len(result) >= len(long_text) * 0.95  # should not be significantly shorter
        assert "技术面分析" in result
        assert "综合结论" in result

    def test_removes_best_buy_point(self):
        result = sanitize_report_locally("现在就是买入的最佳时机，最佳买点已现")
        assert "最佳买点" not in result
        assert "最佳买入时机" not in result


class TestValidateSanitizedReport:
    """Test completeness validation."""

    def test_complete_report_passes(self):
        long_content = "这是分析内容段落。包含足够的信息来通过最小长度检查。" * 10
        report = ("## 技术面分析\n" + long_content +
                  "\n## 基本面分析\n" + long_content +
                  "\n## 投资者情绪分析\n" + long_content +
                  "\n## 风险管控与最终研究结论\n" + long_content +
                  "\n## Kronos 深度学习 K 线预测\n" + long_content +
                  "\n## 综合结论\n" + long_content +
                  "\n本报告仅供参考研究，不构成任何投资建议，盈亏自负。")
        ok, missing = validate_sanitized_report(report, report)
        assert ok is True, f"Missing: {missing}"

    def test_missing_sections_detected(self):
        report = "## 技术面分析\n简短内容"
        ok, missing = validate_sanitized_report(report, report)
        assert ok is False
        assert len(missing) > 0

    def test_disclaimer_at_end_required(self):
        # Report missing the mandatory disclaimer at the end (> 500 chars)
        long_line = "这是分析内容段落包含足够的信息来通过最小长度检查。" * 8
        report = ("## 技术面分析\n" + long_line +
                  "\n## 基本面分析\n" + long_line +
                  "\n## 投资者情绪分析\n" + long_line +
                  "\n## 风险管控\n" + long_line +
                  "\n## Kronos 深度学习 K 线预测\n" + long_line +
                  "\n## 综合结论\n" + long_line +
                  "\n报告在此处正常结束。以上内容为完整分析。")
        ok, missing = validate_sanitized_report(report, report)
        assert ok is False
        assert "DISCLAIMER_AT_END" in missing, f"Missing list: {missing}"

    def test_short_report_detected(self):
        report = "太短"
        ok, missing = validate_sanitized_report(report, report)
        assert ok is False
        assert "MIN_LENGTH" in missing


class TestSanitizeDecision:
    def test_sanitizes_buy_action(self):
        decision = {"action": "买入", "target_price": 1380.0}
        result = sanitize_decision(decision)
        assert result["action"] != "买入"

    def test_sanitizes_sell_action(self):
        decision = {"action": "卖出", "target_price": 50.0}
        result = sanitize_decision(decision)
        assert result["action"] != "卖出"

    def test_preserves_other_fields(self):
        decision = {"action": "买入", "confidence": 0.8, "risk_score": 0.3}
        result = sanitize_decision(decision)
        assert result["confidence"] == 0.8
        assert result["risk_score"] == 0.3

    def test_empty_decision(self):
        result = sanitize_decision({})
        assert result == {}


class TestReviewAndSanitize:
    def test_local_mode_returns_regex_local(self):
        result, method = review_and_sanitize("测试报告", mode="local")
        assert isinstance(result, str)
        assert method == "regex_local"

    def test_preserves_long_text(self):
        long_text = "这是一份详细的股票研究报告。" * 100
        result, method = review_and_sanitize(long_text, mode="local")
        assert len(result) > 0
        assert method == "regex_local"
        # Must preserve most of the original content
        assert len(result) >= len(long_text) * 0.9

    def test_handles_empty_text(self):
        result, method = review_and_sanitize("", mode="local")
        assert isinstance(result, str)
        assert method == "regex_local"

    def test_no_openai_called_for_local_mode(self, monkeypatch):
        """Local mode must never call OpenAI."""
        called = False

        def fake_client(*a, **kw):
            nonlocal called; called = True
            raise RuntimeError("should not be called")

        monkeypatch.setattr("openai.OpenAI", fake_client)
        result, method = review_and_sanitize("测试报告" * 100, mode="local")
        assert method == "regex_local"
        assert not called


class TestFindProhibitedPatterns:
    def test_finds_buy_recommendation(self):
        found = find_prohibited_instruction_patterns("建议买入该股票")
        assert len(found) > 0

    def test_no_false_positives(self):
        found = find_prohibited_instruction_patterns("公司营收同比增长15%")
        assert len(found) == 0
