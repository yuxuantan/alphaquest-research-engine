"""Value-independent variant suggestions derived from a research brief."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from alphaquest.authoring.catalog import get_certified_module_catalog
from alphaquest.authoring.models import CERTIFIED_RECIPE_BINDINGS


_RISK_EXPRESSIONS = (
    ("points_from_entry", "fixed_r", "fixed-point invalidation with gross fixed-R exit"),
    ("percent_from_entry", "fixed_r", "price-scaled invalidation with gross fixed-R exit"),
    (
        "fixed_dollar_per_contract",
        "cost_adjusted_fixed_r",
        "fixed-dollar invalidation with cost-adjusted fixed-R exit",
    ),
    ("points_from_entry", "cost_adjusted_fixed_r", "fixed-point invalidation with cost-adjusted exit"),
    ("fixed_dollar_per_contract", "fixed_r", "fixed-dollar invalidation with gross fixed-R exit"),
)


def suggest_variant_cards(draft: dict[str, Any]) -> list[dict[str, Any]]:
    """Return five editable cards without consulting backtest results.

    The brief is used only for language and direction permissions.  Mechanics
    come exclusively from the certified catalog; no result or evidence paths
    are accepted by this function.
    """

    return [suggest_variant_card(draft, index=index) for index in range(len(_RISK_EXPRESSIONS))]


def suggest_variant_card(
    draft: dict[str, Any],
    *,
    index: int,
    failure_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create one mechanic, using the predecessor failure when a slot is unlocked."""

    if not 0 <= index < len(_RISK_EXPRESSIONS):
        raise ValueError("variant index exceeds the five-variant maximum")
    title = str(draft.get("title") or "Research edge")
    mechanism = str(draft.get("expected_mechanism") or "the frozen economic mechanism")
    execution = draft.get("execution") if isinstance(draft.get("execution"), dict) else {}
    point_value = float(execution.get("point_value") or 50.0)
    tick_size = float(execution.get("tick_size") or 0.25)
    tick_value = float(execution.get("tick_value") or 12.5)
    commission = float(execution.get("commission_per_contract") or 2.5)
    slippage = float(execution.get("slippage_ticks") or 1.0)
    recipe_name = draft.get("certified_recipe")
    if recipe_name is None and draft.get("authoring_lane") == "visual_completed_bar_rule":
        # The caller replaces this seed binding with the reviewed safe rule.  It
        # still needs the five risk structures below before that replacement.
        recipe_name = "opening_range_breakout"
    if recipe_name not in CERTIFIED_RECIPE_BINDINGS:
        raise ValueError("select and review one certified edge recipe before generating variants")
    entry, setup_mode = CERTIFIED_RECIPE_BINDINGS[str(recipe_name)]
    expression_index = _select_risk_expression(draft, index=index, failure_context=failure_context)
    stop, target, difference = _RISK_EXPRESSIONS[expression_index]
    variant_number = index + 1
    failure_note = _failure_note(failure_context)
    return {
                "schema": "alphaquest.variant-draft/v1",
                "variant_id": f"v{variant_number:02d}",
                "title": f"{title} — {difference}",
                "entry": {"module": entry, "params": _default_params("entry", entry, execution, setup_mode), "parameter_grid": {}},
                "stop": {"module": stop, "params": _default_params("sl", stop, execution), "parameter_grid": {}},
                "target": {"module": target, "params": _default_params("tp", target, execution), "parameter_grid": {}},
                "mechanic_rationale": (
                    f"Tests the same frozen {recipe_name} edge and {mechanism} through a {difference} "
                    f"{failure_note}"
                ),
                "entry_rationale": (
                    f"The certified {entry} contract observes only completed information and emits a decision "
                    "that can enter no earlier than the following bar, preserving the frozen causal timeline."
                ),
                "stop_rationale": (
                    f"The certified {stop} contract anchors risk to the actual filled entry and applies the "
                    "instrument tick rules, so losses are evaluated under the declared execution assumptions."
                ),
                "target_rationale": (
                    f"The certified {target} contract derives its exit from information fixed at entry and "
                    "includes the declared cost assumptions without adapting to later observed performance."
                ),
                "timeframe_session_rationale": (
                    "The selected completed-bar timeframe matches the governed dataset, while the confirmed "
                    "session, entry cutoff, and force-flatten times prevent ambiguous or overnight exposure."
                ),
                "known_failure_modes": deepcopy(draft.get("known_failure_modes") or ["The hypothesized behavior may be absent."]),
                "material_difference": (
                    f"This {difference} keeps the one frozen entry edge fixed while changing a certified "
                    "risk invalidation or exit structure rather than only a name, session label, or parameter value. "
                    f"{failure_note}"
                ),
                "confirmed": False,
            }


