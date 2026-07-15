from __future__ import annotations

from collections.abc import Iterable
from typing import Any


MIN_TARGET_R_MULTIPLE = 1.0


def target_rr_violations(
    value: Any,
    *,
    minimum: float = MIN_TARGET_R_MULTIPLE,
    context: str = "config",
) -> list[str]:
    violations: list[str] = []
    _collect_target_rr_violations(value, minimum=minimum, context=context, violations=violations)
    return violations


def require_minimum_target_rr(
    value: Any,
    *,
    minimum: float = MIN_TARGET_R_MULTIPLE,
    context: str = "config",
) -> None:
    violations = target_rr_violations(value, minimum=minimum, context=context)
    if violations:
        joined = "; ".join(violations)
        raise ValueError(f"target_r_multiple must be >= {minimum:.1f} reward:risk: {joined}")


def _collect_target_rr_violations(
    value: Any,
    *,
    minimum: float,
    context: str,
    violations: list[str],
) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            child_context = f"{context}.{key}" if context else str(key)
            if str(key).endswith("target_r_multiple"):
                for candidate in _target_rr_values(item):
                    try:
                        numeric = float(candidate)
                    except (TypeError, ValueError):
                        continue
                    if numeric < minimum:
                        violations.append(f"{child_context}={candidate}")
            _collect_target_rr_violations(
                item,
                minimum=minimum,
                context=child_context,
                violations=violations,
            )
        return

    if isinstance(value, list):
        for idx, item in enumerate(value):
            _collect_target_rr_violations(
                item,
                minimum=minimum,
                context=f"{context}[{idx}]",
                violations=violations,
            )


def _target_rr_values(value: Any) -> Iterable[Any]:
    if isinstance(value, dict):
        out: list[Any] = []
        for item in value.values():
            out.extend(_target_rr_values(item))
        return out
    if isinstance(value, list):
        out: list[Any] = []
        for item in value:
            out.extend(_target_rr_values(item))
        return out
    return [value]
