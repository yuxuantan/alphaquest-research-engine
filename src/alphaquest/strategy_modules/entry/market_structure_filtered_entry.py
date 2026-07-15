from __future__ import annotations

from dataclasses import replace

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.market_structure_pivots import MultiTimeframePivotStructure
from alphaquest.strategy_modules.entry.mes_participation_crowding import MesParticipationCrowdingEntry
from alphaquest.strategy_modules.entry.opening_range_orderflow_breakout import OpeningRangeOrderflowBreakoutEntry
from alphaquest.strategy_modules.entry.prior_value_area_orderflow_acceptance import (
    PriorValueAreaOrderflowAcceptanceEntry,
)
from alphaquest.strategy_modules.entry.price_ending_barrier import PriceEndingBarrierEntry
from alphaquest.strategy_modules.entry.spx_0dte_expiration_pressure import Spx0dteExpirationPressureEntry
from alphaquest.strategy_modules.entry.vwap_pullback_continuation import VwapPullbackContinuationEntry
from alphaquest.utils.time import parse_time


_SUPPORTED_BASE_MODULES = {
    MesParticipationCrowdingEntry.name: MesParticipationCrowdingEntry,
    OpeningRangeOrderflowBreakoutEntry.name: OpeningRangeOrderflowBreakoutEntry,
    PriceEndingBarrierEntry.name: PriceEndingBarrierEntry,
    PriorValueAreaOrderflowAcceptanceEntry.name: PriorValueAreaOrderflowAcceptanceEntry,
    Spx0dteExpirationPressureEntry.name: Spx0dteExpirationPressureEntry,
    VwapPullbackContinuationEntry.name: VwapPullbackContinuationEntry,
}


class MarketStructureFilteredEntry:
    name = "market_structure_filtered_entry"

    def __init__(self, params: dict):
        self.params = params
        base_module = str(params.get("base_module", ""))
        if base_module not in _SUPPORTED_BASE_MODULES:
            raise ValueError(
                "market_structure_filtered_entry base_module must be one of "
                f"{sorted(_SUPPORTED_BASE_MODULES)}."
            )
        self.base_module = base_module
        self.base_entry = _SUPPORTED_BASE_MODULES[base_module](dict(params.get("base_params") or {}))

        rth_start = parse_time(params.get("rth_start", "09:30:00"))
        bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        tick_size = float(params.get("tick_size", 0.25))
        timeframes = _int_list(params.get("timeframes_minutes", [15, 30]))
        self.structure = MultiTimeframePivotStructure(
            timeframes_minutes=timeframes,
            bar_interval_minutes=bar_interval_minutes,
            rth_start=rth_start,
            tick_size=tick_size,
            pivot_left_bars=int(params.get("pivot_left_bars", 1)),
            pivot_right_bars=int(params.get("pivot_right_bars", 1)),
            min_pivot_move_ticks=float(params.get("min_pivot_move_ticks", 0.0)),
            min_aligned_timeframes=int(params.get("min_aligned_timeframes", len(timeframes))),
            carry_pivots_across_sessions=bool(params.get("carry_pivots_across_sessions", False)),
        )

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if bool(bar.get("is_rth", False)):
            self.structure.update(bar)
        signal = self.base_entry.on_bar_close(bar, trades_today=trades_today)
        if signal is None:
            return None
        bias = self.structure.bias()
        if bias["direction"] != signal.direction:
            return None

        filter_fields = {
            "market_structure_filter_base_module": self.base_module,
            "market_structure_filter_result": "passed",
            **self.structure.report_fields("market_structure_filter"),
        }
        metadata = {**signal.metadata, **filter_fields}
        report_fields = {**signal.report_fields, **filter_fields}
        level_type = f"{signal.level_type}_with_market_structure_filter"
        return replace(
            signal,
            level_type=level_type,
            metadata=metadata,
            report_fields=report_fields,
        )


def _int_list(value) -> list[int]:
    if isinstance(value, str):
        value = [item.strip() for item in value.split(",") if item.strip()]
    return [int(item) for item in value]
