from __future__ import annotations

import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.validation import (
    BarWindowRow,
    ConditionSnapshot,
    ExitAudit,
    TickWindowRow,
    TradeSummary,
    ValidationMetadata,
    build_bar_window_rows,
    build_condition_snapshots,
    build_exit_audits,
    build_tick_window_rows,
    build_trade_summaries,
    load_validation_run,
    write_validation_run,
)
from alphaquest.validation.schema import (
    BAR_WINDOWS_FILENAME,
    CONDITION_SNAPSHOTS_FILENAME,
    EVENT_TRANSITIONS_FILENAME,
    EXIT_AUDITS_FILENAME,
    METADATA_FILENAME,
    TICK_WINDOWS_FILENAME,
    TRADES_FILENAME,
    VALIDATION_CHECKS_FILENAME,
    EVENT_TRANSITION_COLUMNS,
    EventTransition,
)


def test_validation_run_round_trips_sample_records(tmp_path):
    eastern = "America/New_York"
    metadata = ValidationMetadata(
        run_id="run12_poc",
        campaign_id="es_video_aoi_lvn_orderflow_playbook",
        strategy_id="yush_range_1",
        variant_id="yush_range_1",
        symbol="ES",
        tick_size=0.25,
        tick_value=12.5,
        timeframe="3m",
        timeframe_minutes=3,
        timezone=eastern,
    )
    entry_time = pd.Timestamp("2024-03-11 09:36:00", tz=eastern)
    exit_time = pd.Timestamp("2024-03-11 09:42:00", tz=eastern)

    metadata_record = write_validation_run(
        tmp_path / "validation_runs" / "run12_poc",
        metadata,
        trades=[
            TradeSummary(
                run_id="run12_poc",
                campaign_id="es_video_aoi_lvn_orderflow_playbook",
                strategy_id="yush_range_1",
                variant_id="yush_range_1",
                trade_id=1,
                symbol="ES",
                contract="ESH24",
                session_date="2024-03-11",
                direction="long",
                entry_time=entry_time,
                entry_price=5200.0,
                entry_order_type="next_bar_open",
                stop_price=5198.0,
                target_price=5204.0,
                exit_time=exit_time,
                exit_price=5204.0,
                exit_reason="target",
                pnl_ticks=16,
                pnl_usd=200,
                r_multiple=2,
                bars_held=2,
                contracts=1,
                fees=4.24,
                slippage=12.5,
                was_forced_flatten=False,
                debug_flags="entry_mode=bar_close",
            )
        ],
        condition_snapshots=[
            ConditionSnapshot(
                trade_id=1,
                signal_time=entry_time - pd.Timedelta(minutes=3),
                decision_bar_time=entry_time - pd.Timedelta(minutes=3),
                entry_execution_time=entry_time,
                swept_level_name="lvn",
                swept_level_price=5199.0,
                volume_filter_pass=True,
                delta_value=850,
                delta_filter_pass=True,
                final_entry_pass=True,
            )
        ],
        bar_windows=[
            BarWindowRow(
                trade_id=1,
                timestamp=entry_time,
                open=5200.0,
                high=5202.0,
                low=5199.5,
                close=5201.0,
                volume=1500,
                bid_volume=650,
                ask_volume=850,
                delta=200,
                is_rth=True,
                session_date="2024-03-11",
            )
        ],
        tick_windows=[
            TickWindowRow(
                trade_id=1,
                timestamp=entry_time + pd.Timedelta(seconds=1),
                price=5200.25,
                volume=10,
                ask_volume=10,
                delta=10,
                price_level=5200.25,
                price_level_ask_volume=10,
                price_level_delta=10,
            )
        ],
        event_transitions=[
            EventTransition(
                trade_id=1,
                session_date="2024-03-11",
                contract="ESH24",
                order_id="VAL-1",
                timestamp=entry_time,
                source_ordinal=42,
                event_index=17,
                transition="entry_filled",
                direction="long",
                price=5200.0,
                active_from_event_index=16,
                stop_price=5198.0,
                target_price=5204.0,
                reason="stop_crossed",
                state_json='{"position":"open"}',
                evidence_json='{"event_price":5200.0}',
            )
        ],
        exit_audits=[
            ExitAudit(
                trade_id=1,
                first_touch_tp_time=exit_time,
                first_touch_exit_decision="target",
                same_bar_ambiguous=False,
                ambiguity_resolution="detail_data",
                max_favorable_excursion_ticks=16,
                max_adverse_excursion_ticks=2,
                highest_price_before_exit=5204.0,
                lowest_price_before_exit=5199.5,
            )
        ],
    )

    run_dir = tmp_path / "validation_runs" / "run12_poc"
    for filename in (
        METADATA_FILENAME,
        TRADES_FILENAME,
        CONDITION_SNAPSHOTS_FILENAME,
        BAR_WINDOWS_FILENAME,
        TICK_WINDOWS_FILENAME,
        EVENT_TRANSITIONS_FILENAME,
        EXIT_AUDITS_FILENAME,
        VALIDATION_CHECKS_FILENAME,
    ):
        assert (run_dir / filename).exists()

    loaded = load_validation_run(run_dir)
    assert metadata_record["record_counts"]["trades"] == 1
    assert loaded.metadata["schema_version"] == "1.4"
    assert loaded.trades.loc[0, "trade_id"] == 1
    assert loaded.trades.loc[0, "entry_time"] == entry_time
    assert str(loaded.trades.loc[0, "entry_time"].tz) in {eastern, "America/New_York"}
    assert bool(loaded.condition_snapshots.loc[0, "final_entry_pass"]) is True
    assert loaded.bar_windows.loc[0, "delta"] == 200
    assert loaded.tick_windows.loc[0, "price_level"] == 5200.25
    assert loaded.exit_audits.loc[0, "ambiguity_resolution"] == "detail_data"
    assert loaded.exit_audits.loc[0, "entry_price"] == 5200.0
    assert "warning_flags" in loaded.exit_audits.columns
    assert metadata_record["record_counts"]["validation_checks"] > 0
    assert metadata_record["record_counts"]["event_transitions"] == 1
    assert loaded.event_transitions.loc[0, "transition"] == "entry_filled"
    transition_frame = pd.read_parquet(run_dir / EVENT_TRANSITIONS_FILENAME)
    assert list(transition_frame.columns) == EVENT_TRANSITION_COLUMNS
    assert transition_frame.loc[0, "transition"] == "entry_filled"
    assert transition_frame.loc[0, "event_index"] == 17
    assert not loaded.validation_checks.empty
    assert "price_logic" in set(loaded.validation_checks["category"])


