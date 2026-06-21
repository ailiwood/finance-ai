"""QuantSage configuration manager with encrypted persistence.

Stores plaintext settings in .env and sensitive keys encrypted
in ~/.quantsage/encrypted_keys.json using Fernet symmetric encryption.

Red Line 5 compliance: API keys NEVER written to code, uploaded, or logged.
"""

from __future__ import annotations

import json
import os
import base64
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TypedDict, Optional, Dict, Any


# === Paths ===

# Project .env path (next to CLAUDE.md)
from src.deployment.resource_path import get_base_path
_PROJECT_ROOT = get_base_path()
_ENV_FILE: Path = _PROJECT_ROOT / ".env"
_ENV_EXAMPLE_FILE: Path = _PROJECT_ROOT / ".env.example"

CONFIG_DIR: Path = Path.home() / ".quantsage"
CONFIG_FILE: Path = CONFIG_DIR / "config.json"
ENCRYPTED_KEYS_FILE: Path = CONFIG_DIR / "encrypted_keys.json"
FERNET_KEY_FILE: Path = CONFIG_DIR / ".fernet_key"
DISCLAIMER_ACCEPTED_FILE: Path = CONFIG_DIR / "disclaimer_accepted"


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


# Fields that must be encrypted (match by suffix)
_ENCRYPTED_FIELD_SUFFIXES = ("_api_key", "_token", "_secret")


# === Fernet encryption ===

def _get_or_create_fernet():
    """Load or create the Fernet encryption key.

    The key is stored at ~/.quantsage/.fernet_key with restrictive permissions.
    """
    from cryptography.fernet import Fernet

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if FERNET_KEY_FILE.exists():
        key = FERNET_KEY_FILE.read_bytes()
        if not key:
            raise ValueError("Fernet key file is empty. Delete ~/.quantsage/ and restart.")
        return Fernet(key)

    # Generate new key
    key = Fernet.generate_key()
    FERNET_KEY_FILE.write_bytes(key)
    # Set restrictive permissions on Unix
    try:
        FERNET_KEY_FILE.chmod(0o600)
        CONFIG_DIR.chmod(0o700)
    except (OSError, NotImplementedError):
        pass  # Windows does not support chmod

    return Fernet(key)


def encrypt_api_key(key: str) -> str:
    """Encrypt an API key. Returns base64-encoded encrypted bytes as string."""
    if not key:
        return ""
    fernet = _get_or_create_fernet()
    encrypted = fernet.encrypt(key.encode("utf-8"))
    return base64.b64encode(encrypted).decode("ascii")


def decrypt_api_key(encrypted: str) -> str:
    """Decrypt an API key. Returns the plaintext key."""
    if not encrypted:
        return ""
    fernet = _get_or_create_fernet()
    raw = base64.b64decode(encrypted.encode("ascii"))
    return fernet.decrypt(raw).decode("utf-8")


# === .env file management ===

def _ensure_env_exists() -> Path:
    """Ensure .env file exists, creating from .env.example if needed."""
    if not _ENV_FILE.exists() and _ENV_EXAMPLE_FILE.exists():
        _ENV_FILE.write_text(_ENV_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    elif not _ENV_FILE.exists():
        _ENV_FILE.write_text("", encoding="utf-8")
    return _ENV_FILE


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


# === Encrypted keys storage ===

def _read_encrypted_keys() -> Dict[str, str]:
    """Read encrypted keys from ~/.quantsage/encrypted_keys.json."""
    if not ENCRYPTED_KEYS_FILE.exists():
        return {}
    try:
        data = json.loads(ENCRYPTED_KEYS_FILE.read_text(encoding="utf-8"))
        # data has _meta and key-value pairs of encrypted strings
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_encrypted_keys(keys: Dict[str, str]) -> None:
    """Write encrypted keys to ~/.quantsage/encrypted_keys.json."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data: Dict[str, Any] = {
        "_meta": {
            "version": 1,
            "updated": datetime.now(timezone.utc).isoformat(),
        }
    }
    data.update(keys)
    ENCRYPTED_KEYS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# === Config load/save ===

def _is_sensitive_field(key: str) -> bool:
    """Check if a config key should be encrypted."""
    return any(key.endswith(suffix) for suffix in _ENCRYPTED_FIELD_SUFFIXES)


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

    Resolution order:
    1. .env file (plaintext, lower priority)
    2. encrypted_keys.json (for sensitive fields, higher priority)
    3. OS environment variables (highest priority, for Docker/CI)

    Returns merged QuantSageConfig dict.
    """
    config: Dict[str, Any] = {}

    # Layer 1: .env file
    env_vars = _read_env_file()
    config.update(_parse_env_to_config(env_vars))

    # Layer 2: encrypted keys (override .env for sensitive fields)
    encrypted = _read_encrypted_keys()
    for key, encrypted_val in encrypted.items():
        try:
            config[key] = decrypt_api_key(encrypted_val)
        except Exception:
            # If decryption fails, skip this key
            pass

    # Layer 3: OS environment variables (highest priority)
    for key in list(config.keys()):
        env_val = os.getenv(key.upper())
        if env_val is not None and env_val != "":
            config[key] = env_val

    return config  # type: ignore[return-value]


def save_config(config: QuantSageConfig) -> None:
    """Save configuration.

    - Non-sensitive fields -> .env file (plaintext)
    - Sensitive fields (API keys, tokens) -> encrypted_keys.json ONLY
    - Sensitive fields are set to placeholder in .env
    """
    # Split into sensitive and non-sensitive
    env_vars: Dict[str, str] = {}
    encrypted_keys: Dict[str, str] = {}

    for key, value in config.items():
        env_key = key.upper()
        if _is_sensitive_field(key):
            # Encrypt and store in encrypted keys file
            str_val = str(value) if value else ""
            if str_val:
                encrypted_keys[key] = encrypt_api_key(str_val)
            # Set placeholder in .env (never plaintext)
            env_vars[env_key] = "___ENCRYPTED___" if str_val else f"your_{key}_here"
        else:
            # Plaintext to .env
            if isinstance(value, bool):
                env_vars[env_key] = "true" if value else "false"
            else:
                env_vars[env_key] = str(value)

    _write_env_file(env_vars)
    if encrypted_keys:
        _write_encrypted_keys(encrypted_keys)


# === Key validation ===

def validate_api_key(provider: str, key: str) -> bool:
    """Format-validate an API key. Does NOT make network calls.

    Rules:
    - DeepSeek: must start with 'sk-', minimum 20 chars
    - DashScope: must start with 'sk-', minimum 20 chars
    - Tushare: minimum 10 chars
    """
    if not key or not key.strip():
        return False

    # Reject placeholder keys
    placeholder_markers = ["your_", "your-", "_here", "-here", "..."]
    key_lower = key.lower()
    if any(marker in key_lower for marker in placeholder_markers):
        return False

    if provider in ("deepseek", "dashscope"):
        if not key.startswith("sk-"):
            return False
        if len(key) < 20:
            return False
    elif provider == "tushare":
        if len(key) < 10:
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
        ENCRYPTED_KEYS_FILE,
        FERNET_KEY_FILE,
        DISCLAIMER_ACCEPTED_FILE,
        CONFIG_FILE,
    ]
    for f in files_to_remove:
        if f.exists():
            f.unlink()
    # Also reset .env to example
    if _ENV_FILE.exists() and _ENV_EXAMPLE_FILE.exists():
        _ENV_FILE.write_text(_ENV_EXAMPLE_FILE.read_text(encoding="utf-8"), encoding="utf-8")


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
