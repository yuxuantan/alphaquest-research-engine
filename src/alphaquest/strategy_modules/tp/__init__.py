from __future__ import annotations

from alphaquest.strategy_modules.tp.cost_adjusted_fixed_r import CostAdjustedFixedRTarget, cost_adjusted_fixed_r_target
from alphaquest.strategy_modules.tp.fixed_r import FixedRTarget, fixed_r_target
from alphaquest.strategy_modules.tp.fixed_dollar_per_contract import (
    FixedDollarPerContractTarget,
    fixed_dollar_per_contract_target,
)
from alphaquest.strategy_modules.tp.gap_fill_fraction import GapFillFractionTarget
from alphaquest.strategy_modules.tp.opening_range_extension import (
    OpeningRangeExtensionTarget,
    opening_range_extension_target,
)
from alphaquest.strategy_modules.tp.opening_range_opposite_edge import (
    OpeningRangeOppositeEdgeTarget,
    opening_range_opposite_edge_target,
)
from alphaquest.strategy_modules.tp.percent_from_entry import PercentFromEntryTarget, percent_from_entry_target
from alphaquest.strategy_modules.tp.points_from_entry import PointsFromEntryTarget
from alphaquest.strategy_modules.tp.prop_fixed_fraction_r import (
    PropFixedFractionRTarget,
    prop_fixed_fraction_r_target,
)
from alphaquest.strategy_modules.tp.signal_fixed_r import SignalFixedRTarget
from alphaquest.strategy_modules.tp.signal_price import SignalPriceTarget


TP_MODULES = {
    CostAdjustedFixedRTarget.name: CostAdjustedFixedRTarget,
    FixedRTarget.name: FixedRTarget,
    FixedDollarPerContractTarget.name: FixedDollarPerContractTarget,
    GapFillFractionTarget.name: GapFillFractionTarget,
    OpeningRangeExtensionTarget.name: OpeningRangeExtensionTarget,
    OpeningRangeOppositeEdgeTarget.name: OpeningRangeOppositeEdgeTarget,
    PercentFromEntryTarget.name: PercentFromEntryTarget,
    PointsFromEntryTarget.name: PointsFromEntryTarget,
    PropFixedFractionRTarget.name: PropFixedFractionRTarget,
    SignalFixedRTarget.name: SignalFixedRTarget,
    SignalPriceTarget.name: SignalPriceTarget,
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
    "FixedDollarPerContractTarget",
    "GapFillFractionTarget",
    "OpeningRangeExtensionTarget",
    "OpeningRangeOppositeEdgeTarget",
    "PercentFromEntryTarget",
    "PointsFromEntryTarget",
    "PropFixedFractionRTarget",
    "SignalFixedRTarget",
    "SignalPriceTarget",
    "cost_adjusted_fixed_r_target",
    "fixed_dollar_per_contract_target",
    "fixed_r_target",
    "opening_range_extension_target",
    "opening_range_opposite_edge_target",
    "percent_from_entry_target",
    "prop_fixed_fraction_r_target",
    "build_tp_module",
]
