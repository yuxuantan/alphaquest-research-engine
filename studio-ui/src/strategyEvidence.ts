export type StrategyEvidenceField = {
  key: string;
  label: string;
};

export type StrategyEvidencePanelDefinition = {
  title: string;
  fields: StrategyEvidenceField[];
};

export type ResolvedStrategyEvidencePanel = {
  title: string;
  rows: Array<StrategyEvidenceField & { value: unknown }>;
};

export type MechanicsComparisonRow = {
  key: string;
  label: string;
  configured: unknown;
  observed: unknown;
};

export type MechanicsComparisonSection = {
  title: string;
  description: string;
  rows: MechanicsComparisonRow[];
};

export type QualifyingFootprintRoute = {
  id: "large_execution" | "top_decile_delta";
  label: string;
  qualified: boolean | null;
  observed: unknown;
  threshold: unknown;
  unit: string;
  percentile: unknown;
  priceLow: unknown;
  priceHigh: unknown;
  side?: unknown;
  qualifiedAt?: unknown;
  referenceDescription: string;
};

export type QualifyingFootprintSummary = {
  rule: "any";
  outcome: "qualified" | "not_qualified" | "unknown";
  kind: string;
  edgePrice: unknown;
  frozenAt: unknown;
  definition: string;
  routes: QualifyingFootprintRoute[];
};

export type FrozenSetupSummary = {
  direction: string;
  edgeRole: "VAH" | "VAL" | "value edge";
  sourceKinds: unknown;
  edgePrice: unknown;
  pocPrice: unknown;
  vahPrice: unknown;
  valPrice: unknown;
  aoiArmedAt: unknown;
  burstSize: unknown;
  burstThreshold: unknown;
  burstQualifiedAt: unknown;
  burstSide: unknown;
  burstPriceLow: unknown;
  burstPriceHigh: unknown;
  sourceDescription?: string;
};

type EvidenceIdentity = {
  metadata?: Record<string, unknown>;
  trade?: Record<string, unknown>;
  strategy_context?: Record<string, unknown>;
  frozen_mechanics?: Record<string, unknown>;
  event_transitions?: Array<Record<string, unknown>>;
};

const AOI_V01_PANELS: StrategyEvidencePanelDefinition[] = [
  {
    title: "AOI confluence and geometry",
    fields: [
      { key: "aoi_side", label: "AOI side" },
      { key: "aoi_box_low", label: "AOI box low" },
      { key: "aoi_box_high", label: "AOI box high" },
      { key: "aoi_width_points", label: "AOI width" },
      { key: "aoi_categories", label: "Confluence categories" },
      { key: "aoi_confluences", label: "Selected confluences" },
      { key: "aoi_lineage_mode", label: "Lineage mode" },
      { key: "aoi_exact_fingerprint", label: "Exact fingerprint" },
    ],
  },
  {
    title: "AOI signal timing",
    fields: [
      { key: "aoi_eligible_timestamp", label: "Exact AOI became valid" },
      { key: "aoi_tap_timestamp", label: "Tap time" },
      { key: "trigger_kind", label: "Trigger type" },
      { key: "trigger_value", label: "Trigger value" },
      { key: "bubble_qualified_timestamp", label: "Trigger qualified" },
      { key: "order_armed_timestamp", label: "Order armed" },
    ],
  },
  {
    title: "AOI execution state",
    fields: [
      { key: "entry_trigger_price", label: "Entry trigger" },
      { key: "initial_stop_price", label: "Initial stop" },
      { key: "risk_points", label: "Initial risk" },
      { key: "entry_profile_poc", label: "Entry POC" },
      { key: "entry_profile_vah", label: "Entry VAH" },
      { key: "entry_profile_val", label: "Entry VAL" },
      { key: "midpoint_activated", label: "Midpoint activated" },
      { key: "midpoint_activated_at", label: "Midpoint activation time" },
    ],
  },
];

const FAILED_AUCTION_V02_PANELS: StrategyEvidencePanelDefinition[] = [
  {
    title: "Selected confluence at signal",
    fields: [
      { key: "failed_auction_side", label: "Value-area side" },
      { key: "failed_auction_boundary", label: "Frozen value boundary" },
      { key: "failed_auction_reference_type", label: "Selected market level" },
      { key: "failed_auction_reference", label: "Market-level price" },
      { key: "failed_auction_excursion_low", label: "Excursion low" },
      { key: "failed_auction_excursion_high", label: "Excursion high" },
      { key: "frozen_entry_poc", label: "Frozen POC objective" },
    ],
  },
  {
    title: "Aggression qualification",
    fields: [
      { key: "failed_auction_aggression_kind", label: "Qualifying route" },
      { key: "failed_auction_aggression_value", label: "Observed aggression" },
      {
        key: "failed_auction_aggression_event_index",
        label: "Aggression event",
      },
      { key: "failed_auction_delta_percentile", label: "Delta percentile" },
      { key: "failed_auction_delta_threshold", label: "Frozen delta threshold" },
      {
        key: "failed_auction_delta_reference_count",
        label: "Delta reference observations",
      },
      {
        key: "failed_auction_big_trade_percentile",
        label: "Big-trade percentile",
      },
      {
        key: "failed_auction_big_trade_threshold",
        label: "Frozen big-trade threshold",
      },
      {
        key: "failed_auction_big_trade_reference_count",
        label: "Big-trade reference observations",
      },
    ],
  },
  {
    title: "Failed-auction causal execution",
    fields: [
      { key: "failed_auction_started_at", label: "Episode started" },
      { key: "failed_auction_reclaimed_at", label: "Boundary reclaimed" },
      {
        key: "failed_auction_reclaim_event_index",
        label: "Reclaim event",
      },
      { key: "entry_event_index", label: "Entry event" },
      { key: "fill_model", label: "Fill model" },
      { key: "time_exit_seconds", label: "Maximum holding time (seconds)" },
    ],
  },
];

const RANGE_EDGE_TRAP_V02_PANELS: StrategyEvidencePanelDefinition[] = [
  {
    title: "Frozen value edge and institutional footprint",
    fields: [
      { key: "aoi_edge_price", label: "Frozen AOI edge" },
      { key: "aoi_frozen_bar_index", label: "AOI frozen bar" },
      { key: "aoi_frozen_at", label: "AOI frozen at" },
      {
        key: "institutional_big_trade_qualified",
        label: "Adaptive large execution qualified",
      },
      {
        key: "institutional_delta_qualified",
        label: "Top-decile delta qualified",
      },
      {
        key: "big_trade_reference_percentile",
        label: "Large-execution percentile",
      },
      {
        key: "big_trade_lookback_sessions",
        label: "Large-execution lookback sessions",
      },
      {
        key: "big_trade_threshold_contracts",
        label: "Frozen large-execution threshold",
      },
      {
        key: "big_trade_reference_observation_count",
        label: "Reference burst observations",
      },
      {
        key: "big_trade_reference_start_session",
        label: "Reference start session",
      },
      {
        key: "big_trade_reference_end_session",
        label: "Reference end session",
      },
      { key: "selected_big_trade_burst_id", label: "Selected burst ID" },
      { key: "selected_big_trade_side", label: "Selected burst side" },
      { key: "selected_big_trade_low_price", label: "Selected burst low" },
      { key: "selected_big_trade_high_price", label: "Selected burst high" },
      { key: "selected_big_trade_size", label: "Selected burst contracts" },
      {
        key: "selected_big_trade_qualified_at",
        label: "Burst causally qualified at",
      },
      { key: "selected_delta_bin_low_price", label: "Delta-bin low" },
      { key: "selected_delta_bin_high_price", label: "Delta-bin high" },
      {
        key: "selected_delta_bin_abs_delta",
        label: "Delta-bin absolute delta",
      },
      {
        key: "selected_delta_bin_threshold",
        label: "Frozen top-decile delta threshold",
      },
      {
        key: "selected_delta_percentile",
        label: "Delta percentile",
      },
    ],
  },
  {
    title: "Directional breakout trend veto",
    fields: [
      {
        key: "directional_trend_veto_passed",
        label: "Direction-aligned trend veto passed",
      },
      { key: "trend_state_at_failure", label: "Trend state at failure" },
      { key: "trend_state_at_entry", label: "Trend state at entry" },
      {
        key: "regime_overlap_at_entry",
        label: "Value-area overlap at entry",
      },
      {
        key: "regime_efficiency_at_entry",
        label: "Directional efficiency at entry",
      },
      {
        key: "rolling_poc_a_at_entry_price",
        label: "Recent-window POC at entry",
      },
      {
        key: "rolling_poc_b_at_entry_price",
        label: "Prior-window POC at entry",
      },
      {
        key: "rolling_midpoint_a_at_entry_price",
        label: "Recent-window midpoint at entry",
      },
      {
        key: "rolling_midpoint_b_at_entry_price",
        label: "Prior-window midpoint at entry",
      },
    ],
  },
  {
    title: "Sweep, failure and causal entry",
    fields: [
      { key: "sweep_bar_index", label: "Sweep bar" },
      { key: "sweep_high_price", label: "Sweep high" },
      { key: "sweep_low_price", label: "Sweep low" },
      { key: "sweep_minimum_ticks", label: "Minimum excursion (ticks)" },
      {
        key: "failure_confirmation_bars",
        label: "Failure confirmation window (bars)",
      },
      { key: "failure_bar_index", label: "Failure bar" },
      { key: "failure_close_price", label: "Failure close" },
      {
        key: "failure_confirmation_rule",
        label: "Failure confirmation rule",
      },
      {
        key: "entry_trigger_rule",
        label: "Entry trigger rule",
      },
      { key: "entry_trigger_price", label: "Stop-entry trigger" },
      { key: "entry_event_index", label: "Entry event" },
      { key: "entry_fill_model", label: "Fill model" },
      { key: "burst_definition", label: "Execution-burst definition" },
      {
        key: "entry_windows_new_york",
        label: "Entry windows (New York)",
      },
    ],
  },
  {
    title: "Frozen objectives, stop, sizing and costs",
    fields: [
      { key: "value_area_poc_price", label: "Frozen POC" },
      { key: "value_area_vah_price", label: "Frozen VAH" },
      { key: "value_area_val_price", label: "Frozen VAL" },
      { key: "target_1_price", label: "T1: frozen value midpoint" },
      { key: "target_2_price", label: "T2: opposite value edge" },
      { key: "target_1_fraction", label: "T1 position fraction" },
      { key: "maximum_holding_bars", label: "Maximum holding bars" },
      { key: "target_1_activated", label: "T1 reached" },
      { key: "target_1_activated_at", label: "T1 reached at" },
      { key: "target_2_reached", label: "T2 reached" },
      { key: "partial_exit_legs", label: "Partial-exit legs" },
      {
        key: "profile_snapshot_timing",
        label: "Objective snapshot timing",
      },
      { key: "planned_stop_ticks", label: "Planned stop distance" },
      { key: "risk_points", label: "Filled price risk" },
      { key: "risk_budget_dollars", label: "Risk budget including costs" },
      { key: "position_sizing_mode", label: "Sizing mode" },
      { key: "target_risk_amount", label: "Target dollar risk" },
      {
        key: "dollar_risk_per_contract",
        label: "Risk plus costs per contract",
      },
      { key: "planned_dollar_risk", label: "Planned total risk" },
      { key: "contracts", label: "Contracts" },
      {
        key: "round_trip_commission_per_contract",
        label: "Round-trip commission per contract",
      },
      { key: "entry_slippage_ticks", label: "Entry slippage" },
      {
        key: "protective_stop_slippage_ticks",
        label: "Protective-stop slippage",
      },
      {
        key: "target_limit_slippage_ticks",
        label: "Target-limit slippage",
      },
    ],
  },
];

