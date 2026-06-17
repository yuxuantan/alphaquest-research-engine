from __future__ import annotations

from propstack.strategy_modules.entry.aqr_bab_factor_state import AqrBabFactorStateEntry
from propstack.strategy_modules.entry.bankruptcy_distress_reversion import BankruptcyDistressReversionEntry
from propstack.strategy_modules.entry.amihud_illiquidity_state import AmihudIlliquidityStateEntry
from propstack.strategy_modules.entry.bls_macro_release_day_drift import BlsMacroReleaseDayDriftEntry
from propstack.strategy_modules.entry.calendar_session_bias import CalendarSessionBiasEntry
from propstack.strategy_modules.entry.cftc_tff_hedging_pressure import CftcTffHedgingPressureEntry
from propstack.strategy_modules.entry.cftc_tff_tiered_hedging_pressure import CftcTffTieredHedgingPressureEntry
from propstack.strategy_modules.entry.cboe_put_call_sentiment import CboePutCallSentimentEntry
from propstack.strategy_modules.entry.cboe_implied_correlation import CboeImpliedCorrelationEntry
from propstack.strategy_modules.entry.cboe_skew_tail_risk import CboeSkewTailRiskEntry
from propstack.strategy_modules.entry.cboe_vix_level_state import CboeVixLevelStateEntry
from propstack.strategy_modules.entry.cboe_vix_term_structure import CboeVixTermStructureEntry
from propstack.strategy_modules.entry.cboe_vxn_vix_dispersion import CboeVxnVixDispersionEntry
from propstack.strategy_modules.entry.chicagofed_cfnai_activity_state import (
    ChicagoFedCfnaiActivityStateEntry,
)
from propstack.strategy_modules.entry.consumer_sentiment_state import ConsumerSentimentStateEntry
from propstack.strategy_modules.entry.connors_rsi2_mean_reversion import ConnorsRsi2MeanReversionEntry
from propstack.strategy_modules.entry.credit_spread_state import CreditSpreadStateEntry
from propstack.strategy_modules.entry.daily_time_series_momentum import DailyTimeSeriesMomentumEntry
from propstack.strategy_modules.entry.daily_short_term_reversal import DailyShortTermReversalEntry
from propstack.strategy_modules.entry.dollar_risk_appetite import DollarRiskAppetiteEntry
from propstack.strategy_modules.entry.epu_policy_uncertainty import EpuPolicyUncertaintyEntry
from propstack.strategy_modules.entry.es_nq_lead_lag import EsNqLeadLagEntry
from propstack.strategy_modules.entry.es_nq_relative_value_reversion import EsNqRelativeValueReversionEntry
from propstack.strategy_modules.entry.es_term_structure_lead_lag import EsTermStructureLeadLagEntry
from propstack.strategy_modules.entry.finra_margin_leverage import FinraMarginLeverageEntry
from propstack.strategy_modules.entry.fomc_pre_announcement_drift import FomcPreAnnouncementDriftEntry
from propstack.strategy_modules.entry.gao_last_half_hour_orderflow import GaoLastHalfHourOrderflowEntry
from propstack.strategy_modules.entry.halloween_seasonal_premium import HalloweenSeasonalPremiumEntry
from propstack.strategy_modules.entry.intraday_capitulation_mr import IntradayCapitulationMREntry
from propstack.strategy_modules.entry.intraday_momentum_priority import IntradayMomentumPriorityEntry
from propstack.strategy_modules.entry.intraday_periodicity_persistence import IntradayPeriodicityPersistenceEntry
from propstack.strategy_modules.entry.late_day_intraday_momentum import LateDayIntradayMomentumEntry
from propstack.strategy_modules.entry.leveraged_etf_rebalance_pressure import LeveragedEtfRebalancePressureEntry
from propstack.strategy_modules.entry.liquidity_risk_capacity_priority import LiquidityRiskCapacityPriorityEntry
from propstack.strategy_modules.entry.market_plumbing_priority import MarketPlumbingPriorityEntry
from propstack.strategy_modules.entry.mes_participation_crowding import MesParticipationCrowdingEntry
from propstack.strategy_modules.entry.monthly_opex_pressure import MonthlyOpexPressureEntry
from propstack.strategy_modules.entry.morning_intraday_momentum import MorningIntradayMomentumEntry
from propstack.strategy_modules.entry.morning_orderflow_momentum import MorningOrderflowMomentumEntry
from propstack.strategy_modules.entry.naaim_exposure_sentiment import NaaimExposureSentimentEntry
from propstack.strategy_modules.entry.opening_range_breakout import OpeningRangeBreakoutEntry
from propstack.strategy_modules.entry.opening_range_filtered_breakout import OpeningRangeFilteredBreakoutEntry
from propstack.strategy_modules.entry.opening_range_inverse_breakout import OpeningRangeInverseBreakoutEntry
from propstack.strategy_modules.entry.opening_range_orderflow_breakout import OpeningRangeOrderflowBreakoutEntry
from propstack.strategy_modules.entry.opening_gap_orderflow_fade import OpeningGapOrderflowFadeEntry
from propstack.strategy_modules.entry.opening_drive_inventory_combo import OpeningDriveInventoryComboEntry
from propstack.strategy_modules.entry.ofr_financial_stress import OfrFinancialStressEntry
from propstack.strategy_modules.entry.oil_price_shock_spillover import OilPriceShockSpilloverEntry
from propstack.strategy_modules.entry.orderflow_regime import OrderflowRegimeEntry
from propstack.strategy_modules.entry.orderflow_recent_pocket_combo import OrderflowRecentPocketComboEntry
from propstack.strategy_modules.entry.overnight_return_late_day_momentum import OvernightReturnLateDayMomentumEntry
from propstack.strategy_modules.entry.overnight_intraday_reversal import OvernightIntradayReversalEntry
from propstack.strategy_modules.entry.overnight_inventory_reversion import OvernightInventoryReversionEntry
from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.pdh_pdl_breakout_continuation import PdhPdlBreakoutContinuationEntry
from propstack.strategy_modules.entry.pdh_pdl_sweep_reclaim import PdhPdlSweepReclaimEntry
from propstack.strategy_modules.entry.positive_delta_dislocation import PositiveDeltaDislocationEntry
from propstack.strategy_modules.entry.preholiday_effect import PreholidayEffectEntry
from propstack.strategy_modules.entry.prior_session_ibs_reversion import PriorSessionIbsReversionEntry
from propstack.strategy_modules.entry.quarterly_expiration_pressure import QuarterlyExpirationPressureEntry
from propstack.strategy_modules.entry.quote_liquidity_sweep_reversion import QuoteLiquiditySweepReversionEntry
from propstack.strategy_modules.entry.range_compression_breakout import RangeCompressionBreakoutEntry
from propstack.strategy_modules.entry.realized_jump_variation_premium import RealizedJumpVariationPremiumEntry
from propstack.strategy_modules.entry.realized_semivariance_asymmetry import RealizedSemivarianceAsymmetryEntry
from propstack.strategy_modules.entry.realized_skewness_reversal import RealizedSkewnessReversalEntry
from propstack.strategy_modules.entry.realized_vol_of_vol_state import RealizedVolOfVolStateEntry
from propstack.strategy_modules.entry.round_number_barrier import RoundNumberBarrierEntry
from propstack.strategy_modules.entry.rth_gap_fade import RthGapFadeEntry
from propstack.strategy_modules.entry.sector_dispersion_state import SectorDispersionStateEntry
from propstack.strategy_modules.entry.sector_rotation_risk_appetite import SectorRotationRiskAppetiteEntry
from propstack.strategy_modules.entry.spx_0dte_expiration_pressure import Spx0dteExpirationPressureEntry
from propstack.strategy_modules.entry.spx_0dte_trend_aligned_pressure import Spx0dteTrendAlignedPressureEntry
from propstack.strategy_modules.entry.turn_of_month_bias import TurnOfMonthBiasEntry
from propstack.strategy_modules.entry.trade_orderflow_multi_pressure import TradeOrderflowMultiPressureEntry
from propstack.strategy_modules.entry.trade_orderflow_multi_state_rank import TradeOrderflowMultiStateRankEntry
from propstack.strategy_modules.entry.trade_orderflow_pressure import TradeOrderflowPressureEntry
from propstack.strategy_modules.entry.trade_orderflow_state_rank import TradeOrderflowStateRankEntry
from propstack.strategy_modules.entry.trade_fragmentation_liquidity_reversion import (
    TradeFragmentationLiquidityReversionEntry,
)
from propstack.strategy_modules.entry.trade_size_segment_orderflow import TradeSizeSegmentOrderflowEntry
from propstack.strategy_modules.entry.treasury_auction_pressure import TreasuryAuctionPressureEntry
from propstack.strategy_modules.entry.treasury_rate_state import TreasuryRateStateEntry
from propstack.strategy_modules.entry.turn_of_year_effect import TurnOfYearEffectEntry
from propstack.strategy_modules.entry.usdjpy_safe_haven import UsdJpySafeHavenEntry
from propstack.strategy_modules.entry.variance_risk_premium_intraday import VarianceRiskPremiumIntradayEntry
from propstack.strategy_modules.entry.vix_expiration_pressure import VixExpirationPressureEntry
from propstack.strategy_modules.entry.volatility_managed_intraday_premium import (
    VolatilityManagedIntradayPremiumEntry,
)
from propstack.strategy_modules.entry.volume_conditioned_liquidity_reversal import (
    VolumeConditionedLiquidityReversalEntry,
)
from propstack.strategy_modules.entry.vpin_toxicity_continuation import VpinToxicityContinuationEntry
from propstack.strategy_modules.entry.vvix_tail_risk import VvixTailRiskEntry
from propstack.strategy_modules.entry.vwap_pullback_continuation import VwapPullbackContinuationEntry


