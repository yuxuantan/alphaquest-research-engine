import { describe, expect, it } from "vitest";

import {
  resolveAdaptiveV18MechanicsComparison,
  resolveFrozenSetup,
  resolveMechanicsComparison,
  resolveQualifyingFootprint,
  resolveStrategyEvidencePanels,
} from "./strategyEvidence";

describe("strategy-specific mechanics evidence panels", () => {
  it("shows the v03 frozen profile, selected burst, and AOI armed time", () => {
    const evidence = {
      metadata: {
        strategy_id: "yush_adaptive_orderflow_range_v3",
        variant_id: "v03",
      },
      trade: { direction: "short" },
      strategy_context: {
        aoi_edge_price: 7394,
        value_area_poc_price: 7389,
        value_area_vah_price: 7394,
        value_area_val_price: 7387,
        aoi_source_kinds: "big_trade",
        aoi_frozen_at: "2026-05-12 13:39:00-04:00",
        selected_big_trade_size: 86,
        big_trade_threshold_contracts: 82,
        selected_big_trade_side: "B",
        selected_big_trade_low_price: 7394.5,
        selected_big_trade_high_price: 7394.5,
        selected_big_trade_qualified_at:
          "2026-05-12 13:34:45.875000-04:00",
        sweep_bar_index: 83,
        entry_trigger_price: 7395,
        entry_order_type: "next_event_stop_market",
        entry_reference_price: 7393.75,
        entry_price: 7393.5,
        reclaim_confirmation_at: "2026-05-12 13:43:02.125000-04:00",
        reclaim_event_index: 81120,
        reclaim_event_price: 7393.75,
        entry_decision_event_index: 81121,
        actual_fill_gate_passed: true,
        planned_stop_ticks: 16,
        minimum_net_reward_to_worst_case_loss: 1,
        net_reward_to_worst_case_loss: 1.24,
        net_target_reward_dollars_per_contract: 18.98,
        worst_case_stop_loss_dollars_per_contract: 15.27,
      },
    };

    expect(resolveFrozenSetup(evidence)).toEqual({
      direction: "short",
      edgeRole: "VAH",
      sourceKinds: "big_trade",
      edgePrice: 7394,
      pocPrice: 7389,
      vahPrice: 7394,
      valPrice: 7387,
      aoiArmedAt: "2026-05-12 13:39:00-04:00",
      burstSize: 86,
      burstThreshold: 82,
      burstQualifiedAt: "2026-05-12 13:34:45.875000-04:00",
      burstSide: "B",
      burstPriceLow: 7394.5,
      burstPriceHigh: 7394.5,
    });
    expect(resolveStrategyEvidencePanels(evidence).map((panel) => panel.title)).toEqual([
      "Frozen AOI source and profile",
      "Sweep, reclaim and causal entry",
      "Stop, both targets, sizing and costs",
    ]);
    const rows = resolveStrategyEvidencePanels(evidence).flatMap(
      (panel) => panel.rows,
    );
    expect(rows.map((row) => row.key)).not.toContain("entry_trigger_price");
    expect(rows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          key: "entry_reference_price",
          label: "Fill-event reference",
          value: 7393.75,
        }),
        expect.objectContaining({
          key: "entry_price",
          label: "Actual modeled fill",
          value: 7393.5,
        }),
        expect.objectContaining({
          key: "reclaim_event_index",
          label: "Reclaim event",
          value: 81120,
        }),
        expect.objectContaining({
          key: "entry_decision_event_index",
          label: "Sole entry-decision event",
          value: 81121,
        }),
        expect.objectContaining({
          key: "net_reward_to_worst_case_loss",
          value: 1.24,
        }),
      ]),
    );
  });

  it("compares the complete v18 frozen mechanics contract with observed trade evidence", () => {
    const evidence = {
      metadata: {
        strategy_id: "yush_adaptive_orderflow_range_v3",
        variant_id: "v03",
        strategy_implementation_version: 18,
      },
      frozen_mechanics: {
        event_parameters: {
          aoi_level_distance_ticks: 4,
          opening_range_seconds: 30,
          delta_profile_percentile: 0.9,
          big_trade_reference_percentile: 0.999,
          big_trade_lookback_sessions: 20,
          big_trade_interval_ms: 100,
          burst_freshness_bars: 3,
          price_bin_ticks: 1,
          value_area_method: "motivewave_standard",
          value_area_fraction: 0.7,
          profile_warmup_bars: 3,
          afternoon_profile_reset: "13:30:00",
          sweep_minimum_ticks: 2,
          sweep_atr_fraction: 0.2,
          entry_offset_ticks: 1,
          failure_confirmation_bars: 3,
          stop_offset_ticks: 1,
          minimum_stop_ticks: 2,
          maximum_stop_atr_multiple: 1.75,
          target_1_fraction: 0.5,
          maximum_holding_bars: 12,
          minimum_net_reward_to_worst_case_loss: 1,
          morning_entry_start: "09:39:00",
          morning_entry_end: "11:30:00",
          afternoon_entry_start: "13:39:00",
          afternoon_entry_end: "15:30:00",
        },
        execution: {
          signal_instrument: "ES",
          execution_instrument: "MES",
          commission_per_contract: 0.51,
          entry_slippage_ticks: 1,
          protective_stop_slippage_ticks: 1,
          target_limit_slippage_ticks: 0,
          flatten_time: "15:55:00",
          position_sizing: {
            mode: "risk_percent_net_liq",
            risk_pct: 0.004,
            min_contracts: 1,
          },
        },
        protocol: { force_flatten_time: "15:55:00" },
      },
      trade: {
        direction: "short",
        contract: "ESM26",
        entry_time: "2026-05-14T15:16:55-04:00",
        exit_time: "2026-05-14T15:32:17-04:00",
        exit_reason: "post_target_1_stop",
      },
      strategy_context: {
        aoi_source_kinds: "delta_profile",
        aoi_identity: "afternoon:short:30121:sources=delta",
        aoi_edge_price: 7530.25,
        institutional_big_trade_qualified: false,
        institutional_delta_qualified: true,
        market_level_qualified: false,
        selected_delta_signed_delta: 275,
        selected_delta_bin_threshold: 275,
        selected_delta_bin_low_price: 7530.75,
        selected_delta_bin_high_price: 7530.75,
        profile_epoch: "afternoon",
        value_area_vah_price: 7530.25,
        value_area_poc_price: 7525,
        value_area_val_price: 7519,
        aoi_frozen_at: "2026-05-14T15:12:00-04:00",
        entry_confirmation_kind: "delta_profile",
        entry_confirmation_id: "bar=114:delta=30124:threshold=103",
        entry_confirmation_at: "2026-05-14T15:15:00-04:00",
        entry_confirmation_price: 7531,
        entry_confirmation_value: 630,
        reclaim_confirmation_at: "2026-05-14T15:15:00.359-04:00",
        sweep_distance_ticks: 3,
        sweep_high_price: 7531.25,
        sweep_low_price: 7526,
        sweep_bar_index: 114,
        reclaim_event_index: 286922,
        reclaim_event_price: 7528.25,
        entry_order_type: "edge_retest_limit",
        entry_reference_price: 7530,
        entry_price: 7530,
        actual_fill_gate_passed: true,
        entry_fill_model: "stop-first cancellation before fill",
        initial_stop_price: 7531.5,
        planned_stop_ticks: 6,
        risk_points: 1.5,
        target_1_price: 7524.75,
        target_2_price: 7519,
        net_reward_to_worst_case_loss: 4.05,
        net_target_reward_dollars_per_contract: 39.605,
        worst_case_stop_loss_dollars_per_contract: 9.77,
        contracts: 20,
        target_risk_amount: 200,
        planned_dollar_risk: 195.4,
        commission: 20.4,
        slippage_cost: 0,
        total_transaction_cost: 20.4,
        signal_instrument: "ES",
        execution_instrument: "MES",
      },
      event_transitions: [
        { transition: "order_submitted" },
        { transition: "entry_filled" },
        { transition: "position_partially_closed" },
        { transition: "position_closed" },
      ],
    };

    const sections = resolveAdaptiveV18MechanicsComparison(evidence);
    expect(sections.map((section) => section.title)).toEqual([
      "AOI source and frozen profile",
      "Separate post-AOI confirmation",
      "Sweep, reclaim and order lifecycle",
      "Stop and both frozen targets",
      "Sizing and execution assumptions",
    ]);
    const rows = sections.flatMap((section) => section.rows);
    expect(rows.find((row) => row.key === "aoi_source")?.observed).toContain(
      "delta_profile",
    );
    expect(rows.find((row) => row.key === "market_level_source")?.configured).toContain(
      "30-second ORH/ORL",
    );
    expect(rows.find((row) => row.key === "confirmation_type")?.observed).toContain(
      "bar=114",
    );
    expect(rows.find((row) => row.key === "order_lifecycle")?.observed).toBe(
      "order_submitted → entry_filled → position_partially_closed → position_closed",
    );
    expect(rows.find((row) => row.key === "targets")?.observed).toContain(
      "T2 7519",
    );
    expect(rows.find((row) => row.key === "position_sizing")?.configured).toContain(
      "0.4%",
    );

    const panelKeys = resolveStrategyEvidencePanels(evidence).flatMap((panel) =>
      panel.rows.map((row) => row.key),
    );
    expect(panelKeys).toEqual(
      expect.arrayContaining([
        "aoi_source_kinds",
        "institutional_delta_qualified",
        "entry_confirmation_kind",
        "target_1_price",
        "target_2_price",
        "execution_instrument",
      ]),
    );
  });

  it("shows the v20 ATR-radius immediate-order contract instead of retired reclaim rules", () => {
    const evidence = {
      metadata: {
        strategy_id: "yush_adaptive_orderflow_range_v3",
        variant_id: "v03",
        strategy_implementation_version: 20,
      },
      frozen_mechanics: {
        event_parameters: {
          context_distance_atr_fraction: 1 / 3,
          burst_freshness_scope: "current_rth_session",
          big_trade_reference_percentile: 0.999,
          big_trade_lookback_sessions: 20,
          big_trade_interval_ms: 100,
          delta_profile_percentile: 0.9,
          price_bin_ticks: 1,
          opening_range_seconds: 30,
          value_area_method: "motivewave_standard",
          value_area_fraction: 0.7,
          profile_warmup_bars: 3,
          afternoon_profile_reset: "disabled",
          failure_confirmation_bars: 3,
          sweep_minimum_ticks: 2,
          sweep_atr_fraction: 0.2,
          entry_offset_ticks: 1,
          minimum_stop_ticks: 2,
          maximum_stop_atr_multiple: 1.75,
          minimum_midpoint_reward_r: 1,
          target_1_fraction: 0.5,
          maximum_holding_bars: 12,
        },
        execution: {
          signal_instrument: "ES",
          execution_instrument: "MES",
          commission_per_contract: 0.51,
          entry_slippage_ticks: 1,
          protective_stop_slippage_ticks: 1,
          target_limit_slippage_ticks: 0,
          flatten_time: "15:55:00",
          position_sizing: {
            mode: "risk_percent_net_liq",
            risk_pct: 0.004,
            min_contracts: 1,
          },
        },
        protocol: { force_flatten_time: "15:55:00" },
      },
      trade: {},
      strategy_context: {
        aoi_edge_price: 6000,
        context_distance_ticks: 12,
        aoi_frozen_at: "2026-08-18T10:00:00-04:00",
        entry_confirmation_at: "2026-08-18T10:03:00-04:00",
        order_activation_at: "2026-08-18T10:03:00-04:00",
        order_activation_event_index: 42,
        midpoint_reward_r: 1.5,
        entry_order_type: "outside_edge_limit",
        entry_reference_price: 6000.25,
      },
    };

    const sections = resolveAdaptiveV18MechanicsComparison(evidence);
    expect(sections.map((section) => section.title)).toContain(
      "Sweep, confirmation and order lifecycle",
    );
    const rows = sections.flatMap((section) => section.rows);
    expect(rows.find((row) => row.key === "source_location")?.configured).toContain(
      "ATR outward",
    );
    expect(rows.find((row) => row.key === "large_execution_source")?.configured).toContain(
      "any burst in the current RTH session",
    );
    expect(rows.find((row) => row.key === "order_activation")?.configured).toContain(
      "no reclaim",
    );
    expect(rows.find((row) => row.key === "payoff_gate")?.configured).toContain(
      "ignore weighted net reward",
    );
    expect(rows.find((row) => row.key === "stop")?.configured).toContain(
      "sweep-bar extreme",
    );

    const v21Sections = resolveAdaptiveV18MechanicsComparison({
      ...evidence,
      metadata: {
        ...evidence.metadata,
        strategy_implementation_version: 21,
      },
      strategy_context: {
        ...evidence.strategy_context,
        entry_order_type: "inside_edge_stop_market",
      },
    });
    expect(v21Sections.map((section) => section.title)).toContain(
      "Sweep, confirmation and stop-entry lifecycle",
    );
    const v21Rows = v21Sections.flatMap((section) => section.rows);
    expect(v21Rows.find((row) => row.key === "order_activation")?.configured).toContain(
      "trigger crossing inside value proves reclaim",
    );
    expect(v21Rows.find((row) => row.key === "limit_order")?.configured).toContain(
      "VAH minus for short; VAL plus for long",
    );

    const v22Rows = resolveAdaptiveV18MechanicsComparison({
      ...evidence,
      metadata: {
        ...evidence.metadata,
        strategy_implementation_version: 22,
      },
    }).flatMap((section) => section.rows);
    expect(v22Rows.find((row) => row.key === "source_location")?.configured).toContain(
      "above or below",
    );
    expect(
      v22Rows.find((row) => row.key === "confirmation_direction_location")?.configured,
    ).toContain("ATR outward");

    const v23Rows = resolveAdaptiveV18MechanicsComparison({
      ...evidence,
      metadata: {
        ...evidence.metadata,
        strategy_implementation_version: 23,
      },
    }).flatMap((section) => section.rows);
    expect(
      v23Rows.find((row) => row.key === "large_execution_source")?.configured,
    ).toContain("consecutive same-price/aggressor sequences");

    const v24Rows = resolveAdaptiveV18MechanicsComparison({
      ...evidence,
      metadata: {
        ...evidence.metadata,
        strategy_implementation_version: 24,
      },
      frozen_mechanics: {
        ...evidence.frozen_mechanics,
        event_parameters: {
          ...evidence.frozen_mechanics.event_parameters,
          delta_profile_price_bin_ticks: 4,
          confirmation_delta_lookback_sessions: 20,
          confirmation_delta_reference_percentile: 0.9,
          entry_offset_ticks: 2,
          stop_offset_ticks: 2,
        },
      },
      strategy_context: {
        ...evidence.strategy_context,
        entry_confirmation_bin_low_price: 7380,
        entry_confirmation_bin_high_price: 7380.75,
        entry_confirmation_threshold: 240,
      },
    }).flatMap((section) => section.rows);
    expect(v24Rows.find((row) => row.key === "delta_source")?.configured).toContain(
      "4-tick MotiveWave fixed cells",
    );
    expect(v24Rows.find((row) => row.key === "confirmation_type")?.configured).toContain(
      "prior-20-session q90",
    );
    expect(v24Rows.find((row) => row.key === "confirmation_direction_location")?.observed).toContain(
      "7380–7380.75",
    );
    expect(v24Rows.find((row) => row.key === "stop")?.configured).toContain(
      "2 ticks beyond",
    );

    const v25Rows = resolveAdaptiveV18MechanicsComparison({
      ...evidence,
      metadata: {
        ...evidence.metadata,
        strategy_implementation_version: 25,
      },
      frozen_mechanics: {
        ...evidence.frozen_mechanics,
        event_parameters: {
          ...evidence.frozen_mechanics.event_parameters,
          delta_profile_price_bin_ticks: 4,
        },
      },
      strategy_context: {
        ...evidence.strategy_context,
        burst_direction_rule:
          "aoi_big_trade_side_unrestricted;separate_short_confirmation_requires_buy_aggressor;separate_long_confirmation_requires_sell_aggressor",
      },
    }).flatMap((section) => section.rows);
    expect(v25Rows.find((row) => row.key === "aoi_source")?.configured).toContain(
      "aggressive burst of either side",
    );
    expect(v25Rows.find((row) => row.key === "delta_source")?.configured).toContain(
      "sign-agnostic",
    );
    expect(
      v25Rows.find((row) => row.key === "confirmation_direction_location")?.configured,
    ).toContain("separate_short_confirmation_requires_buy_aggressor");

    const v26Rows = resolveAdaptiveV18MechanicsComparison({
      ...evidence,
      metadata: {
        ...evidence.metadata,
        strategy_implementation_version: 26,
      },
      frozen_mechanics: {
        ...evidence.frozen_mechanics,
        event_parameters: {
          ...evidence.frozen_mechanics.event_parameters,
          entry_offset_ticks: 2,
        },
      },
      strategy_context: {
        ...evidence.strategy_context,
        aoi_zone_low_price: 7379,
        aoi_zone_high_price: 7381,
        entry_zone_boundary_price: 7381,
      },
    }).flatMap((section) => section.rows);
    expect(v26Rows.find((row) => row.key === "aoi_zone")?.observed).toContain(
      "7379–7381",
    );
    expect(v26Rows.find((row) => row.key === "order_activation")?.configured).toContain(
      "beyond the full AOI zone",
    );
    expect(v26Rows.find((row) => row.key === "limit_order")?.configured).toContain(
      "zone low minus for short; zone high plus for long",
    );
  });

  it("shows the v27 per-bar AOI and fill-time stop contract", () => {
    const evidence = {
      metadata: {
        strategy_id: "yush_adaptive_orderflow_range_v3",
        variant_id: "v03",
        strategy_implementation_version: 27,
      },
      frozen_mechanics: {
        event_parameters: {
          context_distance_atr_fraction: 1 / 3,
          sweep_minimum_ticks: 2,
          sweep_atr_fraction: 0.2,
          entry_offset_ticks: 2,
          stop_offset_ticks: 2,
          minimum_stop_ticks: 2,
          maximum_stop_atr_multiple: 1.75,
          minimum_midpoint_reward_r: 1,
          target_1_fraction: 0.5,
          value_area_method: "motivewave_standard",
          value_area_fraction: 0.7,
        },
        execution: {
          signal_instrument: "ES",
          execution_instrument: "MES",
          entry_slippage_ticks: 1,
          protective_stop_slippage_ticks: 1,
          position_sizing: { mode: "risk_percent_net_liq", risk_pct: 0.004, min_contracts: 1 },
        },
      },
      strategy_context: {
        aoi_source_kinds: "big_trade,delta_profile",
        aoi_identity: "rth:asof_bar=6:short:29524:sources=burst=3+delta=29524:29527:negative",
        aoi_edge_price: 7381,
        aoi_zone_low_price: 7381,
        aoi_zone_high_price: 7381.75,
        aoi_frozen_at: "2026-05-14T09:48:00-04:00",
        value_area_vah_price: 7381,
        value_area_poc_price: 7376,
        value_area_val_price: 7370,
        context_distance_ticks: 7,
        sweep_distance_ticks: 4,
        sweep_high_price: 7385,
        sweep_low_price: 7380,
        sweep_bar_index: 7,
        entry_confirmation_kind: "not_required",
        order_activation_at: "2026-05-14T09:54:00-04:00",
        entry_order_type: "reclaim_side_aoi_zone_stop_market",
        entry_zone_boundary_price: 7381,
        entry_reference_price: 7380.5,
        entry_price: 7380.25,
        entry_fill_model: "no intended-stop invalidation exists before fill",
        sweep_to_entry_high_price: 7386,
        sweep_to_entry_low_price: 7380.5,
        resolved_stop_price: 7386.5,
        stop_resolution_event_index: 1234,
        risk_points: 6.25,
        midpoint_reward_r: 1.2,
        target_1_price: 7375.5,
        target_2_price: 7370,
        contracts: 3,
        planned_dollar_risk: 190,
        signal_instrument: "ES",
        execution_instrument: "MES",
      },
      event_transitions: [
        { transition: "order_submitted" },
        { transition: "entry_filled" },
      ],
    };

    const sections = resolveAdaptiveV18MechanicsComparison(evidence);
    expect(sections.map((section) => section.title)).toEqual([
      "Per-bar VAH / VAL AOI",
      "Ordered sweep and reclaim entry",
      "Fill-time structural stop",
      "AOI-time targets",
      "Sizing and execution assumptions",
    ]);
    const rows = sections.flatMap((section) => section.rows);
    expect(rows.find((row) => row.key === "confirmation")?.configured).toContain(
      "Not required",
    );
    expect(rows.find((row) => row.key === "stop")?.configured).toContain(
      "through the entry event",
    );
    expect(rows.find((row) => row.key === "aoi_source")?.configured).toContain(
      "market levels do not qualify",
    );

    const panelKeys = resolveStrategyEvidencePanels(evidence).flatMap((panel) =>
      panel.rows.map((row) => row.key),
    );
    expect(panelKeys).toEqual(
      expect.arrayContaining([
        "aoi_identity",
        "entry_confirmation_kind",
        "sweep_to_entry_high_price",
        "resolved_stop_price",
      ]),
    );
    expect(panelKeys).not.toContain("entry_confirmation_threshold");
  });

  it("shows the complete v04 contract when a market level alone qualifies the AOI", () => {
    const evidence = {
      metadata: {
        strategy_id: "yush_adaptive_orderflow_range_v4",
        variant_id: "v04",
        strategy_implementation_version: 3,
      },
      frozen_mechanics: {
        event_parameters: {
          context_distance_atr_fraction: 1 / 3,
          delta_profile_price_bin_ticks: 4,
          delta_profile_percentile: 0.9,
          big_trade_reference_percentile: 0.999,
          big_trade_lookback_sessions: 20,
          big_trade_interval_ms: 100,
          sweep_minimum_ticks: 2,
          sweep_atr_fraction: 0.2,
          entry_offset_ticks: 2,
          stop_offset_ticks: 2,
          minimum_stop_ticks: 2,
          maximum_stop_atr_multiple: 1.75,
          minimum_midpoint_reward_r: 1,
          target_1_fraction: 0.5,
          value_area_method: "motivewave_standard",
          value_area_fraction: 0.7,
          morning_entry_start: "09:39:00",
          morning_entry_end: "11:30:00",
          afternoon_entry_start: "13:39:00",
          afternoon_entry_end: "15:30:00",
        },
        execution: {
          signal_instrument: "ES",
          execution_instrument: "MES",
          commission_per_contract: 0.51,
          entry_slippage_ticks: 1,
          protective_stop_slippage_ticks: 1,
          flatten_time: "15:55:00",
          position_sizing: {
            mode: "risk_percent_net_liq",
            risk_pct: 0.004,
            rounding: "floor",
            min_contracts: 1,
          },
        },
        protocol: { force_flatten_time: "15:55:00" },
      },
      trade: {
        direction: "short",
        contract: "ESM26",
        entry_time: "2026-05-14T09:50:58.275-04:00",
        exit_time: "2026-05-14T10:02:03.220-04:00",
      },
      strategy_context: {
        aoi_source_kinds: "market_level",
        aoi_identity: "rth:asof_bar=4:short:sources=market=ONH",
        aoi_edge_price: 7498,
        aoi_zone_low_price: 7498,
        aoi_zone_high_price: 7499.25,
        aoi_frozen_at: "2026-05-14T09:45:00-04:00",
        value_area_vah_price: 7498,
        value_area_poc_price: 7491.75,
        value_area_val_price: 7480.25,
        context_distance_ticks: 5,
        market_level_qualified: true,
        selected_market_level_type: "ONH",
        selected_market_level_price: 7499.25,
        institutional_big_trade_qualified: false,
        institutional_delta_qualified: false,
        sweep_distance_ticks: 3,
        sweep_high_price: 7502.25,
        sweep_low_price: 7497.75,
        sweep_bar_index: 5,
        entry_confirmation_kind: "delta_imprint",
        entry_confirmation_id: "bar=6:event=35102:cell=30008",
        entry_confirmation_at: "2026-05-14T09:49:34.101-04:00",
        entry_confirmation_price: 7502.25,
        entry_confirmation_bin_low_price: 7502,
        entry_confirmation_bin_high_price: 7502.75,
        entry_confirmation_value: 210,
        entry_confirmation_threshold: 200,
        entry_confirmation_bar_index: 6,
        entry_confirmation_bar_start: "2026-05-14T09:48:00-04:00",
        entry_confirmation_bar_end: "2026-05-14T09:51:00-04:00",
        entry_confirmation_reference_count: 184,
        entry_confirmation_percentile_method: "nearest_rank",
        entry_confirmation_comparison: "strict_absolute_greater_than",
        entry_zone_boundary_price: 7498,
        entry_order_type: "reclaim_side_aoi_zone_stop_market",
        entry_reference_price: 7497.5,
        entry_price: 7497.25,
        entry_fill_model: "no intended-stop invalidation exists before fill",
        sweep_to_entry_high_price: 7503.25,
        sweep_to_entry_low_price: 7496.25,
        resolved_stop_price: 7503.75,
        stop_resolution_event_index: 35336,
        risk_points: 6.5,
        midpoint_reward_r: 1.23,
        target_1_price: 7489.25,
        target_1_definition: "frozen_value_area_midpoint_half_exit",
        target_1_fraction: 0.5,
        target_2_price: 7479.75,
        target_2_definition:
          "frozen_opposite_value_area_edge_plus_two_ticks_outside",
        final_target_outside_ticks: 2,
        position_sizing_mode: "risk_percent_net_liq",
        position_sizing_net_liq: 50_000,
        target_risk_amount: 200,
        dollar_risk_per_contract: 34.77,
        planned_dollar_risk: 173.85,
        contracts: 5,
        signal_instrument: "ES",
        execution_instrument: "MES",
      },
      event_transitions: [
        { transition: "order_submitted" },
        { transition: "entry_filled" },
        { transition: "position_partially_closed" },
      ],
    };

    const sections = resolveMechanicsComparison(evidence);
    expect(sections.map((section) => section.title)).toEqual([
      "Per-bar VAH / VAL AOI",
      "Ordered sweep, developing-imprint confirmation and reclaim entry",
      "Fill-time structural stop",
      "AOI-time two-stage targets",
      "Sizing and execution assumptions",
    ]);
    const rows = sections.flatMap((section) => section.rows);
    expect(rows.find((row) => row.key === "market_level_source")).toMatchObject({
      configured: expect.stringContaining("without a large execution or delta"),
      observed: expect.stringContaining("ONH"),
    });
    expect(rows.find((row) => row.key === "separate_confirmation")?.observed).toContain(
      "delta_imprint",
    );
    expect(rows.find((row) => row.key === "separate_confirmation")?.configured).toContain(
      "whole developing three-minute bar",
    );
    expect(rows.find((row) => row.key === "separate_confirmation")?.observed).toContain(
      "completed references 184",
    );
    expect(rows.find((row) => row.key === "reclaim_entry")?.configured).toContain(
      "2 ticks beyond",
    );
    expect(rows.find((row) => row.key === "stop")?.configured).toContain(
      "through the fill event",
    );
    expect(rows.find((row) => row.key === "target_2")?.configured).toContain(
      "2 ticks outside",
    );
    expect(rows.find((row) => row.key === "position_sizing")?.configured).toContain(
      "0.4%",
    );

    const panelKeys = resolveStrategyEvidencePanels(evidence).flatMap((panel) =>
      panel.rows.map((row) => row.key),
    );
    expect(panelKeys).toEqual(
      expect.arrayContaining([
        "market_level_qualified",
        "entry_confirmation_kind",
        "resolved_stop_price",
        "target_1_price",
        "target_2_price",
        "position_sizing_mode",
      ]),
    );
    expect(resolveFrozenSetup(evidence)).toMatchObject({
      sourceKinds: "market_level",
      edgeRole: "VAH",
      edgePrice: 7498,
      sourceDescription: expect.stringContaining(
        "sign-agnostic absolute four-tick delta",
      ),
    });
    expect(resolveQualifyingFootprint(evidence)).toBeNull();
  });

  it("renders failed-auction evidence for v02 without leaking AOI fields", () => {
    const panels = resolveStrategyEvidencePanels({
      metadata: {
        strategy_id: "yush_failed_auction_reclaim",
        variant_id: "v02",
      },
      strategy_context: {
        failed_auction_side: "VAL",
        failed_auction_reference_type: "PDL",
        failed_auction_reference: 7420.25,
        failed_auction_aggression_kind:
          "outward_big_trade_percentile_100ms",
        failed_auction_aggression_value: 32,
        failed_auction_big_trade_percentile: 0.995,
        failed_auction_big_trade_threshold: 20,
        failed_auction_big_trade_reference_count: 8005,
        failed_auction_started_at: "2026-05-18T13:47:15.297Z",
        failed_auction_reclaimed_at: "2026-05-18T13:47:17.633Z",
        entry_event_index: 47801,
        aoi_confluences: "must not appear",
      },
    });

    expect(panels.map((panel) => panel.title)).toEqual([
      "Selected confluence at signal",
      "Aggression qualification",
      "Failed-auction causal execution",
    ]);
    expect(
      panels.flatMap((panel) => panel.rows.map((row) => row.label)),
    ).toEqual(
      expect.arrayContaining([
        "Selected market level",
        "Market-level price",
        "Observed aggression",
        "Big-trade percentile",
        "Frozen big-trade threshold",
        "Big-trade reference observations",
        "Episode started",
        "Boundary reclaimed",
        "Entry event",
      ]),
    );
    expect(
      panels.flatMap((panel) => panel.rows.map((row) => row.key)),
    ).not.toContain("aoi_confluences");
  });

  it("renders the AOI mechanics trace for v01 without failed-auction fields", () => {
    const panels = resolveStrategyEvidencePanels({
      metadata: {
        strategy_id: "yush_orderflow_range",
        variant_id: "v01",
      },
      strategy_context: {
        aoi_side: "VAH",
        aoi_confluences: "PDH@7427.75;DELTA_4T@7429-7429.75",
        aoi_tap_timestamp: "2026-05-18T13:40:00Z",
        trigger_kind: "big_trade_100ms",
        entry_profile_poc: 7420.25,
        failed_auction_reference_type: "must not appear",
      },
    });

    expect(panels.map((panel) => panel.title)).toEqual([
      "AOI confluence and geometry",
      "AOI signal timing",
      "AOI execution state",
    ]);
    expect(
      panels.flatMap((panel) => panel.rows.map((row) => row.key)),
    ).toEqual(
      expect.arrayContaining([
        "aoi_side",
        "aoi_confluences",
        "aoi_tap_timestamp",
        "trigger_kind",
        "entry_profile_poc",
      ]),
    );
    expect(
      panels.flatMap((panel) => panel.rows.map((row) => row.key)),
    ).not.toContain("failed_auction_reference_type");
  });

  it("uses a conservative generic panel for an unregistered strategy", () => {
    const panels = resolveStrategyEvidencePanels({
      metadata: {
        strategy_id: "future_strategy",
        variant_id: "v07",
      },
      strategy_context: {
        trigger_kind: "reclaim",
        trigger_value: 123,
        entry_event_index: 456,
        strategy_private_state: "do not expose implicitly",
      },
    });

    expect(panels).toEqual([
      {
        title: "Strategy decision trace",
        rows: [
          { key: "trigger_kind", label: "Trigger type", value: "reclaim" },
          { key: "trigger_value", label: "Trigger value", value: 123 },
          { key: "entry_event_index", label: "Entry event", value: 456 },
        ],
      },
    ]);
    expect(
      resolveMechanicsComparison({
        metadata: { strategy_id: "future_strategy", variant_id: "v07" },
        strategy_context: { trigger_kind: "reclaim" },
      }),
    ).toEqual([]);
  });

  it("shows only mechanics-validation evidence for institutional v02", () => {
    const panels = resolveStrategyEvidencePanels({
      metadata: {
        strategy_id: "yush_adaptive_orderflow_range",
        variant_id: "v02",
      },
      strategy_context: {
        setup_model: "institutional_footprint_value_edge_failure",
        directional_trend_veto_passed: true,
        trend_state_at_failure: "no_directional_breakout_trend",
        trend_state_at_entry: "no_directional_breakout_trend",
        regime_overlap_at_entry: 0.72,
        regime_efficiency_at_entry: 0.21,
        rolling_poc_a_at_entry_price: 7420,
        rolling_poc_b_at_entry_price: 7419.75,
        rolling_midpoint_a_at_entry_price: 7420.5,
        rolling_midpoint_b_at_entry_price: 7420.25,
        aoi_edge_price: 7430,
        aoi_frozen_bar_index: 20,
        aoi_frozen_at: "2026-05-18T13:30:00Z",
        institutional_footprint_kind:
          "adaptive_large_execution_and_top_decile_delta",
        institutional_big_trade_qualified: true,
        institutional_delta_qualified: true,
        big_trade_reference_percentile: 0.995,
        big_trade_lookback_sessions: 20,
        big_trade_threshold_contracts: 231,
        big_trade_reference_observation_count: 8_005,
        big_trade_reference_start_session: "2026-04-17",
        big_trade_reference_end_session: "2026-05-15",
        selected_big_trade_burst_id: 17,
        selected_big_trade_size: 240,
        selected_delta_bin_abs_delta: 680,
        selected_delta_bin_threshold: 610,
        selected_delta_percentile: 0.9,
        sweep_bar_index: 22,
        sweep_high_price: 7432,
        sweep_low_price: 7428.5,
        sweep_minimum_ticks: 2,
        failure_confirmation_bars: 3,
        failure_bar_index: 23,
        failure_close_price: 7429.25,
        failure_confirmation_rule:
          "completed_close_one_tick_inside_frozen_value_edge",
        entry_trigger_rule:
          "one_tick_inside_frozen_aoi_edge_after_completed_failure",
        value_area_poc_price: 7420,
        value_area_vah_price: 7430,
        value_area_val_price: 7410,
        target_1_price: 7420,
        target_2_price: 7410,
        target_1_fraction: 0.5,
        maximum_holding_bars: 12,
        entry_trigger_price: 7428.75,
        initial_stop_price: 7432.5,
        planned_stop_ticks: 15,
        risk_points: 4,
        risk_budget_dollars: 250,
        position_sizing_mode: "fixed_dollar_risk",
        dollar_risk_per_contract: 228.1,
        planned_dollar_risk: 228.1,
        contracts: 1,
        entry_slippage_ticks: 1,
        protective_stop_slippage_ticks: 1,
        target_limit_slippage_ticks: 0,
        entry_event_index: 37851,
        round_trip_commission_per_contract: 3.1,
        entry_fill_model: "next_trade_stop_market_one_tick_adverse",
        profile_snapshot_timing:
          "frozen_when_value_edge_gained_institutional_footprint",
        entry_windows_new_york: "09:33:00-11:30:00;13:30:00-15:30:00",
        aoi_score: 4,
        sweep_delta: 860,
        effective_sweep_maximum_points: 8.5,
      },
    });

    expect(panels.map((panel) => panel.title)).toEqual([
      "Frozen value edge and institutional footprint",
      "Directional breakout trend veto",
      "Sweep, failure and causal entry",
      "Frozen objectives, stop, sizing and costs",
    ]);
    expect(
      panels
        .flatMap((panel) => panel.rows)
        .find((row) => row.key === "big_trade_threshold_contracts"),
    ).toMatchObject({ value: 231 });
    expect(
      panels
        .flatMap((panel) => panel.rows)
        .find((row) => row.key === "directional_trend_veto_passed"),
    ).toMatchObject({ value: true });
    expect(
      panels
        .flatMap((panel) => panel.rows)
        .find((row) => row.key === "sweep_minimum_ticks"),
    ).toMatchObject({ value: 2 });
    expect(
      panels
        .flatMap((panel) => panel.rows)
        .find((row) => row.key === "target_1_price"),
    ).toMatchObject({ value: 7420 });
    expect(
      panels
        .flatMap((panel) => panel.rows)
        .find((row) => row.key === "selected_big_trade_size"),
    ).toMatchObject({ value: 240 });
    expect(
      panels
        .flatMap((panel) => panel.rows)
        .find((row) => row.key === "selected_delta_bin_threshold"),
    ).toMatchObject({ value: 610 });
    expect(
      panels
        .flatMap((panel) => panel.rows)
        .map((row) => row.key),
    ).not.toContain("aoi_score");
    expect(
      panels
        .flatMap((panel) => panel.rows)
        .map((row) => row.key),
    ).not.toContain("sweep_delta");
    expect(
      panels
        .flatMap((panel) => panel.rows)
        .map((row) => row.key),
    ).not.toContain("effective_sweep_maximum_points");
  });

  it("explains the institutional footprint as an OR rule with frozen comparisons", () => {
    const footprint = resolveQualifyingFootprint({
      metadata: {
        strategy_id: "yush_adaptive_orderflow_range",
        variant_id: "v02",
      },
      strategy_context: {
        institutional_footprint_kind:
          "adaptive_large_execution_and_top_decile_delta",
        institutional_big_trade_qualified: true,
        institutional_delta_qualified: true,
        aoi_edge_price: 7420.75,
        aoi_frozen_at: "2026-05-08T14:51:00Z",
        selected_big_trade_size: 95,
        big_trade_threshold_contracts: 81,
        big_trade_reference_percentile: 0.995,
        big_trade_lookback_sessions: 20,
        big_trade_reference_observation_count: 2_598_312,
        big_trade_reference_start_session: "2026-04-10",
        big_trade_reference_end_session: "2026-05-07",
        selected_big_trade_low_price: 7421.5,
        selected_big_trade_high_price: 7421.5,
        selected_big_trade_side: "B",
        selected_big_trade_qualified_at: "2026-05-08T14:47:04.300Z",
        selected_delta_bin_abs_delta: 1121,
        selected_delta_bin_threshold: 851,
        selected_delta_percentile: 0.9,
        selected_delta_bin_low_price: 7420,
        selected_delta_bin_high_price: 7420.75,
      },
    });

    expect(footprint).toMatchObject({
      rule: "any",
      outcome: "qualified",
      edgePrice: 7420.75,
      routes: [
        {
          id: "large_execution",
          qualified: true,
          observed: 95,
          threshold: 81,
        },
        {
          id: "top_decile_delta",
          qualified: true,
          observed: 1121,
          threshold: 851,
        },
      ],
    });
    expect(footprint?.routes[0].referenceDescription).toContain(
      "2,598,312 reference bursts",
    );
  });

  it("treats one qualifying route as sufficient", () => {
    expect(
      resolveQualifyingFootprint({
        metadata: { strategy_id: "yush_adaptive_orderflow_range" },
        strategy_context: {
          institutional_footprint_kind: "top_decile_delta",
          institutional_big_trade_qualified: false,
          institutional_delta_qualified: true,
        },
      })?.outcome,
    ).toBe("qualified");
  });

  it("omits absent fields and empty panels", () => {
    expect(
      resolveStrategyEvidencePanels({
        metadata: {
          strategy_id: "yush_failed_auction_reclaim",
          variant_id: "v02",
        },
        strategy_context: {
          failed_auction_reference_type: "ONL",
          failed_auction_reference: null,
        },
      }),
    ).toEqual([
      {
        title: "Selected confluence at signal",
        rows: [
          {
            key: "failed_auction_reference_type",
            label: "Selected market level",
            value: "ONL",
          },
        ],
      },
    ]);
  });
});