const ADAPTIVE_RANGE_V03_PANELS: StrategyEvidencePanelDefinition[] = [
  {
    title: "Frozen AOI source and profile",
    fields: [
      { key: "aoi_identity", label: "Exact AOI identity" },
      { key: "aoi_source_kinds", label: "AOI source kinds" },
      { key: "aoi_edge_price", label: "Exact frozen edge" },
      { key: "aoi_zone_low_price", label: "Frozen AOI zone low" },
      { key: "aoi_zone_high_price", label: "Frozen AOI zone high" },
      { key: "entry_zone_boundary_price", label: "Reclaim-side entry boundary" },
      { key: "value_area_poc_price", label: "Frozen POC" },
      { key: "value_area_vah_price", label: "Frozen VAH" },
      { key: "value_area_val_price", label: "Frozen VAL" },
      { key: "aoi_frozen_bar_index", label: "AOI frozen bar" },
      { key: "aoi_frozen_at", label: "AOI armed / profile frozen at" },
      {
        key: "institutional_big_trade_qualified",
        label: "Large-execution burst qualified",
      },
      {
        key: "institutional_delta_qualified",
        label: "Absolute-delta source qualified",
      },
      { key: "market_level_qualified", label: "Market level qualified" },
      {
        key: "big_trade_reference_percentile",
        label: "Large-execution percentile",
      },
      {
        key: "big_trade_lookback_sessions",
        label: "Large-execution lookback sessions",
      },
      { key: "big_trade_threshold_contracts", label: "Frozen burst threshold" },
      {
        key: "big_trade_reference_observation_count",
        label: "Reference burst observations",
      },
      { key: "selected_big_trade_burst_id", label: "Selected burst ID" },
      { key: "selected_big_trade_side", label: "Selected burst side" },
      { key: "selected_big_trade_low_price", label: "Selected burst low" },
      { key: "selected_big_trade_high_price", label: "Selected burst high" },
      { key: "selected_big_trade_size", label: "Selected burst contracts" },
      {
        key: "selected_big_trade_qualified_at",
        label: "Burst causally qualified at",
      },
      { key: "selected_delta_bin_low_price", label: "Selected delta row low" },
      { key: "selected_delta_bin_high_price", label: "Selected delta row high" },
      { key: "selected_delta_signed_delta", label: "Selected signed delta" },
      { key: "selected_delta_bin_threshold", label: "Delta threshold" },
      { key: "selected_delta_percentile", label: "Delta percentile" },
      { key: "selected_market_level_type", label: "Selected market level" },
      { key: "selected_market_level_price", label: "Market-level price" },
      { key: "profile_epoch", label: "Profile epoch" },
      { key: "burst_definition", label: "Execution-burst definition" },
      { key: "delta_profile_definition", label: "Delta-profile definition" },
      { key: "market_level_definition", label: "Market-level definition" },
    ],
  },
  {
    title: "Separate order-flow confirmation",
    fields: [
      { key: "entry_confirmation_kind", label: "Confirmation type" },
      { key: "entry_confirmation_id", label: "Confirmation identity" },
      { key: "entry_confirmation_at", label: "Confirmation available at" },
      { key: "entry_confirmation_price", label: "Confirmation price" },
      { key: "entry_confirmation_bin_low_price", label: "Confirmation cell low" },
      { key: "entry_confirmation_bin_high_price", label: "Confirmation cell high" },
      { key: "entry_confirmation_value", label: "Confirmation magnitude" },
      { key: "entry_confirmation_threshold", label: "Historical delta threshold" },
      { key: "confirmation_delta_reference_percentile", label: "Delta reference percentile" },
      { key: "confirmation_delta_lookback_sessions", label: "Delta lookback sessions" },
      { key: "confirmation_delta_reference_observation_count", label: "Delta reference observations" },
      { key: "confirmation_delta_reference_start_session", label: "Delta reference start" },
      { key: "confirmation_delta_reference_end_session", label: "Delta reference end" },
      { key: "burst_direction_rule", label: "Required direction" },
      { key: "burst_location_rule", label: "Required location" },
      { key: "footprint_definition", label: "AOI and confirmation rule" },
    ],
  },
  {
    title: "Sweep, reclaim and causal entry",
    fields: [
      { key: "sweep_bar_index", label: "Sweep bar" },
      { key: "sweep_high_price", label: "Sweep high" },
      { key: "sweep_low_price", label: "Sweep low" },
      { key: "sweep_minimum_ticks", label: "Minimum excursion (ticks)" },
      { key: "sweep_atr_fraction", label: "Sweep ATR fraction" },
      { key: "sweep_distance_ticks", label: "Applied sweep distance (ticks)" },
      { key: "sweep_crossing_rule", label: "Ordered crossing rule" },
      { key: "failure_confirmation_bars", label: "Maximum reclaim window (bars)" },
      { key: "reclaim_depth_ticks", label: "Required reclaim depth (ticks)" },
      { key: "reclaim_confirmation_at", label: "First inside reclaim at" },
      { key: "reclaim_event_index", label: "Reclaim event" },
      { key: "reclaim_event_price", label: "Reclaim event price" },
      { key: "failure_bar_index", label: "Confirmation bar" },
      { key: "failure_close_price", label: "Confirmation event price" },
      { key: "failure_confirmation_rule", label: "Reclaim rule" },
      { key: "entry_trigger_rule", label: "Entry instruction" },
      { key: "entry_order_type", label: "Entry order type" },
      { key: "entry_decision_event_index", label: "Sole entry-decision event" },
      { key: "actual_fill_gate_passed", label: "Actual-fill gates passed" },
      { key: "entry_reference_price", label: "Fill-event reference" },
      { key: "entry_price", label: "Actual modeled fill" },
      { key: "entry_event_index", label: "Entry event" },
      { key: "entry_fill_model", label: "Fill model" },
      { key: "entry_windows_new_york", label: "Entry windows (New York)" },
      { key: "burst_freshness_bars", label: "Burst freshness (bars)" },
      { key: "burst_freshness_minutes", label: "Burst freshness (minutes)" },
    ],
  },
  {
    title: "Stop, both targets, sizing and costs",
    fields: [
      { key: "target_1_price", label: "T1: frozen midpoint" },
      { key: "target_2_price", label: "T2: frozen opposite edge" },
      { key: "target_1_fraction", label: "T1 position fraction" },
      { key: "target_1_definition", label: "T1 rule" },
      { key: "target_2_definition", label: "T2 rule" },
      { key: "initial_stop_price", label: "Initial stop" },
      { key: "planned_stop_ticks", label: "Planned stop distance" },
      { key: "stop_buffer_ticks", label: "Structural stop buffer (ticks)" },
      { key: "maximum_stop_atr_multiple", label: "Maximum stop ATR multiple" },
      { key: "maximum_holding_bars", label: "Maximum holding bars" },
      { key: "risk_points", label: "Filled price risk" },
      {
        key: "minimum_net_reward_to_worst_case_loss",
        label: "Minimum net payoff ratio",
      },
      {
        key: "net_reward_to_worst_case_loss",
        label: "Actual-fill net payoff ratio",
      },
      {
        key: "net_target_reward_dollars_per_contract",
        label: "Net target reward per contract",
      },
      {
        key: "worst_case_stop_loss_dollars_per_contract",
        label: "Worst-case stop loss per contract",
      },
      { key: "position_sizing_mode", label: "Sizing mode" },
      { key: "target_risk_amount", label: "Target dollar risk" },
      {
        key: "dollar_risk_per_contract",
        label: "Risk plus costs per contract",
      },
      { key: "planned_dollar_risk", label: "Planned total risk" },
      { key: "contracts", label: "Contracts" },
      {
        key: "round_trip_commission_per_contract",
        label: "Round-trip commission per contract",
      },
      { key: "entry_slippage_ticks", label: "Entry slippage" },
      {
        key: "protective_stop_slippage_ticks",
        label: "Protective-stop slippage",
      },
      { key: "target_limit_slippage_ticks", label: "Target slippage" },
      { key: "signal_instrument", label: "Signal instrument" },
      { key: "execution_instrument", label: "Execution instrument" },
      {
        key: "execution_risk_fraction_net_liq",
        label: "Execution risk fraction",
      },
      {
        key: "minimum_contract_affordability_rule",
        label: "Minimum-contract affordability rule",
      },
    ],
  },
];

