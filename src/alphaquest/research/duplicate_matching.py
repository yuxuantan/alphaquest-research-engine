"""Shared deterministic primitives for campaign and backlog duplicate recall."""

from __future__ import annotations

import re
from typing import Any, Mapping


_WORDS = re.compile(r"[a-z0-9]+")
_ECONOMIC_PHRASE_ALIASES = {
    "dealers": "liquidity providers",
    "dealer": "liquidity provider",
    "market makers": "liquidity providers",
    "market maker": "liquidity provider",
    "slow hedging": "delayed hedging",
    "lagged hedging": "delayed hedging",
    "forced selling": "forced flow",
    "forced liquidation": "forced flow",
    "forced liquidations": "forced flow",
}


def token_jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def match_band(*, exact: bool, structured: float, lexical: float) -> str:
    if exact:
        return "EXACT_FINGERPRINT"
    if structured >= 0.6:
        return "HIGH_STRUCTURED_SIMILARITY"
    if structured >= 0.3 or lexical >= 0.3:
        return "POSSIBLE_RELATED_EDGE"
    return "LEXICAL_REVIEW"


def economic_tokens(value: str) -> set[str]:
    """Return versioned deterministic tokens for backlog candidate recall."""

    normalized = value.casefold()
    for source, target in sorted(_ECONOMIC_PHRASE_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        normalized = normalized.replace(source, target)
    return {_economic_token(word) for word in _WORDS.findall(normalized) if len(word) > 2}


def economic_dimension_match(
    query: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    fields: tuple[str, ...],
    available_only: bool = False,
) -> dict[str, Any]:
    """Compare richer backlog dimensions while exposing every component."""

    scores: dict[str, float] = {}
    for field in fields:
        left_raw = query.get(field)
        right_raw = candidate.get(field)
        if available_only and not _has_semantic_value(right_raw):
            continue
        left = economic_tokens(_semantic_text(left_raw))
        right = economic_tokens(_semantic_text(right_raw))
        scores[field] = round(token_jaccard(left, right), 4)
    score = round(sum(scores.values()) / len(scores), 4) if scores else 0.0
    return {
        "taxonomy_schema": "alphaquest.edge-backlog-duplicate-taxonomy/v1",
        "taxonomy_score": score,
        "matched_dimensions": sorted(field for field, value in scores.items() if value >= 0.6),
        "dimension_scores": scores,
    }


def _economic_token(value: str) -> str:
    if value.endswith("ies") and len(value) > 4:
        return value[:-3] + "y"
    if value.endswith("s") and not value.endswith("ss") and len(value) > 4:
        return value[:-1]
    return value


def _semantic_text(value: Any) -> str:
    if isinstance(value, (list, tuple, set)):
        return " ".join(str(item) for item in value)
    return str(value or "")


def _has_semantic_value(value: Any) -> bool:
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return bool(str(value or "").strip())


__all__ = ["economic_dimension_match", "economic_tokens", "match_band", "token_jaccard"]
