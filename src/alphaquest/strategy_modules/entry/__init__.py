from __future__ import annotations

from alphaquest.strategy_modules.metadata import StrategyModuleMetadata, metadata_from_module_class
from alphaquest.strategy_modules.entry.aqr_bab_factor_state import AqrBabFactorStateEntry
from alphaquest.strategy_modules.entry.aoi_vap_acceptance_retest import AoiVapAcceptanceRetestEntry
from alphaquest.strategy_modules.entry.bankruptcy_distress_reversion import BankruptcyDistressReversionEntry
from alphaquest.strategy_modules.entry.amihud_illiquidity_state import AmihudIlliquidityStateEntry
from alphaquest.strategy_modules.entry.ai_gpr_geopolitical_risk_state import (
    AiGprGeopoliticalRiskStateEntry,
)
from alphaquest.strategy_modules.entry.bls_macro_release_day_drift import BlsMacroReleaseDayDriftEntry
from alphaquest.strategy_modules.entry.calendar_session_bias import CalendarSessionBiasEntry
from alphaquest.strategy_modules.entry.safe_bar_rule import SafeBarRuleEntry
from alphaquest.strategy_modules.entry.cftc_tff_hedging_pressure import CftcTffHedgingPressureEntry
from alphaquest.strategy_modules.entry.cftc_tff_tiered_hedging_pressure import CftcTffTieredHedgingPressureEntry
from alphaquest.strategy_modules.entry.cboe_put_call_sentiment import CboePutCallSentimentEntry
from alphaquest.strategy_modules.entry.cboe_put_call_orderflow_confirmation import (
    CboePutCallOrderflowConfirmationEntry,
)
from alphaquest.strategy_modules.entry.cboe_implied_correlation import CboeImpliedCorrelationEntry
from alphaquest.strategy_modules.entry.cboe_implied_correlation_orderflow_confirmation import (
    CboeImpliedCorrelationOrderflowConfirmationEntry,
)
from alphaquest.strategy_modules.entry.cboe_skew_tail_risk import CboeSkewTailRiskEntry
from alphaquest.strategy_modules.entry.cboe_vix_level_state import CboeVixLevelStateEntry
from alphaquest.strategy_modules.entry.cboe_vix_orderflow_confirmation import (
    CboeVixOrderflowConfirmationEntry,
)
from alphaquest.strategy_modules.entry.cboe_vix_term_structure import CboeVixTermStructureEntry
from alphaquest.strategy_modules.entry.cboe_vxn_vix_dispersion import CboeVxnVixDispersionEntry
from alphaquest.strategy_modules.entry.chicagofed_cfnai_activity_state import (
    ChicagoFedCfnaiActivityStateEntry,
)
from alphaquest.strategy_modules.entry.consumer_sentiment_state import ConsumerSentimentStateEntry
from alphaquest.strategy_modules.entry.connors_rsi2_mean_reversion import ConnorsRsi2MeanReversionEntry
from alphaquest.strategy_modules.entry.corporate_equity_supply_state import (
    CorporateEquitySupplyStateEntry,
)
from alphaquest.strategy_modules.entry.credit_spread_state import CreditSpreadStateEntry
from alphaquest.strategy_modules.entry.credit_etf_orderflow_state import CreditEtfOrderflowStateEntry
from alphaquest.strategy_modules.entry.daily_time_series_momentum import DailyTimeSeriesMomentumEntry
from alphaquest.strategy_modules.entry.daily_bollinger_environment import DailyBollingerEnvironmentEntry
from alphaquest.strategy_modules.entry.fifty_two_week_anchor_momentum import FiftyTwoWeekAnchorMomentumEntry
from alphaquest.strategy_modules.entry.fama_french_style_factor_state import (
    FamaFrenchStyleFactorStateEntry,
)
from alphaquest.strategy_modules.entry.weekly_stage_analysis import WeeklyStageAnalysisEntry
from alphaquest.strategy_modules.entry.default_spread_orderflow_state import (
    DefaultSpreadOrderflowStateEntry,
)
from alphaquest.strategy_modules.entry.daily_short_term_reversal import DailyShortTermReversalEntry
from alphaquest.strategy_modules.entry.daily_reversal_orderflow_confirmation import (
    DailyReversalOrderflowConfirmationEntry,
)
from alphaquest.strategy_modules.entry.turnaround_tuesday_reversal import TurnaroundTuesdayReversalEntry
from alphaquest.strategy_modules.entry.dollar_risk_appetite import DollarRiskAppetiteEntry
from alphaquest.strategy_modules.entry.emv_macro_news_state import EmvMacroNewsStateEntry
from alphaquest.strategy_modules.entry.epu_policy_uncertainty import EpuPolicyUncertaintyEntry
from alphaquest.strategy_modules.entry.ema_pullback_orderflow_continuation import (
    EmaPullbackOrderflowContinuationEntry,
)
from alphaquest.strategy_modules.entry.es_nq_lead_lag import EsNqLeadLagEntry
from alphaquest.strategy_modules.entry.nq_es_lead_lag import NqEsLeadLagEntry
from alphaquest.strategy_modules.entry.es_mes_aligned_flow_continuation import EsMesAlignedFlowContinuationEntry
from alphaquest.strategy_modules.entry.es_mes_lead_lag import EsMesLeadLagEntry
from alphaquest.strategy_modules.entry.es_nq_relative_value_reversion import EsNqRelativeValueReversionEntry
from alphaquest.strategy_modules.entry.es_nq_relative_value_orderflow_absorption_reversion import (
    EsNqRelativeValueOrderflowAbsorptionReversionEntry,
)
from alphaquest.strategy_modules.entry.nq_es_relative_value_orderflow_absorption_reversion import (
    NqEsRelativeValueOrderflowAbsorptionReversionEntry,
)
from alphaquest.strategy_modules.entry.nq_es_smt_po3_midpoint_reversion import NqEsSmtPo3MidpointReversionEntry
from alphaquest.strategy_modules.entry.nq_nikkei225_close_spillover import (
    NqNikkei225CloseSpilloverEntry,
)
from alphaquest.strategy_modules.entry.nq_tech_relative_strength import NqTechRelativeStrengthEntry
from alphaquest.strategy_modules.entry.nq_tech_relative_orderflow_confirmation import (
    NqTechRelativeOrderflowConfirmationEntry,
)
from alphaquest.strategy_modules.entry.nq_small_cap_relative_rotation import (
    NqSmallCapRelativeRotationEntry,
)
from alphaquest.strategy_modules.entry.nq_nasdaq_equal_weight_concentration import (
    NqNasdaqEqualWeightConcentrationEntry,
)
from alphaquest.strategy_modules.entry.nq_europe_equity_close_spillover import (
    NqEuropeEquityCloseSpilloverEntry,
)
from alphaquest.strategy_modules.entry.nq_btc_crypto_risk_sentiment import (
    NqBtcCryptoRiskSentimentEntry,
)
from alphaquest.strategy_modules.entry.nq_copper_growth_risk_sentiment import (
    NqCopperGrowthRiskSentimentEntry,
)
from alphaquest.strategy_modules.entry.nq_semiconductor_leadership import (
    NqSemiconductorLeadershipEntry,
)
from alphaquest.strategy_modules.entry.nq_taiwan_semiconductor_spillover import (
    NqTaiwanSemiconductorSpilloverEntry,
)
from alphaquest.strategy_modules.entry.nq_china_tech_risk_sentiment import (
    NqChinaTechRiskSentimentEntry,
)
from alphaquest.strategy_modules.entry.nq_industrial_production_state import (
    NqIndustrialProductionStateEntry,
)
from alphaquest.strategy_modules.entry.nq_retail_inventory_demand import (
    NqRetailInventoryDemandEntry,
)
from alphaquest.strategy_modules.entry.nq_manufacturing_orders_state import (
    NqManufacturingOrdersStateEntry,
)
from alphaquest.strategy_modules.entry.nq_jobless_claims_state import (
    NqJoblessClaimsStateEntry,
)
from alphaquest.strategy_modules.entry.nq_housing_construction_state import (
    NqHousingConstructionStateEntry,
)
from alphaquest.strategy_modules.entry.nq_inflation_pressure_state import (
    NqInflationPressureStateEntry,
)
from alphaquest.strategy_modules.entry.nq_labor_market_slack_state import (
    NqLaborMarketSlackStateEntry,
)
from alphaquest.strategy_modules.entry.nq_productivity_unit_labor_cost_state import (
    NqProductivityUnitLaborCostStateEntry,
)
from alphaquest.strategy_modules.entry.nq_consumer_credit_state import (
    NqConsumerCreditStateEntry,
)
from alphaquest.strategy_modules.entry.nq_corporate_profitability_state import (
    NqCorporateProfitabilityStateEntry,
)
from alphaquest.strategy_modules.entry.nq_credit_quality_stress_state import (
    NqCreditQualityStressStateEntry,
)
from alphaquest.strategy_modules.entry.nq_bank_credit_supply_state import (
    NqBankCreditSupplyStateEntry,
)
from alphaquest.strategy_modules.entry.nq_sloos_bank_lending_survey_state import (
    NqSloosBankLendingSurveyStateEntry,
)
from alphaquest.strategy_modules.entry.nq_trade_balance_quantity_state import (
    NqTradeBalanceQuantityStateEntry,
)
from alphaquest.strategy_modules.entry.nq_fiscal_deficit_treasury_supply_state import (
    NqFiscalDeficitTreasurySupplyStateEntry,
)
from alphaquest.strategy_modules.entry.es_nq_semivariance_filtered_relative_value_absorption import (
    EsNqSemivarianceFilteredRelativeValueAbsorptionEntry,
)
from alphaquest.strategy_modules.entry.es_term_structure_lead_lag import EsTermStructureLeadLagEntry
from alphaquest.strategy_modules.entry.finra_margin_leverage import FinraMarginLeverageEntry
from alphaquest.strategy_modules.entry.fomc_pre_announcement_drift import FomcPreAnnouncementDriftEntry
from alphaquest.strategy_modules.entry.footprint_absorption_initiation import (
    FootprintAbsorptionInitiationEntry,
)
from alphaquest.strategy_modules.entry.gao_last_half_hour_orderflow import GaoLastHalfHourOrderflowEntry
from alphaquest.strategy_modules.entry.gold_platinum_ratio_state import GoldPlatinumRatioStateEntry
from alphaquest.strategy_modules.entry.halloween_seasonal_premium import HalloweenSeasonalPremiumEntry
from alphaquest.strategy_modules.entry.intraday_capitulation_mr import IntradayCapitulationMREntry
from alphaquest.strategy_modules.entry.impulse_pause_orderflow_continuation import (
    ImpulsePauseOrderflowContinuationEntry,
)
from alphaquest.strategy_modules.entry.import_export_price_pressure import ImportExportPricePressureEntry
from alphaquest.strategy_modules.entry.infectious_disease_emv_state import (
    InfectiousDiseaseEmvStateEntry,
)
from alphaquest.strategy_modules.entry.intraday_momentum_priority import IntradayMomentumPriorityEntry
from alphaquest.strategy_modules.entry.volatility_filtered_intraday_momentum_priority import (
    VolatilityFilteredIntradayMomentumPriorityEntry,
)
from alphaquest.strategy_modules.entry.intraday_periodicity_orderflow_confirmation import (
    IntradayPeriodicityOrderflowConfirmationEntry,
)
from alphaquest.strategy_modules.entry.intraday_periodicity_persistence import IntradayPeriodicityPersistenceEntry
from alphaquest.strategy_modules.entry.intraday_range_orderflow_breakout import IntradayRangeOrderflowBreakoutEntry
from alphaquest.strategy_modules.entry.intraday_invariance_dislocation_reversion import (
    IntradayInvarianceDislocationReversionEntry,
)
from alphaquest.strategy_modules.entry.key_reversal_orderflow_reversal import (
    KeyReversalOrderflowReversalEntry,
)
from alphaquest.strategy_modules.entry.large_record_aoi_reaction import LargeRecordAoiReactionEntry
from alphaquest.strategy_modules.entry.large_record_delayed_aoi_confirmation import (
    LargeRecordDelayedAoiConfirmationEntry,
)
from alphaquest.strategy_modules.entry.late_day_intraday_momentum import LateDayIntradayMomentumEntry
from alphaquest.strategy_modules.entry.leveraged_etf_rebalance_pressure import LeveragedEtfRebalancePressureEntry
from alphaquest.strategy_modules.entry.liquidity_risk_capacity_priority import LiquidityRiskCapacityPriorityEntry
from alphaquest.strategy_modules.entry.liquidity_inversion_fvg import LiquidityInversionFvgEntry
from alphaquest.strategy_modules.entry.london_trident_fvg_continuation import LondonTridentFvgContinuationEntry
from alphaquest.strategy_modules.entry.low_toxicity_aoi_false_breakout import (
    LowToxicityAoiFalseBreakoutEntry,
)
from alphaquest.strategy_modules.entry.market_plumbing_priority import MarketPlumbingPriorityEntry
from alphaquest.strategy_modules.entry.market_structure_filtered_entry import MarketStructureFilteredEntry
from alphaquest.strategy_modules.entry.market_structure_pivot_continuation import (
    MarketStructurePivotContinuationEntry,
)
from alphaquest.strategy_modules.entry.macro_event_amd_distribution import MacroEventAmdDistributionEntry
from alphaquest.strategy_modules.entry.max_daily_return_lottery_reversal import (
    MaxDailyReturnLotteryReversalEntry,
)
from alphaquest.strategy_modules.entry.measured_move_pullback_continuation import (
    MeasuredMovePullbackContinuationEntry,
)
from alphaquest.strategy_modules.entry.mes_participation_crowding import MesParticipationCrowdingEntry
from alphaquest.strategy_modules.entry.mes_crowding_aoi_trap import MesCrowdingAoiTrapEntry
from alphaquest.strategy_modules.entry.mes_trend_aoi_pullback import MesTrendAoiPullbackEntry
from alphaquest.strategy_modules.entry.vol_filtered_mes_trend_aoi_pullback import (
    VolFilteredMesTrendAoiPullbackEntry,
)
from alphaquest.strategy_modules.entry.mes_footprint_liquidity_sweep_reversion import (
    MesFootprintLiquiditySweepReversionEntry,
)
from alphaquest.strategy_modules.entry.trend_filtered_mes_participation_crowding import (
    TrendFilteredMesParticipationCrowdingEntry,
)
from alphaquest.strategy_modules.entry.volatility_filtered_trend_mes_participation_crowding import (
    VolatilityFilteredTrendMesParticipationCrowdingEntry,
)
from alphaquest.strategy_modules.entry.nq_mes_crowding_orderflow_window_confirmation import (
    NqMesCrowdingOrderflowWindowConfirmationEntry,
)
from alphaquest.strategy_modules.entry.nq_pivot_mes_orderflow_confirmation import (
    NqPivotMesOrderflowConfirmationEntry,
)
from alphaquest.strategy_modules.entry.monthly_opex_pressure import MonthlyOpexPressureEntry
from alphaquest.strategy_modules.entry.move_treasury_vol_state import MoveTreasuryVolStateEntry
from alphaquest.strategy_modules.entry.morning_intraday_momentum import MorningIntradayMomentumEntry
from alphaquest.strategy_modules.entry.morning_orderflow_momentum import MorningOrderflowMomentumEntry
from alphaquest.strategy_modules.entry.morning_trend_lunch_reversal_orderflow import (
    MorningTrendLunchReversalOrderflowEntry,
)
from alphaquest.strategy_modules.entry.naaim_exposure_sentiment import NaaimExposureSentimentEntry
from alphaquest.strategy_modules.entry.opening_range_breakout import OpeningRangeBreakoutEntry
from alphaquest.strategy_modules.entry.opening_range_filtered_breakout import OpeningRangeFilteredBreakoutEntry
from alphaquest.strategy_modules.entry.opening_range_failed_breakout_orderflow import (
    OpeningRangeFailedBreakoutOrderflowEntry,
)
from alphaquest.strategy_modules.entry.opening_range_failed_breakout_trend_orderflow import (
    OpeningRangeFailedBreakoutTrendOrderflowEntry,
)
from alphaquest.strategy_modules.entry.opening_range_inverse_breakout import OpeningRangeInverseBreakoutEntry
from alphaquest.strategy_modules.entry.opening_range_orderflow_breakout import OpeningRangeOrderflowBreakoutEntry
from alphaquest.strategy_modules.entry.opening_range_nq_orderflow_breakout import (
    OpeningRangeNqOrderflowBreakoutEntry,
)
from alphaquest.strategy_modules.entry.opening_range_retest_orderflow import OpeningRangeRetestOrderflowEntry
from alphaquest.strategy_modules.entry.opening_range_trend_orderflow_breakout import (
    OpeningRangeTrendOrderflowBreakoutEntry,
)
from alphaquest.strategy_modules.entry.opening_vap_absorption_reaction import (
    OpeningVapAbsorptionReactionEntry,
)
from alphaquest.strategy_modules.entry.opening_vap_large_record_reaction import (
    OpeningVapLargeRecordReactionEntry,
)
from alphaquest.strategy_modules.entry.opening_gap_orderflow_fade import OpeningGapOrderflowFadeEntry
from alphaquest.strategy_modules.entry.opening_gap_orderflow_continuation import (
    OpeningGapOrderflowContinuationEntry,
)
from alphaquest.strategy_modules.entry.opening_drive_inventory_combo import OpeningDriveInventoryComboEntry
from alphaquest.strategy_modules.entry.opening_drive_mes_crowding_reversal import (
    OpeningDriveMesCrowdingReversalEntry,
)
from alphaquest.strategy_modules.entry.ofr_financial_stress import OfrFinancialStressEntry
from alphaquest.strategy_modules.entry.oil_price_shock_spillover import OilPriceShockSpilloverEntry
from alphaquest.strategy_modules.entry.orderflow_regime import OrderflowRegimeEntry
from alphaquest.strategy_modules.entry.orderflow_recent_pocket_combo import OrderflowRecentPocketComboEntry
from alphaquest.strategy_modules.entry.overnight_return_late_day_momentum import OvernightReturnLateDayMomentumEntry
from alphaquest.strategy_modules.entry.overnight_intraday_reversal import OvernightIntradayReversalEntry
from alphaquest.strategy_modules.entry.overnight_drift import OvernightDriftEntry
from alphaquest.strategy_modules.entry.overnight_inventory_reversion import OvernightInventoryReversionEntry
from alphaquest.strategy_modules.entry.overnight_range_orderflow_breakout import (
    OvernightRangeOrderflowBreakoutEntry,
)
from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.pdh_pdl_breakout_continuation import PdhPdlBreakoutContinuationEntry
from alphaquest.strategy_modules.entry.pdh_pdl_orderflow_breakout_continuation import (
    PdhPdlOrderflowBreakoutContinuationEntry,
)
from alphaquest.strategy_modules.entry.pdh_pdl_trend_orderflow_breakout_continuation import (
    PdhPdlTrendOrderflowBreakoutContinuationEntry,
)
from alphaquest.strategy_modules.entry.pdh_pdl_sweep_reclaim import PdhPdlSweepReclaimEntry
from alphaquest.strategy_modules.entry.pdh_pdl_vap_absorption_sweep import (
    PdhPdlVapAbsorptionSweepEntry,
)
from alphaquest.strategy_modules.entry.trend_orderflow_pdh_pdl_sweep_reclaim import (
    TrendOrderflowPdhPdlSweepReclaimEntry,
)
from alphaquest.strategy_modules.entry.positive_delta_dislocation import PositiveDeltaDislocationEntry
from alphaquest.strategy_modules.entry.preholiday_effect import PreholidayEffectEntry
from alphaquest.strategy_modules.entry.profile_aoi_footprint_trap import ProfileAoiFootprintTrapEntry
from alphaquest.strategy_modules.entry.tpo_value_edge_auction_rejection import (
    TpoValueEdgeAuctionRejectionEntry,
)
from alphaquest.strategy_modules.entry.nq_nonconfirming_vap_aoi_trap import (
    NqNonconfirmingVapAoiTrapEntry,
)
from alphaquest.strategy_modules.entry.nq_confirming_vap_aoi_breakout import (
    NqConfirmingVapAoiBreakoutEntry,
)
from alphaquest.strategy_modules.entry.true_vap_aoi_breakout_continuation import (
    TrueVapAoiBreakoutContinuationEntry,
)
from alphaquest.strategy_modules.entry.true_vap_value_area_orderflow_acceptance import (
    TrueVapValueAreaOrderflowAcceptanceEntry,
)
from alphaquest.strategy_modules.entry.video_aoi_orderflow_playbook import (
    VideoAoiOrderflowPlaybookEntry,
)
from alphaquest.strategy_modules.entry.video_exact_orderflow_playbook import (
    VideoExactOrderflowPlaybookEntry,
)
from alphaquest.strategy_modules.entry.video_exact_orderflow_playbook_scid_intrabar import (
    VideoExactOrderflowPlaybookScidIntrabarEntry,
)
from alphaquest.strategy_modules.entry.prior_session_ibs_reversion import PriorSessionIbsReversionEntry
from alphaquest.strategy_modules.entry.prior_session_benchmark_orderflow_reaction import (
    PriorSessionBenchmarkOrderflowReactionEntry,
)
from alphaquest.strategy_modules.entry.prior_lvn_orderflow_rejection import PriorLvnOrderflowRejectionEntry
from alphaquest.strategy_modules.entry.prior_value_area_orderflow_acceptance import (
    PriorValueAreaOrderflowAcceptanceEntry,
)
from alphaquest.strategy_modules.entry.prior_value_area_orderflow_rejection import (
    PriorValueAreaOrderflowRejectionEntry,
)
from alphaquest.strategy_modules.entry.prior_poc_orderflow_magnet import PriorPocOrderflowMagnetEntry
from alphaquest.strategy_modules.entry.price_ending_barrier import PriceEndingBarrierEntry
from alphaquest.strategy_modules.entry.trend_filtered_prior_value_area_acceptance import (
    TrendFilteredPriorValueAreaAcceptanceEntry,
)
from alphaquest.strategy_modules.entry.quarterly_expiration_pressure import QuarterlyExpirationPressureEntry
from alphaquest.strategy_modules.entry.quote_liquidity_sweep_reversion import QuoteLiquiditySweepReversionEntry
from alphaquest.strategy_modules.entry.range_compression_orderflow_breakout import (
    RangeCompressionOrderflowBreakoutEntry,
)
from alphaquest.strategy_modules.entry.range_compression_breakout import RangeCompressionBreakoutEntry
from alphaquest.strategy_modules.entry.realized_jump_variation_premium import RealizedJumpVariationPremiumEntry
from alphaquest.strategy_modules.entry.realized_semivariance_asymmetry import RealizedSemivarianceAsymmetryEntry
from alphaquest.strategy_modules.entry.realized_semivariance_orderflow_confirmation import (
    RealizedSemivarianceOrderflowConfirmationEntry,
)
from alphaquest.strategy_modules.entry.realized_skewness_reversal import RealizedSkewnessReversalEntry
from alphaquest.strategy_modules.entry.real_yield_breakeven_state import RealYieldBreakevenStateEntry
from alphaquest.strategy_modules.entry.realized_vol_of_vol_state import RealizedVolOfVolStateEntry
from alphaquest.strategy_modules.entry.round_number_barrier import RoundNumberBarrierEntry
from alphaquest.strategy_modules.entry.round_number_orderflow_barrier import RoundNumberOrderflowBarrierEntry
from alphaquest.strategy_modules.entry.rolling_range_orderflow_sweep_reversal import (
    RollingRangeOrderflowSweepReversalEntry,
)
from alphaquest.strategy_modules.entry.rolling_stat_envelope_orderflow_reversion import (
    RollingStatEnvelopeOrderflowReversionEntry,
)
from alphaquest.strategy_modules.entry.rth_gap_fade import RthGapFadeEntry
from alphaquest.strategy_modules.entry.session_extreme_delta_divergence import (
    SessionExtremeDeltaDivergenceEntry,
)
from alphaquest.strategy_modules.entry.session_liquidity_fvg_reversal import (
    SessionLiquidityFvgReversalEntry,
)
from alphaquest.strategy_modules.entry.session_open_orderflow_reclaim import SessionOpenOrderflowReclaimEntry
from alphaquest.strategy_modules.entry.semivariance_filtered_trend_mes_participation_crowding import (
    SemivarianceFilteredTrendMesParticipationCrowdingEntry,
)
from alphaquest.strategy_modules.entry.sector_dispersion_state import SectorDispersionStateEntry
from alphaquest.strategy_modules.entry.sector_rotation_orderflow_pullback import (
    SectorRotationOrderflowPullbackEntry,
)
from alphaquest.strategy_modules.entry.sector_opening_breadth_orderflow import (
    SectorOpeningBreadthOrderflowEntry,
)
from alphaquest.strategy_modules.entry.sector_rotation_risk_appetite import SectorRotationRiskAppetiteEntry
from alphaquest.strategy_modules.entry.spx_0dte_expiration_pressure import Spx0dteExpirationPressureEntry
from alphaquest.strategy_modules.entry.spx_0dte_orderflow_continuation import (
    Spx0dteOrderflowContinuationEntry,
)
from alphaquest.strategy_modules.entry.spx_0dte_orderflow_confirmation import (
    Spx0dteOrderflowConfirmationEntry,
)
from alphaquest.strategy_modules.entry.spx_0dte_trend_aligned_pressure import Spx0dteTrendAlignedPressureEntry
from alphaquest.strategy_modules.entry.spy_turnover_orderflow_attention import (
    SpyTurnoverOrderflowAttentionEntry,
)
from alphaquest.strategy_modules.entry.turn_of_month_bias import TurnOfMonthBiasEntry
from alphaquest.strategy_modules.entry.trade_orderflow_multi_pressure import TradeOrderflowMultiPressureEntry
from alphaquest.strategy_modules.entry.trade_orderflow_multi_state_rank import TradeOrderflowMultiStateRankEntry
from alphaquest.strategy_modules.entry.trade_orderflow_pressure import TradeOrderflowPressureEntry
from alphaquest.strategy_modules.entry.trade_orderflow_state_rank import TradeOrderflowStateRankEntry
from alphaquest.strategy_modules.entry.trade_fragmentation_liquidity_reversion import (
    TradeFragmentationLiquidityReversionEntry,
)
from alphaquest.strategy_modules.entry.trade_size_segment_orderflow import TradeSizeSegmentOrderflowEntry
from alphaquest.strategy_modules.entry.trend_aligned_orderflow_continuation import (
    TrendAlignedOrderflowContinuationEntry,
)
from alphaquest.strategy_modules.entry.treasury_auction_pressure import TreasuryAuctionPressureEntry
from alphaquest.strategy_modules.entry.treasury_rate_orderflow_state import TreasuryRateOrderflowStateEntry
from alphaquest.strategy_modules.entry.treasury_rate_state import TreasuryRateStateEntry
from alphaquest.strategy_modules.entry.treasury_term_premium_state import TreasuryTermPremiumStateEntry
from alphaquest.strategy_modules.entry.turn_of_year_effect import TurnOfYearEffectEntry
from alphaquest.strategy_modules.entry.usdjpy_safe_haven import UsdJpySafeHavenEntry
from alphaquest.strategy_modules.entry.variance_risk_premium_intraday import VarianceRiskPremiumIntradayEntry
from alphaquest.strategy_modules.entry.variance_ratio_orderflow_regime import (
    VarianceRatioOrderflowRegimeEntry,
)
from alphaquest.strategy_modules.entry.vix_expiration_pressure import VixExpirationPressureEntry
from alphaquest.strategy_modules.entry.volatility_managed_intraday_premium import (
    VolatilityManagedIntradayPremiumEntry,
)
from alphaquest.strategy_modules.entry.volume_conditioned_liquidity_reversal import (
    VolumeConditionedLiquidityReversalEntry,
)
from alphaquest.strategy_modules.entry.wide_range_orderflow_continuation import (
    WideRangeOrderflowContinuationEntry,
)
from alphaquest.strategy_modules.entry.vpin_toxicity_continuation import VpinToxicityContinuationEntry
from alphaquest.strategy_modules.entry.vvix_tail_risk import VvixTailRiskEntry
from alphaquest.strategy_modules.entry.vwap_orderflow_pullback_continuation import (
    VwapOrderflowPullbackContinuationEntry,
)
from alphaquest.strategy_modules.entry.vwap_deviation_orderflow_reversion import (
    VwapDeviationOrderflowReversionEntry,
)
from alphaquest.strategy_modules.entry.vix_term_structure_orderflow_pullback import (
    VixTermStructureOrderflowPullbackEntry,
)
from alphaquest.strategy_modules.entry.vwap_pullback_continuation import VwapPullbackContinuationEntry