def test_validation_run_writes_empty_event_transition_artifact_for_legacy_callers(tmp_path):
    metadata_record = write_validation_run(
        tmp_path / "legacy_validation_run",
        ValidationMetadata(run_id="legacy"),
    )

    transition_path = tmp_path / "legacy_validation_run" / EVENT_TRANSITIONS_FILENAME
    transition_frame = pd.read_parquet(transition_path)
    assert transition_path.exists()
    assert transition_frame.empty
    assert list(transition_frame.columns) == EVENT_TRANSITION_COLUMNS
    assert metadata_record["artifact_files"]["event_transitions"] == EVENT_TRANSITIONS_FILENAME
    assert metadata_record["record_counts"]["event_transitions"] == 0


def test_event_replay_checks_use_causal_transitions_instead_of_bar_snapshots(tmp_path):
    eastern = "America/New_York"
    submitted_at = pd.Timestamp("2025-07-14 10:00:00", tz=eastern)
    entry_at = submitted_at + pd.Timedelta(seconds=1)
    amended_at = entry_at + pd.Timedelta(seconds=30)
    exit_at = amended_at + pd.Timedelta(seconds=10)
    output = tmp_path / "event_validation"
    write_validation_run(
        output,
        ValidationMetadata(
            run_id="event-mechanics",
            campaign_id="yush_orderflow_range",
            strategy_id="yush_orderflow_range",
            variant_id="v01",
            symbol="ES",
            timezone=eastern,
            tick_size=0.25,
            tick_value=12.5,
            timeframe="1m",
            timeframe_minutes=1,
            config_hash="config-hash",
            input_data_hash="input-hash",
            validation_lane="event_replay",
            source_data_type="databento_zip_trades",
            source_data_path="events.zip",
            source_trade_count=1,
            commission_per_contract=2.5,
            slippage_ticks=1,
            point_value=50,
            forced_flatten_time="11:00:00",
        ),
        trades=[
            TradeSummary(
                run_id="event-mechanics",
                campaign_id="yush_orderflow_range",
                strategy_id="yush_orderflow_range",
                variant_id="v01",
                trade_id=1,
                symbol="ES",
                contract="ESU5",
                session_date="2025-07-14",
                direction="short",
                entry_time=entry_at,
                entry_price=99.75,
                entry_order_type="stop_market",
                stop_price=98.0,
                target_price=95.0,
                exit_time=exit_at,
                exit_price=98.25,
                exit_reason="managed_stop",
            )
        ],
        event_transitions=[
            EventTransition(
                session_date="2025-07-14",
                contract="ESU5",
                order_id="VAH",
                timestamp=submitted_at,
                source_ordinal=100,
                event_index=10,
                transition="order_submitted",
                direction="short",
                price=100.0,
                active_from_event_index=11,
                stop_price=102.0,
                state_json='{"transition":"order_submitted"}',
                evidence_json='{"event_index":10}',
            ),
            EventTransition(
                trade_id=1,
                session_date="2025-07-14",
                contract="ESU5",
                order_id="VAH",
                timestamp=entry_at,
                source_ordinal=101,
                event_index=12,
                transition="entry_filled",
                direction="short",
                price=100.0,
                active_from_event_index=12,
                stop_price=102.0,
                state_json='{"transition":"entry_filled"}',
                evidence_json='{"event_index":12}',
            ),
            EventTransition(
                trade_id=1,
                session_date="2025-07-14",
                contract="ESU5",
                order_id="VAH",
                timestamp=amended_at,
                source_ordinal=102,
                event_index=13,
                transition="bracket_amended",
                direction="short",
                price=97.0,
                active_from_event_index=14,
                stop_price=98.0,
                target_price=95.0,
                state_json='{"transition":"bracket_amended"}',
                evidence_json='{"event_index":13}',
            ),
            EventTransition(
                trade_id=1,
                session_date="2025-07-14",
                contract="ESU5",
                order_id="VAH",
                timestamp=exit_at,
                source_ordinal=103,
                event_index=14,
                transition="position_closed",
                direction="short",
                price=98.0,
                active_from_event_index=14,
                stop_price=98.0,
                target_price=95.0,
                reason="managed_stop",
                state_json='{"transition":"position_closed"}',
                evidence_json='{"event_index":14}',
            ),
        ],
    )

    checks = pd.read_parquet(output / VALIDATION_CHECKS_FILENAME)
    exit_audits = pd.read_parquet(output / EXIT_AUDITS_FILENAME)
    assert not (checks["status"] == "ERROR").any()
    assert exit_audits.empty
    assert {
        "identity",
        "time_ordering",
        "price_logic",
        "filter_logic",
        "exit_logic",
        "data_quality",
        "reconciliation",
    } <= set(checks["category"])
    assert "event_managed_bracket_ordered" in set(checks["check_name"])
    assert "condition_snapshot_present" not in set(checks["check_name"])


