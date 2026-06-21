"""Sentiment data source registry — same pattern as LLM providers."""

from __future__ import annotations

from typing import Dict, Any

SourceConfig = Dict[str, Any]

SOURCES: Dict[str, SourceConfig] = {
    "akshare_news": {
        "label": "财经新闻 (AkShare·免费)",
        "needs_key": False,
        "key_env": "",
        "url": "",
        "enabled_default": True,
        "description": "东方财富/新浪财经新闻，免费、免注册",
    },
    "finnhub": {
        "label": "Finnhub (美股)",
        "needs_key": True,
        "key_env": "FINNHUB_API_KEY",
        "url": "https://finnhub.io/api/v1",
        "enabled_default": False,
        "description": "美股实时新闻+情绪，需注册获取免费Key",
    },
    "custom_news": {
        "label": "自定义新闻 API",
        "needs_key": True,
        "key_env": "CUSTOM_NEWS_API_KEY",
        "url": "",
        "enabled_default": False,
        "description": "填入任意新闻API的URL和Key",
    },
}


def get_source(key: str) -> SourceConfig:
    if key not in SOURCES:
        raise KeyError(f"未知情绪数据源: {key}")
    return SOURCES[key]


def get_source_list() -> list[dict]:
    return [
        {"key": k, "label": v["label"], "needs_key": v["needs_key"],
         "enabled_default": v["enabled_default"]}
        for k, v in SOURCES.items()
    ]
