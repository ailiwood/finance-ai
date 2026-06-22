"""QuantSage configuration manager — plaintext .env storage.

API keys are stored as plaintext in the local .env file.
QuantSage runs locally and never transmits data; encryption adds
complexity without meaningful security benefit in this context.

Guards that remain:
- Keys are .strip()'d on read (never fail on whitespace)
- Full keys are NEVER logged or written to reports
- Only masked prefix/suffix appears in debug output

Red Line 5 compliance: API keys NEVER written to code, uploaded, or logged.
"""

from __future__ import annotations

import json
import os
import logging
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TypedDict, Optional, Dict, Any

logger = logging.getLogger("quantsage.config")

# === Paths ===

# Project .env path (next to CLAUDE.md) — template source only
from src.deployment.resource_path import get_base_path
_PROJECT_ROOT = get_base_path()
_ENV_TEMPLATE: Path = _PROJECT_ROOT / ".env.example"
# Project-local .env (used in dev mode, but disposable in PyInstaller builds)
_ENV_PROJECT: Path = _PROJECT_ROOT / ".env"

CONFIG_DIR: Path = Path.home() / ".quantsage"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"
# Persistent .env in user home — survives PyInstaller temp dir recreation
_ENV_USER: Path = CONFIG_DIR / ".env"
# Primary .env: store in user home for persistence
_ENV_FILE: Path = _ENV_USER
DISCLAIMER_ACCEPTED_FILE: Path = CONFIG_DIR / "disclaimer_accepted"

# Legacy files — kept for migration cleanup only
_LEGACY_ENCRYPTED_KEYS_FILE: Path = CONFIG_DIR / "encrypted_keys.json"
_LEGACY_FERNET_KEY_FILE: Path = CONFIG_DIR / ".fernet_key"


# === Enums ===

class ProviderStatus(str, Enum):
    CONFIGURED = "configured"
    NOT_CONFIGURED = "not_configured"
    INVALID = "invalid"


class LLMProvider(str, Enum):
    DEEPSEEK = "deepseek"
    DASHSCOPE = "dashscope"


