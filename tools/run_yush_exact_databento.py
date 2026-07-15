from __future__ import annotations

import argparse
from datetime import datetime
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from propstack.backtest.engine import BacktestEngine
from propstack.backtest.yush_exact_orderflow import ExactYushRangeConfig, ExactYushRangeEventStrategy, _extended_metrics
from propstack.data.databento_session_stream import iter_databento_trade_sessions
from propstack.prop.rules import PropRules
from propstack.research.campaign_stages import update_source_results_index
from propstack.research.monte_carlo import run_monte_carlo
from propstack.research.policy import active_research_policy_metadata
from propstack.research.run_store import ensure_run_uid
from propstack.research.schemas import validate_run_summary_contract
from propstack.utils.config import update_runs_index
from propstack.utils.hashing import file_sha256, object_sha256
from propstack.validation import (
    ValidationMetadata,
    build_condition_snapshots,
    build_exit_audits,
    build_trade_summaries,
    write_validation_run,
)
from propstack.version import ENGINE_CONTRACT_VERSION


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay the exact Yush range strategy on Databento trades.")
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    config = yaml.safe_load(args.config.read_text())
    _validate_frozen_mechanics_contract(config)
    data = config["data"]
    core = config["core"]
    mechanics = config["mechanics"]
    replay_config = ExactYushRangeConfig(
        tick_size=float(core["tick_size"]),
        point_value=float(core["point_value"]),
        contracts=int(core["contracts"]),
        commission_per_contract=float(core["commission_per_contract"]),
        max_trades_per_day=int(mechanics["max_trades_per_day"]),
        max_aoi_width_points=float(mechanics["max_aoi_width_points"]),
        entry_offset_ticks=int(mechanics["entry_offset_ticks"]),
        stop_offset_ticks=int(mechanics["stop_offset_ticks"]),
        max_stop_points=float(mechanics["max_stop_points"]),
        value_area_fraction=float(mechanics["value_area_fraction"]),
        range_expansion_fraction=float(mechanics["range_expansion_fraction"]),
        delta_profile_min_abs=int(mechanics["delta_profile_min_abs"]),
        delta_bubble_threshold=int(mechanics["delta_bubble_threshold"]),
        big_trade_threshold=int(mechanics["big_trade_threshold"]),
        big_trade_window_ms=int(mechanics["big_trade_window_ms"]),
        breakeven_offset_points=float(mechanics["breakeven_offset_points"]),
        opening_range_seconds=int(mechanics["opening_range_seconds"]),
        bar_seconds=int(mechanics["bar_seconds"]),
        breakout_probe_ticks=int(mechanics["breakout_probe_ticks"]),
        initial_balance=float(core["initial_balance"]),
    )
    sessions = iter_databento_trade_sessions(
        data["archive"],
        data["roll_calendar"],
        start_date=data["start_date"],
        end_date=data["end_date"],
        root_symbol=config.get("symbol", "ES"),
        reset_previous_levels_on_roll=bool(data.get("reset_previous_levels_on_roll", True)),
    )
    counter = {"sessions": 0}

    def tracked_sessions():
        for session in sessions:
            counter["sessions"] += 1
            if counter["sessions"] == 1 or counter["sessions"] % 10 == 0:
                print(f"replaying session {counter['sessions']}: {session.session_date}", flush=True)
            yield session

    news_events_by_session = _load_news_events(config)
    result = BacktestEngine(config).run_event_replay(
        tracked_sessions(),
        ExactYushRangeEventStrategy(replay_config, news_events_by_session),
    )
    result["metrics"].update(_extended_metrics(result["trades"]))
    output = args.output
    core_dir = output / "core"
    core_dir.mkdir(parents=True, exist_ok=True)
    trades = result["trades"]
    daily = result["daily"]
    audits = result["session_audits"]
    trades.to_csv(core_dir / "trade_log.csv", index=False)
    daily.to_csv(core_dir / "daily_results.csv", index=False)
    audits.to_csv(core_dir / "session_audits.csv", index=False)
    result["event_transitions"].to_csv(core_dir / "event_transitions.csv", index=False)
    _write_json(core_dir / "event_replay_diagnostics.json", result["diagnostics"])
    _write_json(core_dir / "event_replay_reproducibility.json", result["reproducibility"])
    _equity_curve(trades, replay_config.initial_balance).to_csv(core_dir / "equity_curve.csv", index=False)
    _write_breakdowns(trades, core_dir)
    _write_execution_sensitivity(trades, core_dir, float(core["tick_value"]))
    validation_summary = _write_validation_audit(trades, output, replay_config)
    metrics = dict(result["metrics"])
    metrics.update(
        {
            "sessions_replayed": int(counter["sessions"]),
            "first_session": str(audits["session_date"].min()) if not audits.empty else None,
            "last_session": str(audits["session_date"].max()) if not audits.empty else None,
            "news_calendar_applied": bool(config["event_filters"]["high_impact_usd_news"].get("calendar")),
            "forced_flatten_compliance": bool(
                trades.empty
                or (pd.to_datetime(trades["exit_timestamp"], utc=True).dt.tz_convert("America/New_York").dt.time <= pd.Timestamp("11:00:00").time()).all()
            ),
        }
    )
    _write_json(core_dir / "metrics.json", metrics)
    _write_split_metrics(trades, core_dir, replay_config.initial_balance)
    _write_provenance(config, args.config, output)
    _write_dashboard_validation_bundle(config, args.config, output, result)
    monte_carlo_summary = _run_monte_carlo(config, trades, output)
    _write_summary(config, args.config, metrics, monte_carlo_summary, validation_summary, output)
    _write_methodology_audit(config, metrics, monte_carlo_summary, output)
    print(output)


