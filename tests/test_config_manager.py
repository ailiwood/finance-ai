"""Tests for src/core/config_manager.py"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Override paths to use a temp directory for testing
import src.core.config_manager as cm

# Use a temp test directory instead of ~/.quantsage
_TEST_DIR = Path(__file__).resolve().parent / "_test_quantsage"
_TEST_DIR.mkdir(parents=True, exist_ok=True)


def setup_module():
    """Set up test config directory."""
    cm.CONFIG_DIR = _TEST_DIR
    cm.ENCRYPTED_KEYS_FILE = _TEST_DIR / "encrypted_keys.json"
    cm.FERNET_KEY_FILE = _TEST_DIR / ".fernet_key"
    cm.DISCLAIMER_ACCEPTED_FILE = _TEST_DIR / "disclaimer_accepted"
    cm.CONFIG_FILE = _TEST_DIR / "config.json"
    # Clean any existing test files
    for f in _TEST_DIR.glob("*"):
        f.unlink()


def teardown_module():
    """Clean up test config directory."""
    for f in _TEST_DIR.glob("*"):
        f.unlink()


def test_encrypt_decrypt_roundtrip():
    """encrypt -> decrypt should return original key."""
    original = "sk-test-key-1234567890abcdef"
    encrypted = cm.encrypt_api_key(original)
    assert encrypted != original
    assert len(encrypted) > 0
    decrypted = cm.decrypt_api_key(encrypted)
    assert decrypted == original


def test_encrypt_empty_string():
    """Encrypting empty string should return empty string."""
    assert cm.encrypt_api_key("") == ""


def test_decrypt_empty_string():
    """Decrypting empty string should return empty string."""
    assert cm.decrypt_api_key("") == ""


def test_encrypt_different_keys():
    """Different keys should produce different encrypted outputs."""
    enc1 = cm.encrypt_api_key("sk-key-aaa-bbb-ccc")
    enc2 = cm.encrypt_api_key("sk-key-xxx-yyy-zzz")
    assert enc1 != enc2


def test_validate_deepseek_key_valid():
    """Valid DeepSeek key format should pass."""
    assert cm.validate_api_key("deepseek", "sk-abc123def456ghi789jkl") is True


def test_validate_deepseek_key_invalid_prefix():
    """Key without 'sk-' prefix should fail."""
    assert cm.validate_api_key("deepseek", "bad-key-without-prefix") is False


def test_validate_deepseek_key_too_short():
    """Key shorter than 20 chars should fail."""
    assert cm.validate_api_key("deepseek", "sk-short") is False


def test_validate_placeholder_rejected():
    """Placeholder keys should be rejected."""
    assert cm.validate_api_key("deepseek", "sk-your_api_key_here") is False
    assert cm.validate_api_key("deepseek", "sk-your_deepseek_api_key_here") is False


def test_validate_tushare_key():
    """Tushare key validation should work."""
    assert cm.validate_api_key("tushare", "a" * 20) is True
    assert cm.validate_api_key("tushare", "short") is False


def test_check_disclaimer_accepted_default():
    """Default: disclaimer should not be accepted."""
    # Clean state
    if cm.DISCLAIMER_ACCEPTED_FILE.exists():
        cm.DISCLAIMER_ACCEPTED_FILE.unlink()
    assert cm.check_disclaimer_accepted() is False


def test_set_disclaimer_accepted():
    """After setting, disclaimer should be accepted."""
    cm.set_disclaimer_accepted()
    assert cm.check_disclaimer_accepted() is True


def test_get_key_status_default():
    """Default state: all providers NOT_CONFIGURED."""
    status = cm.get_key_status()
    assert "deepseek" in status
    assert "dashscope" in status


def test_is_configured_default():
    """Default state: not configured."""
    assert cm.is_configured() is False