const ADAPTIVE_RANGE_V27_PANELS: StrategyEvidencePanelDefinition[] = [
  {
    title: "Per-bar AOI source and profile",
    fields: [
      { key: "aoi_identity", label: "Per-bar AOI identity" },
      { key: "aoi_source_kinds", label: "AOI source kinds" },
      { key: "aoi_edge_price", label: "Bar-start value edge" },
      { key: "aoi_zone_low_price", label: "AOI zone low" },
      { key: "aoi_zone_high_price", label: "AOI zone high" },
      { key: "entry_zone_boundary_price", label: "Reclaim-side boundary" },
      { key: "aoi_frozen_bar_index", label: "Source profile bar" },
      { key: "aoi_frozen_at", label: "AOI built at" },
      { key: "institutional_big_trade_qualified", label: "Large execution qualified" },
      { key: "institutional_delta_qualified", label: "Four-tick delta qualified" },
      { key: "selected_big_trade_side", label: "Selected burst side" },
      { key: "selected_big_trade_low_price", label: "Selected burst low" },
      { key: "selected_big_trade_high_price", label: "Selected burst high" },
      { key: "selected_big_trade_size", label: "Selected burst contracts" },
      { key: "selected_delta_bin_low_price", label: "Selected delta cell low" },
      { key: "selected_delta_bin_high_price", label: "Selected delta cell high" },
      { key: "selected_delta_signed_delta", label: "Selected signed delta" },
      { key: "selected_delta_bin_threshold", label: "Delta threshold" },
      { key: "value_area_vah_price", label: "AOI-time VAH" },
      { key: "value_area_poc_price", label: "AOI-time POC" },
      { key: "value_area_val_price", label: "AOI-time VAL" },
    ],
  },
  {
    title: "Ordered sweep and reclaim entry",
    fields: [
      { key: "sweep_bar_index", label: "Sweep bar" },
      { key: "sweep_high_price", label: "Sweep-bar high" },
      { key: "sweep_low_price", label: "Sweep-bar low" },
      { key: "sweep_distance_ticks", label: "Applied sweep distance" },
      { key: "sweep_crossing_rule", label: "Ordered crossing rule" },
      { key: "entry_confirmation_kind", label: "Separate confirmation" },
      { key: "entry_trigger_rule", label: "Entry trigger rule" },
      { key: "entry_order_type", label: "Entry order type" },
      { key: "order_activation_at", label: "Order armed at" },
      { key: "entry_reference_price", label: "Fill-event reference" },
      { key: "entry_price", label: "Modeled fill" },
      { key: "entry_event_index", label: "Entry event" },
      { key: "entry_fill_model", label: "Pending-order lifecycle" },
    ],
  },
  {
    title: "Fill-time stop and frozen targets",
    fields: [
      { key: "stop_determined_at_entry", label: "Stop resolved at entry" },
      { key: "stop_resolution_event_index", label: "Stop-resolution event" },
      { key: "sweep_to_entry_high_price", label: "Sweep-to-entry high" },
      { key: "sweep_to_entry_low_price", label: "Sweep-to-entry low" },
      { key: "resolved_stop_price", label: "Resolved protective stop" },
      { key: "initial_stop_price", label: "Engine initial stop" },
      { key: "risk_points", label: "Filled-price risk" },
      { key: "midpoint_reward_r", label: "Midpoint reward/risk" },
      { key: "target_1_price", label: "T1: AOI-time midpoint" },
      { key: "target_2_price", label: "T2: AOI-time opposite edge" },
      { key: "target_1_fraction", label: "T1 position fraction" },
      { key: "contracts", label: "Contracts" },
      { key: "position_sizing_mode", label: "Sizing mode" },
      { key: "execution_instrument", label: "Execution instrument" },
    ],
  },
];

const ADAPTIVE_RANGE_V04_PANELS: StrategyEvidencePanelDefinition[] = [
  {
    title: "Per-bar AOI sources and frozen profile",
    fields: [
      { key: "aoi_identity", label: "Per-bar AOI identity" },
      { key: "aoi_source_kinds", label: "Qualifying AOI sources" },
      { key: "aoi_edge_price", label: "Bar-start value edge" },
      { key: "aoi_zone_low_price", label: "AOI zone low" },
      { key: "aoi_zone_high_price", label: "AOI zone high" },
      { key: "aoi_frozen_bar_index", label: "Source profile bar" },
      { key: "aoi_frozen_at", label: "AOI built at" },
      { key: "market_level_qualified", label: "Market level qualified" },
      { key: "selected_market_level_type", label: "Selected market level" },
      { key: "selected_market_level_price", label: "Market-level price" },
      { key: "institutional_big_trade_qualified", label: "Large execution qualified" },
      { key: "selected_big_trade_side", label: "Selected burst side" },
      { key: "selected_big_trade_low_price", label: "Selected burst low" },
      { key: "selected_big_trade_high_price", label: "Selected burst high" },
      { key: "selected_big_trade_size", label: "Selected burst contracts" },
      { key: "big_trade_threshold_contracts", label: "Large-execution threshold" },
      { key: "institutional_delta_qualified", label: "Four-tick delta qualified" },
      { key: "selected_delta_bin_low_price", label: "Selected delta cell low" },
      { key: "selected_delta_bin_high_price", label: "Selected delta cell high" },
      { key: "selected_delta_signed_delta", label: "Selected signed delta" },
      { key: "selected_delta_bin_abs_delta", label: "Selected absolute delta" },
      { key: "selected_delta_bin_threshold", label: "Delta threshold" },
      { key: "value_area_vah_price", label: "AOI-time VAH" },
      { key: "value_area_poc_price", label: "AOI-time POC" },
      { key: "value_area_val_price", label: "AOI-time VAL" },
    ],
  },
  {
    title: "Ordered sweep, developing-imprint confirmation and reclaim entry",
    fields: [
      { key: "sweep_bar_index", label: "Sweep bar" },
      { key: "sweep_high_price", label: "Sweep-bar high" },
      { key: "sweep_low_price", label: "Sweep-bar low" },
      { key: "sweep_distance_ticks", label: "Applied sweep distance" },
      { key: "sweep_crossing_rule", label: "Ordered crossing rule" },
      { key: "entry_confirmation_kind", label: "Separate confirmation kind" },
      { key: "entry_confirmation_id", label: "Confirmation identity" },
      { key: "entry_confirmation_at", label: "Confirmation qualified at" },
      { key: "entry_confirmation_price", label: "Confirmation label" },
      { key: "entry_confirmation_value", label: "Signed developing imprint" },
      { key: "entry_confirmation_threshold", label: "Completed-imprint q90" },
      { key: "entry_confirmation_bin_low_price", label: "Confirmation cell low" },
      { key: "entry_confirmation_bin_high_price", label: "Confirmation cell high" },
      { key: "entry_confirmation_bar_index", label: "Developing 3-minute bar" },
      { key: "entry_confirmation_bar_start", label: "Developing bar start" },
      { key: "entry_confirmation_bar_end", label: "Developing bar end" },
      {
        key: "entry_confirmation_reference_count",
        label: "Completed bar-cell reference count",
      },
      { key: "entry_confirmation_percentile_method", label: "Percentile method" },
      { key: "entry_confirmation_comparison", label: "Threshold comparison" },
      { key: "entry_zone_boundary_price", label: "Reclaim-side boundary" },
      { key: "entry_trigger_rule", label: "Reclaim-entry rule" },
      { key: "entry_order_type", label: "Entry order type" },
      { key: "order_activation_at", label: "Order armed at" },
      { key: "order_activation_event_index", label: "Order activation event" },
      { key: "entry_reference_price", label: "Fill-event reference" },
      { key: "entry_price", label: "Modeled fill" },
      { key: "entry_event_index", label: "Entry event" },
      { key: "entry_fill_model", label: "Pending-order lifecycle" },
    ],
  },
  {
    title: "Fill-time stop, both frozen targets and sizing",
    fields: [
      { key: "stop_determined_at_entry", label: "Stop resolved at entry" },
      { key: "stop_resolution_event_index", label: "Stop-resolution event" },
      { key: "sweep_to_entry_high_price", label: "Sweep-to-entry high" },
      { key: "sweep_to_entry_low_price", label: "Sweep-to-entry low" },
      { key: "resolved_stop_price", label: "Resolved protective stop" },
      { key: "initial_stop_price", label: "Engine initial stop" },
      { key: "risk_points", label: "Filled-price risk" },
      { key: "midpoint_reward_r", label: "Midpoint reward/risk" },
      { key: "target_1_price", label: "T1: AOI-time midpoint" },
      { key: "target_1_definition", label: "T1 rule" },
      { key: "target_1_fraction", label: "T1 position fraction" },
      { key: "target_2_price", label: "T2: two ticks outside opposite edge" },
      { key: "target_2_definition", label: "T2 rule" },
      { key: "final_target_outside_ticks", label: "T2 outside-edge offset" },
      { key: "target_1_activated", label: "T1 reached" },
      { key: "target_1_activated_at", label: "T1 reached at" },
      { key: "position_sizing_mode", label: "Sizing mode" },
      { key: "position_sizing_net_liq", label: "Net liquidation before sizing" },
      { key: "target_risk_amount", label: "Target dollar risk" },
      { key: "dollar_risk_per_contract", label: "Risk plus costs per contract" },
      { key: "planned_dollar_risk", label: "Planned total risk" },
      { key: "contracts", label: "Contracts" },
      { key: "execution_instrument", label: "Execution instrument" },
    ],
  },
];

