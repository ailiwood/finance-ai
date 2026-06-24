"""Compliance review gate for generated reports — LOCAL-FIRST architecture.

Design (P0 fix):
  Full reports MUST use mode="local" (deterministic regex + validation).
  LLM rewriting is blocked for full reports to prevent max_tokens truncation.
  LLM may be used for individual short sections only, with strict gate checks.

Usage:
    from src.compliance.report_reviewer import review_and_sanitize
    safe_report, method = review_and_sanitize(raw_report, mode="local")

Compliance: CLAUDE.md Red Lines 2-3; DISCLAIMER.md banned phrase list.
"""

from __future__ import annotations

import logging
import re
from typing import Optional, Sequence, Literal

_log = logging.getLogger("compliance")

# ── System prompt for LLM-based section review (short sections only) ──

_SYSTEM_PROMPT = """你是金融合规审查专家。把研究报告中的内容改写为合规的中性研究表述。

严格规则：
1. 把"买入"/"卖出"/"强烈推荐"/"建议持有"等方向性表述改为中性研究观察。
2. 移除"稳赚""必涨""保证收益""精准预测"等保证性、夸大措辞。
3. 保留所有分析逻辑、数据、推理过程。
4. 不添加额外免责声明（系统会自动添加）。
请直接返回改写后的文本。"""

# ── Local (deterministic) sanitization patterns ──

# Instruction-context replacements: match directive phrases with context
_INSTRUCTION_REPLACEMENTS: list[tuple[str, str]] = [
    # Strong buy/sell directives
    (r"建议买入|推荐买入|强烈买入|买入评级|操作建议.*买入|投资建议.*买入",
     "模型综合信号偏积极，供研究参考"),
    (r"建议卖出|推荐卖出|强烈卖出|卖出评级|操作建议.*卖出|投资建议.*卖出",
     "模型观察到下行风险信号，供研究参考"),
    (r"建议持有|继续持有|持有评级|操作建议.*持有",
     "模型评估为中性区间，供研究参考"),
    # Position directives
    (r"建议加仓|建议增持|加仓建议",
     "模型显示积极信号积累，供研究参考"),
    (r"建议减仓|建议减持|减仓建议",
     "模型显示风险信号增强，供研究参考"),
    (r"建议清仓|建议空仓|清仓建议",
     "模型显示系统性风险信号，供研究参考"),
    (r"建议满仓|满仓建议",
     "模型显示极端积极信号，供研究参考"),
    # Price targets and stops
    (r"目标价[：:]?\s*[\d,.]+",
     "模型估算参考值（基于历史数据回测，不构成投资建议）"),
    (r"止损位[：:]?\s*[\d,.]+",
     "风险观察参考位（基于历史波动率估算，不构成投资建议）"),
    (r"止盈位[：:]?\s*[\d,.]+",
     "盈利观察参考位（基于历史波动率估算，不构成投资建议）"),
    (r"仓位建议[：:]?\s*\d+%?",
     "风险暴露观察说明（基于模型回测，不构成投资建议）"),
    # Guarantee / exaggerated language
    (r"稳赚不赔|稳赚|保证收益|必涨|一定涨|肯定涨",
     "历史回测显示统计优势（不代表未来表现）"),
    (r"精准预测|准确预测|精确预测|确定性预测",
     "模型估算"),
    (r"内幕消息|内部消息|独家消息",
     "公开信息"),
    (r"最佳买点|绝佳买点|最佳买入时机|现在就是买入的最佳时机|黄金买点",
     "模型估值参考位（基于历史数据回测，不构成投资建议）"),
]

# Field-level replacements: lines matching these keys get rewritten entirely
_FIELD_KEYS = [
    r"^\*\*投资评级\*\*",
    r"^\*\*交易提案\*\*",
    r"^\*\*操作策略\*\*",
    r"^\*\*建议\*\*",
    r"^\*\*Action\*\*",
    r"^\*\*最终决策\*\*",
    r"^\*\*综合建议\*\*",
    r"^\*\*投资建议\*\*",
    r"^\*\*操作建议\*\*",
]