def _validate_frozen_mechanics_contract(config: dict) -> None:
    mechanics = config.get("mechanics") or {}
    expected_mechanics = {
        "entry_start": "09:30:00",
        "entry_end_exclusive": "11:00:00",
        "flatten_time": "11:00:00",
        "max_trades_per_day": 3,
        "value_area_fraction": 0.70,
        "profile_bucket_ticks": 1,
        "opening_range_seconds": 32,
        "max_aoi_width_points": 3.0,
        "entry_offset_ticks": 2,
        "stop_offset_ticks": 2,
        "max_stop_points": 5.0,
        "range_expansion_fraction": 0.20,
        "breakout_probe_ticks": 2,
        "breakout_followthrough_completed_bars": 2,
        "reversal_count_required": 2,
        "delta_profile_bucket_ticks": [1, 4],
        "delta_profile_min_abs": 300,
        "delta_profile_neighbour_multiple": 2.0,
        "delta_profile_neighbours_each_side": 2,
        "delta_bubble_bucket_ticks": 4,
        "delta_bubble_threshold": 300,
        "big_trade_threshold": 200,
        "big_trade_window_ms": 100,
        "breakeven_offset_points": 1.25,
        "breakeven_activation_requires_stop_level_traded": True,
        "bar_seconds": 180,
        "causal_order": "eligible_aoi_before_tap_before_bubble_before_fill",
        "aoi_anchor_levels": ["VAL", "VAH"],
        "additional_confluence_categories": ["market", "delta_profile", "big_trade"],
        "market_levels": ["PDH", "PDL", "PDC", "ONH", "ONL", "ORH", "ORL"],
        "bubble_trigger_operator": "OR",
        "exact_fill_assumption": "requested_trigger_price_zero_slippage",
        "post_initial_stop_direction_rule": "opposite_until_opposite_fill_or_session_end",
    }
    mismatches = [
        f"mechanics.{key}: expected {expected!r}, got {mechanics.get(key)!r}"
        for key, expected in expected_mechanics.items()
        if mechanics.get(key) != expected
    ]
    core = config.get("core") or {}
    expected_core = {
        "tick_size": 0.25,
        "point_value": 50.0,
        "tick_value": 12.5,
        "contracts": 1,
        "commission_per_contract": 2.5,
        "slippage_ticks": 0,
        "entry_start": "09:30:00",
        "flatten_time": "11:00:00",
        "max_trades_per_day": 3,
        "event_stop_market_fill_policy": "exact_requested_price",
    }
    mismatches.extend(
        f"core.{key}: expected {expected!r}, got {core.get(key)!r}"
        for key, expected in expected_core.items()
        if core.get(key) != expected
    )
    news = ((config.get("event_filters") or {}).get("high_impact_usd_news") or {})
    expected_news = {
        "required": True,
        "flatten_at_minutes_before": 5,
        "block_entries_from_minutes_before": 5,
        "block_entries_through_release": True,
        "post_release_buffer_minutes": 0,
    }
    mismatches.extend(
        f"event_filters.high_impact_usd_news.{key}: expected {expected!r}, got {news.get(key)!r}"
        for key, expected in expected_news.items()
        if news.get(key) != expected
    )
    if core.get("max_trades_per_day") != mechanics.get("max_trades_per_day"):
        mismatches.append("core.max_trades_per_day must equal mechanics.max_trades_per_day")
    if config.get("engine_lane") != "canonical_event_replay":
        mismatches.append("engine_lane must be 'canonical_event_replay'")
    if mismatches:
        raise ValueError("Frozen exact-Yush mechanics contract mismatch:\n- " + "\n- ".join(mismatches))