const GENERIC_EVENT_PANELS: StrategyEvidencePanelDefinition[] = [
  {
    title: "Strategy decision trace",
    fields: [
      { key: "trigger_kind", label: "Trigger type" },
      { key: "trigger_value", label: "Trigger value" },
      { key: "entry_trigger_price", label: "Entry trigger" },
      { key: "initial_stop_price", label: "Initial stop" },
      { key: "risk_points", label: "Initial risk" },
      { key: "entry_event_index", label: "Entry event" },
      { key: "fill_model", label: "Fill model" },
    ],
  },
];

const VARIANT_PANEL_REGISTRY: Record<
  string,
  StrategyEvidencePanelDefinition[]
> = {
  "yush_orderflow_range:v01": AOI_V01_PANELS,
  "yush_failed_auction_reclaim:v02": FAILED_AUCTION_V02_PANELS,
  "yush_adaptive_orderflow_range:v02": RANGE_EDGE_TRAP_V02_PANELS,
  "yush_adaptive_orderflow_range_v3:v03": ADAPTIVE_RANGE_V03_PANELS,
  "yush_adaptive_orderflow_range_v4:v04": ADAPTIVE_RANGE_V04_PANELS,
};

const STRATEGY_PANEL_REGISTRY: Record<
  string,
  StrategyEvidencePanelDefinition[]
> = {
  yush_orderflow_range: AOI_V01_PANELS,
  yush_failed_auction_reclaim: FAILED_AUCTION_V02_PANELS,
  yush_adaptive_orderflow_range: RANGE_EDGE_TRAP_V02_PANELS,
  yush_adaptive_orderflow_range_v3: ADAPTIVE_RANGE_V03_PANELS,
  yush_adaptive_orderflow_range_v4: ADAPTIVE_RANGE_V04_PANELS,
};

function identityValue(
  evidence: EvidenceIdentity,
  key: "strategy_id" | "variant_id",
): string {
  const value =
    evidence.metadata?.[key] ??
    evidence.trade?.[key] ??
    (key === "strategy_id"
      ? evidence.strategy_context?.strategy_name
      : undefined);
  return String(value ?? "").trim();
}

function hasEvidenceValue(value: unknown): boolean {
  return value !== null && value !== undefined && value !== "";
}

export function resolveStrategyEvidencePanels(
  evidence: EvidenceIdentity,
): ResolvedStrategyEvidencePanel[] {
  const strategyId = identityValue(evidence, "strategy_id");
  const variantId = identityValue(evidence, "variant_id");
  const implementationVersion = Number(
    evidence.metadata?.strategy_implementation_version,
  );
  const definitions =
    strategyId === "yush_adaptive_orderflow_range_v3" &&
    Number.isFinite(implementationVersion) &&
    implementationVersion >= 27
      ? ADAPTIVE_RANGE_V27_PANELS
      : VARIANT_PANEL_REGISTRY[`${strategyId}:${variantId}`] ??
        STRATEGY_PANEL_REGISTRY[strategyId] ??
        GENERIC_EVENT_PANELS;
  const context = evidence.strategy_context ?? {};

  return definitions
    .map((panel) => ({
      title: panel.title,
      rows: panel.fields
        .filter((field) => hasEvidenceValue(context[field.key]))
        .map((field) => ({
          ...field,
          value: context[field.key],
        })),
    }))
    .filter((panel) => panel.rows.length > 0);
}

function recordValue(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function joinedEvidence(parts: unknown[], separator = " · "): string {
  const retained = parts
    .filter((value) => hasEvidenceValue(value))
    .map((value) => String(value));
  return retained.length ? retained.join(separator) : "Not recorded";
}

function labeledEvidence(label: string, value: unknown): string | undefined {
  return hasEvidenceValue(value) ? `${label} ${String(value)}` : undefined;
}

function percentValue(value: unknown): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? `${(parsed * 100).toFixed(1)}%` : "Not recorded";
}

function configuredEntryWindows(params: Record<string, unknown>): string {
  const morning = joinedEvidence(
    [params.morning_entry_start, params.morning_entry_end],
    "–",
  );
  const afternoon = joinedEvidence(
    [params.afternoon_entry_start, params.afternoon_entry_end],
    "–",
  );
  return `${morning}; ${afternoon} New York`;
}

function resolveAdaptiveV27MechanicsComparison(
  evidence: EvidenceIdentity,
): MechanicsComparisonSection[] {
  const frozen = recordValue(evidence.frozen_mechanics);
  const params = recordValue(frozen.event_parameters);
  const execution = recordValue(frozen.execution);
  const sizing = recordValue(execution.position_sizing);
  const context = evidence.strategy_context ?? {};
  const transitions = evidence.event_transitions ?? [];
  if (!Object.keys(params).length || !Object.keys(context).length) return [];
  const lifecycle = transitions.length
    ? transitions.map((row) => row.transition).filter(hasEvidenceValue).map(String).join(" → ")
    : "Not recorded";
  return [
    {
      title: "Per-bar VAH / VAL AOI",
      description: "The latest completed profile independently attempts one AOI at each value edge for the next bar.",
      rows: [
        {
          key: "aoi_source",
          label: "Eligible confluence",
          configured: "q99.9 large execution of either side and/or sign-agnostic top-decile absolute four-tick session delta; market levels do not qualify",
          observed: joinedEvidence([context.aoi_source_kinds, context.aoi_identity]),
        },
        {
          key: "source_location",
          label: "Search radius",
          configured: `${params.context_distance_atr_fraction} ATR above or below the latest VAH / VAL at every three-minute boundary`,
          observed: joinedEvidence([
            `${context.context_distance_ticks} ticks applied`,
            `edge ${context.aoi_edge_price}`,
            `zone ${context.aoi_zone_low_price}–${context.aoi_zone_high_price}`,
          ]),
        },
        {
          key: "profile_snapshot",
          label: "AOI-time profile",
          configured: `${params.value_area_method}; ${percentValue(params.value_area_fraction)} value area; rebuilt each completed three-minute bar; no afternoon reset`,
          observed: joinedEvidence([
            context.aoi_frozen_at,
            `VAH ${context.value_area_vah_price}`,
            `POC ${context.value_area_poc_price}`,
            `VAL ${context.value_area_val_price}`,
          ]),
        },
      ],
    },
    {
      title: "Ordered sweep and reclaim entry",
      description: "The completed ordered sweep arms the reclaim stop entry without another order-flow confirmation.",
      rows: [
        {
          key: "sweep",
          label: "Ordered sweep",
          configured: `inside-edge event followed by an outward event at max(${params.sweep_minimum_ticks} ticks, ${params.sweep_atr_fraction} ATR) during the AOI's next bar`,
          observed: joinedEvidence([
            `${context.sweep_distance_ticks} ticks applied`,
            `high ${context.sweep_high_price}`,
            `low ${context.sweep_low_price}`,
            `bar ${context.sweep_bar_index}`,
          ]),
        },
        {
          key: "confirmation",
          label: "Separate confirmation",
          configured: "Not required; the completed ordered sweep immediately arms the order",
          observed: joinedEvidence([context.entry_confirmation_kind, context.order_activation_at]),
        },
        {
          key: "entry_order",
          label: "AOI-zone reclaim stop",
          configured: `${params.entry_offset_ticks} ticks beyond the reclaim-side AOI-zone boundary; no clock expiry and no pre-fill intended-stop invalidation`,
          observed: joinedEvidence([
            context.entry_order_type,
            `boundary ${context.entry_zone_boundary_price}`,
            `reference ${context.entry_reference_price}`,
            `fill ${context.entry_price}`,
          ]),
        },
        {
          key: "order_lifecycle",
          label: "Observed lifecycle",
          configured: joinedEvidence([
            execution.event_stop_market_fill_policy,
            "no clock expiry",
            "no pre-fill intended-stop invalidation",
          ]),
          observed: joinedEvidence([context.entry_fill_model, lifecycle]),
        },
      ],
    },
    {
      title: "Fill-time structural stop",
      description: "No stop is guessed while the entry is pending; it is resolved before sizing on the exact fill event.",
      rows: [
        {
          key: "stop",
          label: "Sweep-to-entry stop",
          configured: `${params.stop_offset_ticks} ticks beyond the adverse extreme from the sweep bar through the entry event; minimum ${params.minimum_stop_ticks} ticks; maximum ${params.maximum_stop_atr_multiple} ATR`,
          observed: joinedEvidence([
            `path ${context.sweep_to_entry_low_price}–${context.sweep_to_entry_high_price}`,
            `stop ${context.resolved_stop_price ?? context.initial_stop_price}`,
            `event ${context.stop_resolution_event_index}`,
            `risk ${context.risk_points} points`,
          ]),
        },
        {
          key: "payoff_gate",
          label: "Fill-time midpoint gate",
          configured: `gross midpoint reward / resolved structural risk at least ${params.minimum_midpoint_reward_r}`,
          observed: `midpoint R ${context.midpoint_reward_r}`,
        },
      ],
    },
    {
      title: "AOI-time targets",
      description: "Targets stay attached to the profile that created the swept AOI.",
      rows: [
        {
          key: "targets",
          label: "Two-stage exit",
          configured: `${percentValue(params.target_1_fraction)} at AOI-time midpoint; remainder at AOI-time opposite value edge`,
          observed: joinedEvidence([`T1 ${context.target_1_price}`, `T2 ${context.target_2_price}`, context.partial_exit_legs]),
        },
      ],
    },
    {
      title: "Sizing and execution assumptions",
      description: "The resolved stop is validated and then used for MES risk sizing.",
      rows: [
        {
          key: "position_sizing",
          label: "Position sizing",
          configured: `${sizing.mode}; ${percentValue(sizing.risk_pct)} net liquidation risk; floor; minimum ${sizing.min_contracts} contract`,
          observed: joinedEvidence([`${context.contracts} contracts`, `planned risk ${context.planned_dollar_risk}`]),
        },
        {
          key: "execution",
          label: "Execution model",
          configured: joinedEvidence([
            `${execution.signal_instrument} signal / ${execution.execution_instrument} execution`,
            `${execution.entry_slippage_ticks} entry-slippage tick`,
            `${execution.protective_stop_slippage_ticks} stop-slippage tick`,
          ]),
          observed: joinedEvidence([context.signal_instrument, context.execution_instrument]),
        },
      ],
    },
  ];
}

