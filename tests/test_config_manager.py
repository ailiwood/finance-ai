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
    cm._LEGACY_ENCRYPTED_KEYS_FILE = _TEST_DIR / "encrypted_keys.json"
    cm._LEGACY_FERNET_KEY_FILE = _TEST_DIR / ".fernet_key"
    cm.DISCLAIMER_ACCEPTED_FILE = _TEST_DIR / "disclaimer_accepted"
    cm.CONFIG_FILE = _TEST_DIR / "config.json"
    cm._ENV_USER = _TEST_DIR / ".env"
    cm._ENV_FILE = cm._ENV_USER
    # Ensure template exists
    if not cm._ENV_TEMPLATE.exists():
        cm._ENV_TEMPLATE = Path(__file__).resolve().parent.parent / ".env.example"
    # Clean any existing test files
    for f in _TEST_DIR.glob("*"):
        f.unlink()
    # Ensure config dir exists
    _TEST_DIR.mkdir(parents=True, exist_ok=True)


def teardown_module():
    """Clean up test config directory."""
    for f in _TEST_DIR.glob("*"):
        f.unlink()


# === Key validation tests ===

def test_validate_accepts_valid_key():
    """Any non-empty, non-placeholder key should pass (no format checks)."""
    assert cm.validate_api_key("deepseek", "sk-abc123def456ghi789jkl") is True


def test_validate_accepts_any_format():
    """Different provider key formats should all be accepted."""
    assert cm.validate_api_key("deepseek", "sk-any-format") is True
    assert cm.validate_api_key("openai", "sk-proj-abc") is True
    assert cm.validate_api_key("dashscope", "sk-abc123") is True
    assert cm.validate_api_key("custom", "fp_12345") is True


def test_validate_rejects_empty():
    """Empty or whitespace-only keys should be rejected."""
    assert cm.validate_api_key("deepseek", "") is False
    assert cm.validate_api_key("deepseek", "   ") is False


def test_validate_rejects_placeholder():
    """Placeholder keys should be rejected."""
    assert cm.validate_api_key("deepseek", "your_api_key_here") is False
    assert cm.validate_api_key("deepseek", "your_deepseek_api_key_here") is False
    assert cm.validate_api_key("deepseek", "___ENCRYPTED___") is False


def test_validate_rejects_dotdotdot_placeholder():
    """Keys containing '...' should be rejected."""
    assert cm.validate_api_key("deepseek", "sk-...") is False
    assert cm.validate_api_key("deepseek", "your-key-here") is False


def test_validate_accepts_short_keys():
    """Even short keys should pass (format varies, real validity is via API call)."""
    assert cm.validate_api_key("tushare", "short") is True


# === Disclaimer tests ===

def test_check_disclaimer_accepted_default():
    """Default: disclaimer should not be accepted."""
    if cm.DISCLAIMER_ACCEPTED_FILE.exists():
        cm.DISCLAIMER_ACCEPTED_FILE.unlink()
    assert cm.check_disclaimer_accepted() is False


def test_set_disclaimer_accepted():
    """After setting, disclaimer should be accepted."""
    cm.set_disclaimer_accepted()
    assert cm.check_disclaimer_accepted() is True


# === Key status tests ===

def test_get_key_status_default():
    """Default state: all providers NOT_CONFIGURED."""
    status = cm.get_key_status()
    assert "deepseek" in status
    assert "dashscope" in status


def test_is_configured_default():
    """is_configured should return a bool (depends on env state)."""
    assert isinstance(cm.is_configured(), bool)


# === Mask key helper ===

def test_mask_key():
    """_mask_key should never reveal the full key."""
    assert cm._mask_key("") == "<empty>"
    assert cm._mask_key("ab") == "****"
    assert cm._mask_key("sk-abc123def456") == "sk-a****f456"
    # Long key — only first 4 and last 4 visible
    masked = cm._mask_key("sk-ca80b56421d643e39958bed5b7d57f5c")
    assert masked == "sk-c****7f5c"
    assert "ca80b56421d643e39958bed5b7d" not in masked  # middle chars hidden


# === Migration tests ===

def test_migration_cleans_up_legacy_files():
    """If legacy files exist, they should be cleaned up after migration."""
    # Create fake legacy files
    cm._LEGACY_ENCRYPTED_KEYS_FILE.write_text('{"_meta":{},"deepseek_api_key":"fake"}')
    cm._LEGACY_FERNET_KEY_FILE.write_bytes(b"fake_key_data_here_1234567890123")

    # Trigger migration via load_config
    cm._cleanup_legacy_files()

    # Legacy files should be gone
    assert not cm._LEGACY_ENCRYPTED_KEYS_FILE.exists()
    assert not cm._LEGACY_FERNET_KEY_FILE.exists()
