"""Deterministic post-verification of LLM output against the cached source
text. The model cannot ground itself; these checks never consult a model."""

import re

from ci_tool.models import InsightExtraction


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def verify(extraction: InsightExtraction, source_text: str) -> list[str]:
    """Empty list = grounded. Any entry = fail closed upstream."""
    errors = []
    haystack = _squash(source_text)

    if _squash(extraction.quote) not in haystack:
        errors.append("quote is not a verbatim span of the source text")
    for entity in extraction.entities:
        if _squash(entity) not in haystack:
            errors.append(f"entity not found in source text: {entity!r}")
    for number in extraction.numbers:
        if _squash(number) not in haystack:
            errors.append(f"number not found in source text: {number!r}")
    # numbers inside the summary must exist in the source even if the model
    # forgot to declare them (commas stripped so 72,000 matches 72000)
    hay_nocomma = haystack.replace(",", "")
    for num in re.findall(r"\d+(?:\.\d+)*", extraction.summary.replace(",", "")):
        if num not in hay_nocomma:
            errors.append(f"summary number not found in source text: {num!r}")
    return errors


def confidence(trust_tier: int, item_count: int) -> str:
    """Computed, never model-asserted: source tier sets the base, independent
    corroboration (cluster size) bumps it one level."""
    levels = ["low", "medium", "high"]
    index = {1: 2, 2: 1}.get(trust_tier, 0)
    if item_count >= 2:
        index = min(index + 1, 2)
    return levels[index]