function resolveAdaptiveV04MechanicsComparison(
  evidence: EvidenceIdentity,
): MechanicsComparisonSection[] {
  const frozen = recordValue(evidence.frozen_mechanics);
  const params = recordValue(frozen.event_parameters);
  const execution = recordValue(frozen.execution);
  const sizing = recordValue(execution.position_sizing);
  const protocol = recordValue(frozen.protocol);
  const context = evidence.strategy_context ?? {};
  const trade = evidence.trade ?? {};
  const transitions = evidence.event_transitions ?? [];
  if (!Object.keys(params).length || !Object.keys(context).length) return [];

  const lifecycle = transitions.length
    ? transitions
        .map((row) => row.transition)
        .filter(hasEvidenceValue)
        .map(String)
        .join(" → ")
    : "Not recorded";
  const outsideTargetTicks = 2;

  return [
    {
      title: "Per-bar VAH / VAL AOI",
      description:
        "Each completed three-minute profile independently attempts a short VAH AOI and a long VAL AOI for the next bar.",
      rows: [
        {
          key: "aoi_source",
          label: "Eligible AOI sources",
          configured: joinedEvidence([
            "any nearby PDH, PDL, PDC, ONH, ONL, ORH or ORL may independently qualify",
            `${percentValue(params.big_trade_reference_percentile)} prior-${params.big_trade_lookback_sessions}-session large execution of either aggressor side`,
            `sign-agnostic top-${percentValue(params.delta_profile_percentile)} absolute four-tick developing-profile delta`,
          ]),
          observed: joinedEvidence([
            context.aoi_source_kinds,
            context.aoi_identity,
          ]),
        },
        {
          key: "market_level_source",
          label: "Market-level route",
          configured:
            "A nearby market level can qualify the AOI without a large execution or delta cell.",
          observed: joinedEvidence([
            labeledEvidence("qualified", context.market_level_qualified),
            context.selected_market_level_type,
            context.selected_market_level_price,
          ]),
        },
        {
          key: "large_execution_source",
          label: "Large-execution route",
          configured: `${percentValue(params.big_trade_reference_percentile)} MotiveWave-compatible consecutive executions at one price and aggressor side within ${params.big_trade_interval_ms} ms; either side can qualify`,
          observed: joinedEvidence([
            labeledEvidence(
              "qualified",
              context.institutional_big_trade_qualified,
            ),
            labeledEvidence("contracts", context.selected_big_trade_size),
            labeledEvidence("threshold", context.big_trade_threshold_contracts),
            joinedEvidence(
              [
                context.selected_big_trade_low_price,
                context.selected_big_trade_high_price,
              ],
              "–",
            ),
            context.selected_big_trade_side,
          ]),
        },
        {
          key: "delta_source",
          label: "Four-tick delta route",
          configured: `Sign-agnostic absolute developing-profile delta at or above ${percentValue(params.delta_profile_percentile)} across MotiveWave-style ${params.delta_profile_price_bin_ticks}-tick cells`,
          observed: joinedEvidence([
            labeledEvidence(
              "qualified",
              context.institutional_delta_qualified,
            ),
            labeledEvidence("signed", context.selected_delta_signed_delta),
            labeledEvidence("absolute", context.selected_delta_bin_abs_delta),
            labeledEvidence("threshold", context.selected_delta_bin_threshold),
            joinedEvidence(
              [
                context.selected_delta_bin_low_price,
                context.selected_delta_bin_high_price,
              ],
              "–",
            ),
          ]),
        },
        {
          key: "source_location",
          label: "Causal search radius",
          configured: `${params.context_distance_atr_fraction} ATR above or below the latest VAH / VAL at every completed three-minute boundary`,
          observed: joinedEvidence([
            labeledEvidence("applied ticks", context.context_distance_ticks),
            labeledEvidence("edge", context.aoi_edge_price),
            joinedEvidence(
              [context.aoi_zone_low_price, context.aoi_zone_high_price],
              "–",
            ),
          ]),
        },
        {
          key: "profile_snapshot",
          label: "AOI-time profile",
          configured: `${params.value_area_method}; ${percentValue(params.value_area_fraction)} value area; one RTH profile rebuilt each completed three-minute bar without an afternoon reset`,
          observed: joinedEvidence([
            context.aoi_frozen_at,
            labeledEvidence("VAH", context.value_area_vah_price),
            labeledEvidence("POC", context.value_area_poc_price),
            labeledEvidence("VAL", context.value_area_val_price),
          ]),
        },
      ],
    },
    {
      title: "Ordered sweep, developing-imprint confirmation and reclaim entry",
      description:
        "After the ordered sweep, a distinct later big trade or a causal observation of a qualifying whole developing three-minute/four-tick imprint is required before the reclaim stop order can exist.",
      rows: [
        {
          key: "sweep",
          label: "Ordered sweep",
          configured: `inside-edge event followed by a later outward event at max(${params.sweep_minimum_ticks} ticks, ${params.sweep_atr_fraction} ATR) during the AOI's next bar`,
          observed: joinedEvidence([
            labeledEvidence("applied ticks", context.sweep_distance_ticks),
            labeledEvidence("high", context.sweep_high_price),
            labeledEvidence("low", context.sweep_low_price),
            labeledEvidence("bar", context.sweep_bar_index),
          ]),
        },
        {
          key: "separate_confirmation",
          label: "Post-sweep confirmation",
          configured:
            `Required: a distinct q99.9 large execution started after the sweep, or an eligible cell in the whole developing three-minute bar whose absolute ${params.delta_profile_price_bin_ticks}-tick delta is strictly greater than nearest-rank ${percentValue(params.delta_profile_percentile)} of every earlier completed RTH three-minute bar-cell imprint. The developing imprint starts at the bar boundary, not the sweep, and the current bar is excluded from its reference distribution.`,
          observed: joinedEvidence([
            context.entry_confirmation_kind,
            context.entry_confirmation_id,
            context.entry_confirmation_at,
            labeledEvidence("bar", context.entry_confirmation_bar_index),
            joinedEvidence(
              [
                context.entry_confirmation_bar_start,
                context.entry_confirmation_bar_end,
              ],
              "–",
            ),
            labeledEvidence("label", context.entry_confirmation_price),
            labeledEvidence("signed imprint", context.entry_confirmation_value),
            labeledEvidence("q90", context.entry_confirmation_threshold),
            labeledEvidence(
              "completed references",
              context.entry_confirmation_reference_count,
            ),
          ]),
        },
        {
          key: "confirmation_location",
          label: "Confirmation location",
          configured:
            "Short confirmation label must be strictly above the frozen AOI-zone bottom; long confirmation label must be strictly below the frozen AOI-zone top.",
          observed: joinedEvidence([
            labeledEvidence("confirmation", context.entry_confirmation_price),
            joinedEvidence(
              [
                context.entry_confirmation_bin_low_price,
                context.entry_confirmation_bin_high_price,
              ],
              "–",
            ),
            labeledEvidence("zone boundary", context.entry_zone_boundary_price),
          ]),
        },
        {
          key: "reclaim_entry",
          label: "AOI-zone reclaim stop",
          configured: `${params.entry_offset_ticks} ticks beyond the reclaim-side AOI-zone boundary after confirmation; no clock expiry and no pre-fill intended-stop invalidation`,
          observed: joinedEvidence([
            context.entry_order_type,
            labeledEvidence("boundary", context.entry_zone_boundary_price),
            labeledEvidence("reference", context.entry_reference_price),
            labeledEvidence("fill", context.entry_price),
          ]),
        },
        {
          key: "order_lifecycle",
          label: "Observed lifecycle",
          configured: context.entry_fill_model,
          observed: lifecycle,
        },
      ],
    },
    {
      title: "Fill-time structural stop",
      description:
        "The order has no guessed stop; the exact fill event resolves and validates the full sweep-to-entry path before sizing.",
      rows: [
        {
          key: "stop",
          label: "Sweep-to-entry stop",
          configured: `${params.stop_offset_ticks} ticks beyond the adverse extreme from the entire sweep bar through the fill event; minimum ${params.minimum_stop_ticks} ticks; maximum ${params.maximum_stop_atr_multiple} ATR`,
          observed: joinedEvidence([
            joinedEvidence(
              [
                context.sweep_to_entry_low_price,
                context.sweep_to_entry_high_price,
              ],
              "–",
            ),
            labeledEvidence(
              "stop",
              context.resolved_stop_price ?? context.initial_stop_price,
            ),
            labeledEvidence("event", context.stop_resolution_event_index),
            labeledEvidence("risk points", context.risk_points),
          ]),
        },
        {
          key: "payoff_gate",
          label: "Fill-time midpoint gate",
          configured: `gross midpoint reward / resolved structural risk at least ${params.minimum_midpoint_reward_r}`,
          observed: labeledEvidence("midpoint R", context.midpoint_reward_r),
        },
      ],
    },
    {
      title: "AOI-time two-stage targets",
      description:
        "Both targets remain bound to the profile that created the swept AOI.",
      rows: [
        {
          key: "target_1",
          label: "T1 frozen midpoint",
          configured: `${percentValue(params.target_1_fraction)} of the position exits at the AOI-time value-area midpoint`,
          observed: joinedEvidence([
            labeledEvidence("T1", context.target_1_price),
            context.target_1_definition,
            labeledEvidence("reached", context.target_1_activated),
            context.target_1_activated_at,
          ]),
        },
        {
          key: "target_2",
          label: "T2 outside opposite edge",
          configured: `remainder exits ${outsideTargetTicks} ticks outside the AOI-time opposite value edge: below frozen VAL for a short, above frozen VAH for a long`,
          observed: joinedEvidence([
            labeledEvidence("T2", context.target_2_price),
            context.target_2_definition,
            labeledEvidence(
              "outside ticks",
              context.final_target_outside_ticks,
            ),
          ]),
        },
      ],
    },
    {
      title: "Sizing and execution assumptions",
      description:
        "The validated fill-time stop determines integer MES sizing under the certified risk and cost policy.",
      rows: [
        {
          key: "position_sizing",
          label: "Position sizing",
          configured: `${sizing.mode}; ${percentValue(sizing.risk_pct)} current net-liquidation risk; ${sizing.rounding}; minimum ${sizing.min_contracts} contract`,
          observed: joinedEvidence([
            labeledEvidence("mode", context.position_sizing_mode),
            labeledEvidence("net liq", context.position_sizing_net_liq),
            labeledEvidence("target risk", context.target_risk_amount),
            labeledEvidence(
              "per contract",
              context.dollar_risk_per_contract,
            ),
            labeledEvidence("planned risk", context.planned_dollar_risk),
            labeledEvidence("contracts", context.contracts),
          ]),
        },
        {
          key: "minimum_contract",
          label: "Minimum-contract affordability",
          configured:
            "Reject only when one MES including modeled stop slippage and round-turn commission exceeds the certified risk budget.",
          observed: context.minimum_contract_affordability_rule,
        },
        {
          key: "execution",
          label: "Execution model",
          configured: joinedEvidence([
            `${execution.signal_instrument} signal / ${execution.execution_instrument} execution`,
            labeledEvidence("entry slippage ticks", execution.entry_slippage_ticks),
            labeledEvidence(
              "protective-stop slippage ticks",
              execution.protective_stop_slippage_ticks,
            ),
            labeledEvidence(
              "commission per contract per side",
              execution.commission_per_contract,
            ),
          ]),
          observed: joinedEvidence([
            context.signal_instrument,
            context.execution_instrument,
            trade.contract,
          ]),
        },
        {
          key: "session",
          label: "Entry and forced-flat boundaries",
          configured: `${configuredEntryWindows(params)}; flatten ${protocol.force_flatten_time ?? execution.flatten_time}`,
          observed: joinedEvidence([
            trade.entry_time ?? trade.entry_timestamp,
            trade.exit_time ?? trade.exit_timestamp,
          ]),
        },
      ],
    },
  ];
}

