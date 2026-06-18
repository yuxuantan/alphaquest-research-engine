from __future__ import annotations

from propstack.strategy_modules.sl.opening_range_edge import OpeningRangeEdgeStop, opening_range_edge_stop
from propstack.strategy_modules.sl.opening_gap_boundary import OpeningGapBoundaryStop
from propstack.strategy_modules.sl.opening_range_retest_boundary import (
    OpeningRangeRetestBoundaryStop,
    opening_range_retest_boundary_stop,
)
from propstack.strategy_modules.sl.opening_range_width import OpeningRangeWidthStop, opening_range_width_stop
from propstack.strategy_modules.sl.prior_level_retest_boundary import PriorLevelRetestBoundaryStop
from propstack.strategy_modules.sl.fixed_dollar_per_contract import (
    FixedDollarPerContractStop,
    fixed_dollar_per_contract_stop,
)
from propstack.strategy_modules.sl.percent_from_entry import PercentFromEntryStop, percent_from_entry_stop
from propstack.strategy_modules.sl.signal_percent_from_entry import SignalPercentFromEntryStop
from propstack.strategy_modules.sl.sweep_extreme import SweepExtremeStop, sweep_stop


SL_MODULES = {
    OpeningRangeEdgeStop.name: OpeningRangeEdgeStop,
    OpeningGapBoundaryStop.name: OpeningGapBoundaryStop,
    OpeningRangeRetestBoundaryStop.name: OpeningRangeRetestBoundaryStop,
    OpeningRangeWidthStop.name: OpeningRangeWidthStop,
    FixedDollarPerContractStop.name: FixedDollarPerContractStop,
    PercentFromEntryStop.name: PercentFromEntryStop,
    PriorLevelRetestBoundaryStop.name: PriorLevelRetestBoundaryStop,
    SignalPercentFromEntryStop.name: SignalPercentFromEntryStop,
    SweepExtremeStop.name: SweepExtremeStop,
}


def build_sl_module(config: dict):
    name = config.get("module", SweepExtremeStop.name)
    params = config.get("params", {})
    try:
        return SL_MODULES[name](params)
    except KeyError as exc:
        raise ValueError(f"Unknown SL module: {name}") from exc


__all__ = [
    "OpeningRangeEdgeStop",
    "OpeningGapBoundaryStop",
    "OpeningRangeRetestBoundaryStop",
    "OpeningRangeWidthStop",
    "FixedDollarPerContractStop",
    "PercentFromEntryStop",
    "PriorLevelRetestBoundaryStop",
    "fixed_dollar_per_contract_stop",
    "opening_range_edge_stop",
    "opening_range_retest_boundary_stop",
    "opening_range_width_stop",
    "percent_from_entry_stop",
    "SignalPercentFromEntryStop",
    "SweepExtremeStop",
    "sweep_stop",
    "build_sl_module",
]
