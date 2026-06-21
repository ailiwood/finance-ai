"""LLM-based compliance review gate for generated reports.

Before a report is displayed to the user, it passes through this gate which:
1. Reviews the text via the configured LLM (DeepSeek), rewriting directional
   investment advice ("买入"/"卖出"/"目标价") into neutral research language.
2. Removes emotional, exaggerated, or guarantee-like phrasing.
3. Strips any language that could be construed as financial advice.
4. Falls back to regex-based keyword substitution if the LLM is unavailable.

Compliance: CLAUDE.md Red Lines 2-3; DISCLAIMER.md banned phrase list.

Usage:
    from src.compliance.report_reviewer import review_and_sanitize
    safe_report = review_and_sanitize(raw_report)
"""

from __future__ import annotations

import re
from typing import Optional

# ── System prompt for compliance review ──

_SYSTEM_PROMPT = """你是金融合规审查专家。你的任务是把研究报告中的内容改写为合规的中性研究表述。

严格规则：
1. 把"买入"/"卖出"/"强烈推荐"/"建议持有"等方向性表述改为中性研究观察。
   例："建议买入" → "模型显示该公司在X维度表现积极，供研究参考"
   例："目标价1380元" → "基于历史数据回测，模型估算参考区间为X-Y元"
   例："卖出信号" → "模型观察到下行风险信号，仅供研究参考"
2. 移除"稳赚""必涨""保证收益""精准预测""内幕消息"等保证性、夸大措辞。
3. 保留所有分析逻辑、数据、推理过程——只改表述方式，不改分析内容。
4. 确保每段输出不含任何投资建议、荐股、或交易指导含义。
5. 不要添加额外的免责声明（系统会自动添加）。

请直接返回改写后的文本，不要加任何前缀或说明。"""

# ── Regex fallback patterns ──

_DIRECTIONAL_REPLACEMENTS: list[tuple[str, str]] = [
    # Action words → neutral
    (r"建议买入|推荐买入|强烈买入|买入评级", "模型综合评估偏积极，供研究参考"),
    (r"建议卖出|推荐卖出|强烈卖出|卖出评级", "模型观察到下行风险信号，供研究参考"),
    (r"建议持有|继续持有|持有评级", "模型评估为中性，供研究参考"),
    (r"目标价[：:]?\s*[\d,.]+", "参考估值区间（基于历史数据回测，不构成投资建议）"),
    (r"止损位[：:]?\s*[\d,.]+", "风险管理参考位（基于历史波动率估算）"),
    # Guarantee words
    (r"稳赚不赔|稳赚|保证收益|必涨|一定涨|肯定涨", "历史回测显示统计优势（不代表未来表现）"),
    (r"精准预测|准确预测|精确预测", "模型估算"),
    (r"内幕消息|内部消息|独家消息", "公开信息"),
]

# Direction → neutral description mapping
_DIRECTION_MAP = {
    "买入": "模型综合评估偏积极",
    "卖出": "模型观察到下行风险信号",
    "持有": "模型评估为中性",
    "看多": "信号偏积极",
    "看空": "信号偏谨慎",
    "中性": "信号为中性",
}


def review_and_sanitize(report_text: str) -> str:
    """Review and sanitize report text through LLM, with regex fallback.

    Args:
        report_text: Raw report text (may contain directional investment advice).

    Returns:
        Sanitized text with neutral research language.
    """
    # Try LLM review first
    llm_result = _review_via_llm(report_text)
    if llm_result is not None:
        return llm_result

    # Fallback: regex-based sanitization
    return _review_via_regex(report_text)


def _review_via_llm(text: str) -> Optional[str]:
    """Attempt LLM-based compliance review. Returns None on failure."""
    try:
        from src.core.config_manager import load_config
        config = load_config()
        api_key = config.get("deepseek_api_key", "") or __import__("os").environ.get(
            "DEEPSEEK_API_KEY", ""
        )
        if not api_key or api_key.startswith("your_"):
            return None

        from openai import OpenAI

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=60.0,
        )

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"请审查并改写以下研究报告：\n\n{text}"},
            ],
            max_tokens=4000,
            temperature=0.1,
        )

        if response.choices and response.choices[0].message.content:
            return response.choices[0].message.content.strip()

    except Exception:
        pass

    return None


def _review_via_regex(text: str) -> str:
    """Regex-based compliance sanitization as fallback."""
    result = text

    # Replace action-direction phrases
    for pattern, replacement in _DIRECTIONAL_REPLACEMENTS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

    # Replace decision dict fields in the report
    for direction_word, neutral in _DIRECTION_MAP.items():
        result = re.sub(
            rf"\b{re.escape(direction_word)}\b",
            neutral,
            result,
        )

    return result


def sanitize_decision(decision: dict) -> dict:
    """Sanitize a single decision dict, replacing directional language.

    Args:
        decision: Raw decision dict from TradingAgents-CN (may contain
                  'action': '买入'/'卖出', 'target_price', etc.)

    Returns:
        Sanitized dict with neutral language.
    """
    safe = dict(decision)

    if "action" in safe and str(safe["action"]) in _DIRECTION_MAP:
        safe["action"] = "中性（详见分析报告）"

    if "reasoning" in safe and isinstance(safe["reasoning"], str):
        safe["reasoning"] = _review_via_regex(safe["reasoning"])

    return safe