def test_builders_map_existing_trade_log_columns_without_strategy_logic():
    trade_log = pd.DataFrame(
        [
            {
                "trade_id": 7,
                "strategy_name": "yush_range_1",
                "session_date": "2024-03-11",
                "direction": "short",
                "entry_timestamp": pd.Timestamp("2024-03-11 10:00:00", tz="America/New_York"),
                "entry_price": 5200.0,
                "entry_mode": "intrabar",
                "stop_price": 5202.0,
                "target_price": 5196.0,
                "exit_timestamp": pd.Timestamp("2024-03-11 10:09:00", tz="America/New_York"),
                "exit_price": 5196.0,
                "exit_reason": "target",
                "net_pnl": 196.0,
                "r_multiple": 2.0,
                "contracts": 1,
                "commission": 4.0,
                "slippage_cost": 0.0,
                "was_forced_flatten": False,
                "market_level_type": "lvn",
                "market_level_price": 5199.75,
                "sweep_timestamp": pd.Timestamp("2024-03-11 09:57:00", tz="America/New_York"),
                "reclaim_timestamp": pd.Timestamp("2024-03-11 10:00:00", tz="America/New_York"),
                "signal_timestamp": pd.Timestamp("2024-03-11 09:59:00", tz="America/New_York"),
                "intended_entry_timestamp": pd.Timestamp("2024-03-11 10:00:00", tz="America/New_York"),
                "rolling_volume": 1100.0,
                "signed_volume": -700.0,
                "delta_imbalance": -0.35,
                "buy_volume": 200.0,
                "sell_volume": 900.0,
                "volume": 1100.0,
                "max_favorable_excursion": 4.5,
                "max_adverse_excursion": 0.5,
                "intrabar_source_quality_label": "scid_record",
            }
        ]
    )
    metadata = ValidationMetadata(
        run_id="runA",
        campaign_id="campaignA",
        variant_id="variantA",
        symbol="ES",
        tick_size=0.25,
        timeframe_minutes=3,
    )

    summaries = build_trade_summaries(trade_log, metadata)
    snapshots = build_condition_snapshots(trade_log, metadata)
    audits = build_exit_audits(trade_log, metadata)

    assert summaries.loc[0, "run_id"] == "runA"
    assert summaries.loc[0, "strategy_id"] == "yush_range_1"
    assert summaries.loc[0, "pnl_ticks"] == 16
    assert summaries.loc[0, "bars_held"] == 3
    assert summaries.loc[0, "fees"] == 4
    assert "intrabar_source_quality_label=scid_record" in summaries.loc[0, "debug_flags"]
    assert snapshots.loc[0, "swept_level_name"] == "lvn"
    assert snapshots.loc[0, "delta_value"] == -700
    assert snapshots.loc[0, "ask_volume"] == 200
    assert snapshots.loc[0, "bid_volume"] == 900
    assert audits.loc[0, "max_favorable_excursion_ticks"] == 18
    assert audits.loc[0, "max_adverse_excursion_ticks"] == 2
    assert audits.loc[0, "entry_price"] == 5200
    assert audits.loc[0, "mfe_ticks"] == 18
    assert audits.loc[0, "mae_ticks"] == 2


