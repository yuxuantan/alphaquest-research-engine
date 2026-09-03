"""Shared deterministic primitives for campaign and backlog duplicate recall."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import re
from typing import Any


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


def legacy_tokens(value: str) -> set[str]:
    """Return the exact token set used by the pre-P2 campaign matcher."""

    return {word for word in _WORDS.findall(value.lower()) if len(word) > 2}


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

    return _dimension_match(
        query,
        candidate,
        fields=fields,
        tokenizer=lambda _field, value: economic_tokens(_semantic_text(value)),
        taxonomy_schema="alphaquest.edge-backlog-duplicate-taxonomy/v1",
        available_only=available_only,
        sort_matched_dimensions=True,
    )


def deterministic_duplicate_score(
    *,
    query_tokens: set[str],
    candidate_tokens: set[str],
    query_fingerprint: str | None,
    candidate_fingerprint: str | None,
    query_dimensions: Mapping[str, Any] | None,
    candidate_dimensions: Mapping[str, Any] | None,
    dimension_fields: Sequence[str],
    dimension_tokenizer: Callable[[str, Any], set[str]],
    taxonomy_schema: str,
    available_only: bool = False,
    sort_matched_dimensions: bool = True,
) -> dict[str, Any]:
    """Run the single deterministic scoring core used by every adapter."""

    if query_dimensions is None or candidate_dimensions is None:
        taxonomy = {
            "taxonomy_schema": taxonomy_schema,
            "taxonomy_score": 0.0,
            "matched_dimensions": [],
            "dimension_scores": {},
        }
    else:
        taxonomy = _dimension_match(
            query_dimensions,
            candidate_dimensions,
            fields=dimension_fields,
            tokenizer=dimension_tokenizer,
            taxonomy_schema=taxonomy_schema,
            available_only=available_only,
            sort_matched_dimensions=sort_matched_dimensions,
        )
    return {
        "exact_fingerprint": bool(
            query_fingerprint is not None
            and candidate_fingerprint is not None
            and query_fingerprint == candidate_fingerprint
        ),
        "lexical_similarity": round(token_jaccard(query_tokens, candidate_tokens), 4),
        **taxonomy,
    }


def rank_duplicate_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    identity_field: str,
    lexical_field: str,
    minimum_similarity: float,
    minimum_structured_similarity: float = 0.3,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Apply the shared recall threshold, match band, and stable ranking."""

    eligible: list[dict[str, Any]] = []
    for candidate in candidates:
        item = dict(candidate)
        force_recall = bool(item.pop("_force_recall", False))
        structured = float(item.get("taxonomy_score") or 0.0)
        lexical = float(item.get(lexical_field) or 0.0)
        exact = bool(item.get("exact_fingerprint"))
        item["match_band"] = match_band(exact=exact, structured=structured, lexical=lexical)
        if exact or lexical >= float(minimum_similarity) or structured >= minimum_structured_similarity or force_recall:
            eligible.append(item)
    ranked = sorted(
        eligible,
        key=lambda item: (
            not bool(item["exact_fingerprint"]),
            -float(item.get("taxonomy_score") or 0.0),
            -float(item.get(lexical_field) or 0.0),
            str(item[identity_field]),
        ),
    )
    if limit is None:
        return ranked
    return ranked[: max(1, int(limit))]


def _dimension_match(
    query: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    fields: Sequence[str],
    tokenizer: Callable[[str, Any], set[str]],
    taxonomy_schema: str,
    available_only: bool,
    sort_matched_dimensions: bool,
) -> dict[str, Any]:
    scores: dict[str, float] = {}
    for field in fields:
        left_raw = query.get(field)
        right_raw = candidate.get(field)
        if available_only and not _has_semantic_value(right_raw):
            continue
        left = tokenizer(field, left_raw)
        right = tokenizer(field, right_raw)
        scores[field] = round(token_jaccard(left, right), 4)
    score = round(sum(scores.values()) / len(scores), 4) if scores else 0.0
    matched = [field for field, value in scores.items() if value >= 0.6]
    if sort_matched_dimensions:
        matched.sort()
    return {
        "taxonomy_schema": taxonomy_schema,
        "taxonomy_score": score,
        "matched_dimensions": matched,
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


__all__ = [
    "deterministic_duplicate_score",
    "economic_dimension_match",
    "economic_tokens",
    "legacy_tokens",
    "match_band",
    "rank_duplicate_candidates",
    "token_jaccard",
]
