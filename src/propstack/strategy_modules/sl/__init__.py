from __future__ import annotations

from propstack.strategy_modules.sl.opening_range_edge import OpeningRangeEdgeStop, opening_range_edge_stop
from propstack.strategy_modules.sl.opening_range_width import OpeningRangeWidthStop, opening_range_width_stop
from propstack.strategy_modules.sl.percent_from_entry import PercentFromEntryStop, percent_from_entry_stop
from propstack.strategy_modules.sl.signal_percent_from_entry import SignalPercentFromEntryStop
from propstack.strategy_modules.sl.sweep_extreme import SweepExtremeStop, sweep_stop


SL_MODULES = {
    OpeningRangeEdgeStop.name: OpeningRangeEdgeStop,
    OpeningRangeWidthStop.name: OpeningRangeWidthStop,
    PercentFromEntryStop.name: PercentFromEntryStop,
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
    "OpeningRangeWidthStop",
    "PercentFromEntryStop",
    "opening_range_edge_stop",
    "opening_range_width_stop",
    "percent_from_entry_stop",
    "SignalPercentFromEntryStop",
    "SweepExtremeStop",
    "sweep_stop",
    "build_sl_module",
]