def test_bar_and_tick_window_builders_normalize_orderflow_columns():
    bars = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2024-03-11 10:00:00", tz="America/New_York"),
                "open": 5200,
                "high": 5201,
                "low": 5199,
                "close": 5200.5,
                "volume": 500,
                "buy_volume": 300,
                "sell_volume": 200,
                "signed_volume": 100,
                "is_rth": True,
                "session_date": "2024-03-11",
                "previous_rth_high": 5210,
            }
        ]
    )
    ticks = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2024-03-11 10:00:01", tz="America/New_York"),
                "price": 5200.25,
                "volume": 12,
                "buy_volume": 12,
                "sell_volume": 0,
                "signed_volume": 12,
            }
        ]
    )

    bar_rows = build_bar_window_rows(bars, trade_id=99)
    tick_rows = build_tick_window_rows(ticks, trade_id=99)

    assert bar_rows.loc[0, "trade_id"] == 99
    assert bar_rows.loc[0, "ask_volume"] == 300
    assert bar_rows.loc[0, "bid_volume"] == 200
    assert bar_rows.loc[0, "delta"] == 100
    assert bar_rows.loc[0, "prev_rth_high"] == 5210
    assert tick_rows.loc[0, "price_level"] == 5200.25
    assert tick_rows.loc[0, "price_level_delta"] == 12


def test_engine_validation_output_writes_and_reloads_artifacts(tmp_path):
    cfg = {
        "strategy_name": "calendar_session_bias",
        "strategy": {
            "entry": {
                "module": "calendar_session_bias",
                "params": {
                    "signal_time": "09:31:00",
                    "bar_interval_minutes": 1,
                    "weekday_directions": {2: "long"},
                    "max_trades_per_day": 1,
                },
            },
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 20.0}},
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.02}},
            "flatten_time": "09:34:00",
        },
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 0,
            "slippage_ticks": 0,
            "contracts": 1,
            "validation_export": {
                "enabled": True,
                "window_bars_before": 1,
                "window_bars_after": 1,
            },
        },
    }
    rows = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp(f"2024-01-03 09:{minute:02d}", tz="America/New_York"),
                "session_date": pd.Timestamp("2024-01-03").date(),
                "is_rth": True,
                "open": 100.0,
                "high": 100.2,
                "low": 99.8,
                "close": 100.0,
                "volume": 1000,
                "buy_volume": 550,
                "sell_volume": 450,
                "signed_volume": 100,
            }
            for minute in range(30, 36)
        ]
    )

    result = BacktestEngine(cfg).run(rows)
    metadata = ValidationMetadata(
        run_id="run_validation_test",
        campaign_id="test_campaign",
        strategy_id="calendar_session_bias",
        variant_id="test_variant",
        symbol="ES",
        stage="core",
        tick_size=0.25,
        tick_value=12.5,
        timeframe="1m",
        timeframe_minutes=1,
    )
    validation = result["validation"]
    write_validation_run(
        tmp_path / "validation_runs" / "core",
        metadata,
        trades=build_trade_summaries(result["trades"], metadata),
        condition_snapshots=validation["condition_snapshots"],
        bar_windows=validation["bar_windows"],
        tick_windows=validation["tick_windows"],
        exit_audits=validation["exit_audits"],
    )

    loaded = load_validation_run(tmp_path / "validation_runs" / "core")

    assert len(result["trades"]) == 1
    assert len(loaded.trades) == len(result["trades"])
    assert len(loaded.condition_snapshots) == len(result["trades"])
    assert len(loaded.exit_audits) == len(result["trades"])
    assert "tick_count_checked" in loaded.exit_audits.columns
    assert loaded.trades.loc[0, "trade_id"] == result["trades"].iloc[0]["trade_id"]
    assert loaded.condition_snapshots.loc[0, "entry_execution_time"] == result["trades"].iloc[0]["entry_timestamp"]
    assert "report.bar.signed_volume" in loaded.condition_snapshots.loc[0, "raw_orderflow_values"] or (
        "bar.signed_volume" in loaded.condition_snapshots.loc[0, "raw_orderflow_values"]
    )
