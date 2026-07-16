from __future__ import annotations

from collections.abc import Mapping
import math
import statistics
from typing import Any

from pydantic import ValidationError

from alphaquest.authoring.models import (
    AllConditionV1,
    AnyConditionV1,
    BUILTIN_BAR_FEATURES,
    BarRuleV1,
    ComparisonConditionV1,
    ConditionV1,
    ConstantValueV1,
    CrossConditionV1,
    FeatureValueV1,
    NotConditionV1,
    RangeConditionV1,
    RollingValueV1,
    TunableValueV1,
    ValueExpressionV1,
)


_MISSING = object()
_NUMERIC_BUILTINS = frozenset({"open", "high", "low", "close", "volume"})
_LOOKAHEAD_MARKERS = (
    "future",
    "final",
    "centered",
    "session_final",
    "final_session",
    "current_session_high",
    "current_session_low",
    "current_day_high",
    "current_day_low",
    "day_final",
)


class BarRuleValidationError(ValueError):
    """Raised when a visual rule is not safely executable at bar close."""


def validate_bar_rule(
    rule: BarRuleV1 | Mapping[str, Any],
    *,
    certified_features: set[str] | frozenset[str] | None = None,
) -> BarRuleV1:
    """Parse and causally validate a Studio bar rule.

    ``certified_features`` must come from governed dataset metadata.  Omitting it
    intentionally limits a rule to raw, completed-bar OHLCV fields.
    """

    try:
        parsed = rule if isinstance(rule, BarRuleV1) else BarRuleV1.model_validate(dict(rule))
    except (ValidationError, TypeError, ValueError) as exc:
        raise BarRuleValidationError(f"invalid safe bar rule: {exc}") from exc

    allowed = set(BUILTIN_BAR_FEATURES)
    if certified_features:
        allowed.update(str(item) for item in certified_features)
    referenced = referenced_features(parsed)
    prohibited = sorted(name for name in referenced if _looks_future_derived(name))
    if prohibited:
        raise BarRuleValidationError(
            "future/session-final features are prohibited: " + ", ".join(prohibited)
        )
    unsupported = sorted(referenced - allowed)
    if unsupported:
        raise BarRuleValidationError(
            "rule references features that are not causally certified: " + ", ".join(unsupported)
        )
    for operand in _operands(parsed):
        if isinstance(operand, RollingValueV1):
            if operand.feature in BUILTIN_BAR_FEATURES and operand.feature not in _NUMERIC_BUILTINS:
                raise BarRuleValidationError(f"rolling {operand.function} requires a numeric feature")
    return parsed


def referenced_features(rule: BarRuleV1) -> set[str]:
    names: set[str] = set()
    for operand in _operands(rule):
        if isinstance(operand, FeatureValueV1):
            names.add(operand.name)
        elif isinstance(operand, RollingValueV1):
            names.add(operand.feature)
    return names


def required_history_bars(rule: BarRuleV1) -> int:
    required = 1
    contains_cross = False
    for condition in _conditions(rule):
        contains_cross = contains_cross or isinstance(condition, CrossConditionV1)
    for operand in _operands(rule):
        if isinstance(operand, FeatureValueV1):
            required = max(required, operand.lag + 1)
        elif isinstance(operand, RollingValueV1):
            required = max(required, operand.lag + operand.window)
    return required + int(contains_cross)


