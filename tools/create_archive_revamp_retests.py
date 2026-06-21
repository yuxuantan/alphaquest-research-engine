from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CREATED_AT = "2026-06-21"


class NoAliasDumper(yaml.SafeDumper):
    def ignore_aliases(self, data):
        return True


def _dump_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(data, Dumper=NoAliasDumper, sort_keys=False, width=100),
        encoding="utf-8",
    )


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _common_apex() -> dict[str, Any]:
    return {
        "enabled": True,
        "timezone": "America/New_York",
        "latest_flat_time": "16:59:59",
        "force_flatten_enabled": True,
        "force_flatten_time": "16:58:30",
        "latest_entry_time": "16:45:00",
        "cancel_pending_orders_before_flatten": True,
        "no_overnight_positions": True,
        "reject_if_position_after_flatten_deadline": True,
        "reject_if_pending_order_after_flatten_deadline": True,
        "reject_if_entry_after_latest_entry_time": True,
    }


def _core(symbol: str, flatten_time: str, data_subset: dict[str, Any]) -> dict[str, Any]:
    tick_value = 12.5 if symbol == "ES" else 5.0
    point_value = 50.0 if symbol == "ES" else 20.0
    return {
        "data_subset": data_subset,
        "initial_balance": 150000,
        "tick_size": 0.25,
        "point_value": point_value,
        "tick_value": tick_value,
        "commission_per_contract": 2.5,
        "slippage_ticks": 1,
        "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
        "daily_loss_limit": 4000,
        "daily_profit_stop": 1000000000,
        "flatten_time": flatten_time,
        "max_trades_per_day": 1,
    }


def _benchmarks(min_pf: float, min_expectancy_r: float, min_mar: float) -> dict[str, Any]:
    return {
        "min_trades_per_year": 50,
        "preferred_min_total_trades": 500,
        "min_profit_factor": min_pf,
        "min_total_net_profit": 0,
        "min_expectancy_r": min_expectancy_r,
        "min_win_rate": 0.4,
        "max_drawdown_pct": 0.10,
        "min_cagr": 0.0,
        "min_mar": min_mar,
        "max_daily_loss": 1500,
        "max_consecutive_losses": 8,
        "max_best_day_concentration": 0.4,
        "min_positive_month_rate": 0.50,
        "min_wfa_profitable_window_rate": 0.70,
        "min_monte_carlo_prop_pass_chance": 0.50,
    }


def _stage_sections(data_subset: dict[str, Any], params: dict[str, list[Any]]) -> dict[str, Any]:
    return {
        "core_grid": {
            "data_subset": data_subset,
            "objective": "MAR",
            "min_profitable_iteration_rate": 0.70,
            "retain_iteration_reports": False,
            "parallel": {"enabled": True, "workers": 6, "scope": "grid"},
            "parameters": params,
        },
        "monkey": {
            "data_subset": data_subset,
            "runs": 300,
            "seed": 7,
            "beat_threshold": 0.90,
            "retain_iteration_reports": False,
            "parallel": {"enabled": True, "workers": 6, "scope": "runs"},
            "constraints": {
                "trade_count_tolerance_pct": 0.05,
                "long_short_ratio_tolerance": 0.05,
                "average_bars_tolerance_pct": 0.10,
                "duration_shape": 0.70,
                "rth_only": True,
                "enforce_non_overlapping": True,
                "enforce_max_trades_per_day": False,
            },
        },
        "wfa": {
            "data_subset": data_subset,
            "mode": "unanchored",
            "train_months": 48,
            "test_months": 12,
            "step_months": 12,
            "objective": "MAR",
            "selection_exclusive_min_trades_per_year": 50,
            "early_exit_min_train_profit_factor": 1.0,
            "parallel": {"enabled": True, "workers": 6, "scope": "window_grid"},
            "parameters": params,
        },
        "campaign_tests": {
            "acceptance_oos_test": {"train_months": 24, "test_months": 6},
        },
        "prop_rules": {
            "starting_balance": 150000,
            "daily_loss_limit": 4000,
            "trailing_drawdown": 4000,
            "max_contracts": 10,
            "max_best_day_profit_percentage": 0.50,
            "min_trading_days": 10,
            "payout_threshold": 188.9,
            "profit_target_pct": 0.06,
            "drawdown_limit_pct": 0.0267,
        },
        "monte_carlo": {
            "trade_source": "core",
            "runs": 300,
            "seed": 11,
            "path_months": 6,
            "skip_trade_probability": 0.05,
            "adverse_slippage_per_trade": 12.5,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "cluster_losses": True,
            "retain_path_trades": False,
            "retain_path_events": False,
            "parallel": {"enabled": True, "workers": 6, "scope": "runs"},
        },
    }


