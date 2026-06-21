"""LLM provider registry.

All mainstream LLM providers accessible via OpenAI-compatible /chat/completions.
base_url values verified against official docs as of 2026-06.
Providers marked with '需用户核对' need user verification.
"""

from __future__ import annotations

from typing import Dict, Any

ProviderConfig = Dict[str, Any]

PROVIDERS: Dict[str, ProviderConfig] = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "key_env": "DEEPSEEK_API_KEY",
        "openai_compatible": True,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "o3-mini", "o4-mini"],
        "key_env": "OPENAI_API_KEY",
        "openai_compatible": True,
    },
    "moonshot": {
        "label": "月之暗面 Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
        "key_env": "MOONSHOT_API_KEY",
        "openai_compatible": True,
    },
    "minimax": {
        "label": "MiniMax",
        "base_url": "https://api.minimaxi.com/v1",  # 需用户核对最新
        "models": ["abab6.5s-chat", "abab7-chat"],
        "key_env": "MINIMAX_API_KEY",
        "openai_compatible": True,
    },
    "dashscope": {
        "label": "阿里通义千问 (DashScope)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": ["qwen-turbo", "qwen-plus", "qwen-max"],
        "key_env": "DASHSCOPE_API_KEY",
        "openai_compatible": True,
    },
    "zhipu": {
        "label": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "models": ["glm-4", "glm-4-flash"],
        "key_env": "ZHIPU_API_KEY",
        "openai_compatible": True,
    },
    "volcengine": {
        "label": "字节豆包 (Volcengine Ark)",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "models": ["doubao-1-5-pro-256k", "doubao-1-5-lite-256k"],
        "key_env": "VOLCENGINE_API_KEY",
        "openai_compatible": True,
    },
    "qianfan": {
        "label": "百度文心 (Qianfan)",
        "base_url": "https://qianfan.baidubce.com/v2",  # 需用户核对
        "models": ["ernie-4.0-turbo-8k", "ernie-3.5-8k"],
        "key_env": "QIANFAN_API_KEY",
        "openai_compatible": True,
    },
    "hunyuan": {
        "label": "腾讯混元",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "models": ["hunyuan-turbos-latest", "hunyuan-large"],
        "key_env": "HUNYUAN_API_KEY",
        "openai_compatible": True,
    },
    "openrouter": {
        "label": "OpenRouter（聚合海量模型）",
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["openai/gpt-4o", "anthropic/claude-sonnet-4",
                    "google/gemini-2.5-pro", "meta-llama/llama-4-maverick"],
        "key_env": "OPENROUTER_API_KEY",
        "openai_compatible": True,
        "note": "一个 Key 通吃海量模型，适合兜底",
    },
    "siliconflow": {
        "label": "硅基流动 (SiliconFlow)",
        "base_url": "https://api.siliconflow.cn/v1",
        "models": ["deepseek-ai/DeepSeek-V3", "Qwen/Qwen3-235B-A22B"],
        "key_env": "SILICONFLOW_API_KEY",
        "openai_compatible": True,
        "note": "聚合多家开源模型，性价比高",
    },
    "ollama": {
        "label": "本地 Ollama（免费、无需 Key）",
        "base_url": "http://localhost:11434/v1",
        "models": ["qwen3:14b", "deepseek-r1:14b", "llama3:8b"],
        "key_env": "",  # 无需 key
        "openai_compatible": True,
        "note": "本地运行，零成本，隐私安全",
    },
    "custom": {
        "label": "自定义 (OpenAI 兼容)",
        "base_url": "",
        "models": [],
        "key_env": "CUSTOM_API_KEY",
        "openai_compatible": True,
        "note": "填写任意 OpenAI 兼容的 base_url 和 model",
    },
}


def get_provider(key: str) -> ProviderConfig:
    """Get provider config by key. Raises KeyError if not found."""
    if key not in PROVIDERS:
        raise KeyError(f"未知供应商: {key}。可用: {list(PROVIDERS.keys())}")
    return PROVIDERS[key]


def get_provider_list() -> list[dict]:
    """Return list of providers for UI dropdown."""
    return [
        {"key": k, "label": v["label"], "models": v["models"],
         "needs_key": bool(v.get("key_env"))}
        for k, v in PROVIDERS.items()
    ]