def _select_risk_expression(
    draft: dict[str, Any],
    *,
    index: int,
    failure_context: dict[str, Any] | None,
) -> int:
    if not failure_context:
        return index
    used = {
        (
            str(((item.get("stop") or {}).get("module") or "")),
            str(((item.get("target") or {}).get("module") or "")),
        )
        for item in draft.get("variants") or []
        if isinstance(item, dict)
    }
    available = [
        position
        for position, (stop, target, _) in enumerate(_RISK_EXPRESSIONS)
        if (stop, target) not in used
    ]
    if not available:
        raise ValueError("no materially distinct certified mechanic remains within the five-variant maximum")
    text = " ".join(
        str(failure_context.get(key) or "")
        for key in ("stage", "metric", "reason", "verdict_message")
    ).casefold()
    if any(token in text for token in ("drawdown", "ruin", "prop_rule", "monte_carlo", "monkey")):
        ranked = (2, 3, 1, 4, 0)
    elif any(token in text for token in ("profit", "expectancy", "payoff", "transaction_cost", "cost")):
        ranked = (3, 2, 1, 4, 0)
    elif any(token in text for token in ("walk_forward", "wfa", "stability", "neighbor", "regime")):
        ranked = (1, 2, 3, 4, 0)
    else:
        ranked = tuple(range(index, len(_RISK_EXPRESSIONS))) + tuple(range(index))
    return next(position for position in ranked if position in available)


def _failure_note(failure_context: dict[str, Any] | None) -> str:
    if not failure_context:
        return "The mechanic is frozen before any performance result is observed."
    stage = str(failure_context.get("stage") or "terminal assessment")
    metric = str(failure_context.get("metric") or "campaign verdict")
    actual = failure_context.get("actual")
    threshold = failure_context.get("threshold")
    comparison = ""
    if actual is not None or threshold is not None:
        comparison = f" (actual {actual!r}; threshold {threshold!r})"
    return (
        f"This mechanic was selected from the remaining certified structures after the predecessor failed "
        f"{stage}/{metric}{comparison}; it is a new predeclared test, not a reinterpretation of that result."
    )


def binding_defaults(module_type: str, module_name: str, execution: dict[str, Any] | None = None) -> dict[str, Any]:
    return _default_params(module_type, module_name, execution or {}, None)


def _default_params(
    module_type: str,
    module_name: str,
    execution: dict[str, Any],
    setup_mode: str | None = None,
) -> dict[str, Any]:
    manifest = get_certified_module_catalog().get(module_type, module_name)
    params = {
        name: deepcopy(spec.default)
        for name, spec in manifest.parameters.items()
        if spec.default is not None
    }
    if module_name == "calendar_session_bias":
        params["weekday_directions"] = {str(day): "long" for day in range(5)}
    elif module_name == "daily_time_series_momentum" and setup_mode:
        params["setup_mode"] = setup_mode
    elif module_name == "fixed_dollar_per_contract":
        params.update({"dollars_per_contract": 250.0, "tick_value": float(execution.get("tick_value") or 12.5)})
    elif module_name == "cost_adjusted_fixed_r":
        params.update(
            {
                "tick_size": float(execution.get("tick_size") or 0.25),
                "tick_value": float(execution.get("tick_value") or 12.5),
                "commission_per_contract": float(execution.get("commission_per_contract") or 2.5),
                "slippage_ticks": float(execution.get("slippage_ticks") or 1.0),
            }
        )
    return params


__all__ = ["binding_defaults", "suggest_variant_card", "suggest_variant_cards"]
