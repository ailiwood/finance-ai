"""Banned phrase scanner for compliance enforcement.

Scans any text for prohibited phrases defined in DISCLAIMER.md.
Used before any user-facing output is rendered.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, NamedTuple

from .disclaimer import parse_banned_phrases, get_ui_disclaimer


class ComplianceViolation(NamedTuple):
    """A single compliance violation found in text."""
    phrase: str
    category: str  # "banned_phrase" | "missing_disclaimer"


class ComplianceError(Exception):
    """Raised when text fails compliance check (banned phrases or missing disclaimer)."""

    def __init__(self, violations: List[ComplianceViolation]) -> None:
        self.violations = violations
        phrases = ", ".join(v.phrase for v in violations)
        super().__init__(
            f"合规校验失败: 发现 {len(violations)} 个违规项 — {phrases}"
        )


# === Banned phrase list ===

# Loaded once at module import time from DISCLAIMER.md
_BANNED_PHRASES: List[str] = parse_banned_phrases()


# === Fuzzy pattern generation ===

def _build_fuzzy_pattern(phrase: str) -> str:
    """Build a regex pattern that matches the phrase and common variants.

    Strategy: strip quotes from the phrase in DISCLAIMER.md, then
    match the core characters with optional surrounding characters
    to catch embedded variants (e.g., "稳赚" matches "稳赚不赔").
    """
    # Escape for regex, then make it a substring match
    escaped = re.escape(phrase)
    return escaped


def _compile_patterns() -> List[re.Pattern]:
    """Compile all banned phrase patterns."""
    patterns: List[re.Pattern] = []
    for phrase in _BANNED_PHRASES:
        pat = _build_fuzzy_pattern(phrase)
        patterns.append(re.compile(pat, re.IGNORECASE))
    return patterns


_COMPILED_PATTERNS: List[re.Pattern] = _compile_patterns()


# === Public API ===

def check_banned_phrases(text: str) -> List[str]:
    """Scan text for banned phrases.

    Args:
        text: The text to scan.

    Returns:
        List of banned phrase strings found. Empty list = clean.
    """
    found: List[str] = []
    for i, pattern in enumerate(_COMPILED_PATTERNS):
        if pattern.search(text):
            found.append(_BANNED_PHRASES[i])
    return found


def has_disclaimer(text: str) -> bool:
    """Check if the text contains the standard disclaimer or a permitted variant.

    Checks for key phrases that must be present:
    - "仅供参考研究"
    - "不构成任何投资建议"
    - "盈亏自负"

    At least 2 of 3 must be present to pass.
    """
    required = [
        "仅供参考研究",
        "不构成任何投资建议",
        "盈亏自负",
    ]
    matches = sum(1 for phrase in required if phrase in text)
    return matches >= 2


def assert_compliant(text: str) -> None:
    """Assert that text is compliant.

    Checks:
    1. No banned phrases
    2. Disclaimer is present (or text is short enough to be a UI label)

    Raises:
        ComplianceError: If any check fails.
    """
    violations: List[ComplianceViolation] = []

    # Check banned phrases
    banned = check_banned_phrases(text)
    for phrase in banned:
        violations.append(ComplianceViolation(phrase, "banned_phrase"))

    # Check disclaimer presence (skip for very short labels)
    if len(text) > 50 and not has_disclaimer(text):
        violations.append(
            ComplianceViolation("缺少免责声明", "missing_disclaimer")
        )

    if violations:
        raise ComplianceError(violations)


def scan_file(filepath: Path) -> List[ComplianceViolation]:
    """Scan a single file for compliance violations.

    Args:
        filepath: Path to the file to scan.

    Returns:
        List of violations found.
    """
    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []

    violations: List[ComplianceViolation] = []
    banned = check_banned_phrases(content)
    for phrase in banned:
        violations.append(
            ComplianceViolation(f"{phrase} (in {filepath.name})", "banned_phrase")
        )
    return violations


def scan_project(root: Path | None = None) -> List[ComplianceViolation]:
    """Full-project compliance scan.

    Scans all .py, .md, .txt files in the project root.
    Excludes: .git, .claude, __pycache__, venv, .venv, node_modules.

    Args:
        root: Project root directory. Defaults to the quantage project root.

    Returns:
        List of all violations found across the project.
    """
    if root is None:
        root = Path(__file__).resolve().parent.parent.parent

    exclude_dirs = {
        ".git", ".claude", "__pycache__", "venv", ".venv",
        "node_modules", ".tox", "dist", "build", "cache",
    }
    scan_extensions = {".py", ".md", ".txt"}

    all_violations: List[ComplianceViolation] = []

    for filepath in root.rglob("*"):
        # Skip excluded directories
        if any(excl in filepath.parts for excl in exclude_dirs):
            continue

        if filepath.suffix in scan_extensions and filepath.is_file():
            violations = scan_file(filepath)
            if violations:
                all_violations.extend(violations)

    return all_violations