ENTRY_MODULES = {
    AqrBabFactorStateEntry.name: AqrBabFactorStateEntry,
    BankruptcyDistressReversionEntry.name: BankruptcyDistressReversionEntry,
    AmihudIlliquidityStateEntry.name: AmihudIlliquidityStateEntry,
    BlsMacroReleaseDayDriftEntry.name: BlsMacroReleaseDayDriftEntry,
    CalendarSessionBiasEntry.name: CalendarSessionBiasEntry,
    CftcTffHedgingPressureEntry.name: CftcTffHedgingPressureEntry,
    CftcTffTieredHedgingPressureEntry.name: CftcTffTieredHedgingPressureEntry,
    CboePutCallSentimentEntry.name: CboePutCallSentimentEntry,
    CboeImpliedCorrelationEntry.name: CboeImpliedCorrelationEntry,
    CboeSkewTailRiskEntry.name: CboeSkewTailRiskEntry,
    CboeVixLevelStateEntry.name: CboeVixLevelStateEntry,
    CboeVixTermStructureEntry.name: CboeVixTermStructureEntry,
    CboeVxnVixDispersionEntry.name: CboeVxnVixDispersionEntry,
    ChicagoFedCfnaiActivityStateEntry.name: ChicagoFedCfnaiActivityStateEntry,
    ConsumerSentimentStateEntry.name: ConsumerSentimentStateEntry,
    ConnorsRsi2MeanReversionEntry.name: ConnorsRsi2MeanReversionEntry,
    CreditSpreadStateEntry.name: CreditSpreadStateEntry,
    DailyTimeSeriesMomentumEntry.name: DailyTimeSeriesMomentumEntry,
    DailyShortTermReversalEntry.name: DailyShortTermReversalEntry,
    DollarRiskAppetiteEntry.name: DollarRiskAppetiteEntry,
    EpuPolicyUncertaintyEntry.name: EpuPolicyUncertaintyEntry,
    EsNqLeadLagEntry.name: EsNqLeadLagEntry,
    EsNqRelativeValueReversionEntry.name: EsNqRelativeValueReversionEntry,
    EsTermStructureLeadLagEntry.name: EsTermStructureLeadLagEntry,
    FinraMarginLeverageEntry.name: FinraMarginLeverageEntry,
    FomcPreAnnouncementDriftEntry.name: FomcPreAnnouncementDriftEntry,
    GaoLastHalfHourOrderflowEntry.name: GaoLastHalfHourOrderflowEntry,
    HalloweenSeasonalPremiumEntry.name: HalloweenSeasonalPremiumEntry,
    IntradayCapitulationMREntry.name: IntradayCapitulationMREntry,
    IntradayMomentumPriorityEntry.name: IntradayMomentumPriorityEntry,
    IntradayPeriodicityPersistenceEntry.name: IntradayPeriodicityPersistenceEntry,
    LateDayIntradayMomentumEntry.name: LateDayIntradayMomentumEntry,
    LeveragedEtfRebalancePressureEntry.name: LeveragedEtfRebalancePressureEntry,
    LiquidityRiskCapacityPriorityEntry.name: LiquidityRiskCapacityPriorityEntry,
    MarketPlumbingPriorityEntry.name: MarketPlumbingPriorityEntry,
    MesParticipationCrowdingEntry.name: MesParticipationCrowdingEntry,
    MonthlyOpexPressureEntry.name: MonthlyOpexPressureEntry,
    MorningIntradayMomentumEntry.name: MorningIntradayMomentumEntry,
    MorningOrderflowMomentumEntry.name: MorningOrderflowMomentumEntry,
    NaaimExposureSentimentEntry.name: NaaimExposureSentimentEntry,
    OpeningRangeBreakoutEntry.name: OpeningRangeBreakoutEntry,
    OpeningGapOrderflowFadeEntry.name: OpeningGapOrderflowFadeEntry,
    OpeningDriveInventoryComboEntry.name: OpeningDriveInventoryComboEntry,
    OfrFinancialStressEntry.name: OfrFinancialStressEntry,
    OilPriceShockSpilloverEntry.name: OilPriceShockSpilloverEntry,
    OpeningRangeFilteredBreakoutEntry.name: OpeningRangeFilteredBreakoutEntry,
    OpeningRangeInverseBreakoutEntry.name: OpeningRangeInverseBreakoutEntry,
    OpeningRangeOrderflowBreakoutEntry.name: OpeningRangeOrderflowBreakoutEntry,
    OrderflowRegimeEntry.name: OrderflowRegimeEntry,
    OrderflowRecentPocketComboEntry.name: OrderflowRecentPocketComboEntry,
    OvernightReturnLateDayMomentumEntry.name: OvernightReturnLateDayMomentumEntry,
    OvernightIntradayReversalEntry.name: OvernightIntradayReversalEntry,
    OvernightInventoryReversionEntry.name: OvernightInventoryReversionEntry,
    PdhPdlBreakoutContinuationEntry.name: PdhPdlBreakoutContinuationEntry,
    PdhPdlSweepReclaimEntry.name: PdhPdlSweepReclaimEntry,
    PositiveDeltaDislocationEntry.name: PositiveDeltaDislocationEntry,
    PreholidayEffectEntry.name: PreholidayEffectEntry,
    PriorSessionIbsReversionEntry.name: PriorSessionIbsReversionEntry,
    QuarterlyExpirationPressureEntry.name: QuarterlyExpirationPressureEntry,
    QuoteLiquiditySweepReversionEntry.name: QuoteLiquiditySweepReversionEntry,
    RangeCompressionBreakoutEntry.name: RangeCompressionBreakoutEntry,
    RealizedJumpVariationPremiumEntry.name: RealizedJumpVariationPremiumEntry,
    RealizedSemivarianceAsymmetryEntry.name: RealizedSemivarianceAsymmetryEntry,
    RealizedSkewnessReversalEntry.name: RealizedSkewnessReversalEntry,
    RealizedVolOfVolStateEntry.name: RealizedVolOfVolStateEntry,
    RoundNumberBarrierEntry.name: RoundNumberBarrierEntry,
    RthGapFadeEntry.name: RthGapFadeEntry,
    SectorDispersionStateEntry.name: SectorDispersionStateEntry,
    SectorRotationRiskAppetiteEntry.name: SectorRotationRiskAppetiteEntry,
    Spx0dteExpirationPressureEntry.name: Spx0dteExpirationPressureEntry,
    Spx0dteTrendAlignedPressureEntry.name: Spx0dteTrendAlignedPressureEntry,
    TurnOfMonthBiasEntry.name: TurnOfMonthBiasEntry,
    TradeOrderflowMultiPressureEntry.name: TradeOrderflowMultiPressureEntry,
    TradeOrderflowMultiStateRankEntry.name: TradeOrderflowMultiStateRankEntry,
    TradeOrderflowPressureEntry.name: TradeOrderflowPressureEntry,
    TradeOrderflowStateRankEntry.name: TradeOrderflowStateRankEntry,
    TradeFragmentationLiquidityReversionEntry.name: TradeFragmentationLiquidityReversionEntry,
    TradeSizeSegmentOrderflowEntry.name: TradeSizeSegmentOrderflowEntry,
    TreasuryAuctionPressureEntry.name: TreasuryAuctionPressureEntry,
    TreasuryRateStateEntry.name: TreasuryRateStateEntry,
    TurnOfYearEffectEntry.name: TurnOfYearEffectEntry,
    UsdJpySafeHavenEntry.name: UsdJpySafeHavenEntry,
    VarianceRiskPremiumIntradayEntry.name: VarianceRiskPremiumIntradayEntry,
    VixExpirationPressureEntry.name: VixExpirationPressureEntry,
    VolatilityManagedIntradayPremiumEntry.name: VolatilityManagedIntradayPremiumEntry,
    VolumeConditionedLiquidityReversalEntry.name: VolumeConditionedLiquidityReversalEntry,
    VpinToxicityContinuationEntry.name: VpinToxicityContinuationEntry,
    VvixTailRiskEntry.name: VvixTailRiskEntry,
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
    "AqrBabFactorStateEntry",
    "AmihudIlliquidityStateEntry",
    "BankruptcyDistressReversionEntry",
    "BlsMacroReleaseDayDriftEntry",
    "CalendarSessionBiasEntry",
    "CftcTffHedgingPressureEntry",
    "CftcTffTieredHedgingPressureEntry",
    "CboePutCallSentimentEntry",
    "CboeImpliedCorrelationEntry",
    "CboeSkewTailRiskEntry",
    "CboeVixTermStructureEntry",
    "CboeVxnVixDispersionEntry",
    "ChicagoFedCfnaiActivityStateEntry",
    "ConsumerSentimentStateEntry",
    "ConnorsRsi2MeanReversionEntry",
    "DailyTimeSeriesMomentumEntry",
    "DailyShortTermReversalEntry",
    "DollarRiskAppetiteEntry",
    "EpuPolicyUncertaintyEntry",
    "EsNqLeadLagEntry",
    "EsNqRelativeValueReversionEntry",
    "EsTermStructureLeadLagEntry",
    "FomcPreAnnouncementDriftEntry",
    "GaoLastHalfHourOrderflowEntry",
    "HalloweenSeasonalPremiumEntry",
    "IntradayCapitulationMREntry",
    "IntradayMomentumPriorityEntry",
    "LateDayIntradayMomentumEntry",
    "LeveragedEtfRebalancePressureEntry",
    "LiquidityRiskCapacityPriorityEntry",
    "MarketPlumbingPriorityEntry",
    "MesParticipationCrowdingEntry",
    "MonthlyOpexPressureEntry",
    "MorningIntradayMomentumEntry",
    "MorningOrderflowMomentumEntry",
    "NaaimExposureSentimentEntry",
    "OpeningRangeBreakoutEntry",
    "OpeningGapOrderflowFadeEntry",
    "OpeningDriveInventoryComboEntry",
    "OpeningRangeFilteredBreakoutEntry",
    "OpeningRangeInverseBreakoutEntry",
    "OilPriceShockSpilloverEntry",
    "OrderflowRegimeEntry",
    "OrderflowRecentPocketComboEntry",
    "OfrFinancialStressEntry",
    "OvernightReturnLateDayMomentumEntry",
    "OvernightIntradayReversalEntry",
    "OvernightInventoryReversionEntry",
    "PdhPdlBreakoutContinuationEntry",
    "PdhPdlSweepReclaimEntry",
    "PositiveDeltaDislocationEntry",
    "PreholidayEffectEntry",
    "PriorSessionIbsReversionEntry",
    "QuarterlyExpirationPressureEntry",
    "QuoteLiquiditySweepReversionEntry",
    "RangeCompressionBreakoutEntry",
    "RealizedJumpVariationPremiumEntry",
    "RealizedSemivarianceAsymmetryEntry",
    "RealizedSkewnessReversalEntry",
    "RealizedVolOfVolStateEntry",
    "RoundNumberBarrierEntry",
    "RthGapFadeEntry",
    "SectorDispersionStateEntry",
    "SectorRotationRiskAppetiteEntry",
    "Spx0dteExpirationPressureEntry",
    "Spx0dteTrendAlignedPressureEntry",
    "TurnOfMonthBiasEntry",
    "TradeOrderflowMultiPressureEntry",
    "TradeOrderflowMultiStateRankEntry",
    "TradeOrderflowPressureEntry",
    "TradeOrderflowStateRankEntry",
    "TradeFragmentationLiquidityReversionEntry",
    "TradeSizeSegmentOrderflowEntry",
    "TreasuryAuctionPressureEntry",
    "TreasuryRateStateEntry",
    "TurnOfYearEffectEntry",
    "UsdJpySafeHavenEntry",
    "VarianceRiskPremiumIntradayEntry",
    "VixExpirationPressureEntry",
    "VolatilityManagedIntradayPremiumEntry",
    "VolumeConditionedLiquidityReversalEntry",
    "VpinToxicityContinuationEntry",
    "VvixTailRiskEntry",
    "VwapPullbackContinuationEntry",
    "build_entry_module",
]
