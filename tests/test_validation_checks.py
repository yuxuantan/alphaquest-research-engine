from __future__ import annotations

import pandas as pd

from alphaquest.validation.checks import run_validation_checks


def _rows(report: pd.DataFrame, check_name: str) -> pd.DataFrame:
    return report[report["check_name"] == check_name]


def test_event_post_target_stop_is_validated_as_stop_not_target() -> None:
    start = pd.Timestamp("2026-05-08 11:00:00", tz="America/New_York")
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "session_date": "2026-05-08",
                "contract": "ESM26",
                "direction": "short",
                "entry_time": start,
                "exit_time": start + pd.Timedelta(minutes=1),
                "entry_price": 101.0,
                "stop_price": 100.0,
                "target_price": 90.0,
                "exit_price": 100.0,
                "exit_reason": "post_target_1_stop",
            }
        ]
    )
    events = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "session_date": "2026-05-08",
                "contract": "ESM26",
                "order_id": "short_1",
                "timestamp": start - pd.Timedelta(milliseconds=2),
                "source_ordinal": 1,
                "event_index": 1,
                "transition": "order_submitted",
                "direction": "short",
                "price": 101.25,
                "active_from_event_index": 2,
                "stop_price": 102.0,
                "target_price": None,
                "reason": "strategy_signal",
                "state_json": "{}",
                "evidence_json": "{}",
            },
            {
                "trade_id": 1,
                "session_date": "2026-05-08",
                "contract": "ESM26",
                "order_id": "short_1",
                "timestamp": start,
                "source_ordinal": 2,
                "event_index": 2,
                "transition": "entry_filled",
                "direction": "short",
                "price": 101.0,
                "active_from_event_index": 2,
                "stop_price": 102.0,
                "target_price": None,
                "reason": "entry",
                "state_json": "{}",
                "evidence_json": "{}",
            },
            {
                "trade_id": 1,
                "session_date": "2026-05-08",
                "contract": "ESM26",
                "order_id": "short_1",
                "timestamp": start + pd.Timedelta(minutes=1),
                "source_ordinal": 3,
                "event_index": 3,
                "transition": "position_closed",
                "direction": "short",
                "price": 100.0,
                "active_from_event_index": None,
                "stop_price": 100.0,
                "target_price": 90.0,
                "reason": "post_target_1_stop",
                "state_json": "{}",
                "evidence_json": "{}",
            },
        ]
    )

    report = run_validation_checks(
        trades,
        pd.DataFrame(),
        pd.DataFrame(),
        metadata={
            "validation_lane": "event_replay",
            "tick_size": 0.25,
            "minimum_trade_samples": 1,
        },
        event_transitions=events,
    )

    assert _rows(report, "event_stop_exit_has_stop_touch").iloc[0]["status"] == "PASS"
    assert _rows(report, "event_target_exit_has_target_touch").empty


def test_event_limit_entry_slippage_is_capped_at_the_submitted_limit() -> None:
    entry_time = pd.Timestamp("2026-05-28 13:54:09", tz="America/New_York")
    for direction, stop_price in (("long", 99.0), ("short", 101.0)):
        trades = pd.DataFrame(
            [
                {
                    "trade_id": 1,
                    "direction": direction,
                    "entry_time": entry_time,
                    "entry_price": 100.0,
                    "entry_trigger_price": 100.0,
                    "stop_price": stop_price,
                    "exit_time": entry_time + pd.Timedelta(minutes=1),
                    "exit_price": 100.0,
                    "exit_reason": "time_exit",
                }
            ]
        )
        events = pd.DataFrame(
            [
                {
                    "trade_id": 1,
                    "session_date": "2026-05-28",
                    "contract": "ESM26",
                    "order_id": f"{direction}_1",
                    "timestamp": entry_time,
                    "source_ordinal": 1,
                    "event_index": 2,
                    "transition": "entry_filled",
                    "direction": direction,
                    "price": 100.0,
                    "active_from_event_index": 2,
                    "stop_price": stop_price,
                    "target_price": None,
                    "reason": "limit_entry_filled",
                    "state_json": "{}",
                    "evidence_json": "{}",
                }
            ]
        )

        report = run_validation_checks(
            trades,
            pd.DataFrame(),
            pd.DataFrame(),
            metadata={
                "validation_lane": "event_replay",
                "tick_size": 0.25,
                "slippage_ticks": 1,
                "minimum_trade_samples": 1,
            },
            event_transitions=events,
        )

        row = _rows(report, "event_entry_slippage_reconciled").iloc[0]
        assert row["status"] == "PASS"
        assert row["expected"] == "100.0"
        assert row["actual"] == "100.0"