ENTRY_MODULES = {
    AqrBabFactorStateEntry.name: AqrBabFactorStateEntry,
    AiGprGeopoliticalRiskStateEntry.name: AiGprGeopoliticalRiskStateEntry,
    AoiVapAcceptanceRetestEntry.name: AoiVapAcceptanceRetestEntry,
    BankruptcyDistressReversionEntry.name: BankruptcyDistressReversionEntry,
    AmihudIlliquidityStateEntry.name: AmihudIlliquidityStateEntry,
    BlsMacroReleaseDayDriftEntry.name: BlsMacroReleaseDayDriftEntry,
    CalendarSessionBiasEntry.name: CalendarSessionBiasEntry,
    SafeBarRuleEntry.name: SafeBarRuleEntry,
    CftcTffHedgingPressureEntry.name: CftcTffHedgingPressureEntry,
    CftcTffTieredHedgingPressureEntry.name: CftcTffTieredHedgingPressureEntry,
    CboePutCallSentimentEntry.name: CboePutCallSentimentEntry,
    CboePutCallOrderflowConfirmationEntry.name: CboePutCallOrderflowConfirmationEntry,
    CboeImpliedCorrelationEntry.name: CboeImpliedCorrelationEntry,
    CboeImpliedCorrelationOrderflowConfirmationEntry.name: CboeImpliedCorrelationOrderflowConfirmationEntry,
    CboeSkewTailRiskEntry.name: CboeSkewTailRiskEntry,
    CboeVixLevelStateEntry.name: CboeVixLevelStateEntry,
    CboeVixOrderflowConfirmationEntry.name: CboeVixOrderflowConfirmationEntry,
    CboeVixTermStructureEntry.name: CboeVixTermStructureEntry,
    CboeVxnVixDispersionEntry.name: CboeVxnVixDispersionEntry,
    ChicagoFedCfnaiActivityStateEntry.name: ChicagoFedCfnaiActivityStateEntry,
    ConsumerSentimentStateEntry.name: ConsumerSentimentStateEntry,
    ConnorsRsi2MeanReversionEntry.name: ConnorsRsi2MeanReversionEntry,
    CorporateEquitySupplyStateEntry.name: CorporateEquitySupplyStateEntry,
    CreditSpreadStateEntry.name: CreditSpreadStateEntry,
    CreditEtfOrderflowStateEntry.name: CreditEtfOrderflowStateEntry,
    DailyTimeSeriesMomentumEntry.name: DailyTimeSeriesMomentumEntry,
    DailyBollingerEnvironmentEntry.name: DailyBollingerEnvironmentEntry,
    FiftyTwoWeekAnchorMomentumEntry.name: FiftyTwoWeekAnchorMomentumEntry,
    FamaFrenchStyleFactorStateEntry.name: FamaFrenchStyleFactorStateEntry,
    WeeklyStageAnalysisEntry.name: WeeklyStageAnalysisEntry,
    DefaultSpreadOrderflowStateEntry.name: DefaultSpreadOrderflowStateEntry,
    DailyShortTermReversalEntry.name: DailyShortTermReversalEntry,
    DailyReversalOrderflowConfirmationEntry.name: DailyReversalOrderflowConfirmationEntry,
    TurnaroundTuesdayReversalEntry.name: TurnaroundTuesdayReversalEntry,
    DollarRiskAppetiteEntry.name: DollarRiskAppetiteEntry,
    EmaPullbackOrderflowContinuationEntry.name: EmaPullbackOrderflowContinuationEntry,
    EmvMacroNewsStateEntry.name: EmvMacroNewsStateEntry,
    EpuPolicyUncertaintyEntry.name: EpuPolicyUncertaintyEntry,
    EsMesAlignedFlowContinuationEntry.name: EsMesAlignedFlowContinuationEntry,
    EsMesLeadLagEntry.name: EsMesLeadLagEntry,
    EsNqLeadLagEntry.name: EsNqLeadLagEntry,
    NqEsLeadLagEntry.name: NqEsLeadLagEntry,
    EsNqRelativeValueReversionEntry.name: EsNqRelativeValueReversionEntry,
    EsNqRelativeValueOrderflowAbsorptionReversionEntry.name: EsNqRelativeValueOrderflowAbsorptionReversionEntry,
    NqEsRelativeValueOrderflowAbsorptionReversionEntry.name: NqEsRelativeValueOrderflowAbsorptionReversionEntry,
    NqEsSmtPo3MidpointReversionEntry.name: NqEsSmtPo3MidpointReversionEntry,
    NqNikkei225CloseSpilloverEntry.name: NqNikkei225CloseSpilloverEntry,
    NqTechRelativeStrengthEntry.name: NqTechRelativeStrengthEntry,
    NqTechRelativeOrderflowConfirmationEntry.name: NqTechRelativeOrderflowConfirmationEntry,
    NqSmallCapRelativeRotationEntry.name: NqSmallCapRelativeRotationEntry,
    NqNasdaqEqualWeightConcentrationEntry.name: NqNasdaqEqualWeightConcentrationEntry,
    NqEuropeEquityCloseSpilloverEntry.name: NqEuropeEquityCloseSpilloverEntry,
    NqBtcCryptoRiskSentimentEntry.name: NqBtcCryptoRiskSentimentEntry,
    NqCopperGrowthRiskSentimentEntry.name: NqCopperGrowthRiskSentimentEntry,
    NqSemiconductorLeadershipEntry.name: NqSemiconductorLeadershipEntry,
    NqTaiwanSemiconductorSpilloverEntry.name: NqTaiwanSemiconductorSpilloverEntry,
    NqChinaTechRiskSentimentEntry.name: NqChinaTechRiskSentimentEntry,
    NqIndustrialProductionStateEntry.name: NqIndustrialProductionStateEntry,
    NqRetailInventoryDemandEntry.name: NqRetailInventoryDemandEntry,
    NqManufacturingOrdersStateEntry.name: NqManufacturingOrdersStateEntry,
    NqJoblessClaimsStateEntry.name: NqJoblessClaimsStateEntry,
    NqHousingConstructionStateEntry.name: NqHousingConstructionStateEntry,
    NqInflationPressureStateEntry.name: NqInflationPressureStateEntry,
    NqLaborMarketSlackStateEntry.name: NqLaborMarketSlackStateEntry,
    NqProductivityUnitLaborCostStateEntry.name: NqProductivityUnitLaborCostStateEntry,
    NqConsumerCreditStateEntry.name: NqConsumerCreditStateEntry,
    NqCorporateProfitabilityStateEntry.name: NqCorporateProfitabilityStateEntry,
    NqCreditQualityStressStateEntry.name: NqCreditQualityStressStateEntry,
    NqBankCreditSupplyStateEntry.name: NqBankCreditSupplyStateEntry,
    NqSloosBankLendingSurveyStateEntry.name: NqSloosBankLendingSurveyStateEntry,
    NqTradeBalanceQuantityStateEntry.name: NqTradeBalanceQuantityStateEntry,
    NqFiscalDeficitTreasurySupplyStateEntry.name: NqFiscalDeficitTreasurySupplyStateEntry,
    EsNqSemivarianceFilteredRelativeValueAbsorptionEntry.name: EsNqSemivarianceFilteredRelativeValueAbsorptionEntry,
    EsTermStructureLeadLagEntry.name: EsTermStructureLeadLagEntry,
    FinraMarginLeverageEntry.name: FinraMarginLeverageEntry,
    FomcPreAnnouncementDriftEntry.name: FomcPreAnnouncementDriftEntry,
    FootprintAbsorptionInitiationEntry.name: FootprintAbsorptionInitiationEntry,
    GaoLastHalfHourOrderflowEntry.name: GaoLastHalfHourOrderflowEntry,
    GoldPlatinumRatioStateEntry.name: GoldPlatinumRatioStateEntry,
    HalloweenSeasonalPremiumEntry.name: HalloweenSeasonalPremiumEntry,
    ImpulsePauseOrderflowContinuationEntry.name: ImpulsePauseOrderflowContinuationEntry,
    ImportExportPricePressureEntry.name: ImportExportPricePressureEntry,
    InfectiousDiseaseEmvStateEntry.name: InfectiousDiseaseEmvStateEntry,
    IntradayCapitulationMREntry.name: IntradayCapitulationMREntry,
    IntradayMomentumPriorityEntry.name: IntradayMomentumPriorityEntry,
    VolatilityFilteredIntradayMomentumPriorityEntry.name: VolatilityFilteredIntradayMomentumPriorityEntry,
    IntradayPeriodicityOrderflowConfirmationEntry.name: IntradayPeriodicityOrderflowConfirmationEntry,
    IntradayRangeOrderflowBreakoutEntry.name: IntradayRangeOrderflowBreakoutEntry,
    IntradayInvarianceDislocationReversionEntry.name: IntradayInvarianceDislocationReversionEntry,
    IntradayPeriodicityPersistenceEntry.name: IntradayPeriodicityPersistenceEntry,
    KeyReversalOrderflowReversalEntry.name: KeyReversalOrderflowReversalEntry,
    LargeRecordAoiReactionEntry.name: LargeRecordAoiReactionEntry,
    LargeRecordDelayedAoiConfirmationEntry.name: LargeRecordDelayedAoiConfirmationEntry,
    LateDayIntradayMomentumEntry.name: LateDayIntradayMomentumEntry,
    LeveragedEtfRebalancePressureEntry.name: LeveragedEtfRebalancePressureEntry,
    LiquidityRiskCapacityPriorityEntry.name: LiquidityRiskCapacityPriorityEntry,
    LiquidityInversionFvgEntry.name: LiquidityInversionFvgEntry,
    LondonTridentFvgContinuationEntry.name: LondonTridentFvgContinuationEntry,
    LowToxicityAoiFalseBreakoutEntry.name: LowToxicityAoiFalseBreakoutEntry,
    MacroEventAmdDistributionEntry.name: MacroEventAmdDistributionEntry,
    MarketPlumbingPriorityEntry.name: MarketPlumbingPriorityEntry,
    MarketStructureFilteredEntry.name: MarketStructureFilteredEntry,
    MarketStructurePivotContinuationEntry.name: MarketStructurePivotContinuationEntry,
    MaxDailyReturnLotteryReversalEntry.name: MaxDailyReturnLotteryReversalEntry,
    MeasuredMovePullbackContinuationEntry.name: MeasuredMovePullbackContinuationEntry,
    MesCrowdingAoiTrapEntry.name: MesCrowdingAoiTrapEntry,
    MesTrendAoiPullbackEntry.name: MesTrendAoiPullbackEntry,
    VolFilteredMesTrendAoiPullbackEntry.name: VolFilteredMesTrendAoiPullbackEntry,
    MesParticipationCrowdingEntry.name: MesParticipationCrowdingEntry,
    MesFootprintLiquiditySweepReversionEntry.name: MesFootprintLiquiditySweepReversionEntry,
    TrendFilteredMesParticipationCrowdingEntry.name: TrendFilteredMesParticipationCrowdingEntry,
    VolatilityFilteredTrendMesParticipationCrowdingEntry.name: VolatilityFilteredTrendMesParticipationCrowdingEntry,
    NqMesCrowdingOrderflowWindowConfirmationEntry.name: NqMesCrowdingOrderflowWindowConfirmationEntry,
    NqPivotMesOrderflowConfirmationEntry.name: NqPivotMesOrderflowConfirmationEntry,
    MonthlyOpexPressureEntry.name: MonthlyOpexPressureEntry,
    MoveTreasuryVolStateEntry.name: MoveTreasuryVolStateEntry,
    MorningIntradayMomentumEntry.name: MorningIntradayMomentumEntry,
    MorningOrderflowMomentumEntry.name: MorningOrderflowMomentumEntry,
    MorningTrendLunchReversalOrderflowEntry.name: MorningTrendLunchReversalOrderflowEntry,
    NaaimExposureSentimentEntry.name: NaaimExposureSentimentEntry,
    OpeningRangeBreakoutEntry.name: OpeningRangeBreakoutEntry,
    OpeningGapOrderflowFadeEntry.name: OpeningGapOrderflowFadeEntry,
    OpeningGapOrderflowContinuationEntry.name: OpeningGapOrderflowContinuationEntry,
    OpeningDriveInventoryComboEntry.name: OpeningDriveInventoryComboEntry,
    OpeningDriveMesCrowdingReversalEntry.name: OpeningDriveMesCrowdingReversalEntry,
    OfrFinancialStressEntry.name: OfrFinancialStressEntry,
    OilPriceShockSpilloverEntry.name: OilPriceShockSpilloverEntry,
    OpeningRangeFilteredBreakoutEntry.name: OpeningRangeFilteredBreakoutEntry,
    OpeningRangeFailedBreakoutOrderflowEntry.name: OpeningRangeFailedBreakoutOrderflowEntry,
    OpeningRangeFailedBreakoutTrendOrderflowEntry.name: OpeningRangeFailedBreakoutTrendOrderflowEntry,
    OpeningRangeInverseBreakoutEntry.name: OpeningRangeInverseBreakoutEntry,
    OpeningRangeOrderflowBreakoutEntry.name: OpeningRangeOrderflowBreakoutEntry,
    OpeningRangeNqOrderflowBreakoutEntry.name: OpeningRangeNqOrderflowBreakoutEntry,
    OpeningRangeRetestOrderflowEntry.name: OpeningRangeRetestOrderflowEntry,
    OpeningRangeTrendOrderflowBreakoutEntry.name: OpeningRangeTrendOrderflowBreakoutEntry,
    OpeningVapAbsorptionReactionEntry.name: OpeningVapAbsorptionReactionEntry,
    OpeningVapLargeRecordReactionEntry.name: OpeningVapLargeRecordReactionEntry,
    OrderflowRegimeEntry.name: OrderflowRegimeEntry,
    OrderflowRecentPocketComboEntry.name: OrderflowRecentPocketComboEntry,
    OvernightReturnLateDayMomentumEntry.name: OvernightReturnLateDayMomentumEntry,
    OvernightIntradayReversalEntry.name: OvernightIntradayReversalEntry,
    OvernightDriftEntry.name: OvernightDriftEntry,
    OvernightInventoryReversionEntry.name: OvernightInventoryReversionEntry,
    OvernightRangeOrderflowBreakoutEntry.name: OvernightRangeOrderflowBreakoutEntry,
    PdhPdlBreakoutContinuationEntry.name: PdhPdlBreakoutContinuationEntry,
    PdhPdlOrderflowBreakoutContinuationEntry.name: PdhPdlOrderflowBreakoutContinuationEntry,
    PdhPdlTrendOrderflowBreakoutContinuationEntry.name: PdhPdlTrendOrderflowBreakoutContinuationEntry,
    PdhPdlSweepReclaimEntry.name: PdhPdlSweepReclaimEntry,
    PdhPdlVapAbsorptionSweepEntry.name: PdhPdlVapAbsorptionSweepEntry,
    TrendOrderflowPdhPdlSweepReclaimEntry.name: TrendOrderflowPdhPdlSweepReclaimEntry,
    PositiveDeltaDislocationEntry.name: PositiveDeltaDislocationEntry,
    PreholidayEffectEntry.name: PreholidayEffectEntry,
    ProfileAoiFootprintTrapEntry.name: ProfileAoiFootprintTrapEntry,
    TpoValueEdgeAuctionRejectionEntry.name: TpoValueEdgeAuctionRejectionEntry,
    NqNonconfirmingVapAoiTrapEntry.name: NqNonconfirmingVapAoiTrapEntry,
    NqConfirmingVapAoiBreakoutEntry.name: NqConfirmingVapAoiBreakoutEntry,
    TrueVapAoiBreakoutContinuationEntry.name: TrueVapAoiBreakoutContinuationEntry,
    TrueVapValueAreaOrderflowAcceptanceEntry.name: TrueVapValueAreaOrderflowAcceptanceEntry,
    VideoAoiOrderflowPlaybookEntry.name: VideoAoiOrderflowPlaybookEntry,
    VideoExactOrderflowPlaybookEntry.name: VideoExactOrderflowPlaybookEntry,
    VideoExactOrderflowPlaybookScidIntrabarEntry.name: VideoExactOrderflowPlaybookScidIntrabarEntry,
    PriorSessionBenchmarkOrderflowReactionEntry.name: PriorSessionBenchmarkOrderflowReactionEntry,
    PriorSessionIbsReversionEntry.name: PriorSessionIbsReversionEntry,
    PriorLvnOrderflowRejectionEntry.name: PriorLvnOrderflowRejectionEntry,
    PriorPocOrderflowMagnetEntry.name: PriorPocOrderflowMagnetEntry,
    PriceEndingBarrierEntry.name: PriceEndingBarrierEntry,
    PriorValueAreaOrderflowAcceptanceEntry.name: PriorValueAreaOrderflowAcceptanceEntry,
    PriorValueAreaOrderflowRejectionEntry.name: PriorValueAreaOrderflowRejectionEntry,
    TrendFilteredPriorValueAreaAcceptanceEntry.name: TrendFilteredPriorValueAreaAcceptanceEntry,
    QuarterlyExpirationPressureEntry.name: QuarterlyExpirationPressureEntry,
    QuoteLiquiditySweepReversionEntry.name: QuoteLiquiditySweepReversionEntry,
    RangeCompressionOrderflowBreakoutEntry.name: RangeCompressionOrderflowBreakoutEntry,
    RangeCompressionBreakoutEntry.name: RangeCompressionBreakoutEntry,
    RealizedJumpVariationPremiumEntry.name: RealizedJumpVariationPremiumEntry,
    RealizedSemivarianceAsymmetryEntry.name: RealizedSemivarianceAsymmetryEntry,
    RealizedSemivarianceOrderflowConfirmationEntry.name: RealizedSemivarianceOrderflowConfirmationEntry,
    RealizedSkewnessReversalEntry.name: RealizedSkewnessReversalEntry,
    RealYieldBreakevenStateEntry.name: RealYieldBreakevenStateEntry,
    RealizedVolOfVolStateEntry.name: RealizedVolOfVolStateEntry,
    RoundNumberBarrierEntry.name: RoundNumberBarrierEntry,
    RoundNumberOrderflowBarrierEntry.name: RoundNumberOrderflowBarrierEntry,
    RollingRangeOrderflowSweepReversalEntry.name: RollingRangeOrderflowSweepReversalEntry,
    RollingStatEnvelopeOrderflowReversionEntry.name: RollingStatEnvelopeOrderflowReversionEntry,
    RthGapFadeEntry.name: RthGapFadeEntry,
    SessionExtremeDeltaDivergenceEntry.name: SessionExtremeDeltaDivergenceEntry,
    SessionLiquidityFvgReversalEntry.name: SessionLiquidityFvgReversalEntry,
    SessionOpenOrderflowReclaimEntry.name: SessionOpenOrderflowReclaimEntry,
    SemivarianceFilteredTrendMesParticipationCrowdingEntry.name: SemivarianceFilteredTrendMesParticipationCrowdingEntry,
    SectorDispersionStateEntry.name: SectorDispersionStateEntry,
    SectorOpeningBreadthOrderflowEntry.name: SectorOpeningBreadthOrderflowEntry,
    SectorRotationOrderflowPullbackEntry.name: SectorRotationOrderflowPullbackEntry,
    SectorRotationRiskAppetiteEntry.name: SectorRotationRiskAppetiteEntry,
    Spx0dteExpirationPressureEntry.name: Spx0dteExpirationPressureEntry,
    Spx0dteOrderflowContinuationEntry.name: Spx0dteOrderflowContinuationEntry,
    Spx0dteOrderflowConfirmationEntry.name: Spx0dteOrderflowConfirmationEntry,
    Spx0dteTrendAlignedPressureEntry.name: Spx0dteTrendAlignedPressureEntry,
    SpyTurnoverOrderflowAttentionEntry.name: SpyTurnoverOrderflowAttentionEntry,
    TurnOfMonthBiasEntry.name: TurnOfMonthBiasEntry,
    TradeOrderflowMultiPressureEntry.name: TradeOrderflowMultiPressureEntry,
    TradeOrderflowMultiStateRankEntry.name: TradeOrderflowMultiStateRankEntry,
    TradeOrderflowPressureEntry.name: TradeOrderflowPressureEntry,
    TradeOrderflowStateRankEntry.name: TradeOrderflowStateRankEntry,
    TradeFragmentationLiquidityReversionEntry.name: TradeFragmentationLiquidityReversionEntry,
    TradeSizeSegmentOrderflowEntry.name: TradeSizeSegmentOrderflowEntry,
    TrendAlignedOrderflowContinuationEntry.name: TrendAlignedOrderflowContinuationEntry,
    TreasuryAuctionPressureEntry.name: TreasuryAuctionPressureEntry,
    TreasuryRateOrderflowStateEntry.name: TreasuryRateOrderflowStateEntry,
    TreasuryRateStateEntry.name: TreasuryRateStateEntry,
    TreasuryTermPremiumStateEntry.name: TreasuryTermPremiumStateEntry,
    TurnOfYearEffectEntry.name: TurnOfYearEffectEntry,
    UsdJpySafeHavenEntry.name: UsdJpySafeHavenEntry,
    VarianceRiskPremiumIntradayEntry.name: VarianceRiskPremiumIntradayEntry,
    VarianceRatioOrderflowRegimeEntry.name: VarianceRatioOrderflowRegimeEntry,
    VixExpirationPressureEntry.name: VixExpirationPressureEntry,
    VolatilityManagedIntradayPremiumEntry.name: VolatilityManagedIntradayPremiumEntry,
    VolumeConditionedLiquidityReversalEntry.name: VolumeConditionedLiquidityReversalEntry,
    WideRangeOrderflowContinuationEntry.name: WideRangeOrderflowContinuationEntry,
    VpinToxicityContinuationEntry.name: VpinToxicityContinuationEntry,
    VvixTailRiskEntry.name: VvixTailRiskEntry,
    VwapOrderflowPullbackContinuationEntry.name: VwapOrderflowPullbackContinuationEntry,
    VwapDeviationOrderflowReversionEntry.name: VwapDeviationOrderflowReversionEntry,
    VixTermStructureOrderflowPullbackEntry.name: VixTermStructureOrderflowPullbackEntry,
    VwapPullbackContinuationEntry.name: VwapPullbackContinuationEntry,
}