class SafeBarRuleEvaluator:
    """Incrementally evaluates a validated rule using completed bars only."""

    def __init__(
        self,
        rule: BarRuleV1 | Mapping[str, Any],
        *,
        certified_features: set[str] | frozenset[str] | None = None,
        tunable_values: Mapping[str, Any] | None = None,
    ) -> None:
        self.rule = validate_bar_rule(rule, certified_features=certified_features)
        self.certified_features = frozenset(certified_features or ())
        self.tunable_values = _resolve_tunables(self.rule, tunable_values or {})
        self._history_limit = required_history_bars(self.rule)
        self._history: list[dict[str, Any]] = []

    @property
    def history_size(self) -> int:
        return len(self._history)

    def evaluate(self, completed_bar: Mapping[str, Any]) -> str | None:
        """Return ``long``, ``short``, or ``None`` for one completed bar.

        A bar is appended before evaluation, so lag zero means the bar which has
        just closed.  The simulator remains responsible for filling any emitted
        signal at the next bar open.
        """

        self._history.append(dict(completed_bar))
        if len(self._history) > self._history_limit:
            del self._history[: len(self._history) - self._history_limit]
        long_signal = self._evaluate_condition(self.rule.long_rule) if self.rule.long_rule else False
        short_signal = self._evaluate_condition(self.rule.short_rule) if self.rule.short_rule else False
        if long_signal == short_signal:
            return None
        return "long" if long_signal else "short"

    def _evaluate_condition(self, condition: ConditionV1, *, offset: int = 0) -> bool:
        return self._condition_result(condition, offset=offset) is True

    def _condition_result(self, condition: ConditionV1, *, offset: int = 0) -> bool | None:
        if isinstance(condition, AllConditionV1):
            results = [self._condition_result(item, offset=offset) for item in condition.conditions]
            if False in results:
                return False
            return None if None in results else True
        if isinstance(condition, AnyConditionV1):
            results = [self._condition_result(item, offset=offset) for item in condition.conditions]
            if True in results:
                return True
            return None if None in results else False
        if isinstance(condition, NotConditionV1):
            result = self._condition_result(condition.condition, offset=offset)
            return None if result is None else not result
        if isinstance(condition, ComparisonConditionV1):
            left = self._value(condition.left, offset=offset)
            right = self._value(condition.right, offset=offset)
            return _compare_result(condition.operator, left, right)
        if isinstance(condition, RangeConditionV1):
            value = self._value(condition.value, offset=offset)
            lower = self._value(condition.lower, offset=offset)
            upper = self._value(condition.upper, offset=offset)
            if _missing(value, lower, upper):
                return None
            try:
                return lower <= value <= upper if condition.inclusive else lower < value < upper
            except TypeError:
                return False
        if isinstance(condition, CrossConditionV1):
            left_now = self._value(condition.left, offset=offset)
            right_now = self._value(condition.right, offset=offset)
            left_prior = self._value(condition.left, offset=offset + 1)
            right_prior = self._value(condition.right, offset=offset + 1)
            if _missing(left_now, right_now, left_prior, right_prior):
                return None
            try:
                if condition.direction == "above":
                    return left_now > right_now and left_prior <= right_prior
                return left_now < right_now and left_prior >= right_prior
            except TypeError:
                return False
        return False

    def _value(self, expression: ValueExpressionV1, *, offset: int) -> Any:
        if isinstance(expression, ConstantValueV1):
            return expression.value
        if isinstance(expression, TunableValueV1):
            return self.tunable_values[expression.name]
        if isinstance(expression, FeatureValueV1):
            return self._feature(expression.name, expression.lag + offset)
        if isinstance(expression, RollingValueV1):
            end = len(self._history) - expression.lag - offset
            if end <= 0:
                return _MISSING
            start = max(0, end - expression.window)
            values = [self._feature_at(expression.feature, index) for index in range(start, end)]
            numeric = [float(value) for value in values if _finite_number(value)]
            minimum = expression.min_periods if expression.min_periods is not None else expression.window
            if len(numeric) < minimum:
                return _MISSING
            if expression.function == "mean":
                return sum(numeric) / len(numeric)
            if expression.function == "sum":
                return sum(numeric)
            if expression.function == "min":
                return min(numeric)
            if expression.function == "max":
                return max(numeric)
            return statistics.pstdev(numeric)
        return _MISSING

    def _feature(self, name: str, lag: int) -> Any:
        index = len(self._history) - 1 - lag
        if index < 0:
            return _MISSING
        return self._feature_at(name, index)

    def _feature_at(self, name: str, index: int) -> Any:
        value = self._history[index].get(name, _MISSING)
        if value is None:
            return _MISSING
        if isinstance(value, float) and not math.isfinite(value):
            return _MISSING
        return value


def _resolve_tunables(rule: BarRuleV1, supplied: Mapping[str, Any]) -> dict[str, Any]:
    definitions = {item.name: item for item in rule.tunables}
    unknown = set(supplied) - set(definitions)
    if unknown:
        raise BarRuleValidationError("unknown tunable values: " + ", ".join(sorted(unknown)))
    values = {name: supplied.get(name, definition.default) for name, definition in definitions.items()}
    for name, value in values.items():
        definition = definitions[name]
        if value not in definition.values or type(value) not in {type(item) for item in definition.values}:
            raise BarRuleValidationError(f"tunable {name!r} must be one of its predeclared typed values")
    return values


def _compare_result(operator: str, left: Any, right: Any) -> bool | None:
    if _missing(left, right):
        return None
    try:
        if operator == "gt":
            return left > right
        if operator == "gte":
            return left >= right
        if operator == "lt":
            return left < right
        if operator == "lte":
            return left <= right
        if operator == "eq":
            return type(left) is type(right) and left == right
        if operator == "ne":
            return type(left) is type(right) and left != right
    except TypeError:
        return False
    return False


def _missing(*values: Any) -> bool:
    return any(value is _MISSING for value in values)


def _finite_number(value: Any) -> bool:
    return type(value) in {int, float} and math.isfinite(float(value))


def _looks_future_derived(name: str) -> bool:
    normalized = name.strip().lower()
    return any(marker in normalized for marker in _LOOKAHEAD_MARKERS)


def _conditions(rule: BarRuleV1) -> list[ConditionV1]:
    found: list[ConditionV1] = []

    def visit(condition: ConditionV1 | None) -> None:
        if condition is None:
            return
        found.append(condition)
        if isinstance(condition, (AllConditionV1, AnyConditionV1)):
            for child in condition.conditions:
                visit(child)
        elif isinstance(condition, NotConditionV1):
            visit(condition.condition)

    visit(rule.long_rule)
    visit(rule.short_rule)
    return found


def _operands(rule: BarRuleV1) -> list[ValueExpressionV1]:
    values: list[ValueExpressionV1] = []
    for condition in _conditions(rule):
        if isinstance(condition, ComparisonConditionV1):
            values.extend((condition.left, condition.right))
        elif isinstance(condition, RangeConditionV1):
            values.extend((condition.value, condition.lower, condition.upper))
        elif isinstance(condition, CrossConditionV1):
            values.extend((condition.left, condition.right))
    return values


__all__ = [
    "BarRuleValidationError",
    "SafeBarRuleEvaluator",
    "referenced_features",
    "required_history_bars",
    "validate_bar_rule",
]