/**
 * Build the reviewer-facing v18 contract as configured-rule versus observed
 * evidence.  Configured values come from the hash-bound YAML projection, never
 * from values reverse-engineered out of the realized trade.
 */
export function resolveAdaptiveV18MechanicsComparison(
  evidence: EvidenceIdentity,
): MechanicsComparisonSection[] {
  const implementationVersion = Number(
    evidence.metadata?.strategy_implementation_version,
  );
  const usesAtrContextImmediateOrder =
    !Number.isNaN(implementationVersion) && implementationVersion >= 20;
  const usesInsideEdgeStopEntry =
    !Number.isNaN(implementationVersion) && implementationVersion >= 21;
  const usesSymmetricAoiContext =
    !Number.isNaN(implementationVersion) && implementationVersion >= 22;
  const usesMotiveWaveConsecutiveBursts =
    !Number.isNaN(implementationVersion) && implementationVersion >= 23;
  const usesFourTickHistoricalDelta =
    !Number.isNaN(implementationVersion) && implementationVersion >= 24;
  const usesDirectionNeutralAoiOrderflow =
    !Number.isNaN(implementationVersion) && implementationVersion >= 25;
  const usesAoiZoneEntry =
    !Number.isNaN(implementationVersion) && implementationVersion >= 26;
  if (
    identityValue(evidence, "strategy_id") !==
      "yush_adaptive_orderflow_range_v3" ||
    (!Number.isNaN(implementationVersion) && implementationVersion < 18)
  ) {
    return [];
  }
  if (Number.isFinite(implementationVersion) && implementationVersion >= 27) {
    return resolveAdaptiveV27MechanicsComparison(evidence);
  }
  const frozen = recordValue(evidence.frozen_mechanics);
  const params = recordValue(frozen.event_parameters);
  const execution = recordValue(frozen.execution);
  const sizing = recordValue(execution.position_sizing);
  const protocol = recordValue(frozen.protocol);
  const context = evidence.strategy_context ?? {};
  const trade = evidence.trade ?? {};
  const transitions = evidence.event_transitions ?? [];
  if (!Object.keys(params).length || !Object.keys(context).length) return [];

  const edge = context.aoi_edge_price;
  const sourceLocation = joinedEvidence([
    hasEvidenceValue(context.selected_big_trade_low_price)
      ? `burst ${context.selected_big_trade_low_price}–${context.selected_big_trade_high_price}`
      : null,
    hasEvidenceValue(context.selected_delta_bin_low_price)
      ? `delta row ${context.selected_delta_bin_low_price}–${context.selected_delta_bin_high_price}`
      : null,
    hasEvidenceValue(context.selected_market_level_type)
      ? `${context.selected_market_level_type} ${context.selected_market_level_price}`
      : null,
  ]);
  const lifecycle = transitions.length
    ? transitions
        .map((row) => row.transition)
        .filter(hasEvidenceValue)
        .map(String)
        .join(" → ")
    : "Not recorded";
  const configuredStop = usesFourTickHistoricalDelta
    ? `${params.minimum_stop_ticks} tick minimum; maximum ${params.maximum_stop_atr_multiple} ATR; ${params.stop_offset_ticks} ticks beyond ordered sweep-bar extreme`
    : usesAtrContextImmediateOrder
    ? `${params.minimum_stop_ticks} tick minimum; maximum ${params.maximum_stop_atr_multiple} ATR; stop at ordered sweep-bar extreme`
    : `${params.minimum_stop_ticks} tick minimum; maximum ${params.maximum_stop_atr_multiple} ATR; ${params.stop_offset_ticks} tick beyond adverse sweep-to-reclaim extreme`;
  const configuredCosts = joinedEvidence([
    `commission ${execution.commission_per_contract} per contract/side`,
    `entry slippage ${execution.entry_slippage_ticks} tick`,
    `stop slippage ${execution.protective_stop_slippage_ticks} tick`,
    `target slippage ${execution.target_limit_slippage_ticks} ticks`,
  ]);

  return [
    {
      title: "AOI source and frozen profile",
      description: "Why this exact VAH or VAL became eligible and what was frozen.",
      rows: [
        {
          key: "aoi_source",
          label: "Eligible AOI source",
          configured: usesDirectionNeutralAoiOrderflow
            ? "VAH/VAL plus any one of: q99.9 aggressive burst of either side, sign-agnostic top-decile absolute profile delta, or compatible completed market level"
            : "VAH/VAL plus any one of: q99.9 aggressive burst, directional top-decile profile delta, or compatible completed market level",
          observed: joinedEvidence([
            context.aoi_source_kinds,
            context.aoi_identity,
          ]),
        },
        {
          key: "source_location",
          label: "Source location around edge",
          configured: usesSymmetricAoiContext
            ? `${params.context_distance_atr_fraction} ATR above or below the exact value edge, frozen at AOI creation`
            : usesAtrContextImmediateOrder
              ? `${params.context_distance_atr_fraction} ATR outward from the exact value edge, frozen at AOI creation`
            : `${params.aoi_level_distance_ticks} ticks outward from the exact value edge`,
          observed: joinedEvidence([
            `edge ${edge}`,
            usesAtrContextImmediateOrder
              ? `${context.context_distance_ticks} ticks applied`
              : null,
            sourceLocation,
          ]),
        },
        ...(usesAoiZoneEntry
          ? [
              {
                key: "aoi_zone",
                label: "Frozen AOI zone",
                configured:
                  "Minimum-to-maximum price span containing the frozen edge and every selected confluence-source bound",
                observed: joinedEvidence([
                  `${context.aoi_zone_low_price}–${context.aoi_zone_high_price}`,
                  `reclaim-side boundary ${context.entry_zone_boundary_price}`,
                ]),
              },
            ]
          : []),
        {
          key: "large_execution_source",
          label: "Large-execution source",
          configured: usesAtrContextImmediateOrder
            ? `q${Number(params.big_trade_reference_percentile) * 100}; prior ${params.big_trade_lookback_sessions} sessions; ${params.big_trade_interval_ms} ms ${usesMotiveWaveConsecutiveBursts ? "consecutive same-price/aggressor sequences" : "cells"}; any burst in the current RTH session${usesDirectionNeutralAoiOrderflow ? "; either aggressor side may form the AOI" : ""}`
            : `q${Number(params.big_trade_reference_percentile) * 100}; prior ${params.big_trade_lookback_sessions} sessions; ${params.big_trade_interval_ms} ms cells; fresh for ${params.burst_freshness_bars} bars`,
          observed: joinedEvidence([
            `qualified ${context.institutional_big_trade_qualified}`,
            hasEvidenceValue(context.selected_big_trade_size)
              ? `${context.selected_big_trade_size} contracts versus ${context.big_trade_threshold_contracts}`
              : null,
            context.selected_big_trade_qualified_at,
          ]),
        },
        {
          key: "delta_source",
          label: "Delta-profile source",
          configured: `${usesDirectionNeutralAoiOrderflow ? "sign-agnostic" : "directional"} top ${100 - Number(params.delta_profile_percentile) * 100}% absolute delta; ${usesFourTickHistoricalDelta ? params.delta_profile_price_bin_ticks : params.price_bin_ticks}-tick ${usesFourTickHistoricalDelta ? "MotiveWave fixed cells" : "rows"}`,
          observed: joinedEvidence([
            `qualified ${context.institutional_delta_qualified}`,
            hasEvidenceValue(context.selected_delta_signed_delta)
              ? `signed delta ${context.selected_delta_signed_delta} versus threshold ${context.selected_delta_bin_threshold}`
              : null,
            hasEvidenceValue(context.selected_delta_bin_low_price)
              ? `row ${context.selected_delta_bin_low_price}`
              : null,
          ]),
        },
        {
          key: "market_level_source",
          label: "Market-level source",
          configured: `PDH/PDL, causal ONH/ONL, or completed ${params.opening_range_seconds}-second ORH/ORL`,
          observed: joinedEvidence([
            `qualified ${context.market_level_qualified}`,
            context.selected_market_level_type,
            context.selected_market_level_price,
          ]),
        },
        {
          key: "profile_snapshot",
          label: "Frozen profile snapshot",
          configured: `${params.value_area_method}; ${percentValue(params.value_area_fraction)} value area; ${params.profile_warmup_bars}-bar warmup; reset ${params.afternoon_profile_reset}`,
          observed: joinedEvidence([
            context.profile_epoch,
            `VAH ${context.value_area_vah_price}`,
            `POC ${context.value_area_poc_price}`,
            `VAL ${context.value_area_val_price}`,
            context.aoi_frozen_at,
          ]),
        },
      ],
    },
    {
      title: "Separate post-AOI confirmation",
      description: "Fresh order flow that is distinct from the observation which created the AOI.",
      rows: [
        {
          key: "confirmation_type",
          label: "Permitted confirmation",
          configured: usesFourTickHistoricalDelta
            ? `A different post-AOI q99.9 burst or a later completed-bar directional ${params.delta_profile_price_bin_ticks}-tick delta cell reaching prior-${params.confirmation_delta_lookback_sessions}-session q${Number(params.confirmation_delta_reference_percentile) * 100}`
            : "A different post-AOI q99.9 burst or a later completed-bar directional top-decile delta row",
          observed: joinedEvidence([
            context.entry_confirmation_kind,
            context.entry_confirmation_id,
          ]),
        },
        {
          key: "confirmation_timing",
          label: "Causal timing",
          configured: usesAtrContextImmediateOrder
            ? `Strictly after AOI freeze and within ${params.failure_confirmation_bars} completed bars after the sweep`
            : "Strictly after AOI freeze and available no later than the first inside reclaim",
          observed: joinedEvidence([
            `AOI ${context.aoi_frozen_at}`,
            `confirmation ${context.entry_confirmation_at}`,
            usesAtrContextImmediateOrder
              ? `order activation ${context.order_activation_at}`
              : `reclaim ${context.reclaim_confirmation_at}`,
          ]),
        },
        {
          key: "confirmation_direction_location",
          label: "Direction and location",
          configured: joinedEvidence([
            context.burst_direction_rule,
            usesAtrContextImmediateOrder
              ? `${params.context_distance_atr_fraction} ATR outward (${context.context_distance_ticks} ticks frozen)`
              : `${params.aoi_level_distance_ticks} ticks outward`,
          ]),
          observed: joinedEvidence([
            hasEvidenceValue(context.entry_confirmation_bin_low_price)
              ? `${context.entry_confirmation_bin_low_price}–${context.entry_confirmation_bin_high_price}`
              : context.entry_confirmation_price,
            `magnitude ${context.entry_confirmation_value}`,
            hasEvidenceValue(context.entry_confirmation_threshold)
              ? `threshold ${context.entry_confirmation_threshold}`
              : null,
          ]),
        },
      ],
    },
    {
      title: usesInsideEdgeStopEntry
        ? "Sweep, confirmation and stop-entry lifecycle"
        : usesAtrContextImmediateOrder
          ? "Sweep, confirmation and order lifecycle"
        : "Sweep, reclaim and order lifecycle",
      description: "Ordered-event proof of the failed auction and the subsequent resting-limit behavior.",
      rows: [
        {
          key: "sweep",
          label: "Ordered sweep",
          configured: `at least ${params.sweep_minimum_ticks} ticks and ${params.sweep_atr_fraction} ATR after an inside-edge crossing`,
          observed: joinedEvidence([
            `${context.sweep_distance_ticks} ticks applied`,
            `high ${context.sweep_high_price}`,
            `low ${context.sweep_low_price}`,
            `bar ${context.sweep_bar_index}`,
          ]),
        },
        {
          key: usesAtrContextImmediateOrder ? "order_activation" : "reclaim",
          label: usesAtrContextImmediateOrder
            ? "Immediate order activation"
            : "Event-level reclaim",
          configured: usesInsideEdgeStopEntry
            ? usesAoiZoneEntry
              ? `after separate order-flow confirmation; stop trigger crossing beyond the full AOI zone proves reclaim; gross midpoint reward/risk at least ${params.minimum_midpoint_reward_r}`
              : `after separate order-flow confirmation; stop trigger crossing inside value proves reclaim; gross midpoint reward/risk at least ${params.minimum_midpoint_reward_r}`
            : usesAtrContextImmediateOrder
              ? `after separate order-flow confirmation; no reclaim; gross midpoint reward/risk at least ${params.minimum_midpoint_reward_r}`
            : `first ordered trade ${params.entry_offset_ticks} tick inside within ${params.failure_confirmation_bars} completed bars after the sweep bar`,
          observed: usesAtrContextImmediateOrder
            ? joinedEvidence([
                context.order_activation_at,
                `event ${context.order_activation_event_index}`,
                `midpoint R ${context.midpoint_reward_r}`,
              ])
            : joinedEvidence([
                context.reclaim_confirmation_at,
                `event ${context.reclaim_event_index}`,
                `price ${context.reclaim_event_price}`,
              ]),
        },
        {
          key: "limit_order",
          label: usesInsideEdgeStopEntry
            ? usesAoiZoneEntry
              ? "AOI-zone reclaim stop-market entry"
              : "Inside-edge stop-market entry"
            : usesAtrContextImmediateOrder
              ? "Resting outside-edge limit"
            : "Resting edge-retest limit",
          configured: usesInsideEdgeStopEntry
            ? usesAoiZoneEntry
              ? `Armed immediately after confirmation ${params.entry_offset_ticks} ticks beyond the reclaim-side AOI-zone boundary (zone low minus for short; zone high plus for long); gap-aware stop-market fill; no clock/bar expiry; cancel if the initial stop trades first`
              : `Armed immediately after confirmation at ${params.entry_offset_ticks} tick inside the frozen edge (VAH minus for short; VAL plus for long); gap-aware stop-market fill; no clock/bar expiry; cancel if the initial stop trades first`
            : usesAtrContextImmediateOrder
              ? `Armed immediately after confirmation at ${params.entry_offset_ticks} tick outside the frozen edge; no clock/bar expiry; cancel if the initial stop trades first`
            : "Armed by the confirmed reclaim; no clock/bar expiry; cancel if the initial stop trades first",
          observed: joinedEvidence([
            context.entry_order_type,
            `reference ${context.entry_reference_price}`,
            `fill ${context.entry_price}`,
            `fill gate ${context.actual_fill_gate_passed}`,
          ]),
        },
        {
          key: "order_lifecycle",
          label: "Retained order lifecycle",
          configured: context.entry_fill_model,
          observed: lifecycle,
        },
      ],
    },
    {
      title: "Stop and both frozen targets",
      description: "The complete risk and scale-out contract used for this trade.",
      rows: [
        {
          key: "stop",
          label: "Structural protective stop",
          configured: configuredStop,
          observed: joinedEvidence([
            `initial ${context.initial_stop_price}`,
            `${context.planned_stop_ticks} ticks`,
            `${context.risk_points} points from fill`,
          ]),
        },
        {
          key: "targets",
          label: "Frozen scale-out targets",
          configured: `${percentValue(params.target_1_fraction)} at frozen midpoint; remainder at frozen opposite value edge`,
          observed: joinedEvidence([
            `T1 ${context.target_1_price}`,
            `T2 ${context.target_2_price}`,
            context.partial_exit_legs,
          ]),
        },
        {
          key: "payoff_gate",
          label: usesAtrContextImmediateOrder
            ? "Pre-order midpoint payoff gate"
            : "Fill-time payoff gate",
          configured: usesAtrContextImmediateOrder
            ? `gross midpoint reward / structural stop risk at least ${params.minimum_midpoint_reward_r}; ignore weighted net reward`
            : `weighted net reward / worst-case loss at least ${params.minimum_net_reward_to_worst_case_loss}`,
          observed: usesAtrContextImmediateOrder
            ? joinedEvidence([
                `midpoint R ${context.midpoint_reward_r}`,
                `stop loss ${context.worst_case_stop_loss_dollars_per_contract} per contract`,
              ])
            : joinedEvidence([
                `ratio ${context.net_reward_to_worst_case_loss}`,
                `reward ${context.net_target_reward_dollars_per_contract} per contract`,
                `loss ${context.worst_case_stop_loss_dollars_per_contract} per contract`,
              ]),
        },
        {
          key: "maximum_hold",
          label: "Maximum holding period",
          configured: `${params.maximum_holding_bars} completed bars`,
          observed: joinedEvidence([
            trade.exit_reason,
            trade.exit_time ?? trade.exit_timestamp,
          ]),
        },
      ],
    },
    {
      title: "Sizing and execution assumptions",
      description: "Instrument mapping, risk budget, costs, session windows and forced-flat boundary.",
      rows: [
        {
          key: "instruments",
          label: "Signal and execution instruments",
          configured: `${execution.signal_instrument} signal / ${execution.execution_instrument} execution`,
          observed: joinedEvidence([
            context.signal_instrument,
            context.execution_instrument,
            trade.contract,
          ]),
        },
        {
          key: "position_sizing",
          label: "Position sizing",
          configured: `${sizing.mode}; ${percentValue(sizing.risk_pct)} net liquidation risk; floor; minimum ${sizing.min_contracts} contract`,
          observed: joinedEvidence([
            `${context.contracts} contracts`,
            `target risk ${context.target_risk_amount}`,
            `planned risk ${context.planned_dollar_risk}`,
          ]),
        },
        {
          key: "costs",
          label: "Execution costs",
          configured: configuredCosts,
          observed: joinedEvidence([
            `commission ${context.commission}`,
            `slippage ${context.slippage_cost}`,
            `total ${context.total_transaction_cost}`,
          ]),
        },
        {
          key: "session",
          label: "Entry and forced-flat boundaries",
          configured: `${configuredEntryWindows(params)}; flatten ${protocol.force_flatten_time ?? execution.flatten_time}`,
          observed: joinedEvidence([
            trade.entry_time ?? trade.entry_timestamp,
            trade.exit_time ?? trade.exit_timestamp,
          ]),
        },
      ],
    },
  ];
}