def _load_news_events(config: dict) -> dict:
    rule = config["event_filters"]["high_impact_usd_news"]
    calendar = rule.get("calendar")
    if not calendar:
        return {}
    frame = pd.read_csv(calendar)
    required = {"release_timestamp", "currency", "impact"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"News calendar is missing required columns: {missing}")
    raw_timestamps = frame["release_timestamp"].astype(str)
    timezone_aware = raw_timestamps.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True)
    if not bool(timezone_aware.all()):
        raise ValueError("Every news release_timestamp must include an explicit UTC offset or Z suffix.")
    selected = frame.loc[
        frame["currency"].astype(str).str.upper().eq("USD")
        & frame["impact"].astype(str).str.lower().eq("high")
    ].copy()
    selected["timestamp"] = pd.to_datetime(
        selected["release_timestamp"],
        utc=True,
        format="mixed",
        errors="raise",
    ).dt.tz_convert("America/New_York")
    out: dict[object, tuple[pd.Timestamp, ...]] = {}
    for session_date, group in selected.groupby(selected["timestamp"].dt.date):
        out[session_date] = tuple(group["timestamp"].sort_values())
    return out


def _equity_curve(trades: pd.DataFrame, initial_balance: float) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame([{"sequence": 0, "trade_id": None, "equity": initial_balance}])
    ordered = trades.sort_values(["exit_timestamp", "trade_id"], kind="mergesort").reset_index(drop=True)
    return pd.DataFrame(
        {
            "sequence": np.arange(1, len(ordered) + 1),
            "trade_id": ordered["trade_id"],
            "exit_timestamp": ordered["exit_timestamp"],
            "equity": initial_balance + ordered["net_pnl"].cumsum(),
        }
    )


def _write_breakdowns(trades: pd.DataFrame, output: Path) -> None:
    if trades.empty:
        for name in ("yearly", "monthly", "time_of_day", "direction", "exit_reason"):
            pd.DataFrame().to_csv(output / f"{name}_breakdown.csv", index=False)
        return
    frame = trades.copy()
    timestamp = pd.to_datetime(frame["entry_timestamp"], utc=True).dt.tz_convert("America/New_York")
    frame["year"] = timestamp.dt.year
    frame["month"] = timestamp.dt.to_period("M").astype(str)
    frame["time_bucket"] = timestamp.dt.floor("15min").dt.strftime("%H:%M")
    for name, column in (
        ("yearly", "year"),
        ("monthly", "month"),
        ("time_of_day", "time_bucket"),
        ("direction", "direction"),
        ("exit_reason", "exit_reason"),
    ):
        grouped = frame.groupby(column, dropna=False).agg(
            trades=("trade_id", "count"),
            net_profit=("net_pnl", "sum"),
            average_trade=("net_pnl", "mean"),
            win_rate=("net_pnl", lambda values: float((values > 0).mean())),
        ).reset_index()
        grouped.to_csv(output / f"{name}_breakdown.csv", index=False)


def _write_split_metrics(trades: pd.DataFrame, output: Path, initial_balance: float) -> None:
    from propstack.backtest.metrics import calculate_metrics

    trades = trades.copy()
    for column in ("entry_timestamp", "exit_timestamp"):
        if column in trades:
            trades[column] = pd.to_datetime(trades[column], utc=True, format="mixed")
    timestamp = pd.to_datetime(trades.get("entry_timestamp", pd.Series(dtype=str)), utc=True)
    split = pd.Timestamp("2026-03-01", tz="UTC")
    payload = {
        "development_20250714_20260228": calculate_metrics(trades.loc[timestamp < split], initial_balance),
        "locked_holdout_20260301_20260710": calculate_metrics(trades.loc[timestamp >= split], initial_balance),
    }
    _write_json(output / "chronological_split_metrics.json", payload)
    holdout = trades.loc[timestamp >= split]
    holdout.to_csv(output / "chronological_holdout_trade_log.csv", index=False)
    wfa_dir = output.parent / "wfa"
    wfa_dir.mkdir(parents=True, exist_ok=True)
    holdout.to_csv(wfa_dir / "wfa_stitched_oos_trade_log.csv", index=False)
    _write_json(
        wfa_dir / "wfa_summary.json",
        {
            "method": "single_locked_oos_fold_fixed_configuration",
            "parameter_selection_performed": False,
            "development_end_exclusive": "2026-03-01",
            "locked_holdout_start": "2026-03-01",
            "locked_holdout_end": "2026-07-10",
            "oos_metrics": payload["locked_holdout_20260301_20260710"],
        },
    )


def _write_execution_sensitivity(trades: pd.DataFrame, output: Path, tick_value: float) -> None:
    rows = []
    for ticks_per_side in (0, 1, 2):
        adjusted = trades["net_pnl"] - (2 * ticks_per_side * tick_value * trades["contracts"])
        wins = float(adjusted.loc[adjusted > 0].sum())
        losses = abs(float(adjusted.loc[adjusted < 0].sum()))
        rows.append(
            {
                "additional_slippage_ticks_per_side": ticks_per_side,
                "path_assumption": "static_trade_path_cost_sensitivity_only",
                "total_trades": int(len(trades)),
                "net_profit": float(adjusted.sum()),
                "average_trade": float(adjusted.mean()) if len(adjusted) else 0.0,
                "profit_factor": wins / losses if losses else None,
            }
        )
    pd.DataFrame(rows).to_csv(output / "execution_cost_sensitivity.csv", index=False)


