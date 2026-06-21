"""Tests for report_reviewer compliance gate."""

import pytest
from src.compliance.report_reviewer import (
    review_and_sanitize,
    sanitize_decision,
    _review_via_regex,
)


class TestRegexSanitize:
    def test_removes_buy_recommendation(self):
        result = _review_via_regex("建议买入该股票，目标价1380元")
        assert "建议买入" not in result
        assert "买入" not in result or "模型" in result
        assert "1380" not in result or "区间" in result

    def test_removes_sell_recommendation(self):
        result = _review_via_regex("建议卖出该股票，止损位15元")
        assert "建议卖出" not in result
        assert "止损位" not in result or "管理" in result

    def test_removes_guarantee_phrases(self):
        result = _review_via_regex("稳赚不赔的好机会，必涨无疑")
        assert "稳赚" not in result
        assert "必涨" not in result

    def test_removes_precise_prediction(self):
        result = _review_via_regex("精准预测明日涨停")
        assert "精准预测" not in result or "模型" in result

    def test_preserves_neutral_content(self):
        original = "公司营收同比增长15%，现金流健康"
        result = _review_via_regex(original)
        assert "营收同比增长15%" in result
        assert "现金流健康" in result

    def test_removes_target_price(self):
        result = _review_via_regex("目标价: 200元")
        assert "200元" not in result or "区间" in result

    def test_direction_map_replacements(self):
        result = _review_via_regex("综合判断：买入")
        assert "买入" not in result or "积极" in result


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
    def test_returns_tuple(self):
        result, method = review_and_sanitize("测试报告")
        assert isinstance(result, str)
        assert method in ("llm", "regex")

    def test_preserves_long_text(self):
        long_text = "这是一份详细的股票研究报告。" * 10
        result, method = review_and_sanitize(long_text)
        assert len(result) > 0
        assert method in ("llm", "regex")

    def test_handles_empty_text(self):
        result, method = review_and_sanitize("")
        assert isinstance(result, str)
        assert method in ("llm", "regex")