def _es_data() -> tuple[dict[str, Any], dict[str, Any]]:
    data_subset = {
        "start_date": "2011-01-03",
        "end_date": "2026-06-09",
        "session_labels": ["RTH"],
    }
    data = {
        "dataset_id": "es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny",
        "source_timeframe": "1m",
        "source": "parquet",
        "raw_parquet": "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet",
        "symbol": "ES",
        "timezone": "America/New_York",
        "exchange_timezone": "America/New_York",
        "feature_set": "none",
        "warmup_days": 10,
        "rth_start": "09:30:00",
        "rth_end": "15:59:00",
    }
    return data, data_subset


def _nq_data() -> tuple[dict[str, Any], dict[str, Any]]:
    data_subset = {
        "start_date": "2011-01-03",
        "end_date": "2026-06-12",
        "session_labels": ["RTH"],
    }
    data = {
        "dataset_id": "nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny",
        "source_timeframe": "1m",
        "source": "parquet",
        "raw_parquet": "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet",
        "symbol": "NQ",
        "timezone": "America/New_York",
        "exchange_timezone": "America/New_York",
        "feature_set": "none",
        "warmup_days": 10,
        "rth_start": "09:30:00",
        "rth_end": "15:59:00",
    }
    return data, data_subset


def _metadata(edge: str, mechanic: str, timeframe: str, failure_modes: str) -> dict[str, Any]:
    return {
        "academic_source": edge,
        "edge_thesis": mechanic,
        "mechanic": mechanic,
        "timeframe_rationale": timeframe,
        "mechanics_review_required": True,
        "mechanics_review_version": CREATED_AT,
        "mechanics_review": {
            "mechanic_expresses_edge": (
                mechanic
                + " The decision is made only after the source window has closed, so the signal expresses the archived edge without using future session highs, lows, VWAP, or final daily ranges."
            ),
            "entry_logic_rationale": (
                "The entry module consumes completed bars only, emits a signal at the configured signal or breakout close, and leaves execution to the engine for the next eligible bar. "
                "Session times are explicit America/New_York values and the configured max-trades-per-day gate prevents multiple same-day attempts."
            ),
            "stop_loss_rationale": (
                "The stop is declared before the run and is either a fixed percent-from-entry stop or the fixed archived slot stop carried in signal metadata. "
                "It is tick-rounded by the stop module and exposed to the engine's same-bar stop-target ordering assumptions."
            ),
            "target_exit_rationale": (
                "The profit target is a fixed reward-risk multiple declared before testing, with no target below 1.0R. "
                "Hard intraday flattening remains configured independently so any open position is closed before the prop-rule cutoff."
            ),
            "profitability_rationale": (
                "If the archived behavior is genuine rather than a historical artifact, neighboring thresholds should remain profitable after commission, one tick of slippage, pessimistic fill handling, and walk-forward selection from in-sample data only."
            ),
            "known_failure_modes": failure_modes,
            "pre_test_decision": "approve_for_testing",
        },
    }


def _campaign_yaml(campaign_id: str, title: str, instrument: str, edge_family: str, hypothesis: str, sources: list[dict[str, Any]], variants: list[str]) -> dict[str, Any]:
    return {
        "campaign_id": campaign_id,
        "title": title,
        "decision": "TEST",
        "created_at": CREATED_AT,
        "instrument": instrument,
        "market_timezone": "America/New_York",
        "edge_family": edge_family,
        "hypothesis": hypothesis,
        "sources": sources,
        "rationale": (
            "This revamp retest ports archive strategies that passed many historical stages or were close to passing into the current authored campaign tree. "
            "Only pre-result parameter spaces are declared here, and old over-wide grids are narrowed solely to satisfy current methodology caps."
        ),
        "data_needs": [
            "local completed-bar Sierra RTH orderflow parquet",
            "America/New_York timestamp handling and RTH session labels",
            "commission, slippage, tick size, point value, and forced flatten configured in each variant",
        ],
        "lookahead_risks": [
            "All signal windows are completed before the engine can enter on the next bar.",
            "No final session value, future daily range, future VWAP, or post-entry orderflow is used in the signal.",
            "Any pass remains only a candidate strategy pending source comparison and manual due diligence.",
        ],
        "duplicate_edge_check": {
            "archive_retest_scope": True,
            "active_revamp_direct_test_missing": True,
            "conclusion": (
                "These variants retest specific archived mechanics that were not directly present under the revamp source tree. "
                "They are not evidence for a new economic edge unless the current staged flow also passes."
            ),
        },
        "variants": variants,
        "rescue_policy": {
            "allowed": False,
            "reason": "Archive retests must be accepted or rejected under the predeclared current-compliant grids; no post-result rescue is authorized.",
        },
    }