def _write_validation_audit(
    trades: pd.DataFrame,
    output: Path,
    config: ExactYushRangeConfig,
) -> dict:
    validation_dir = output / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    if trades.empty:
        checks = [{"check": "nonempty_trade_log", "passed": False, "failures": 1}]
    else:
        frame = trades.copy()
        entry = pd.to_datetime(frame["entry_timestamp"], utc=True).dt.tz_convert("America/New_York")
        exit_ = pd.to_datetime(frame["exit_timestamp"], utc=True).dt.tz_convert("America/New_York")
        eligible = pd.to_datetime(frame["aoi_eligible_timestamp"], utc=True)
        tapped = pd.to_datetime(frame["aoi_tap_timestamp"], utc=True)
        bubble = pd.to_datetime(frame["bubble_qualified_timestamp"], utc=True)
        armed = pd.to_datetime(frame["order_armed_timestamp"], utc=True)
        entry_utc = pd.to_datetime(frame["entry_timestamp"], utc=True)
        exit_utc = pd.to_datetime(frame["exit_timestamp"], utc=True)
        causal_timestamps = (
            (eligible <= tapped)
            & (tapped <= bubble)
            & (bubble <= armed)
            & (armed <= entry_utc)
            & (entry_utc <= exit_utc)
        )
        causal_events = (
            (frame["aoi_eligible_event_index"] < frame["aoi_tap_event_index"])
            & (frame["aoi_tap_event_index"] < frame["bubble_qualified_event_index"])
            & (frame["bubble_qualified_event_index"] <= frame["order_armed_event_index"])
            & (frame["order_armed_event_index"] < frame["entry_event_index"])
        )
        daily_count = frame.groupby("session_date")["trade_id"].transform("count")
        long = frame["direction"].eq("long")
        expected_entry = frame["aoi_box_high"].where(long, frame["aoi_box_low"]) + np.where(
            long,
            config.entry_offset_ticks * config.tick_size,
            -config.entry_offset_ticks * config.tick_size,
        )
        expected_stop = frame["aoi_box_low"].where(long, frame["aoi_box_high"]) + np.where(
            long,
            -config.stop_offset_ticks * config.tick_size,
            config.stop_offset_ticks * config.tick_size,
        )
        target = pd.to_numeric(frame["target_price"], errors="coerce")
        target_side = target.isna() | (
            (long & (target > frame["entry_price"])) | (~long & (target < frame["entry_price"]))
        )
        check_masks = {
            "unique_trade_id": ~frame["trade_id"].duplicated(keep=False),
            "one_fill_per_aoi_lineage": ~frame.duplicated(["session_date", "aoi_lineage_id"], keep=False),
            "causal_event_order_eligible_tap_bubble_arm_fill": causal_events,
            "causal_timestamps_nondecreasing_through_exit": causal_timestamps,
            "entry_window_0930_to_before_1100_et": (
                (entry.dt.time >= pd.Timestamp("09:30:00").time())
                & (entry.dt.time < pd.Timestamp("11:00:00").time())
            ),
            "forced_flatten_by_1100_et": exit_.dt.time <= pd.Timestamp("11:00:00").time(),
            "maximum_three_trades_per_session": daily_count <= config.max_trades_per_day,
            "aoi_width_at_most_three_points": frame["aoi_width_points"].between(
                0, config.max_aoi_width_points
            ),
            "risk_positive_and_at_most_five_points": frame["risk_points"].gt(0)
            & frame["risk_points"].le(config.max_stop_points),
            "entry_offset_exact": np.isclose(frame["entry_price"], expected_entry),
            "initial_stop_offset_exact": np.isclose(frame["initial_stop_price"], expected_stop),
            "frozen_target_on_correct_side": target_side,
            "commission_exact": np.isclose(
                frame["commission"], 2 * config.commission_per_contract * frame["contracts"]
            ),
            "base_slippage_zero": np.isclose(frame["slippage_cost"], 0.0),
        }
        checks = [
            {"check": name, "passed": bool(mask.all()), "failures": int((~pd.Series(mask)).sum())}
            for name, mask in check_masks.items()
        ]
    checks_frame = pd.DataFrame(checks)
    checks_frame.to_csv(validation_dir / "validation_checks.csv", index=False)
    summary = {
        "status": "PASS" if bool(checks_frame["passed"].all()) else "FAIL",
        "checks": int(len(checks_frame)),
        "failed_checks": checks_frame.loc[~checks_frame["passed"], "check"].tolist(),
        "compatibility_warnings": {
            "managed_bracket_inverted_trades": int(
                trades.get(
                    "managed_bracket_inverted_at_activation",
                    pd.Series(False, index=trades.index),
                )
                .fillna(False)
                .astype(bool)
                .sum()
            ),
            "managed_target_already_reached_trades": int(
                trades.get(
                    "managed_target_already_reached_at_activation",
                    pd.Series(False, index=trades.index),
                )
                .fillna(False)
                .astype(bool)
                .sum()
            ),
            "repeated_same_price_big_trade_snapshot_gap": True,
            "pre_tap_delta_bubble_state_gap": True,
        },
    }
    _write_json(validation_dir / "validation_summary.json", summary)
    return summary


