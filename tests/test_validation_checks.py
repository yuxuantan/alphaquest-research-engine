from __future__ import annotations

import pandas as pd

from alphaquest.validation.checks import run_validation_checks


def _rows(report: pd.DataFrame, check_name: str) -> pd.DataFrame:
    return report[report["check_name"] == check_name]


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