def _orderflow_campaign() -> list[Path]:
    campaign_id = "es_archive_morning_orderflow_hold_retest"
    data, data_subset = _es_data()
    variants = [
        {
            "variant_id": "signed_flow_1030_flatten_1515",
            "flow_mode": "signed_imbalance",
            "flatten_time": "15:15:00",
            "min_signal_return_ticks": 16,
            "min_orderflow_imbalance": 0.03,
        },
        {
            "variant_id": "signed_flow_1030_flatten_1530",
            "flow_mode": "signed_imbalance",
            "flatten_time": "15:30:00",
            "min_signal_return_ticks": 16,
            "min_orderflow_imbalance": 0.02,
        },
        {
            "variant_id": "large10_flow_1030_flatten_1515",
            "flow_mode": "large10_imbalance",
            "flatten_time": "15:15:00",
            "min_signal_return_ticks": 16,
            "min_orderflow_imbalance": 0.02,
        },
        {
            "variant_id": "large20_flow_1030_flatten_1515",
            "flow_mode": "large20_imbalance",
            "flatten_time": "15:15:00",
            "min_signal_return_ticks": 16,
            "min_orderflow_imbalance": 0.02,
        },
        {
            "variant_id": "broad_large_alignment_1030_flatten_1515",
            "flow_mode": "broad_large_alignment",
            "flatten_time": "15:15:00",
            "min_signal_return_ticks": 16,
            "min_orderflow_imbalance": 0.02,
        },
    ]
    root = PROJECT_ROOT / "campaigns" / campaign_id
    _dump_yaml(
        root / "campaign.yaml",
        _campaign_yaml(
            campaign_id,
            "ES archived morning orderflow hold retest",
            "ES",
            "archive_opening_window_orderflow_continuation_late_hold",
            "A completed first-hour ES move should have same-day continuation value when completed aggregate trade-side orderflow confirms aggressive participation in the same direction.",
            [
                {
                    "title": "Market Intraday Momentum",
                    "authors": "Lei Gao, Yufeng Han, Sophia Zhengzi Li, Guofu Zhou",
                    "year": 2018,
                    "venue": "Journal of Financial Economics",
                    "link": "https://ideas.repec.org/a/eee/jfinec/v129y2018i2p394-414.html",
                    "doi": "10.1016/j.jfineco.2018.05.009",
                    "relevance": "Supports testing whether completed early intraday information predicts later same-day index futures returns.",
                },
                {
                    "title": "The Price Impact of Order Book Events",
                    "authors": "Rama Cont, Arseniy Kukanov, Sasha Stoikov",
                    "year": 2014,
                    "venue": "Journal of Financial Econometrics",
                    "link": "https://academic.oup.com/jfec/article-abstract/12/1/47/816163",
                    "doi": "10.1093/jjfinec/nbt003",
                    "relevance": "Motivates orderflow imbalance as a short-horizon price-pressure proxy, while this implementation uses aggregate completed-bar Sierra proxies rather than full-depth quote OFI.",
                },
            ],
            [item["variant_id"] for item in variants],
        ),
    )

    params = {
        "entry.params.min_signal_return_ticks": [8, 16, 24],
        "entry.params.min_orderflow_imbalance": [0.0, 0.02, 0.03],
        "sl.params.stop_pct": [0.0015, 0.002, 0.0025],
        "tp.params.target_r_multiple": [3.0, 4.0, 6.0],
    }
    paths: list[Path] = []
    for variant in variants:
        variant_id = variant["variant_id"]
        flatten_time = variant["flatten_time"]
        cfg = {
            "campaign_id": campaign_id,
            "variant_id": variant_id,
            "test_run_id": "run1",
            "strategy_name": "morning_orderflow_momentum",
            "symbol": "ES",
            "dataset_id": data["dataset_id"],
            "timeframe": "1m",
            "research_metadata": _metadata(
                "Gao et al. (2018) intraday momentum plus Cont, Kukanov, and Stoikov (2014) orderflow imbalance.",
                f"At the completed 10:30 ET first-hour close, trade ES in the direction of the 09:30-10:30 return only when completed {variant['flow_mode']} confirms that direction, then hold until {flatten_time} unless stop or target is hit.",
                "One-minute bars preserve the archived 10:30 ET signal timing, keep the source window completed before entry, and expose intraday stop/target conflicts to the engine.",
                "The archived late-hold orderflow variant may have been a narrow period artifact; Sierra aggregate signed-volume proxies may differ from true aggressor-side labels, and late-session holding can concentrate losses during reversals.",
            ),
            "data": data,
            "apex_rules": _common_apex(),
            "strategy": {
                "entry": {
                    "module": "morning_orderflow_momentum",
                    "params": {
                        "setup_mode": variant_id,
                        "direction_mode": "two_sided_continuation",
                        "flow_mode": variant["flow_mode"],
                        "rth_start": "09:30:00",
                        "signal_time": "10:30:00",
                        "flatten_time": flatten_time,
                        "bar_interval_minutes": 1,
                        "tick_size": 0.25,
                        "min_signal_return_ticks": variant["min_signal_return_ticks"],
                        "min_orderflow_imbalance": variant["min_orderflow_imbalance"],
                        "stop_pct": 0.0015,
                        "target_r_multiple": 3.0,
                        "max_trades_per_day": 1,
                    },
                },
                "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.0015, "round_to_tick": True}},
                "tp": {"module": "fixed_r", "params": {"target_r_multiple": 3.0}},
                "flatten_time": flatten_time,
            },
            "core": _core("ES", flatten_time, data_subset),
            "benchmarks": _benchmarks(1.3, 0.05, 0.5),
            **_stage_sections(data_subset, params),
        }
        vroot = root / "variants" / variant_id
        _dump_yaml(vroot / "config.yaml", cfg)
        _write_modules(vroot, "orderflow")
        _write_variant_readme(vroot, campaign_id, variant_id, cfg)
        paths.append(vroot / "config.yaml")
    return paths


