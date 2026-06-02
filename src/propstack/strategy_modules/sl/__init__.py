from __future__ import annotations

from propstack.strategy_modules.sl.opening_range_edge import OpeningRangeEdgeStop, opening_range_edge_stop
from propstack.strategy_modules.sl.sweep_extreme import SweepExtremeStop, sweep_stop


SL_MODULES = {
    OpeningRangeEdgeStop.name: OpeningRangeEdgeStop,
    SweepExtremeStop.name: SweepExtremeStop,
}


def build_sl_module(config: dict):
    name = config.get("module", SweepExtremeStop.name)
    params = config.get("params", {})
    try:
        return SL_MODULES[name](params)
    except KeyError as exc:
        raise ValueError(f"Unknown SL module: {name}") from exc


__all__ = ["OpeningRangeEdgeStop", "opening_range_edge_stop", "SweepExtremeStop", "sweep_stop", "build_sl_module"]