_FIELD_REPLACEMENT = "**研究观点**: 模型综合评估（基于历史数据回测，仅供研究参考，不构成投资建议）"

# Direction → neutral mapping for decision dicts
_DIRECTION_MAP = {
    "买入": "偏积极",
    "卖出": "偏谨慎",
    "持有": "中性区间",
    "看多": "偏积极",
    "看空": "偏谨慎",
}

# Required report sections for completeness check
DEFAULT_REQUIRED_SECTIONS = [
    "技术面分析",
    "基本面分析",
    "投资者情绪分析",
    "风险管控",
    "Kronos",
    "综合结论",
]


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def review_and_sanitize(
    report_text: str,
    *,
    mode: Literal["local", "section_llm", "auto"] = "local",
    expected_sections: Sequence[str] | None = None,
) -> tuple[str, str]:
    """Review and sanitize report text.

    Args:
        report_text: Raw report text.
        mode: "local" (default, deterministic regex), "section_llm" (per-section LLM, gated),
              "auto" (LLM for short text, local otherwise).
        expected_sections: Required section titles for completeness validation.

    Returns:
        (sanitized_text, method) where method is one of:
          "regex_local" — deterministic local filtering
          "regex_fallback_truncation" — LLM was truncated, fell back to local
          "regex_fallback_exception" — LLM failed, fell back to local
          "regex_fallback_short" — LLM output too short, fell back to local
    """
    # Mode "local": never call LLM — deterministic regex only
    if mode == "local":
        return sanitize_report_locally(report_text), "regex_local"

    # Mode "auto": use LLM only for short text (< 3500 chars)
    if mode == "auto" and len(report_text) < 3500:
        llm_result = _review_via_llm(report_text)
        if llm_result is not None:
            return llm_result, "llm_section"
        return sanitize_report_locally(report_text), "regex_fallback_exception"

    # Mode "auto" with long text or "section_llm": fall back to local for full reports
    if mode in ("auto", "section_llm"):
        _log.warning(
            "Full report too long for LLM review (%d chars). Using local filter.",
            len(report_text),
        )
        return sanitize_report_locally(report_text), "regex_local"

    return sanitize_report_locally(report_text), "regex_local"


def sanitize_report_locally(text: str) -> str:
    """Deterministic local sanitization — never calls LLM, never truncates.

    Applies context-aware regex replacements that:
    - Preserve markdown headings and structure
    - Replace trading directives with neutral research language
    - Remove guarantee/exaggerated language
    - Do NOT globally replace standalone direction words
    """
    result = text

    # 1. Replace instruction-context phrases
    for pattern, replacement in _INSTRUCTION_REPLACEMENTS:
        result = re.sub(pattern, replacement, result)

    # 2. Replace field-level directive lines
    for field_pattern in _FIELD_KEYS:
        result = re.sub(
            rf"({field_pattern}.*)$",
            _FIELD_REPLACEMENT,
            result,
            flags=re.MULTILINE,
        )

    return result