def _momentum_slots(kind: str) -> tuple[str, list[dict[str, Any]], dict[str, list[Any]], str]:
    if kind == "priority_long50":
        return (
            "15:59:00",
            [
                _slot("nq_1030_short_weakness", "short", "short", "10:30:00", 40, 0.0035, 3.0),
                _slot("nq_1130_long_strength", "long", "long", "11:30:00", 50, 0.0035, 2.5),
            ],
            {
                "entry.params.short_min_signal_return_bps": [35, 40, 45],
                "entry.params.long_min_signal_return_bps": [45, 50, 55],
            },
            "first a 10:30 short weakness slot, then an 11:30 long strength slot with the archived long threshold centered at 50 bps",
        )
    if kind == "priority_base":
        return (
            "15:59:00",
            [
                _slot("nq_1030_short_weakness", "short", "short", "10:30:00", 40, 0.0035, 3.0),
                _slot("nq_1130_long_strength", "long", "long", "11:30:00", 40, 0.0035, 2.5),
            ],
            {
                "entry.params.short_min_signal_return_bps": [35, 40, 45],
                "entry.params.long_min_signal_return_bps": [35, 40, 45],
            },
            "first a 10:30 short weakness slot, then an 11:30 long strength slot with the archived base threshold centered at 40 bps",
        )
    if kind == "long_balanced":
        return (
            "15:59:00",
            [
                _slot(
                    "nq_1030_long_strength",
                    "main",
                    "long",
                    "10:30:00",
                    40,
                    0.0035,
                    3.0,
                    min_source_efficiency=0.0,
                    min_close_location=0.0,
                    max_source_range_bps=200,
                )
            ],
            {
                "entry.params.main_min_signal_return_bps": [30, 35, 40],
                "entry.params.main_max_source_range_bps": [180, 200, 220],
            },
            "a single 10:30 long strength slot with the archived 200 bps maximum source-range cap centered in the grid",
        )
    if kind == "long_efficiency":
        return (
            "15:59:00",
            [
                _slot(
                    "nq_1030_long_strength_efficiency",
                    "main",
                    "long",
                    "10:30:00",
                    40,
                    0.0035,
                    3.0,
                    min_source_efficiency=0.55,
                    min_close_location=0.55,
                    max_source_range_bps=200,
                )
            ],
            {
                "entry.params.main_min_signal_return_bps": [30, 35, 40],
                "entry.params.main_max_source_range_bps": [160, 200, 240],
            },
            "a single 10:30 long strength slot requiring a cleaner directional close and source-window efficiency",
        )
    if kind == "short_weakness":
        return (
            "15:59:00",
            [
                _slot(
                    "nq_1030_short_weakness_only",
                    "main",
                    "short",
                    "10:30:00",
                    40,
                    0.0035,
                    3.0,
                    min_source_efficiency=0.0,
                    min_close_location=0.0,
                    max_source_range_bps=220,
                )
            ],
            {
                "entry.params.main_min_signal_return_bps": [30, 40, 50],
                "entry.params.main_max_source_range_bps": [180, 220, 260],
            },
            "a single 10:30 short weakness slot that isolates the short side of the archived priority rule",
        )
    raise ValueError(kind)