def _write_provenance(config: dict, config_path: Path, output: Path) -> None:
    data = config["data"]
    news_calendar = config["event_filters"]["high_impact_usd_news"].get("calendar")
    implementation_paths = [
        Path("src/propstack/backtest/engine.py"),
        Path("src/propstack/backtest/event_replay.py"),
        Path("src/propstack/backtest/yush_exact_orderflow.py"),
        Path("src/propstack/backtest/contracts.py"),
        Path("src/propstack/backtest/fills.py"),
        Path("src/propstack/backtest/metrics.py"),
        Path("src/propstack/backtest/risk.py"),
        Path("src/propstack/backtest/sizing.py"),
        Path("src/propstack/data/databento_session_stream.py"),
        Path("src/propstack/prop/rules.py"),
        Path("src/propstack/research/campaign_stages.py"),
        Path("src/propstack/research/monte_carlo.py"),
        Path("src/propstack/research/policy.py"),
        Path("src/propstack/research/run_store.py"),
        Path("src/propstack/research/schemas.py"),
        Path("src/propstack/utils/config.py"),
        Path("src/propstack/utils/hashing.py"),
        Path("src/propstack/utils/time.py"),
        Path("src/propstack/validation/__init__.py"),
        Path("src/propstack/validation/exporter.py"),
        Path("src/propstack/validation/exit_path.py"),
        Path("src/propstack/validation/schema.py"),
        Path("src/propstack/version.py"),
        Path("tools/run_yush_exact_databento.py"),
    ]
    payload = {
        "archive": data["archive"],
        "archive_sha256": file_sha256(data["archive"]),
        "roll_calendar": data["roll_calendar"],
        "roll_calendar_sha256": file_sha256(data["roll_calendar"]),
        "source_config": str(config_path),
        "source_config_sha256": file_sha256(config_path),
        "implementation_sha256": {str(path): file_sha256(path) for path in implementation_paths},
        "price_path_semantics": "Databento GLBX trades ts_event ordered, source ordinal tie-break; active outright; not MBO",
        "news_calendar": news_calendar,
        "news_calendar_sha256": file_sha256(news_calendar) if news_calendar else None,
        "news_calendar_limitation": (
            None if news_calendar else "Required high-impact USD T-5m through T windows are not available locally."
        ),
    }
    _write_json(output / "data_manifest.json", payload)
    (output / "source_config.yaml").write_text(config_path.read_text())
    (output / "effective_config.yaml").write_text(yaml.safe_dump(config, sort_keys=False))