def validate_sanitized_report(
    raw_text: str,
    sanitized_text: str,
    expected_sections: Sequence[str] | None = None,
) -> tuple[bool, list[str]]:
    """Check that sanitized report is structurally complete.

    Returns:
        (is_valid, missing_sections) tuple.
    """
    sections = expected_sections or DEFAULT_REQUIRED_SECTIONS
    missing = []

    # Check minimum length
    if len(sanitized_text) < 500:
        missing.append("MIN_LENGTH")

    # Check for truncation — last 300 chars should contain disclaimer or proper ending
    tail = sanitized_text.strip()[-300:]
    if "仅供参考" not in tail and "免责" not in tail:
        missing.append("DISCLAIMER_AT_END")

    # Check mid-sentence cutoff
    last_char = sanitized_text.strip()[-1]
    if last_char not in ".。！？\n*>)：:…":
        missing.append("MID_SENTENCE_CUTOFF")

    # Check required sections by markdown heading
    for section in sections:
        if f"## {section}" not in sanitized_text and f"# {section}" not in sanitized_text:
            # Also check with emoji prefix (common in report headings)
            found = False
            for line in sanitized_text.split("\n"):
                if line.strip().startswith("##") and section in line:
                    found = True
                    break
            if not found:
                missing.append(section)

    # Check relative length (should not lose >30% of content)
    if len(sanitized_text) < len(raw_text) * 0.5:
        if "LENGTH_RATIO" not in missing:
            missing.append("LENGTH_RATIO")

    return len(missing) == 0, missing


def find_prohibited_instruction_patterns(text: str) -> list[str]:
    """Scan for prohibited trading instruction patterns. Returns list of matches."""
    prohibited = [
        r"建议买入|推荐买入|强烈买入|买入评级",
        r"建议卖出|推荐卖出|强烈卖出|卖出评级",
        r"止损位|止盈位|目标价",
        r"稳赚|必涨|保证收益|精准预测",
        r"最佳买点|最佳买入时机",
        r"仓位建议",
    ]
    found = []
    for pattern in prohibited:
        matches = re.findall(pattern, text)
        found.extend(matches)
    return found


def sanitize_decision(decision: dict) -> dict:
    """Sanitize a single decision dict from TradingAgents-CN.

    Replaces directional 'action' values with neutral research language.
    """
    safe = dict(decision)
    if "action" in safe and str(safe["action"]) in _DIRECTION_MAP:
        safe["action"] = f"模型信号{_DIRECTION_MAP[str(safe['action'])]}（详见分析报告）"
    if "reasoning" in safe and isinstance(safe["reasoning"], str):
        safe["reasoning"] = sanitize_report_locally(safe["reasoning"])
    return safe


# ══════════════════════════════════════════════════════════════════════════════
# PRIVATE: LLM-based review (GATED — short sections only)
# ══════════════════════════════════════════════════════════════════════════════

def _review_via_llm(text: str) -> Optional[str]:
    """LLM-based compliance review with strict acceptance gates.

    Returns None (triggering local fallback) on ANY of:
    - finish_reason != "stop"
    - Output is empty
    - Output is < 50% of input length
    - Exception during API call
    - Missing API key
    """
    try:
        from src.core.config_manager import load_config
        config = load_config()
        api_key = config.get("deepseek_api_key", "") or __import__("os").environ.get(
            "DEEPSEEK_API_KEY", ""
        )
        if not api_key or api_key.startswith("your_"):
            return None

        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com", timeout=60.0)

        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"请审查并改写以下研究内容：\n\n{text}"},
            ],
            max_tokens=4000,
            temperature=0.1,
        )

        if not response.choices or not response.choices[0].message.content:
            _log.warning("LLM review: empty response")
            return None

        content = response.choices[0].message.content.strip()
        finish_reason = getattr(response.choices[0], "finish_reason", None)

        # Gate 1: finish_reason must be "stop"
        if finish_reason != "stop":
            _log.warning(
                "LLM review rejected: finish_reason=%s (expected 'stop'). Falling back to local.",
                finish_reason,
            )
            return None

        # Gate 2: output must not be empty
        if not content:
            _log.warning("LLM review rejected: empty content after strip")
            return None

        # Gate 3: output must be at least 50% of input length
        input_len = len(text)
        output_len = len(content)
        if output_len < input_len * 0.5:
            _log.warning(
                "LLM review rejected: output too short (%d chars vs %d input). Falling back to local.",
                output_len, input_len,
            )
            return None

        return content

    except Exception as e:
        _log.warning("LLM review exception (falling back to local): %s", e)
        return None