def _slot(
    slot_id: str,
    prefix: str,
    direction: str,
    signal_time: str,
    min_signal_return_bps: float,
    stop_pct: float,
    target_r_multiple: float,
    *,
    min_source_efficiency: float = 0.0,
    min_close_location: float = 0.0,
    max_source_range_bps: float | None = None,
) -> dict[str, Any]:
    slot = {
        "slot_id": slot_id,
        "param_prefix": prefix,
        "direction": direction,
        "source_start": "09:30:00",
        "signal_time": signal_time,
        "min_signal_return_bps": min_signal_return_bps,
        "min_signal_return_ticks": 0,
        "min_source_efficiency": min_source_efficiency,
        "min_close_location": min_close_location,
        "min_source_range_bps": 0,
        "max_source_range_bps": max_source_range_bps,
        "stop_pct": stop_pct,
        "target_r_multiple": target_r_multiple,
        "flatten_time": "15:59:00",
    }
    return slot


def _momentum_campaign() -> list[Path]:
    campaign_id = "nq_archive_intraday_momentum_retest"
    data, data_subset = _nq_data()
    variants = [
        ("priority_short1030_long1130_long50", "priority_long50"),
        ("priority_short1030_long1130_base", "priority_base"),
        ("long_only_1030_strength_balanced", "long_balanced"),
        ("long_only_1030_strength_efficiency", "long_efficiency"),
        ("short_only_1030_weakness", "short_weakness"),
    ]
    root = PROJECT_ROOT / "campaigns" / campaign_id
    _dump_yaml(
        root / "campaign.yaml",
        _campaign_yaml(
            campaign_id,
            "NQ archived intraday momentum retest",
            "NQ",
            "archive_nq_intraday_return_priority_and_morning_strength",
            "Large completed NQ morning returns may persist intraday, with priority given to an early short weakness signal before a later long strength signal in the archived rule.",
            [
                {
                    "title": "Market Intraday Momentum",
                    "authors": "Lei Gao, Yufeng Han, Sophia Zhengzi Li, Guofu Zhou",
                    "year": 2018,
                    "venue": "Journal of Financial Economics",
                    "link": "https://ideas.repec.org/a/eee/jfinec/v129y2018i2p394-414.html",
                    "doi": "10.1016/j.jfineco.2018.05.009",
                    "relevance": "Supports testing whether completed intraday index-market returns forecast later same-day direction.",
                },
                {
                    "title": "Time Series Momentum",
                    "authors": "Tobias J. Moskowitz, Yao Hua Ooi, Lasse Heje Pedersen",
                    "year": 2012,
                    "venue": "Journal of Financial Economics",
                    "link": "https://www.sciencedirect.com/science/article/abs/pii/S0304405X11002613",
                    "doi": "10.1016/j.jfineco.2011.11.003",
                    "relevance": "Provides broader evidence that futures returns can persist, while this campaign tests only intraday completed-window persistence.",
                },
            ],
            [item[0] for item in variants],
        ),
    )

    paths: list[Path] = []
    for variant_id, kind in variants:
        flatten_time, slots, params, slot_description = _momentum_slots(kind)
        cfg = {
            "campaign_id": campaign_id,
            "variant_id": variant_id,
            "test_run_id": "run1",
            "strategy_name": "intraday_momentum_priority",
            "symbol": "NQ",
            "dataset_id": data["dataset_id"],
            "timeframe": "5m",
            "research_metadata": _metadata(
                "Gao et al. (2018) intraday momentum and Moskowitz, Ooi, and Pedersen (2012) futures time-series momentum.",
                f"Use completed NQ RTH bars from 09:30 ET through each signal time; the active rule tests {slot_description}, then flattens by 15:59 ET unless the fixed slot stop or fixed-R target is hit.",
                "Five-minute bars match the archived NQ staged tests while keeping each source window complete at the signal close and leaving the engine to enter on the next bar.",
                "The archive used Databento dominant-session data while this revamp retest uses the local Sierra completed-bar cache; any pass therefore needs source-comparison review, and narrow NQ trend days can dominate results.",
            ),
            "data": data,
            "apex_rules": _common_apex(),
            "strategy": {
                "entry": {
                    "module": "intraday_momentum_priority",
                    "params": {
                        "setup_mode": variant_id,
                        "rth_start": "09:30:00",
                        "bar_interval_minutes": 5,
                        "tick_size": 0.25,
                        "max_trades_per_day": 1,
                        "slots": slots,
                    },
                },
                "sl": {
                    "module": "signal_percent_from_entry",
                    "params": {"default_stop_pct": 0.0035, "metadata_key": "stop_pct", "round_to_tick": True},
                },
                "tp": {
                    "module": "signal_fixed_r",
                    "params": {"default_target_r_multiple": 3.0, "metadata_key": "target_r_multiple"},
                },
                "flatten_time": flatten_time,
            },
            "core": _core("NQ", flatten_time, data_subset),
            "benchmarks": _benchmarks(1.3, 0.05, 0.5),
            **_stage_sections(data_subset, params),
        }
        vroot = root / "variants" / variant_id
        _dump_yaml(vroot / "config.yaml", cfg)
        _write_modules(vroot, "momentum")
        _write_variant_readme(vroot, campaign_id, variant_id, cfg)
        paths.append(vroot / "config.yaml")
    return paths