def build_entry_module(config: dict):
    name = config.get("module", PdhPdlSweepReclaimEntry.name)
    params = config.get("params", {})
    try:
        return ENTRY_MODULES[name](params)
    except KeyError as exc:
        raise ValueError(f"Unknown entry module: {name}") from exc


def entry_module_metadata(name: str) -> StrategyModuleMetadata:
    try:
        module_cls = ENTRY_MODULES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown entry module: {name}") from exc
    return metadata_from_module_class("entry", module_cls)


def all_entry_module_metadata() -> dict[str, StrategyModuleMetadata]:
    return {name: metadata_from_module_class("entry", module_cls) for name, module_cls in ENTRY_MODULES.items()}


__all__ = [
    "Signal",
    "AqrBabFactorStateEntry",
    "AiGprGeopoliticalRiskStateEntry",
    "AoiVapAcceptanceRetestEntry",
    "AmihudIlliquidityStateEntry",
    "BankruptcyDistressReversionEntry",
    "BlsMacroReleaseDayDriftEntry",
    "CalendarSessionBiasEntry",
    "SafeBarRuleEntry",
    "CftcTffHedgingPressureEntry",
    "CftcTffTieredHedgingPressureEntry",
    "CboePutCallSentimentEntry",
    "CboePutCallOrderflowConfirmationEntry",
    "CboeImpliedCorrelationEntry",
    "CboeImpliedCorrelationOrderflowConfirmationEntry",
    "CboeSkewTailRiskEntry",
    "CboeVixOrderflowConfirmationEntry",
    "CboeVixTermStructureEntry",
    "CboeVxnVixDispersionEntry",
    "ChicagoFedCfnaiActivityStateEntry",
    "ConsumerSentimentStateEntry",
    "ConnorsRsi2MeanReversionEntry",
    "CorporateEquitySupplyStateEntry",
    "CreditEtfOrderflowStateEntry",
    "DailyTimeSeriesMomentumEntry",
    "DailyBollingerEnvironmentEntry",
    "FiftyTwoWeekAnchorMomentumEntry",
    "FamaFrenchStyleFactorStateEntry",
    "WeeklyStageAnalysisEntry",
    "DefaultSpreadOrderflowStateEntry",
    "DailyShortTermReversalEntry",
    "DailyReversalOrderflowConfirmationEntry",
    "TurnaroundTuesdayReversalEntry",
    "DollarRiskAppetiteEntry",
    "EmaPullbackOrderflowContinuationEntry",
    "EmvMacroNewsStateEntry",
    "EpuPolicyUncertaintyEntry",
    "EsMesLeadLagEntry",
    "EsNqLeadLagEntry",
    "NqEsLeadLagEntry",
    "EsNqRelativeValueReversionEntry",
    "EsNqRelativeValueOrderflowAbsorptionReversionEntry",
    "NqEsRelativeValueOrderflowAbsorptionReversionEntry",
    "NqNikkei225CloseSpilloverEntry",
    "NqTechRelativeStrengthEntry",
    "NqTechRelativeOrderflowConfirmationEntry",
    "NqSmallCapRelativeRotationEntry",
    "NqNasdaqEqualWeightConcentrationEntry",
    "NqEuropeEquityCloseSpilloverEntry",
    "NqBtcCryptoRiskSentimentEntry",
    "NqCopperGrowthRiskSentimentEntry",
    "NqSemiconductorLeadershipEntry",
    "NqTaiwanSemiconductorSpilloverEntry",
    "NqChinaTechRiskSentimentEntry",
    "NqIndustrialProductionStateEntry",
    "NqRetailInventoryDemandEntry",
    "NqManufacturingOrdersStateEntry",
    "NqJoblessClaimsStateEntry",
    "NqHousingConstructionStateEntry",
    "NqInflationPressureStateEntry",
    "NqProductivityUnitLaborCostStateEntry",
    "NqConsumerCreditStateEntry",
    "NqBankCreditSupplyStateEntry",
    "NqTradeBalanceQuantityStateEntry",
    "NqFiscalDeficitTreasurySupplyStateEntry",
    "EsNqSemivarianceFilteredRelativeValueAbsorptionEntry",
    "EsTermStructureLeadLagEntry",
    "FootprintAbsorptionInitiationEntry",
    "FomcPreAnnouncementDriftEntry",
    "GaoLastHalfHourOrderflowEntry",
    "GoldPlatinumRatioStateEntry",
    "HalloweenSeasonalPremiumEntry",
    "ImpulsePauseOrderflowContinuationEntry",
    "ImportExportPricePressureEntry",
    "InfectiousDiseaseEmvStateEntry",
    "IntradayCapitulationMREntry",
    "IntradayMomentumPriorityEntry",
    "VolatilityFilteredIntradayMomentumPriorityEntry",
    "IntradayPeriodicityOrderflowConfirmationEntry",
    "IntradayRangeOrderflowBreakoutEntry",
    "KeyReversalOrderflowReversalEntry",
    "LargeRecordAoiReactionEntry",
    "LargeRecordDelayedAoiConfirmationEntry",
    "LateDayIntradayMomentumEntry",
    "LeveragedEtfRebalancePressureEntry",
    "LiquidityRiskCapacityPriorityEntry",
    "LiquidityInversionFvgEntry",
    "LowToxicityAoiFalseBreakoutEntry",
    "MacroEventAmdDistributionEntry",
    "MarketPlumbingPriorityEntry",
    "MaxDailyReturnLotteryReversalEntry",
    "MeasuredMovePullbackContinuationEntry",
    "MesCrowdingAoiTrapEntry",
    "MesTrendAoiPullbackEntry",
    "VolFilteredMesTrendAoiPullbackEntry",
    "MesParticipationCrowdingEntry",
    "MesFootprintLiquiditySweepReversionEntry",
    "TrendFilteredMesParticipationCrowdingEntry",
    "VolatilityFilteredTrendMesParticipationCrowdingEntry",
    "NqMesCrowdingOrderflowWindowConfirmationEntry",
    "NqPivotMesOrderflowConfirmationEntry",
    "MonthlyOpexPressureEntry",
    "MoveTreasuryVolStateEntry",
    "MorningIntradayMomentumEntry",
    "MorningOrderflowMomentumEntry",
    "MorningTrendLunchReversalOrderflowEntry",
    "NaaimExposureSentimentEntry",
    "OpeningRangeBreakoutEntry",
    "OpeningGapOrderflowFadeEntry",
    "OpeningGapOrderflowContinuationEntry",
    "OpeningDriveInventoryComboEntry",
    "OpeningDriveMesCrowdingReversalEntry",
    "OpeningRangeFilteredBreakoutEntry",
    "OpeningRangeFailedBreakoutTrendOrderflowEntry",
    "OpeningRangeInverseBreakoutEntry",
    "OilPriceShockSpilloverEntry",
    "OrderflowRegimeEntry",
    "OrderflowRecentPocketComboEntry",
    "OfrFinancialStressEntry",
    "OvernightReturnLateDayMomentumEntry",
    "OvernightIntradayReversalEntry",
    "OvernightDriftEntry",
    "OvernightInventoryReversionEntry",
    "PdhPdlBreakoutContinuationEntry",
    "PdhPdlOrderflowBreakoutContinuationEntry",
    "PdhPdlTrendOrderflowBreakoutContinuationEntry",
    "PdhPdlSweepReclaimEntry",
    "PdhPdlVapAbsorptionSweepEntry",
    "TrendOrderflowPdhPdlSweepReclaimEntry",
    "PositiveDeltaDislocationEntry",
    "PreholidayEffectEntry",
    "ProfileAoiFootprintTrapEntry",
    "NqNonconfirmingVapAoiTrapEntry",
    "NqConfirmingVapAoiBreakoutEntry",
    "NqEsSmtPo3MidpointReversionEntry",
    "TrueVapAoiBreakoutContinuationEntry",
    "TrueVapValueAreaOrderflowAcceptanceEntry",
    "VideoAoiOrderflowPlaybookEntry",
    "VideoExactOrderflowPlaybookEntry",
    "VideoExactOrderflowPlaybookScidIntrabarEntry",
    "PriorSessionBenchmarkOrderflowReactionEntry",
    "PriorSessionIbsReversionEntry",
    "PriorLvnOrderflowRejectionEntry",
    "PriorPocOrderflowMagnetEntry",
    "PriceEndingBarrierEntry",
    "PriorValueAreaOrderflowAcceptanceEntry",
    "PriorValueAreaOrderflowRejectionEntry",
    "TrendFilteredPriorValueAreaAcceptanceEntry",
    "QuarterlyExpirationPressureEntry",
    "QuoteLiquiditySweepReversionEntry",
    "RangeCompressionOrderflowBreakoutEntry",
    "RangeCompressionBreakoutEntry",
    "RealizedJumpVariationPremiumEntry",
    "RealizedSemivarianceAsymmetryEntry",
    "RealizedSemivarianceOrderflowConfirmationEntry",
    "RealizedSkewnessReversalEntry",
    "RealizedVolOfVolStateEntry",
    "RoundNumberBarrierEntry",
    "RollingRangeOrderflowSweepReversalEntry",
    "RollingStatEnvelopeOrderflowReversionEntry",
    "RthGapFadeEntry",
    "SessionExtremeDeltaDivergenceEntry",
    "SessionLiquidityFvgReversalEntry",
    "SessionOpenOrderflowReclaimEntry",
    "SemivarianceFilteredTrendMesParticipationCrowdingEntry",
    "SectorDispersionStateEntry",
    "SectorOpeningBreadthOrderflowEntry",
    "SectorRotationOrderflowPullbackEntry",
    "SectorRotationRiskAppetiteEntry",
    "Spx0dteExpirationPressureEntry",
    "Spx0dteOrderflowConfirmationEntry",
    "Spx0dteTrendAlignedPressureEntry",
    "SpyTurnoverOrderflowAttentionEntry",
    "TurnOfMonthBiasEntry",
    "TradeOrderflowMultiPressureEntry",
    "TradeOrderflowMultiStateRankEntry",
    "TradeOrderflowPressureEntry",
    "TradeOrderflowStateRankEntry",
    "TradeFragmentationLiquidityReversionEntry",
    "TradeSizeSegmentOrderflowEntry",
    "TrendAlignedOrderflowContinuationEntry",
    "OpeningRangeTrendOrderflowBreakoutEntry",
    "OpeningRangeNqOrderflowBreakoutEntry",
    "OpeningVapAbsorptionReactionEntry",
    "OpeningVapLargeRecordReactionEntry",
    "TreasuryAuctionPressureEntry",
    "TreasuryRateOrderflowStateEntry",
    "TreasuryRateStateEntry",
    "TreasuryTermPremiumStateEntry",
    "TurnOfYearEffectEntry",
    "UsdJpySafeHavenEntry",
    "VarianceRiskPremiumIntradayEntry",
    "VarianceRatioOrderflowRegimeEntry",
    "VixExpirationPressureEntry",
    "VolatilityManagedIntradayPremiumEntry",
    "VolumeConditionedLiquidityReversalEntry",
    "WideRangeOrderflowContinuationEntry",
    "VpinToxicityContinuationEntry",
    "VvixTailRiskEntry",
    "VixTermStructureOrderflowPullbackEntry",
    "VwapOrderflowPullbackContinuationEntry",
    "VwapDeviationOrderflowReversionEntry",
    "VwapPullbackContinuationEntry",
    "build_entry_module",
    "entry_module_metadata",
    "all_entry_module_metadata",
]
