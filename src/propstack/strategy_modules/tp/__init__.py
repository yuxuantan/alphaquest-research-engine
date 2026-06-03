from __future__ import annotations

from propstack.strategy_modules.tp.cost_adjusted_fixed_r import CostAdjustedFixedRTarget, cost_adjusted_fixed_r_target
from propstack.strategy_modules.tp.fixed_r import FixedRTarget, fixed_r_target
from propstack.strategy_modules.tp.opening_range_extension import (
    OpeningRangeExtensionTarget,
    opening_range_extension_target,
)
from propstack.strategy_modules.tp.percent_from_entry import PercentFromEntryTarget, percent_from_entry_target


TP_MODULES = {
    CostAdjustedFixedRTarget.name: CostAdjustedFixedRTarget,
    FixedRTarget.name: FixedRTarget,
    OpeningRangeExtensionTarget.name: OpeningRangeExtensionTarget,
    PercentFromEntryTarget.name: PercentFromEntryTarget,
}


def build_tp_module(config: dict):
    name = config.get("module", FixedRTarget.name)
    params = config.get("params", {})
    try:
        return TP_MODULES[name](params)
    except KeyError as exc:
        raise ValueError(f"Unknown TP module: {name}") from exc


__all__ = [
    "CostAdjustedFixedRTarget",
    "FixedRTarget",
    "OpeningRangeExtensionTarget",
    "PercentFromEntryTarget",
    "cost_adjusted_fixed_r_target",
    "fixed_r_target",
    "opening_range_extension_target",
    "percent_from_entry_target",
    "build_tp_module",
]