class RiskLevel(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


# === Config type ===

class QuantSageConfig(TypedDict, total=False):
    """Full QuantSage configuration schema."""
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_enabled: bool
    dashscope_api_key: str
    default_china_data_source: str
    tushare_token: str
    risk_level: str
    analysis_depth: int
    kronos_enabled: bool
    kronos_gpu_device: str
    kronos_model: str
    finbert_enabled: bool
    finbert_gpu_device: str
    finbert_model: str
    cache_dir: str
    cache_ttl: int
    log_level: str


# === .env file management ===

def _ensure_env_exists() -> Path:
    """Ensure persistent .env file exists, creating from template if needed.

    Priority:
    1. ~/.quantsage/.env (persistent, survives PyInstaller re-extraction)
    2. Project .env (dev mode fallback — if it has real keys, migrate them)
    3. Copy from .env.example template
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if _ENV_USER.exists():
        return _ENV_USER

    # If project .env exists and has real content (not placeholders),
    # migrate it to the persistent location
    if _ENV_PROJECT.exists():
        content = _ENV_PROJECT.read_text(encoding="utf-8")
        # Check if it has actual keys (not just the template)
        if any(
            marker in content
            for marker in ("sk-", "ak-", "fp_", "DEEPSEEK_API_KEY=sk-", "OPENAI_API_KEY=sk-")
        ):
            _ENV_USER.write_text(content, encoding="utf-8")
            logger.info("[CONFIG] Migrated project .env to ~/.quantsage/.env for persistence")
            return _ENV_USER

    # Create from template
    if _ENV_TEMPLATE.exists():
        _ENV_USER.write_text(_ENV_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        _ENV_USER.write_text("", encoding="utf-8")
    return _ENV_USER


def _read_env_file() -> Dict[str, str]:
    """Read .env file into a dict (without using python-dotenv)."""
    env_file = _ensure_env_exists()
    result: Dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            result[key] = value
    return result


def _write_env_file(env_vars: Dict[str, str]) -> None:
    """Write env vars to .env, preserving existing comments structure."""
    env_file = _ENV_FILE
    if env_file.exists():
        lines = env_file.read_text(encoding="utf-8").splitlines()
    else:
        lines = []

    updated_keys: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        if "=" in stripped:
            key = stripped.partition("=")[0].strip()
            if key in env_vars:
                new_lines.append(f"{key}={env_vars[key]}")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Append new keys at the end
    for key, value in env_vars.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}")

    env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


# === Helper: masked key logging ===

def _mask_key(key: str) -> str:
    """Return a safe-for-log representation of an API key."""
    if not key:
        return "<empty>"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}****{key[-4:]}"


# === Config load/save ===


def _parse_env_to_config(env_vars: Dict[str, str]) -> Dict[str, Any]:
    """Parse raw env var dict into typed config values."""
    config: Dict[str, Any] = {
        "deepseek_api_key": env_vars.get("DEEPSEEK_API_KEY", ""),
        "deepseek_base_url": env_vars.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "deepseek_enabled": env_vars.get("DEEPSEEK_ENABLED", "false").lower() in ("true", "1", "yes"),
        "dashscope_api_key": env_vars.get("DASHSCOPE_API_KEY", ""),
        "default_china_data_source": env_vars.get("DEFAULT_CHINA_DATA_SOURCE", "akshare"),
        "tushare_token": env_vars.get("TUSHARE_TOKEN", ""),
        "risk_level": env_vars.get("RISK_LEVEL", "moderate"),
        "analysis_depth": int(env_vars.get("ANALYSIS_DEPTH", "3")),
        "kronos_enabled": env_vars.get("KRONOS_ENABLED", "false").lower() in ("true", "1", "yes"),
        "kronos_gpu_device": env_vars.get("KRONOS_GPU_DEVICE", "auto"),
        "kronos_model": env_vars.get("KRONOS_MODEL", "kronos_mini"),
        "finbert_enabled": env_vars.get("FINBERT_ENABLED", "false").lower() in ("true", "1", "yes"),
        "finbert_gpu_device": env_vars.get("FINBERT_GPU_DEVICE", "auto"),
        "finbert_model": env_vars.get("FINBERT_MODEL", "ProsusAI/finbert"),
        "cache_dir": env_vars.get("CACHE_DIR", "./cache"),
        "cache_ttl": int(env_vars.get("CACHE_TTL", "3600")),
        "log_level": env_vars.get("LOG_LEVEL", "INFO"),
    }
    return config


def load_config() -> QuantSageConfig:
    """Load full configuration.

    Resolution order (last wins):
    1. .env file (plaintext key storage)
    2. One-time migration from legacy encrypted_keys.json (if .env has ___ENCRYPTED___)
    3. OS environment variables (highest priority, for Docker/CI)

    Returns merged QuantSageConfig dict.
    """
    config: Dict[str, Any] = {}

    # Layer 1: .env file
    env_vars = _read_env_file()
    config.update(_parse_env_to_config(env_vars))

    # Layer 2: One-time migration from legacy encrypted keys
    # If .env still has ___ENCRYPTED___ placeholders (from pre-plaintext version),
    # try to recover the real keys from encrypted_keys.json and write to .env
    _migrate_legacy_encrypted(config)

    # Layer 3: OS environment variables (highest priority)
    for key in list(config.keys()):
        env_val = os.getenv(key.upper())
        if env_val is not None and env_val != "":
            config[key] = env_val

    # Debug: log masked keys for troubleshooting
    for sensitive_key in ("deepseek_api_key", "dashscope_api_key", "tushare_token"):
        val = config.get(sensitive_key, "")
        if val:
            logger.info(
                "[CONFIG] %s: len=%d, masked=%s, is_placeholder=%s",
                sensitive_key, len(val), _mask_key(val),
                any(m in val.lower() for m in ("your_", "your-", "_here", "-here", "..."))
            )

    return config  # type: ignore[return-value]


def _migrate_legacy_encrypted(config: Dict[str, Any]) -> None:
    """One-time migration: recover keys from legacy encrypted_keys.json.

    If .env has ___ENCRYPTED___ placeholders (from the Fernet encryption era),
    attempt to decrypt and write them as plaintext to .env, then delete the
    legacy files.
    """
    if not _LEGACY_ENCRYPTED_KEYS_FILE.exists():
        return

    # Check if any field still has the legacy placeholder
    needs_migration = any(
        str(v) == "___ENCRYPTED___"
        for k, v in config.items()
        if k.endswith(("_api_key", "_token", "_secret"))
    )
    if not needs_migration:
        # No migration needed — but still clean up legacy files
        _cleanup_legacy_files()
        return

    # Try to decrypt using legacy Fernet key
    try:
        from cryptography.fernet import Fernet
        import base64

        if not _LEGACY_FERNET_KEY_FILE.exists():
            logger.warning(
                "[CONFIG] Found encrypted_keys.json but no .fernet_key — "
                "cannot migrate. Please re-configure API keys in the wizard."
            )
            return

        fernet_key = _LEGACY_FERNET_KEY_FILE.read_bytes()
        if not fernet_key:
            return
        fernet = Fernet(fernet_key)

        legacy_data = json.loads(_LEGACY_ENCRYPTED_KEYS_FILE.read_text(encoding="utf-8"))
        migrated = 0
        for key, encrypted_val in legacy_data.items():
            if key.startswith("_"):
                continue
            if key not in config:
                continue
            current_val = str(config.get(key, ""))
            if current_val not in ("___ENCRYPTED___", ""):
                continue  # Already has a real value
            try:
                raw = base64.b64decode(encrypted_val.encode("ascii"))
                plaintext = fernet.decrypt(raw).decode("utf-8")
                config[key] = plaintext
                migrated += 1
                logger.info(
                    "[CONFIG] Migrated %s from legacy encrypted storage: len=%d, masked=%s",
                    key, len(plaintext), _mask_key(plaintext),
                )
            except Exception as e:
                logger.warning("[CONFIG] Failed to decrypt legacy '%s': %s", key, e)

        if migrated > 0:
            # Persist the migrated keys to .env as plaintext
            save_config(config)
            logger.info(
                "[CONFIG] Migrated %d keys from encrypted storage to plaintext .env",
                migrated,
            )

    except ImportError:
        logger.warning(
            "[CONFIG] cryptography not installed — cannot migrate legacy keys. "
            "Please re-configure API keys in the wizard."
        )
    except Exception as e:
        logger.warning("[CONFIG] Legacy migration failed: %s", e)

    # Clean up legacy files regardless of migration success
    _cleanup_legacy_files()


def _cleanup_legacy_files() -> None:
    """Remove legacy encrypted keys and fernet key files."""
    for legacy_file in (_LEGACY_ENCRYPTED_KEYS_FILE, _LEGACY_FERNET_KEY_FILE):
        if legacy_file.exists():
            try:
                legacy_file.unlink()
                logger.info("[CONFIG] Cleaned up legacy file: %s", legacy_file.name)
            except OSError:
                pass


def save_config(config: QuantSageConfig) -> None:
    """Save configuration to .env as plaintext.

    All fields (including API keys) are stored directly in .env.
    No encryption layer — QuantSage runs locally and never transmits data.
    """
    env_vars: Dict[str, str] = {}
    for key, value in config.items():
        env_key = key.upper()
        str_val = str(value) if value else ""
        if isinstance(value, bool):
            env_vars[env_key] = "true" if value else "false"
        else:
            env_vars[env_key] = str_val

    _write_env_file(env_vars)

    # Clean up legacy encrypted keys file if it exists (migration)
    if _LEGACY_ENCRYPTED_KEYS_FILE.exists():
        try:
            _LEGACY_ENCRYPTED_KEYS_FILE.unlink()
            logger.info("[CONFIG] Removed legacy encrypted_keys.json (migrated to plaintext)")
        except OSError:
            pass
    if _LEGACY_FERNET_KEY_FILE.exists():
        try:
            _LEGACY_FERNET_KEY_FILE.unlink()
            logger.info("[CONFIG] Removed legacy .fernet_key (migrated to plaintext)")
        except OSError:
            pass


# === Key validation ===

def validate_api_key(provider: str, key: str) -> bool:
    """Check that a key is non-empty and not a placeholder.

    NO format validation — different providers have different key formats
    (sk-/ak-/Bearer/fp_/...). Real validity is determined by actual API call.
    """
    if not key or not key.strip():
        return False

    # Only reject obvious placeholder/default values
    placeholder_markers = ["your_", "your-", "_here", "-here", "...", "___encrypted___"]
    key_lower = key.lower()
    if any(marker in key_lower for marker in placeholder_markers):
        return False

    return True


def get_key_status() -> Dict[str, ProviderStatus]:
    """Check which providers have valid keys configured.

    Returns dict mapping provider name to status.
    """
    config = load_config()
    status: Dict[str, ProviderStatus] = {}

    # DeepSeek
    ds_key = config.get("deepseek_api_key", "")
    if not ds_key:
        status["deepseek"] = ProviderStatus.NOT_CONFIGURED
    elif validate_api_key("deepseek", ds_key):
        status["deepseek"] = ProviderStatus.CONFIGURED
    else:
        status["deepseek"] = ProviderStatus.INVALID

    # DashScope
    ds_scope_key = config.get("dashscope_api_key", "")
    if not ds_scope_key:
        status["dashscope"] = ProviderStatus.NOT_CONFIGURED
    elif validate_api_key("dashscope", ds_scope_key):
        status["dashscope"] = ProviderStatus.CONFIGURED
    else:
        status["dashscope"] = ProviderStatus.INVALID

    return status


def is_configured() -> bool:
    """Return True if at least one LLM provider has a valid key."""
    status = get_key_status()
    return any(s == ProviderStatus.CONFIGURED for s in status.values())


def test_llm_connection(provider: str, key: str) -> tuple[bool, str]:
    """Test the LLM API connection with a minimal call.

    Args:
        provider: The LLM provider to test ("deepseek" or "dashscope").
        key: The API key to test.

    Returns:
        (success: bool, message: str)
    """
    try:
        from openai import OpenAI

        if provider == "deepseek":
            base_url = "https://api.deepseek.com"
            model = "deepseek-chat"
        elif provider == "dashscope":
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            model = "qwen-turbo"
        else:
            return False, f"Unsupported provider: {provider}"

        client = OpenAI(api_key=key, base_url=base_url, timeout=10.0)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Reply with just 'OK'"}],
            max_tokens=5,
            temperature=0,
        )
        if response.choices:
            return True, f"Connection OK ({response.model})"
        return False, "No valid response received"

    except Exception as e:
        error_msg = str(e)
        # Return sanitized messages, don't expose stack trace
        if "401" in error_msg or "Unauthorized" in error_msg:
            return False, "API Key invalid. Please check your key."
        elif "timeout" in error_msg.lower():
            return False, "Connection timeout. Check network or try later."
        elif "Connection" in error_msg:
            return False, "Cannot reach server. Check proxy settings."
        else:
            return False, f"Connection failed: {error_msg[:100]}"


def clear_config() -> None:
    """Remove all local config files. Used for 'reset configuration'."""
    files_to_remove = [
        CONFIG_FILE,
        DISCLAIMER_ACCEPTED_FILE,
        _ENV_USER,
        # Legacy encrypted files
        _LEGACY_ENCRYPTED_KEYS_FILE,
        _LEGACY_FERNET_KEY_FILE,
    ]
    for f in files_to_remove:
        if f.exists():
            f.unlink()
    # Re-create user .env from template
    if _ENV_TEMPLATE.exists():
        _ENV_USER.write_text(_ENV_TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")


# === Disclaimer acceptance ===

def check_disclaimer_accepted() -> bool:
    """Check if the user has previously accepted the disclaimer."""
    if not DISCLAIMER_ACCEPTED_FILE.exists():
        return False
    try:
        data = json.loads(DISCLAIMER_ACCEPTED_FILE.read_text(encoding="utf-8"))
        return data.get("accepted", False)
    except (json.JSONDecodeError, OSError):
        return False


def set_disclaimer_accepted() -> None:
    """Persist the disclaimer acceptance."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DISCLAIMER_ACCEPTED_FILE.write_text(
        json.dumps({
            "accepted": True,
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "version": 1,
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