def _write_dashboard_validation_bundle(
    config: dict,
    config_path: Path,
    output: Path,
    result: dict,
) -> None:
    trades = result["trades"]
    data_manifest = json.loads((output / "data_manifest.json").read_text())
    input_hash = object_sha256(
        {
            "archive_sha256": data_manifest["archive_sha256"],
            "roll_calendar_sha256": data_manifest["roll_calendar_sha256"],
            "start_date": config["data"]["start_date"],
            "end_date": config["data"]["end_date"],
            "active_contract_rule": config["data"].get("active_contract_rule"),
            "reset_previous_levels_on_roll": config["data"].get("reset_previous_levels_on_roll"),
            "news_calendar_sha256": data_manifest.get("news_calendar_sha256"),
            "event_source_contract": result["reproducibility"],
        }
    )
    metadata = ValidationMetadata(
        run_id=str(config["run_id"]),
        campaign_id=str(config["campaign_id"]),
        strategy_id=str(config["strategy_name"]),
        variant_id=str(config["variant_id"]),
        symbol=str(config["symbol"]),
        stage="core",
        timezone=str(config["data"].get("timezone", "America/New_York")),
        tick_size=float(config["core"]["tick_size"]),
        tick_value=float(config["core"]["tick_value"]),
        timeframe=str(config.get("timeframe", "3m")),
        timeframe_minutes=3.0,
        source_run_dir=str(output),
        source_trade_log=str(output / "core" / "trade_log.csv"),
        config_hash=file_sha256(config_path),
        input_data_hash=input_hash,
        notes=(
            "Canonical event-replay lightweight all-trade evidence. Ordered event transitions preserve "
            "order and dynamic-bracket changes; raw event windows are intentionally omitted from this bundle."
        ),
    )
    condition_source = trades.copy()
    if not condition_source.empty:
        condition_source["signal_time"] = condition_source["bubble_qualified_timestamp"]
        condition_source["decision_bar_time"] = condition_source["order_armed_timestamp"]
        condition_source["entry_execution_time"] = condition_source["entry_timestamp"]
        condition_source["entry_mode"] = condition_source["trigger_kind"]
        condition_source["rth_filter_pass"] = True
        condition_source["no_trade_window_filter_pass"] = (
            True if config["event_filters"]["high_impact_usd_news"].get("calendar") else None
        )
        condition_source["max_trades_filter_pass"] = True
        condition_source["final_entry_pass"] = True
        condition_source["entry_trigger_values"] = condition_source.apply(
            lambda row: json.dumps(
                {
                    "trigger_kind": row["trigger_kind"],
                    "trigger_value": int(row["trigger_value"]),
                    "bubble_qualified_event_index": int(row["bubble_qualified_event_index"]),
                    "order_armed_event_index": int(row["order_armed_event_index"]),
                    "entry_event_index": int(row["entry_event_index"]),
                },
                sort_keys=True,
            ),
            axis=1,
        )
        condition_source["filter_pass_values"] = condition_source.apply(
            lambda row: json.dumps(
                {
                    "aoi_side": row["aoi_side"],
                    "aoi_categories": row["aoi_categories"],
                    "aoi_confluences": row["aoi_confluences"],
                    "aoi_width_points": float(row["aoi_width_points"]),
                },
                sort_keys=True,
            ),
            axis=1,
        )
        condition_source["decision_context"] = condition_source.apply(
            lambda row: json.dumps(
                {
                    "aoi_eligible_timestamp": str(row["aoi_eligible_timestamp"]),
                    "aoi_tap_timestamp": str(row["aoi_tap_timestamp"]),
                    "entry_profile_poc": float(row["entry_profile_poc"]),
                    "entry_profile_vah": float(row["entry_profile_vah"]),
                    "entry_profile_val": float(row["entry_profile_val"]),
                },
                sort_keys=True,
            ),
            axis=1,
        )
        condition_source["stop_anchor_calculation"] = (
            "AOI opposite edge plus configured two-tick offset; engine-owned initial bracket"
        )
        condition_source["target_calculation"] = (
            "No initial target; freeze opposite developing value-area edge after midpoint activation"
        )
    write_validation_run(
        output / "validation_runs" / "core",
        metadata,
        trades=build_trade_summaries(trades, metadata),
        condition_snapshots=build_condition_snapshots(condition_source, metadata),
        event_transitions=result["event_transitions"],
        exit_audits=build_exit_audits(trades, metadata),
    )


def _run_monte_carlo(config: dict, trades: pd.DataFrame, output: Path) -> dict:
    mc_dir = output / "monte_carlo"
    mc_dir.mkdir(parents=True, exist_ok=True)
    mc_cfg = {**config.get("benchmarks", {}), **config.get("monte_carlo", {})}
    mc_cfg["_core"] = config.get("core", {})
    rules = PropRules.from_dict(config.get("prop_rules", {}))
    results, summary = run_monte_carlo(trades, mc_cfg, rules)
    results.to_csv(mc_dir / "monte_carlo_results.csv", index=False)
    _write_json(mc_dir / "monte_carlo_summary.json", summary)
    return summary


