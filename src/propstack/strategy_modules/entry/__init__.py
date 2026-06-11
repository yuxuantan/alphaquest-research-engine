from __future__ import annotations

from propstack.strategy_modules.entry.calendar_session_bias import CalendarSessionBiasEntry
from propstack.strategy_modules.entry.cftc_tff_hedging_pressure import CftcTffHedgingPressureEntry
from propstack.strategy_modules.entry.cftc_tff_tiered_hedging_pressure import CftcTffTieredHedgingPressureEntry
from propstack.strategy_modules.entry.daily_time_series_momentum import DailyTimeSeriesMomentumEntry
from propstack.strategy_modules.entry.intraday_capitulation_mr import IntradayCapitulationMREntry
from propstack.strategy_modules.entry.late_day_intraday_momentum import LateDayIntradayMomentumEntry
from propstack.strategy_modules.entry.liquidity_risk_capacity_priority import LiquidityRiskCapacityPriorityEntry
from propstack.strategy_modules.entry.market_plumbing_priority import MarketPlumbingPriorityEntry
from propstack.strategy_modules.entry.morning_intraday_momentum import MorningIntradayMomentumEntry
from propstack.strategy_modules.entry.opening_range_breakout import OpeningRangeBreakoutEntry
from propstack.strategy_modules.entry.opening_range_filtered_breakout import OpeningRangeFilteredBreakoutEntry
from propstack.strategy_modules.entry.opening_range_inverse_breakout import OpeningRangeInverseBreakoutEntry
from propstack.strategy_modules.entry.opening_drive_inventory_combo import OpeningDriveInventoryComboEntry
from propstack.strategy_modules.entry.orderflow_recent_pocket_combo import OrderflowRecentPocketComboEntry
from propstack.strategy_modules.entry.overnight_return_late_day_momentum import OvernightReturnLateDayMomentumEntry
from propstack.strategy_modules.entry.overnight_inventory_reversion import OvernightInventoryReversionEntry
from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.pdh_pdl_breakout_continuation import PdhPdlBreakoutContinuationEntry
from propstack.strategy_modules.entry.pdh_pdl_sweep_reclaim import PdhPdlSweepReclaimEntry
from propstack.strategy_modules.entry.rth_gap_fade import RthGapFadeEntry
from propstack.strategy_modules.entry.turn_of_month_bias import TurnOfMonthBiasEntry
from propstack.strategy_modules.entry.trade_orderflow_multi_pressure import TradeOrderflowMultiPressureEntry
from propstack.strategy_modules.entry.trade_orderflow_multi_state_rank import TradeOrderflowMultiStateRankEntry
from propstack.strategy_modules.entry.trade_orderflow_pressure import TradeOrderflowPressureEntry
from propstack.strategy_modules.entry.trade_orderflow_state_rank import TradeOrderflowStateRankEntry
from propstack.strategy_modules.entry.volume_conditioned_liquidity_reversal import (
    VolumeConditionedLiquidityReversalEntry,
)
from propstack.strategy_modules.entry.vpin_toxicity_continuation import VpinToxicityContinuationEntry
from propstack.strategy_modules.entry.vwap_pullback_continuation import VwapPullbackContinuationEntry


ENTRY_MODULES = {
    CalendarSessionBiasEntry.name: CalendarSessionBiasEntry,
    CftcTffHedgingPressureEntry.name: CftcTffHedgingPressureEntry,
    CftcTffTieredHedgingPressureEntry.name: CftcTffTieredHedgingPressureEntry,
    DailyTimeSeriesMomentumEntry.name: DailyTimeSeriesMomentumEntry,
    IntradayCapitulationMREntry.name: IntradayCapitulationMREntry,
    LateDayIntradayMomentumEntry.name: LateDayIntradayMomentumEntry,
    LiquidityRiskCapacityPriorityEntry.name: LiquidityRiskCapacityPriorityEntry,
    MarketPlumbingPriorityEntry.name: MarketPlumbingPriorityEntry,
    MorningIntradayMomentumEntry.name: MorningIntradayMomentumEntry,
    OpeningRangeBreakoutEntry.name: OpeningRangeBreakoutEntry,
    OpeningDriveInventoryComboEntry.name: OpeningDriveInventoryComboEntry,
    OpeningRangeFilteredBreakoutEntry.name: OpeningRangeFilteredBreakoutEntry,
    OpeningRangeInverseBreakoutEntry.name: OpeningRangeInverseBreakoutEntry,
    OrderflowRecentPocketComboEntry.name: OrderflowRecentPocketComboEntry,
    OvernightReturnLateDayMomentumEntry.name: OvernightReturnLateDayMomentumEntry,
    OvernightInventoryReversionEntry.name: OvernightInventoryReversionEntry,
    PdhPdlBreakoutContinuationEntry.name: PdhPdlBreakoutContinuationEntry,
    PdhPdlSweepReclaimEntry.name: PdhPdlSweepReclaimEntry,
    RthGapFadeEntry.name: RthGapFadeEntry,
    TurnOfMonthBiasEntry.name: TurnOfMonthBiasEntry,
    TradeOrderflowMultiPressureEntry.name: TradeOrderflowMultiPressureEntry,
    TradeOrderflowMultiStateRankEntry.name: TradeOrderflowMultiStateRankEntry,
    TradeOrderflowPressureEntry.name: TradeOrderflowPressureEntry,
    TradeOrderflowStateRankEntry.name: TradeOrderflowStateRankEntry,
    VolumeConditionedLiquidityReversalEntry.name: VolumeConditionedLiquidityReversalEntry,
    VpinToxicityContinuationEntry.name: VpinToxicityContinuationEntry,
    VwapPullbackContinuationEntry.name: VwapPullbackContinuationEntry,
}


def build_entry_module(config: dict):
    name = config.get("module", PdhPdlSweepReclaimEntry.name)
    params = config.get("params", {})
    try:
        return ENTRY_MODULES[name](params)
    except KeyError as exc:
        raise ValueError(f"Unknown entry module: {name}") from exc


__all__ = [
    "Signal",
    "CalendarSessionBiasEntry",
    "CftcTffHedgingPressureEntry",
    "CftcTffTieredHedgingPressureEntry",
    "DailyTimeSeriesMomentumEntry",
    "IntradayCapitulationMREntry",
    "LateDayIntradayMomentumEntry",
    "LiquidityRiskCapacityPriorityEntry",
    "MarketPlumbingPriorityEntry",
    "MorningIntradayMomentumEntry",
    "OpeningRangeBreakoutEntry",
    "OpeningDriveInventoryComboEntry",
    "OpeningRangeFilteredBreakoutEntry",
    "OpeningRangeInverseBreakoutEntry",
    "OrderflowRecentPocketComboEntry",
    "OvernightReturnLateDayMomentumEntry",
    "OvernightInventoryReversionEntry",
    "PdhPdlBreakoutContinuationEntry",
    "PdhPdlSweepReclaimEntry",
    "RthGapFadeEntry",
    "TurnOfMonthBiasEntry",
    "TradeOrderflowMultiPressureEntry",
    "TradeOrderflowMultiStateRankEntry",
    "TradeOrderflowPressureEntry",
    "TradeOrderflowStateRankEntry",
    "VolumeConditionedLiquidityReversalEntry",
    "VpinToxicityContinuationEntry",
    "VwapPullbackContinuationEntry",
    "build_entry_module",
]
