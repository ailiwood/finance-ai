"""Tests for multi-LLM provider registry and client."""

import pytest
from src.llm.providers import PROVIDERS, get_provider, get_provider_list


class TestProviderRegistry:
    def test_all_providers_have_required_fields(self):
        for key, cfg in PROVIDERS.items():
            assert "label" in cfg, f"{key} missing label"
            assert "base_url" in cfg or key == "custom", f"{key} missing base_url"
            assert "models" in cfg, f"{key} missing models"
            assert "openai_compatible" in cfg, f"{key} missing openai_compatible"

    def test_deepseek_is_default(self):
        assert "deepseek" in PROVIDERS
        assert PROVIDERS["deepseek"]["models"][0] == "deepseek-chat"

    def test_custom_provider_has_empty_base_url(self):
        assert PROVIDERS["custom"]["base_url"] == ""
        assert PROVIDERS["custom"]["models"] == []

    def test_ollama_no_key_required(self):
        assert PROVIDERS["ollama"]["key_env"] == ""

    def test_get_provider_valid(self):
        cfg = get_provider("deepseek")
        assert cfg["label"] == "DeepSeek"

    def test_get_provider_raises_keyerror(self):
        with pytest.raises(KeyError):
            get_provider("nonexistent")

    def test_get_provider_list_returns_list(self):
        providers = get_provider_list()
        assert len(providers) > 5
        assert any(p["key"] == "custom" for p in providers)
        assert any(p["key"] == "ollama" for p in providers)

    def test_all_openai_compatible(self):
        for key, cfg in PROVIDERS.items():
            assert cfg["openai_compatible"], f"{key} must be OpenAI compatible"


class TestLLMClient:
    def test_client_construction(self):
        from src.llm.client import LLMClient
        client = LLMClient("deepseek", "sk-test", model="deepseek-chat")
        assert client.model == "deepseek-chat"
        assert "api.deepseek.com" in client.base_url

    def test_client_custom_base_url(self):
        from src.llm.client import LLMClient
        client = LLMClient("custom", "sk-test", base_url="https://my.api.com/v1", model="my-model")
        assert client.base_url == "https://my.api.com/v1"
        assert client.model == "my-model"

    def test_test_connection_returns_tuple(self):
        from src.llm.client import test_connection
        ok, msg = test_connection("deepseek", "invalid-key")
        assert isinstance(ok, bool)
        assert isinstance(msg, str)
