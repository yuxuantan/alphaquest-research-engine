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
from alphaquest.strategy_modules.entry.yush_range_1 import YushRange1Entry
from alphaquest.strategy_modules.entry.yush_range_2 import YushRange2Entry
from alphaquest.strategy_modules.entry.yush_range_3 import YushRange3Entry
from alphaquest.strategy_modules.entry.yush_range_4 import YushRange4Entry
from alphaquest.strategy_modules.entry.yush_range_5 import YushRange5Entry
from alphaquest.strategy_modules.entry.yush_range_6 import YushRange6Entry
from alphaquest.strategy_modules.entry.yush_range_7 import YushRange7Entry
from alphaquest.strategy_modules.entry.yush_range_8 import YushRange8Entry
from alphaquest.strategy_modules.entry.yush_range_9 import YushRange9Entry
from alphaquest.strategy_modules.entry.yush_range_10 import YushRange10Entry
from alphaquest.strategy_modules.entry.yush_range_11 import YushRange11Entry
from alphaquest.strategy_modules.entry.yush_range_12 import YushRange12Entry
from alphaquest.strategy_modules.entry.yush_range_13 import YushRange13Entry
from alphaquest.strategy_modules.entry.yush_range_14 import YushRange14Entry
from alphaquest.strategy_modules.entry.yush_range_15 import YushRange15Entry
from alphaquest.strategy_modules.entry.yush_range_16 import YushRange16Entry
from alphaquest.strategy_modules.entry.yush_range_17 import YushRange17Entry
from alphaquest.strategy_modules.entry.yush_range_18 import YushRange18Entry
from alphaquest.strategy_modules.entry.yush_range_19 import YushRange19Entry
from alphaquest.strategy_modules.entry.yush_range_20 import YushRange20Entry
from alphaquest.strategy_modules.entry.yush_range_21 import YushRange21Entry
from alphaquest.strategy_modules.entry.yush_range_22 import YushRange22Entry
from alphaquest.strategy_modules.entry.yush_range_23 import YushRange23Entry
from alphaquest.strategy_modules.entry.yush_range_24 import YushRange24Entry
from alphaquest.strategy_modules.entry.yush_range_25 import YushRange25Entry
from alphaquest.strategy_modules.entry.yush_range_26 import YushRange26Entry
from alphaquest.strategy_modules.entry.yush_range_27 import YushRange27Entry
from alphaquest.strategy_modules.entry.yush_range_28 import YushRange28Entry
from alphaquest.strategy_modules.entry.yush_range_29 import YushRange29Entry
from alphaquest.strategy_modules.entry.yush_range_30 import YushRange30Entry
from alphaquest.strategy_modules.entry.yush_range_31 import YushRange31Entry
from alphaquest.strategy_modules.entry.yush_trend_1 import YushTrend1Entry
from alphaquest.strategy_modules.entry.yush_trend_2 import YushTrend2Entry
from alphaquest.strategy_modules.entry.yush_trend_3 import YushTrend3Entry
from alphaquest.strategy_modules.entry.yush_trend_4 import YushTrend4Entry
from alphaquest.strategy_modules.entry.yush_trend_5 import YushTrend5Entry
from alphaquest.strategy_modules.entry.yush_trend_6 import YushTrend6Entry
from alphaquest.strategy_modules.entry.yush_trend_7 import YushTrend7Entry
from alphaquest.strategy_modules.entry.yush_trend_8 import YushTrend8Entry
from alphaquest.strategy_modules.entry.yush_trend_9 import YushTrend9Entry
from alphaquest.strategy_modules.entry.yush_trend_10 import YushTrend10Entry
from alphaquest.strategy_modules.entry.yush_trend_11 import YushTrend11Entry
from alphaquest.strategy_modules.entry.yush_trend_12 import YushTrend12Entry
from alphaquest.strategy_modules.entry.yush_trend_13 import YushTrend13Entry
from alphaquest.strategy_modules.entry.yush_trend_14 import YushTrend14Entry
from alphaquest.strategy_modules.entry.yush_trend_15 import YushTrend15Entry
from alphaquest.strategy_modules.entry.yush_trend_16 import YushTrend16Entry
from alphaquest.strategy_modules.entry.yush_trend_17 import YushTrend17Entry
from alphaquest.strategy_modules.entry.yush_trend_18 import YushTrend18Entry
from alphaquest.strategy_modules.entry.yush_trend_19 import YushTrend19Entry
from alphaquest.strategy_modules.entry.yush_trend_20 import YushTrend20Entry
from alphaquest.strategy_modules.entry.yush_trend_21 import YushTrend21Entry
from alphaquest.strategy_modules.entry.yush_trend_22 import YushTrend22Entry
from alphaquest.strategy_modules.entry.yush_trend_23 import YushTrend23Entry
from alphaquest.strategy_modules.entry.yush_trend_24 import YushTrend24Entry
from alphaquest.strategy_modules.entry.yush_trend_25 import YushTrend25Entry
from alphaquest.strategy_modules.entry.yush_trend_26 import YushTrend26Entry
from alphaquest.strategy_modules.entry.yush_trend_27 import YushTrend27Entry
from alphaquest.strategy_modules.entry.yush_trend_28 import YushTrend28Entry
from alphaquest.strategy_modules.entry.yush_trend_29 import YushTrend29Entry
from alphaquest.strategy_modules.entry.yush_trend_30 import YushTrend30Entry
from alphaquest.strategy_modules.entry.yush_trend_31 import YushTrend31Entry
from alphaquest.strategy_modules.entry.yush_trend_32 import YushTrend32Entry
from alphaquest.strategy_modules.entry.yush_trend_33 import YushTrend33Entry
from alphaquest.strategy_modules.entry.yush_trend_34 import YushTrend34Entry
from alphaquest.strategy_modules.entry.yush_trend_35 import YushTrend35Entry
from alphaquest.strategy_modules.entry.yush_trend_36 import YushTrend36Entry
from alphaquest.strategy_modules.entry.yush_trend_37 import YushTrend37Entry
from alphaquest.strategy_modules.entry.yush_trend_38 import YushTrend38Entry
from alphaquest.strategy_modules.entry.yush_trend_39 import YushTrend39Entry
from alphaquest.strategy_modules.entry.yush_trend_40 import YushTrend40Entry
from alphaquest.strategy_modules.entry.yush_trend_41 import YushTrend41Entry
from alphaquest.strategy_modules.entry.yush_trend_42 import YushTrend42Entry
from alphaquest.strategy_modules.entry.yush_trend_43 import YushTrend43Entry
from alphaquest.strategy_modules.entry.yush_trend_44 import YushTrend44Entry
from alphaquest.strategy_modules.entry.yush_trend_45 import YushTrend45Entry
from alphaquest.strategy_modules.entry.yush_trend_46 import YushTrend46Entry
from alphaquest.strategy_modules.entry.yush_trend_47 import YushTrend47Entry
from alphaquest.strategy_modules.entry.yush_trend_48 import YushTrend48Entry
from alphaquest.strategy_modules.entry.yush_trend_49 import YushTrend49Entry
from alphaquest.strategy_modules.entry.yush_trend_50 import YushTrend50Entry
from alphaquest.strategy_modules.entry.yush_trend_51 import YushTrend51Entry
from alphaquest.strategy_modules.entry.yush_trend_52 import YushTrend52Entry
from alphaquest.strategy_modules.entry.yush_trend_53 import YushTrend53Entry
from alphaquest.strategy_modules.entry.yush_trend_54 import YushTrend54Entry
from alphaquest.strategy_modules.entry.yush_trend_55 import YushTrend55Entry
from alphaquest.strategy_modules.entry.yush_trend_56 import YushTrend56Entry
from alphaquest.strategy_modules.entry.yush_trend_57 import YushTrend57Entry
from alphaquest.strategy_modules.entry.yush_trend_58 import YushTrend58Entry
from alphaquest.strategy_modules.entry.yush_trend_59 import YushTrend59Entry
from alphaquest.strategy_modules.entry.yush_trend_60 import YushTrend60Entry
from alphaquest.strategy_modules.entry.yush_trend_61 import YushTrend61Entry
from alphaquest.strategy_modules.entry.yush_trend_62 import YushTrend62Entry
from alphaquest.strategy_modules.entry.yush_trend_63 import YushTrend63Entry
from alphaquest.strategy_modules.entry.yush_trend_64 import YushTrend64Entry
from alphaquest.strategy_modules.entry.yush_trend_65 import YushTrend65Entry
from alphaquest.strategy_modules.entry.yush_trend_66 import YushTrend66Entry
from alphaquest.strategy_modules.entry.yush_trend_67 import YushTrend67Entry
from alphaquest.strategy_modules.entry.yush_trend_68 import YushTrend68Entry
from alphaquest.strategy_modules.entry.yush_trend_69 import YushTrend69Entry
from alphaquest.strategy_modules.entry.yush_trend_70 import YushTrend70Entry
from alphaquest.strategy_modules.entry.yush_trend_71 import YushTrend71Entry
from alphaquest.strategy_modules.entry.yush_trend_72 import YushTrend72Entry
from alphaquest.strategy_modules.entry.yush_trend_73 import YushTrend73Entry
from alphaquest.strategy_modules.entry.yush_trend_74 import YushTrend74Entry
from alphaquest.strategy_modules.entry.yush_trend_75 import YushTrend75Entry
from alphaquest.strategy_modules.entry.yush_trend_76 import YushTrend76Entry
from alphaquest.strategy_modules.entry.yush_trend_77 import YushTrend77Entry
from alphaquest.strategy_modules.entry.yush_trend_78 import YushTrend78Entry
from alphaquest.strategy_modules.entry.yush_trend_79 import YushTrend79Entry
from alphaquest.strategy_modules.entry.yush_trend_81 import YushTrend81Entry
from alphaquest.strategy_modules.entry.yush_trend_82 import YushTrend82Entry
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
    YushRange1Entry.name: YushRange1Entry,
    YushRange2Entry.name: YushRange2Entry,
    YushRange3Entry.name: YushRange3Entry,
    YushRange4Entry.name: YushRange4Entry,
    YushRange5Entry.name: YushRange5Entry,
    YushRange6Entry.name: YushRange6Entry,
    YushRange7Entry.name: YushRange7Entry,
    YushRange8Entry.name: YushRange8Entry,
    YushRange9Entry.name: YushRange9Entry,
    YushRange10Entry.name: YushRange10Entry,
    YushRange11Entry.name: YushRange11Entry,
    YushRange12Entry.name: YushRange12Entry,
    YushRange13Entry.name: YushRange13Entry,
    YushRange14Entry.name: YushRange14Entry,
    YushRange15Entry.name: YushRange15Entry,
    YushRange16Entry.name: YushRange16Entry,
    YushRange17Entry.name: YushRange17Entry,
    YushRange18Entry.name: YushRange18Entry,
    YushRange19Entry.name: YushRange19Entry,
    YushRange20Entry.name: YushRange20Entry,
    YushRange21Entry.name: YushRange21Entry,
    YushRange22Entry.name: YushRange22Entry,
    YushRange23Entry.name: YushRange23Entry,
    YushRange24Entry.name: YushRange24Entry,
    YushRange25Entry.name: YushRange25Entry,
    YushRange26Entry.name: YushRange26Entry,
    YushRange27Entry.name: YushRange27Entry,
    YushRange28Entry.name: YushRange28Entry,
    YushRange29Entry.name: YushRange29Entry,
    YushRange30Entry.name: YushRange30Entry,
    YushRange31Entry.name: YushRange31Entry,
    YushTrend1Entry.name: YushTrend1Entry,
    YushTrend2Entry.name: YushTrend2Entry,
    YushTrend3Entry.name: YushTrend3Entry,
    YushTrend4Entry.name: YushTrend4Entry,
    YushTrend5Entry.name: YushTrend5Entry,
    YushTrend6Entry.name: YushTrend6Entry,
    YushTrend7Entry.name: YushTrend7Entry,
    YushTrend8Entry.name: YushTrend8Entry,
    YushTrend9Entry.name: YushTrend9Entry,
    YushTrend10Entry.name: YushTrend10Entry,
    YushTrend11Entry.name: YushTrend11Entry,
    YushTrend12Entry.name: YushTrend12Entry,
    YushTrend13Entry.name: YushTrend13Entry,
    YushTrend14Entry.name: YushTrend14Entry,
    YushTrend15Entry.name: YushTrend15Entry,
    YushTrend16Entry.name: YushTrend16Entry,
    YushTrend17Entry.name: YushTrend17Entry,
    YushTrend18Entry.name: YushTrend18Entry,
    YushTrend19Entry.name: YushTrend19Entry,
    YushTrend20Entry.name: YushTrend20Entry,
    YushTrend21Entry.name: YushTrend21Entry,
    YushTrend22Entry.name: YushTrend22Entry,
    YushTrend23Entry.name: YushTrend23Entry,
    YushTrend24Entry.name: YushTrend24Entry,
    YushTrend25Entry.name: YushTrend25Entry,
    YushTrend26Entry.name: YushTrend26Entry,
    YushTrend27Entry.name: YushTrend27Entry,
    YushTrend28Entry.name: YushTrend28Entry,
    YushTrend29Entry.name: YushTrend29Entry,
    YushTrend30Entry.name: YushTrend30Entry,
    YushTrend31Entry.name: YushTrend31Entry,
    YushTrend32Entry.name: YushTrend32Entry,
    YushTrend33Entry.name: YushTrend33Entry,
    YushTrend34Entry.name: YushTrend34Entry,
    YushTrend35Entry.name: YushTrend35Entry,
    YushTrend36Entry.name: YushTrend36Entry,
    YushTrend37Entry.name: YushTrend37Entry,
    YushTrend38Entry.name: YushTrend38Entry,
    YushTrend39Entry.name: YushTrend39Entry,
    YushTrend40Entry.name: YushTrend40Entry,
    YushTrend41Entry.name: YushTrend41Entry,
    YushTrend42Entry.name: YushTrend42Entry,
    YushTrend43Entry.name: YushTrend43Entry,
    YushTrend44Entry.name: YushTrend44Entry,
    YushTrend45Entry.name: YushTrend45Entry,
    YushTrend46Entry.name: YushTrend46Entry,
    YushTrend47Entry.name: YushTrend47Entry,
    YushTrend48Entry.name: YushTrend48Entry,
    YushTrend49Entry.name: YushTrend49Entry,
    YushTrend50Entry.name: YushTrend50Entry,
    YushTrend51Entry.name: YushTrend51Entry,
    YushTrend52Entry.name: YushTrend52Entry,
    YushTrend53Entry.name: YushTrend53Entry,
    YushTrend54Entry.name: YushTrend54Entry,
    YushTrend55Entry.name: YushTrend55Entry,
    YushTrend56Entry.name: YushTrend56Entry,
    YushTrend57Entry.name: YushTrend57Entry,
    YushTrend58Entry.name: YushTrend58Entry,
    YushTrend59Entry.name: YushTrend59Entry,
    YushTrend60Entry.name: YushTrend60Entry,
    YushTrend61Entry.name: YushTrend61Entry,
    YushTrend62Entry.name: YushTrend62Entry,
    YushTrend63Entry.name: YushTrend63Entry,
    YushTrend64Entry.name: YushTrend64Entry,
    YushTrend65Entry.name: YushTrend65Entry,
    YushTrend66Entry.name: YushTrend66Entry,
    YushTrend67Entry.name: YushTrend67Entry,
    YushTrend68Entry.name: YushTrend68Entry,
    YushTrend69Entry.name: YushTrend69Entry,
    YushTrend70Entry.name: YushTrend70Entry,
    YushTrend71Entry.name: YushTrend71Entry,
    YushTrend72Entry.name: YushTrend72Entry,
    YushTrend73Entry.name: YushTrend73Entry,
    YushTrend74Entry.name: YushTrend74Entry,
    YushTrend75Entry.name: YushTrend75Entry,
    YushTrend76Entry.name: YushTrend76Entry,
    YushTrend77Entry.name: YushTrend77Entry,
    YushTrend78Entry.name: YushTrend78Entry,
    YushTrend79Entry.name: YushTrend79Entry,
    YushTrend81Entry.name: YushTrend81Entry,
    YushTrend82Entry.name: YushTrend82Entry,
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
    "YushRange1Entry",
    "YushRange2Entry",
    "YushRange3Entry",
    "YushRange4Entry",
    "YushRange5Entry",
    "YushRange6Entry",
    "YushRange7Entry",
    "YushRange8Entry",
    "YushRange9Entry",
    "YushRange10Entry",
    "YushRange11Entry",
    "YushRange12Entry",
    "YushRange13Entry",
    "YushRange14Entry",
    "YushRange15Entry",
    "YushRange16Entry",
    "YushRange17Entry",
    "YushRange18Entry",
    "YushRange19Entry",
    "YushRange20Entry",
    "YushRange21Entry",
    "YushRange22Entry",
    "YushRange23Entry",
    "YushRange24Entry",
    "YushRange25Entry",
    "YushRange26Entry",
    "YushRange27Entry",
    "YushRange28Entry",
    "YushRange29Entry",
    "YushRange30Entry",
    "YushRange31Entry",
    "YushTrend1Entry",
    "YushTrend2Entry",
    "YushTrend3Entry",
    "YushTrend4Entry",
    "YushTrend5Entry",
    "YushTrend6Entry",
    "YushTrend7Entry",
    "YushTrend8Entry",
    "YushTrend9Entry",
    "YushTrend10Entry",
    "YushTrend11Entry",
    "YushTrend12Entry",
    "YushTrend13Entry",
    "YushTrend14Entry",
    "YushTrend15Entry",
    "YushTrend16Entry",
    "YushTrend17Entry",
    "YushTrend18Entry",
    "YushTrend19Entry",
    "YushTrend20Entry",
    "YushTrend21Entry",
    "YushTrend22Entry",
    "YushTrend23Entry",
    "YushTrend24Entry",
    "YushTrend25Entry",
    "YushTrend26Entry",
    "YushTrend27Entry",
    "YushTrend28Entry",
    "YushTrend29Entry",
    "YushTrend30Entry",
    "YushTrend31Entry",
    "YushTrend32Entry",
    "YushTrend33Entry",
    "YushTrend34Entry",
    "YushTrend35Entry",
    "YushTrend36Entry",
    "YushTrend37Entry",
    "YushTrend38Entry",
    "YushTrend39Entry",
    "YushTrend40Entry",
    "YushTrend41Entry",
    "YushTrend42Entry",
    "YushTrend43Entry",
    "YushTrend44Entry",
    "YushTrend45Entry",
    "YushTrend46Entry",
    "YushTrend47Entry",
    "YushTrend48Entry",
    "YushTrend49Entry",
    "YushTrend50Entry",
    "YushTrend51Entry",
    "YushTrend52Entry",
    "YushTrend53Entry",
    "YushTrend54Entry",
    "YushTrend55Entry",
    "YushTrend56Entry",
    "YushTrend57Entry",
    "YushTrend58Entry",
    "YushTrend59Entry",
    "YushTrend60Entry",
    "YushTrend61Entry",
    "YushTrend62Entry",
    "YushTrend63Entry",
    "YushTrend64Entry",
    "YushTrend65Entry",
    "YushTrend66Entry",
    "YushTrend67Entry",
    "YushTrend68Entry",
    "YushTrend69Entry",
    "YushTrend70Entry",
    "YushTrend71Entry",
    "YushTrend72Entry",
    "YushTrend73Entry",
    "YushTrend74Entry",
    "YushTrend75Entry",
    "YushTrend76Entry",
    "YushTrend77Entry",
    "YushTrend78Entry",
    "YushTrend79Entry",
    "YushTrend81Entry",
    "YushTrend82Entry",
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