def test_event_transition_identity_allows_multiple_order_cancellations_on_one_fill_event() -> None:
    entry = pd.Timestamp("2026-05-28 13:54:09", tz="America/New_York")
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "session_date": "2026-05-28",
                "contract": "ESM26",
                "direction": "short",
                "entry_time": entry,
                "entry_price": 100.0,
                "entry_trigger_price": 100.0,
                "stop_price": 101.0,
                "exit_time": entry + pd.Timedelta(minutes=1),
                "exit_price": 101.0,
                "exit_reason": "initial_stop",
            }
        ]
    )
    common = {
        "trade_id": 1,
        "session_date": "2026-05-28",
        "contract": "ESM26",
        "direction": "short",
        "state_json": "{}",
        "evidence_json": "{}",
        "target_price": None,
    }
    events = pd.DataFrame(
        [
            {
                **common,
                "order_id": "short_1",
                "timestamp": entry - pd.Timedelta(milliseconds=1),
                "source_ordinal": 1,
                "event_index": 1,
                "transition": "order_submitted",
                "price": 100.0,
                "active_from_event_index": 2,
                "stop_price": None,
                "reason": "strategy_request",
            },
            {
                **common,
                "order_id": "short_1",
                "timestamp": entry,
                "source_ordinal": 2,
                "event_index": 2,
                "transition": "entry_filled",
                "price": 100.0,
                "active_from_event_index": 2,
                "stop_price": 101.0,
                "reason": "stop_entry_triggered",
            },
            *[
                {
                    **common,
                    "order_id": order_id,
                    "timestamp": entry,
                    "source_ordinal": 2,
                    "event_index": 2,
                    "transition": "order_cancelled",
                    "price": trigger,
                    "active_from_event_index": 2,
                    "stop_price": None,
                    "reason": "position_opened_cancel_other_entries",
                }
                for order_id, trigger in (("short_2", 99.5), ("short_3", 99.0))
            ],
            {
                **common,
                "order_id": "short_1",
                "timestamp": entry + pd.Timedelta(minutes=1),
                "source_ordinal": 3,
                "event_index": 3,
                "transition": "position_closed",
                "price": 101.0,
                "active_from_event_index": 3,
                "stop_price": 101.0,
                "reason": "initial_stop",
            },
        ]
    )

    report = run_validation_checks(
        trades,
        pd.DataFrame(),
        pd.DataFrame(),
        metadata={
            "validation_lane": "event_replay",
            "tick_size": 0.25,
            "minimum_trade_samples": 1,
        },
        event_transitions=events,
    )

    row = _rows(report, "event_transition_keys_unique").iloc[0]
    assert row["status"] == "PASS"
    assert row["expected"] == "unique timestamp/source_ordinal/order_id/transition"


def test_empty_trade_sample_reports_the_real_mechanics_blocker():
    report = run_validation_checks(
        pd.DataFrame(columns=["trade_id"]),
        pd.DataFrame(),
        pd.DataFrame(),
        metadata={"validation_lane": "event_replay"},
    )

    row = _rows(report, "mechanics_review_trade_sample_present").iloc[0]
    assert row["status"] == "ERROR"
    assert row["actual"] == "0"
    assert _rows(report, "unique_trade_id").empty


def test_strategy_specific_minimum_trade_sample_is_enforced():
    report = run_validation_checks(
        pd.DataFrame({"trade_id": [1, 2, 3]}),
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        metadata={"minimum_trade_samples": 5},
    )

    row = _rows(report, "mechanics_review_trade_sample_present").iloc[0]
    assert row["status"] == "ERROR"
    assert row["expected"] == "at least 5 completed trades"
    assert row["actual"] == "3"