export function resolveMechanicsComparison(
  evidence: EvidenceIdentity,
): MechanicsComparisonSection[] {
  if (
    identityValue(evidence, "strategy_id") ===
    "yush_adaptive_orderflow_range_v4"
  ) {
    return resolveAdaptiveV04MechanicsComparison(evidence);
  }
  return resolveAdaptiveV18MechanicsComparison(evidence);
}

function retainedBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function compactNumber(value: unknown): string {
  const number = Number(value);
  return Number.isFinite(number)
    ? new Intl.NumberFormat("en-US", { maximumFractionDigits: 3 }).format(number)
    : "not retained";
}

export function resolveFrozenSetup(
  evidence: EvidenceIdentity,
): FrozenSetupSummary | null {
  const strategyId = identityValue(evidence, "strategy_id");
  if (
    strategyId !== "yush_adaptive_orderflow_range_v3" &&
    strategyId !== "yush_adaptive_orderflow_range_v4"
  ) {
    return null;
  }
  const context = evidence.strategy_context ?? {};
  if (
    !hasEvidenceValue(context.aoi_edge_price) &&
    !hasEvidenceValue(context.value_area_poc_price) &&
    !hasEvidenceValue(context.selected_big_trade_size) &&
    !hasEvidenceValue(context.aoi_frozen_at)
  ) {
    return null;
  }
  const direction = String(
    evidence.trade?.direction ?? context.direction ?? "",
  ).toLowerCase();
  return {
    direction,
    edgeRole:
      direction === "short"
        ? "VAH"
        : direction === "long"
          ? "VAL"
          : "value edge",
    sourceKinds: context.aoi_source_kinds,
    edgePrice: context.aoi_edge_price,
    pocPrice: context.value_area_poc_price,
    vahPrice: context.value_area_vah_price,
    valPrice: context.value_area_val_price,
    aoiArmedAt: context.aoi_frozen_at,
    burstSize: context.selected_big_trade_size,
    burstThreshold: context.big_trade_threshold_contracts,
    burstQualifiedAt: context.selected_big_trade_qualified_at,
    burstSide: context.selected_big_trade_side,
    burstPriceLow: context.selected_big_trade_low_price,
    burstPriceHigh: context.selected_big_trade_high_price,
    ...(strategyId === "yush_adaptive_orderflow_range_v4"
      ? {
          sourceDescription:
            "The AOI may be independently qualified by a nearby market level, a direction-neutral large execution, or sign-agnostic absolute four-tick delta. Entry still requires a distinct later large execution or a qualifying whole developing three-minute/four-tick delta imprint.",
        }
      : {}),
  };
}

