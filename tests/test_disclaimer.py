"""Tests for src/compliance/disclaimer.py"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.compliance.disclaimer import (
    load_disclaimer,
    get_ui_disclaimer,
    get_footer_text,
    get_pdf_footer_text,
    get_api_disclaimer,
    parse_banned_phrases,
)


def test_load_disclaimer_returns_text():
    """load_disclaimer should return a non-empty string."""
    text = load_disclaimer()
    assert isinstance(text, str)
    assert len(text) > 50
    assert "仅供参考" in text


def test_get_ui_disclaimer():
    """get_ui_disclaimer should contain key phrases."""
    text = get_ui_disclaimer()
    assert "仅供参考" in text
    assert "不构成任何投资建议" in text
    assert "盈亏自负" in text


def test_get_footer_text():
    """get_footer_text should mention QuantSage."""
    text = get_footer_text()
    assert "QuantSage" in text
    assert "仅供参考" in text


def test_get_pdf_footer_text():
    """get_pdf_footer_text should be compact."""
    text = get_pdf_footer_text()
    assert "QuantSage" in text
    assert len(text) < 100


def test_get_api_disclaimer():
    """get_api_disclaimer should contain key compliance phrases."""
    text = get_api_disclaimer()
    assert "仅供参考" in text


def test_parse_banned_phrases_returns_list():
    """parse_banned_phrases should return a non-empty list of strings."""
    phrases = parse_banned_phrases()
    assert isinstance(phrases, list)
    assert len(phrases) >= 5
    for phrase in phrases:
        assert isinstance(phrase, str)
        assert len(phrase) > 0


def test_parse_banned_phrases_contains_key_phrases():
    """Key banned phrases must be present."""
    phrases = parse_banned_phrases()
    assert "推荐买入" in phrases
    assert "稳赚" in phrases
    assert "必涨" in phrases


def test_cached_sections():
    """Calling disclaimer functions multiple times should work (caching)."""
    t1 = load_disclaimer()
    t2 = load_disclaimer()
    assert t1 == t2  # Same result on repeated calls