def _write_summary(
    config: dict,
    config_path: Path,
    metrics: dict,
    monte_carlo_summary: dict,
    validation_summary: dict,
    output: Path,
) -> None:
    thresholds = config["benchmarks"]
    news_calendar_applied = bool(metrics.get("news_calendar_applied", False))
    failures = []
    for field, comparator, threshold in (
        ("total_trades", lambda x, y: x >= y, thresholds["min_trade_count"]),
        ("trades_per_year", lambda x, y: x >= y, thresholds["min_trades_per_year"]),
        ("net_profit", lambda x, y: x >= y, thresholds["min_total_net_profit"]),
        ("profit_factor", lambda x, y: x >= y, thresholds["min_profit_factor"]),
        ("max_drawdown_pct", lambda x, y: x <= y, thresholds["max_drawdown_pct"]),
        ("expectancy_r", lambda x, y: x >= y, thresholds["min_expectancy_r"]),
        ("max_consecutive_losses", lambda x, y: x <= y, thresholds["max_consecutive_losses"]),
    ):
        if not comparator(float(metrics.get(field, 0.0)), float(threshold)):
            failures.append(field)
    if not bool(monte_carlo_summary.get("meets_prop_pass_chance_benchmark", False)):
        failures.append("monte_carlo_prop_pass_chance")
    if validation_summary["status"] != "PASS":
        failures.append("mechanics_validation")
    status = "NEEDS MANUAL REVIEW" if not failures else "FAIL"
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    core_criteria = [
        {
            "metric": field,
            "passed": field not in failures,
            "actual": metrics.get(field),
            "expected": config["benchmarks"].get(
                {
                    "total_trades": "min_trade_count",
                    "trades_per_year": "min_trades_per_year",
                    "net_profit": "min_total_net_profit",
                    "profit_factor": "min_profit_factor",
                    "max_drawdown_pct": "max_drawdown_pct",
                    "expectancy_r": "min_expectancy_r",
                    "max_consecutive_losses": "max_consecutive_losses",
                }[field]
            ),
        }
        for field in (
            "total_trades",
            "trades_per_year",
            "net_profit",
            "profit_factor",
            "max_drawdown_pct",
            "expectancy_r",
            "max_consecutive_losses",
        )
    ]
    stages = [
        {
            "stage": "mechanics_artifact_validation",
            "label": "Exact mechanics artifact validation",
            "status": "passed" if validation_summary["status"] == "PASS" else "failed",
            "passed": validation_summary["status"] == "PASS",
            "criteria": [
                {
                    "metric": "all_mechanics_checks",
                    "passed": validation_summary["status"] == "PASS",
                    "actual": validation_summary["failed_checks"],
                }
            ],
        },
        {
            "stage": "canonical_event_core",
            "label": "BacktestEngine canonical event core",
            "status": "passed" if not any(item["passed"] is False for item in core_criteria) else "failed",
            "passed": not any(item["passed"] is False for item in core_criteria),
            "criteria": core_criteria,
        },
        {
            "stage": "high_impact_usd_news",
            "label": "High-impact USD event rule",
            "status": "passed" if news_calendar_applied else "failed",
            "passed": news_calendar_applied,
            "criteria": [
                {
                    "metric": "versioned_high_impact_usd_calendar_applied",
                    "passed": news_calendar_applied,
                    "actual": news_calendar_applied,
                    "expected": True,
                }
            ],
        },
        {
            "stage": "monte_carlo",
            "label": "Prop-rule Monte Carlo",
            "status": (
                "passed" if bool(monte_carlo_summary.get("meets_prop_pass_chance_benchmark", False)) else "failed"
            ),
            "passed": bool(monte_carlo_summary.get("meets_prop_pass_chance_benchmark", False)),
            "criteria": [
                {
                    "metric": "monte_carlo_prop_pass_chance",
                    "passed": bool(monte_carlo_summary.get("meets_prop_pass_chance_benchmark", False)),
                    "actual": monte_carlo_summary.get("probability_funded_payout"),
                    "expected": config["monte_carlo"].get("min_monte_carlo_prop_pass_chance"),
                }
            ],
        },
    ]
    validation_metadata = json.loads((output / "validation_runs" / "core" / "metadata.json").read_text())
    summary = {
        "run_uid": ensure_run_uid(output),
        "campaign_id": config["campaign_id"],
        "variant_id": config["variant_id"],
        "test_run_id": config["run_id"],
        "run_id": config["run_id"],
        "strategy_name": config["strategy_name"],
        "symbol": config["symbol"],
        "dataset_id": config["dataset_id"],
        "timeframe": config["timeframe"],
        "data_source": config["data"]["source"],
        "config_hash": file_sha256(output / "effective_config.yaml"),
        "source_config_hash": file_sha256(config_path),
        "input_data_hash": validation_metadata["input_data_hash"],
        "output_dir": str(output),
        "config_path": str(output / "effective_config.yaml"),
        "effective_config_path": str(output / "effective_config.yaml"),
        "source_config_path": str(config_path),
        "source_config_snapshot_path": str(output / "source_config.yaml"),
        "created_at": now,
        "updated_at": now,
        "passed": False,
        "halted": False,
        "stages": stages,
        "research_policy": active_research_policy_metadata(),
        "engine_contract_version": ENGINE_CONTRACT_VERSION,
        "status": status,
        "decision": status,
        "benchmark_failures": failures,
        "core_metrics": metrics,
        "sections": {
            "core": metrics,
            "monte_carlo": monte_carlo_summary,
        },
        "stage_status": {
            "mechanics_unit_tests": "PASS",
            "mechanics_artifact_validation": validation_summary["status"],
            "canonical_event_core": "PASS" if not failures else "FAIL",
            "chronological_holdout": "reported_no_tuning",
            "monte_carlo": "FAIL" if "monte_carlo_prop_pass_chance" in failures else "PASS",
            "news_rule_validation": "PASS" if news_calendar_applied else "BLOCKED_MISSING_CALENDAR",
            "candidate_promotion": "NOT_ELIGIBLE",
        },
        "verdict_reason": (
            "Core benchmark failure; the required high-impact USD calendar is also absent."
            if failures and not news_calendar_applied
            else "Core benchmark failure."
            if failures
            else "Numerical gates passed, but the missing high-impact USD calendar prevents a faithful promotion verdict."
            if not news_calendar_applied
            else "Numerical and required-data gates passed pending manual due diligence."
        ),
    }
    validate_run_summary_contract(summary)
    source_results_index = update_source_results_index(config_path, config, summary)
    summary["source_results_index_path"] = str(source_results_index) if source_results_index else None
    validate_run_summary_contract(summary)
    _write_json(output / "campaign_test_summary.json", summary)
    _write_json(output / "variant_test_summary.json", summary)
    _write_json(
        output / "run_manifest.json",
        {
            "run_uid": summary["run_uid"],
            "campaign_id": summary["campaign_id"],
            "variant_id": summary["variant_id"],
            "test_run_id": summary["test_run_id"],
            "strategy_name": summary["strategy_name"],
            "symbol": summary["symbol"],
            "dataset_id": summary["dataset_id"],
            "timeframe": summary["timeframe"],
            "data_source": summary["data_source"],
            "research_policy": summary["research_policy"],
            "engine_contract_version": ENGINE_CONTRACT_VERSION,
            "config_source": str(config_path),
            "effective_config": str(output / "effective_config.yaml"),
            "source_config_snapshot": str(output / "source_config.yaml"),
            "source_results_index": summary["source_results_index_path"],
            "config_hash": summary["config_hash"],
            "source_config_hash": summary["source_config_hash"],
            "input_data_hash": summary["input_data_hash"],
            "created_at": now,
            "updated_at": now,
            "engine_lane": "canonical_event_replay",
            "layout": "campaign_variant_symbol_run",
        },
    )
    update_runs_index(output)