export function resolveQualifyingFootprint(
  evidence: EvidenceIdentity,
): QualifyingFootprintSummary | null {
  if (identityValue(evidence, "strategy_id") !== "yush_adaptive_orderflow_range") {
    return null;
  }
  const context = evidence.strategy_context ?? {};
  const bigQualified = retainedBoolean(
    context.institutional_big_trade_qualified,
  );
  const deltaQualified = retainedBoolean(
    context.institutional_delta_qualified,
  );
  if (
    bigQualified === null &&
    deltaQualified === null &&
    !hasEvidenceValue(context.institutional_footprint_kind)
  ) {
    return null;
  }
  const qualifiedRoutes = [bigQualified, deltaQualified].filter(
    (value) => value === true,
  ).length;
  const retainedRoutes = [bigQualified, deltaQualified].filter(
    (value) => value !== null,
  ).length;
  const referenceSessions = compactNumber(
    context.big_trade_lookback_sessions,
  );
  const referenceObservations = compactNumber(
    context.big_trade_reference_observation_count,
  );
  const referenceDates =
    hasEvidenceValue(context.big_trade_reference_start_session) &&
    hasEvidenceValue(context.big_trade_reference_end_session)
      ? ` from ${String(context.big_trade_reference_start_session)} through ${String(
          context.big_trade_reference_end_session,
        )}`
      : "";
  return {
    rule: "any",
    outcome:
      qualifiedRoutes > 0
        ? "qualified"
        : retainedRoutes > 0
          ? "not_qualified"
          : "unknown",
    kind: String(
      context.institutional_footprint_kind || "institutional_footprint",
    ),
    edgePrice: context.aoi_edge_price,
    frozenAt: context.aoi_frozen_at,
    definition: String(
      context.profile_snapshot_timing ||
        "The exact value edge is frozen when at least one qualifying footprint is causally available.",
    ),
    routes: [
      {
        id: "large_execution",
        label: "Adaptive large execution",
        qualified: bigQualified,
        observed: context.selected_big_trade_size,
        threshold: context.big_trade_threshold_contracts,
        unit: "contracts",
        percentile: context.big_trade_reference_percentile,
        priceLow: context.selected_big_trade_low_price,
        priceHigh: context.selected_big_trade_high_price,
        side: context.selected_big_trade_side,
        qualifiedAt: context.selected_big_trade_qualified_at,
        referenceDescription: `100 ms burst threshold from the prior ${referenceSessions} sessions (${referenceObservations} reference bursts${referenceDates})`,
      },
      {
        id: "top_decile_delta",
        label: "Top-decile developing delta",
        qualified: deltaQualified,
        observed: context.selected_delta_bin_abs_delta,
        threshold: context.selected_delta_bin_threshold,
        unit: "absolute delta",
        percentile: context.selected_delta_percentile,
        priceLow: context.selected_delta_bin_low_price,
        priceHigh: context.selected_delta_bin_high_price,
        referenceDescription:
          "Developing session absolute delta ranked across retained price bins",
      },
    ],
  };
}