def _range_campaign() -> list[Path]:
    campaign_id = "nq_archive_range_compression_retest"
    data, data_subset = _nq_data()
    variants = [
        {
            "variant_id": "nr7_or30_1040_rank_relaxed_138cap",
            "setup_mode": "nr7_or30_1040_rank_relaxed_138cap",
            "start_time": "10:15:00",
            "end_time": "10:40:00",
            "lookback_days": 7,
            "max_range_rank_pct": 0.45,
            "max_prior_range_points": 138,
            "breakout_level_source": "opening_range",
            "opening_range_minutes": 30,
            "require_inside_day": False,
            "require_open_inside_reference": False,
            "min_breakout_ticks": 4,
        },
        {
            "variant_id": "nr7_or30_morning_range_capped",
            "setup_mode": "nr7_or30_morning_range_capped",
            "start_time": "10:15:00",
            "end_time": "10:30:00",
            "lookback_days": 7,
            "max_range_rank_pct": 0.45,
            "max_prior_range_points": 120,
            "breakout_level_source": "opening_range",
            "opening_range_minutes": 30,
            "require_inside_day": False,
            "require_open_inside_reference": False,
            "min_breakout_ticks": 4,
        },
        {
            "variant_id": "nr7_or30_1045_rank_relaxed_135cap",
            "setup_mode": "nr7_or30_1045_rank_relaxed_135cap",
            "start_time": "10:15:00",
            "end_time": "10:45:00",
            "lookback_days": 7,
            "max_range_rank_pct": 0.45,
            "max_prior_range_points": 135,
            "breakout_level_source": "opening_range",
            "opening_range_minutes": 30,
            "require_inside_day": False,
            "require_open_inside_reference": False,
            "min_breakout_ticks": 4,
        },
        {
            "variant_id": "nr7_or30_1130_range_capped",
            "setup_mode": "nr7_or30_1130_range_capped",
            "start_time": "10:15:00",
            "end_time": "11:30:00",
            "lookback_days": 7,
            "max_range_rank_pct": 0.45,
            "max_prior_range_points": 120,
            "breakout_level_source": "opening_range",
            "opening_range_minutes": 30,
            "require_inside_day": False,
            "require_open_inside_reference": False,
            "min_breakout_ticks": 4,
        },
        {
            "variant_id": "id_nr4_prior_session_breakout",
            "setup_mode": "id_nr4",
            "start_time": "09:35:00",
            "end_time": "14:30:00",
            "lookback_days": 4,
            "max_range_rank_pct": 0.25,
            "max_prior_range_points": None,
            "breakout_level_source": "prior_session",
            "opening_range_minutes": 30,
            "require_inside_day": True,
            "require_open_inside_reference": False,
            "min_breakout_ticks": 0,
        },
    ]
    root = PROJECT_ROOT / "campaigns" / campaign_id
    _dump_yaml(
        root / "campaign.yaml",
        _campaign_yaml(
            campaign_id,
            "NQ archived range compression retest",
            "NQ",
            "archive_nq_nr7_or30_and_inside_nr4_breakout",
            "A narrow prior NQ session or inside narrow-range day may create compression that resolves through a completed opening-range or prior-session breakout.",
            [
                {
                    "title": "Day Trading With Short Term Price Patterns and Opening Range Breakout",
                    "authors": "Toby Crabel",
                    "year": 1990,
                    "venue": "Trader's Press",
                    "link": "https://www.traderspress.com/",
                    "relevance": "Documents narrow-range and opening-range breakout patterns used as the archived range-compression mechanics.",
                },
                {
                    "title": "Street Smarts",
                    "authors": "Linda Bradford Raschke and Laurence A. Connors",
                    "year": 1995,
                    "venue": "M. Gordon Publishing",
                    "link": "https://lbrgroup.com/",
                    "relevance": "Practitioner source for NR7 and intraday breakout concepts; this implementation adds current cost, fill, and prop-rule gates.",
                },
            ],
            [item["variant_id"] for item in variants],
        ),
    )

    params = {
        "entry.params.max_range_rank_pct": [0.25, 0.45, 0.60],
        "entry.params.min_breakout_ticks": [0, 4],
        "sl.params.stop_pct": [0.003, 0.0035, 0.004],
        "tp.params.target_r_multiple": [1.25, 1.5, 2.0],
    }
    paths: list[Path] = []
    for variant in variants:
        variant_id = variant["variant_id"]
        entry_params = {
            "setup_mode": variant["setup_mode"],
            "rth_start": "09:30:00",
            "start_time": variant["start_time"],
            "end_time": variant["end_time"],
            "bar_interval_minutes": 5,
            "opening_range_minutes": variant["opening_range_minutes"],
            "lookback_days": variant["lookback_days"],
            "max_range_rank_pct": variant["max_range_rank_pct"],
            "require_inside_day": variant["require_inside_day"],
            "breakout_level_source": variant["breakout_level_source"],
            "min_prior_range_points": 0,
            "min_breakout_ticks": variant["min_breakout_ticks"],
            "tick_size": 0.25,
            "allow_long": True,
            "allow_short": True,
            "max_trades_per_day": 1,
            "require_open_inside_reference": variant["require_open_inside_reference"],
        }
        if variant["max_prior_range_points"] is not None:
            entry_params["max_prior_range_points"] = variant["max_prior_range_points"]
        cfg = {
            "campaign_id": campaign_id,
            "variant_id": variant_id,
            "test_run_id": "run1",
            "strategy_name": "range_compression_breakout",
            "symbol": "NQ",
            "dataset_id": data["dataset_id"],
            "timeframe": "5m",
            "research_metadata": _metadata(
                "Crabel (1990) narrow-range and opening-range breakouts plus Raschke and Connors (1995) short-term price patterns.",
                f"After a completed prior-session compression setup, trade NQ breakouts of the {variant['breakout_level_source']} reference from {variant['start_time']} to {variant['end_time']}, then flatten at 15:59 ET unless stop or target is hit.",
                "Five-minute bars match the archive NQ tests, ensure the opening range or prior-session reference is completed before breakout confirmation, and keep stop/target ordering visible to the engine.",
                "Compression breakouts are vulnerable to false breaks, old archive data was Databento while this retest uses Sierra completed bars, and relaxing rank or range caps can create narrow-date overfit if neighboring parameters do not hold up.",
            ),
            "data": data,
            "apex_rules": _common_apex(),
            "strategy": {
                "entry": {"module": "range_compression_breakout", "params": entry_params},
                "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.0035, "round_to_tick": True}},
                "tp": {
                    "module": "cost_adjusted_fixed_r",
                    "params": {
                        "target_r_multiple": 1.5,
                        "tick_size": 0.25,
                        "tick_value": 5.0,
                        "commission_per_contract": 2.5,
                        "slippage_ticks": 1,
                        "round_to_tick": True,
                    },
                },
                "flatten_time": "15:59:00",
            },
            "core": _core("NQ", "15:59:00", data_subset),
            "benchmarks": _benchmarks(1.3, 0.05, 0.5),
            **_stage_sections(data_subset, params),
        }
        vroot = root / "variants" / variant_id
        _dump_yaml(vroot / "config.yaml", cfg)
        _write_modules(vroot, "range")
        _write_variant_readme(vroot, campaign_id, variant_id, cfg)
        paths.append(vroot / "config.yaml")
    return paths