def test_validation_checks_flag_time_ordering_and_price_logic_errors():
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "direction": "long",
                "entry_time": pd.Timestamp("2024-01-03 09:31", tz="America/New_York"),
                "exit_time": pd.Timestamp("2024-01-03 09:30", tz="America/New_York"),
                "entry_price": 100.0,
                "stop_price": 101.0,
                "target_price": 99.0,
                "entry_order_type": "next_bar_open",
                "exit_reason": "stop",
            }
        ]
    )
    conditions = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "signal_time": pd.Timestamp("2024-01-03 09:32", tz="America/New_York"),
                "decision_bar_time": pd.Timestamp("2024-01-03 09:32", tz="America/New_York"),
                "entry_mode": "bar_close",
                "final_entry_pass": True,
            }
        ]
    )

    report = run_validation_checks(trades, conditions, pd.DataFrame(), pd.DataFrame(), pd.DataFrame())

    assert _rows(report, "signal_time_before_entry_time").iloc[0]["status"] == "ERROR"
    assert _rows(report, "exit_not_before_entry").iloc[0]["status"] == "ERROR"
    assert _rows(report, "bar_close_entry_not_before_signal_close").iloc[0]["status"] == "ERROR"
    assert _rows(report, "long_stop_below_entry").iloc[0]["status"] == "ERROR"
    assert _rows(report, "long_target_above_entry").iloc[0]["status"] == "ERROR"


def test_validation_checks_flag_filter_logic_errors():
    trade_time = pd.Timestamp("2024-01-03 09:33", tz="America/New_York")
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "direction": "short",
                "entry_time": trade_time,
                "exit_time": trade_time + pd.Timedelta(minutes=3),
                "entry_price": 100.0,
                "stop_price": 101.0,
                "target_price": 99.0,
            }
        ]
    )
    conditions = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "sweep_time": pd.Timestamp("2024-01-03 09:30", tz="America/New_York"),
                "reclaim_time": pd.Timestamp("2024-01-03 09:33", tz="America/New_York"),
                "reclaim_window_bars": 1,
                "volume_filter_pass": True,
                "delta_filter_pass": True,
                "rth_filter_pass": True,
                "final_entry_pass": True,
                "raw_orderflow_values": '{"bar.volume": 90, "volume_threshold": 100, "delta_pct": -5, "min_delta_pct": 10}',
            }
        ]
    )
    bars = pd.DataFrame(
        [
            {"trade_id": 1, "timestamp": pd.Timestamp("2024-01-03 09:30", tz="America/New_York"), "is_rth": False},
            {"trade_id": 1, "timestamp": pd.Timestamp("2024-01-03 09:31", tz="America/New_York"), "is_rth": False},
            {"trade_id": 1, "timestamp": pd.Timestamp("2024-01-03 09:32", tz="America/New_York"), "is_rth": False},
            {"trade_id": 1, "timestamp": pd.Timestamp("2024-01-03 09:33", tz="America/New_York"), "is_rth": False},
        ]
    )

    report = run_validation_checks(trades, conditions, bars, pd.DataFrame(), pd.DataFrame())

    assert _rows(report, "volume_filter_threshold").iloc[0]["status"] == "ERROR"
    assert _rows(report, "delta_filter_threshold").iloc[0]["status"] == "ERROR"
    assert _rows(report, "reclaim_window_distance").iloc[0]["status"] == "ERROR"
    assert _rows(report, "rth_filter_matches_session_flag").iloc[0]["status"] == "ERROR"


def test_validation_checks_flag_final_entry_and_exit_logic_errors():
    entry = pd.Timestamp("2024-01-03 09:31", tz="America/New_York")
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "direction": "long",
                "entry_time": entry,
                "exit_time": entry + pd.Timedelta(minutes=1),
                "entry_price": 100.0,
                "stop_price": 99.0,
                "target_price": 102.0,
                "exit_reason": "target",
            }
        ]
    )
    conditions = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "signal_time": entry,
                "volume_filter_pass": False,
                "final_entry_pass": True,
            }
        ]
    )
    exits = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "exit_reason": "target",
                "tp_hit_on_exit_bar": False,
                "sl_hit_on_exit_bar": True,
                "same_bar_ambiguous": False,
            }
        ]
    )

    report = run_validation_checks(trades, conditions, pd.DataFrame(), pd.DataFrame(), exits)

    assert _rows(report, "final_entry_required_filters").iloc[0]["status"] == "ERROR"
    assert _rows(report, "target_exit_has_target_touch").iloc[0]["status"] == "ERROR"


