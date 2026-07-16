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
    cards: list[dict[str, Any]] = []
    for index, (stop, target, difference) in enumerate(_RISK_EXPRESSIONS, start=1):
        cards.append(
            {
                "schema": "alphaquest.variant-draft/v1",
                "variant_id": f"v{index:02d}",
                "title": f"{title} — {difference}",
                "entry": {"module": entry, "params": _default_params("entry", entry, execution, setup_mode), "parameter_grid": {}},
                "stop": {"module": stop, "params": _default_params("sl", stop, execution), "parameter_grid": {}},
                "target": {"module": target, "params": _default_params("tp", target, execution), "parameter_grid": {}},
                "mechanic_rationale": (
                    f"Tests the same frozen {recipe_name} edge and {mechanism} through a {difference} "
                    "without using observed PnL."
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
                    "risk invalidation or exit structure rather than only a name, session label, or parameter value."
                ),
                "confirmed": False,
            }
        )
    return cards


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


__all__ = ["binding_defaults", "suggest_variant_cards"]