def _write_modules(vroot: Path, kind: str) -> None:
    modules = vroot / "strategy_modules"
    if kind == "orderflow":
        _write_text(
            modules / "entry.py",
            "from propstack.strategy_modules.entry.morning_orderflow_momentum import MorningOrderflowMomentumEntry\n\nENTRY_MODULE = MorningOrderflowMomentumEntry\n",
        )
        _write_text(
            modules / "stop.py",
            "from propstack.strategy_modules.sl.percent_from_entry import PercentFromEntryStop\n\nSTOP_MODULE = PercentFromEntryStop\n",
        )
        _write_text(
            modules / "target.py",
            "from propstack.strategy_modules.tp.fixed_r import FixedRTarget\n\nTARGET_MODULE = FixedRTarget\n",
        )
        return
    if kind == "momentum":
        _write_text(
            modules / "entry.py",
            "from propstack.strategy_modules.entry.intraday_momentum_priority import IntradayMomentumPriorityEntry\n\nENTRY_MODULE = IntradayMomentumPriorityEntry\n",
        )
        _write_text(
            modules / "stop.py",
            "from propstack.strategy_modules.sl.signal_percent_from_entry import SignalPercentFromEntryStop\n\nSTOP_MODULE = SignalPercentFromEntryStop\n",
        )
        _write_text(
            modules / "target.py",
            "from propstack.strategy_modules.tp.signal_fixed_r import SignalFixedRTarget\n\nTARGET_MODULE = SignalFixedRTarget\n",
        )
        return
    if kind == "range":
        _write_text(
            modules / "entry.py",
            "from propstack.strategy_modules.entry.range_compression_breakout import RangeCompressionBreakoutEntry\n\nENTRY_MODULE = RangeCompressionBreakoutEntry\n",
        )
        _write_text(
            modules / "stop.py",
            "from propstack.strategy_modules.sl.percent_from_entry import PercentFromEntryStop\n\nSTOP_MODULE = PercentFromEntryStop\n",
        )
        _write_text(
            modules / "target.py",
            "from propstack.strategy_modules.tp.cost_adjusted_fixed_r import CostAdjustedFixedRTarget\n\nTARGET_MODULE = CostAdjustedFixedRTarget\n",
        )
        return
    raise ValueError(kind)


def _write_variant_readme(vroot: Path, campaign_id: str, variant_id: str, cfg: dict[str, Any]) -> None:
    mechanic = cfg["research_metadata"]["mechanic"]
    params = cfg["core_grid"]["parameters"]
    combo_count = 1
    for values in params.values():
        combo_count *= len(values)
    _write_text(
        vroot / "README.md",
        (
            f"# {campaign_id} / {variant_id}\n\n"
            f"{mechanic}\n\n"
            f"Parameter grid: {combo_count} combinations, capped to at most two entry parameters, one stop parameter, and one target parameter before testing.\n"
        ),
    )


def main() -> None:
    paths = []
    paths.extend(_orderflow_campaign())
    paths.extend(_momentum_campaign())
    paths.extend(_range_campaign())
    for path in paths:
        print(path.relative_to(PROJECT_ROOT))


if __name__ == "__main__":
    main()