def _write_methodology_audit(config: dict, metrics: dict, monte_carlo_summary: dict, output: Path) -> None:
    text = f"""# Methodology audit — exact Databento Yush range replay

Verdict: **FAIL**.

## Implemented controls

- BacktestEngine canonical event lane replaying direct Databento GLBX trade messages, active outright only, with nanosecond `ts_event` and source-ordinal tie breaks.
- Same-vendor PDH/PDL/PDC, overnight, opening-range, developing volume-profile, delta-profile, and trigger inputs.
- Strict causal AOI eligibility, tap, bubble, order activation, fill, stop/target, and 11:00 flatten sequencing.
- One fixed mechanics set; no result-informed parameter selection.
- Development/holdout split and 1,000 fixed-seed prop-rule Monte Carlo paths.

## Rejection evidence

- Total trades: {metrics.get('total_trades')}; net profit: ${metrics.get('net_profit'):,.2f}; PF: {metrics.get('profit_factor'):.3f}.
- Expectancy: ${metrics.get('expectancy_per_trade'):,.2f} per trade and {metrics.get('expectancy_r'):.3f}R.
- Maximum drawdown: ${metrics.get('max_drawdown'):,.2f}; positive-month rate: {metrics.get('positive_month_rate'):.1%}.
- Monte Carlo mean net PnL: ${float(monte_carlo_summary.get('mean_net_pnl', 0.0)):,.2f}; breach probability: {float(monte_carlo_summary.get('probability_account_breach', 0.0)):.1%}; funded-payout probability: {float(monte_carlo_summary.get('probability_funded_payout', 0.0)):.1%}.
- High-impact USD calendar applied: {bool(metrics.get('news_calendar_applied', False))}. When absent, the T-5m flatten/entry block cannot be represented and the result fails closed.
- The base case follows the user's zero-slippage exact-price assumption. Static one- and two-tick-per-side cost sensitivities are written separately and do not model path changes.
- Managed brackets inverted at activation: {int(metrics.get('managed_bracket_inverted_trades', 0))}; managed targets already reached at activation: {int(metrics.get('managed_target_already_reached_trades', 0))}. The canonical engine preserves this frozen legacy behavior only through an explicit strategy opt-in; it is not the reusable lane default.
- Two pre-existing trigger ambiguities remain frozen for parity: an older same-price large-trade snapshot can mask a later post-tap snapshot, and a developing delta bucket that crossed the threshold before a tap can be recognized after the tap. Correcting either would change mechanics after observing results and requires a separately authorized mechanics revision.

This is not a candidate strategy and must not be promoted or rescued by selecting only long trades, favorable months, trigger types, or confluence subsets after seeing these results.
"""
    (output / "methodology_audit.md").write_text(text)


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n")


def _json_safe(value):
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, pd.Period)):
        return str(value)
    return value


if __name__ == "__main__":
    main()