def test_validation_checks_pass_same_bar_when_ordered_tick_path_resolves_it():
    entry = pd.Timestamp("2024-01-03 09:31", tz="America/New_York")
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "direction": "short",
                "entry_time": entry,
                "exit_time": entry + pd.Timedelta(seconds=30),
                "entry_price": 100.0,
                "stop_price": 101.0,
                "target_price": 99.0,
                "exit_reason": "target",
            }
        ]
    )
    conditions = pd.DataFrame([{"trade_id": 1, "signal_time": entry, "final_entry_pass": True}])
    exits = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "exit_reason": "target",
                "first_touch_decision": "target",
                "first_touch_exit_decision": "target",
                "first_touch_tp_time": entry + pd.Timedelta(seconds=10),
                "first_touch_sl_time": entry + pd.Timedelta(seconds=20),
                "tp_hit_on_exit_bar": True,
                "sl_hit_on_exit_bar": True,
                "same_bar_ambiguous": True,
                "ambiguity_resolution": "detail_data",
                "engine_exit_matches_path": True,
                "warning_flags": "same_bar_resolved_by_tick_path",
            }
        ]
    )

    report = run_validation_checks(trades, conditions, pd.DataFrame(), pd.DataFrame(), exits)

    assert _rows(report, "same_bar_ambiguity_flagged").iloc[0]["status"] == "PASS"


def test_validation_checks_warn_same_bar_when_not_tick_resolved():
    entry = pd.Timestamp("2024-01-03 09:31", tz="America/New_York")
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "direction": "short",
                "entry_time": entry,
                "exit_time": entry + pd.Timedelta(seconds=30),
                "entry_price": 100.0,
                "stop_price": 101.0,
                "target_price": 99.0,
                "exit_reason": "stop",
            }
        ]
    )
    conditions = pd.DataFrame([{"trade_id": 1, "signal_time": entry, "final_entry_pass": True}])
    exits = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "exit_reason": "stop",
                "first_touch_exit_decision": "stop",
                "tp_hit_on_exit_bar": True,
                "sl_hit_on_exit_bar": True,
                "same_bar_ambiguous": True,
                "ambiguity_resolution": "pessimistic_stop_first",
            }
        ]
    )

    report = run_validation_checks(trades, conditions, pd.DataFrame(), pd.DataFrame(), exits)

    assert _rows(report, "same_bar_ambiguity_flagged").iloc[0]["status"] == "WARNING"


def test_validation_checks_warn_on_data_quality_issues():
    entry = pd.Timestamp("2024-01-03 09:31")
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "session_date": "2024-01-04",
                "direction": "long",
                "entry_time": entry,
                "exit_time": pd.Timestamp("2024-01-03 09:32"),
                "entry_price": 100.0,
                "stop_price": 99.0,
                "target_price": 102.0,
            }
        ]
    )
    conditions = pd.DataFrame([{"trade_id": 1, "signal_time": entry, "final_entry_pass": True}])
    bars = pd.DataFrame(
        [
            {"trade_id": 1, "timestamp": pd.Timestamp("2024-01-03 09:32"), "volume": 10},
            {"trade_id": 1, "timestamp": pd.Timestamp("2024-01-03 09:31"), "volume": 12},
        ]
    )

    report = run_validation_checks(trades, conditions, bars, pd.DataFrame(), pd.DataFrame())

    assert _rows(report, "tick_window_present").iloc[0]["status"] == "WARNING"
    assert _rows(report, "orderflow_fields_present").iloc[0]["status"] == "WARNING"
    assert _rows(report, "bar_timestamps_monotonic").iloc[0]["status"] == "WARNING"
    assert _rows(report, "session_date_matches_entry").iloc[0]["status"] == "WARNING"
    assert _rows(report, "timestamps_timezone_aware").iloc[0]["status"] == "WARNING"
