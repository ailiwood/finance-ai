"""Tests for src/compliance/phrase_checker.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.compliance.phrase_checker import (
    check_banned_phrases,
    has_disclaimer,
    assert_compliant,
    ComplianceError,
    ComplianceViolation,
    scan_file,
)


def test_check_banned_phrases_clean():
    """Clean text should return empty list."""
    result = check_banned_phrases("这是一段正常的分析文本，基于数据分析得出参考观点。")
    assert result == []


def test_check_banned_phrases_single_violation():
    """Single banned phrase should be detected."""
    result = check_banned_phrases("推荐买入这只股票")
    assert len(result) >= 1
    assert "推荐买入" in result


def test_check_banned_phrases_multiple_violations():
    """Multiple banned phrases in same text should all be detected."""
    result = check_banned_phrases("推荐买入这只股票，稳赚不赔，必涨无疑")
    assert len(result) >= 2
    assert "推荐买入" in result
    assert "稳赚" in result


def test_check_banned_phrases_fuzzy_match():
    """Banned phrases embedded in longer words should be detected."""
    # "稳赚" appears in "稳赚不赔"
    result = check_banned_phrases("这个方法稳赚不赔")
    assert "稳赚" in result


def test_has_disclaimer_true():
    """Text with all required disclaimer phrases should return True."""
    text = "本软件仅供参考研究，不构成任何投资建议，盈亏自负。"
    assert has_disclaimer(text) is True


def test_has_disclaimer_false():
    """Text without disclaimer should return False."""
    text = "这是一段没有免责声明的普通分析文本。"
    assert has_disclaimer(text) is False


def test_has_disclaimer_partial():
    """Text with only 1 of 3 required phrases should return False."""
    text = "仅供参考研究的分析报告"
    assert has_disclaimer(text) is False


def test_assert_compliant_passes():
    """Clean text with disclaimer should not raise."""
    text = "基于数据分析的参考观点。本软件仅供参考研究，不构成任何投资建议，盈亏自负。"
    # Should not raise
    assert_compliant(text)


def test_assert_compliant_raises_on_banned():
    """Text with banned phrases should raise ComplianceError."""
    try:
        assert_compliant("推荐买入这只股票，保证收益")
        assert False, "Should have raised"
    except ComplianceError as e:
        assert len(e.violations) >= 1
        assert any(v.category == "banned_phrase" for v in e.violations)


def test_scan_file_clean():
    """Scanning a clean file should return empty list."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("这是一段正常的分析文本。仅供参考研究，不构成任何投资建议。")
        f.flush()
        violations = scan_file(Path(f.name))
    Path(f.name).unlink()
    # Should be clean
    banned_violations = [v for v in violations if v.category == "banned_phrase"]
    assert len(banned_violations) == 0


def test_scan_file_violation():
    """Scanning a file with banned phrase should detect it."""
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write("推荐买入！稳赚！")
        f.flush()
        violations = scan_file(Path(f.name))
    Path(f.name).unlink()

    banned_violations = [v for v in violations if v.category == "banned_phrase"]
    assert len(banned_violations) >= 1
