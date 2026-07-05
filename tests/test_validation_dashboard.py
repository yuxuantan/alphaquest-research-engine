from __future__ import annotations

import pandas as pd
import pytest

from propstack.dashboard.validation_app import (
    aggregate_footprint_by_price,
    add_review_annotations,
    build_review_queue,
    chart_y_range,
    checklist_rows,
    discover_validation_runs,
    exit_path_summary_frame,
    filter_trade_table,
    key_levels_from_artifacts,
    load_run_without_ticks,
    load_manual_reviews,
    make_exit_path_figure,
    make_price_figure,
    manual_review_summary,
    orderflow_filter_explanations,
    orderflow_warnings,
    prepare_trade_table,
    prepare_orderflow_bar_table,
    price_chart_config,
    raw_debug_frame,
    save_manual_review_annotation,
    selected_bar_footprint_detail,
)
from propstack.validation import (
    BarWindowRow,
    ConditionSnapshot,
    ExitAudit,
    TickWindowRow,
    TradeSummary,
    ValidationMetadata,
    load_tick_window_for_trade,
    write_validation_run,
)


def test_dashboard_discovers_validation_runs_and_defers_tick_load(tmp_path):
    run_dir = tmp_path / "backtest-campaigns" / "campaign" / "variant" / "ES" / "run1" / "validation_runs" / "core"
    metadata = ValidationMetadata(run_id="run1", strategy_id="strategy", symbol="ES")
    write_validation_run(
        run_dir,
        metadata,
        trades=[
            TradeSummary(
                run_id="run1",
                trade_id=1,
                symbol="ES",
                entry_time=pd.Timestamp("2024-01-03 09:31", tz="America/New_York"),
                exit_time=pd.Timestamp("2024-01-03 09:33", tz="America/New_York"),
            )
        ],
        tick_windows=[
            TickWindowRow(
                trade_id=1,
                timestamp=pd.Timestamp("2024-01-03 09:31:01", tz="America/New_York"),
                price=100.25,
                volume=5,
            )
        ],
    )

    discovered = discover_validation_runs(tmp_path / "backtest-campaigns")
    loaded_without_ticks = load_run_without_ticks(run_dir)
    selected_ticks = load_tick_window_for_trade(run_dir, 1)

    assert run_dir in discovered
    assert len(loaded_without_ticks.trades) == 1
    assert loaded_without_ticks.tick_windows.empty
    assert len(selected_ticks) == 1
    assert selected_ticks.loc[0, "price"] == 100.25


def test_manual_review_annotations_persist_and_summarize(tmp_path):
    run_dir = tmp_path / "validation_runs" / "core"

    saved = save_manual_review_annotation(
        run_dir,
        1,
        "Bug suspected",
        "entry appears early",
        reviewed_at="2026-07-05T00:00:00+00:00",
    )
    loaded = load_manual_reviews(run_dir)
    trades = prepare_trade_table(pd.DataFrame({"trade_id": [1, 2]}))
    annotated = add_review_annotations(trades, loaded)
    summary = manual_review_summary(trades, loaded)

    assert len(saved) == 1
    assert loaded.loc[0, "trade_id"] == 1
    assert loaded.loc[0, "reviewer_status"] == "Bug suspected"
    assert annotated.loc[0, "reviewer_status"] == "Bug suspected"
    assert annotated.loc[1, "reviewer_status_display"] == "Unreviewed"
    assert summary["number_reviewed"] == 1
    assert summary["number_bug_suspected"] == 1
    assert summary["review_completion_pct"] == 50.0


def test_manual_review_annotation_upserts_by_trade_id(tmp_path):
    run_dir = tmp_path / "validation_runs" / "core"

    save_manual_review_annotation(run_dir, 1, "Needs deeper review", "first", reviewed_at="2026-07-05T00:00:00+00:00")
    save_manual_review_annotation(run_dir, 1, "Correct", "second", reviewed_at="2026-07-05T00:01:00+00:00")
    loaded = load_manual_reviews(run_dir)

    assert len(loaded) == 1
    assert loaded.loc[0, "reviewer_status"] == "Correct"
    assert loaded.loc[0, "reviewer_notes"] == "second"


def test_build_review_queue_samples_and_filters_unreviewed():
    trades = pd.DataFrame(
        {
            "trade_id": list(range(1, 31)),
            "entry_time": pd.date_range("2024-01-01 09:30", periods=30, freq="min", tz="America/New_York"),
            "r_multiple": list(range(-15, 15)),
            "pnl_ticks": list(range(-15, 15)),
            "was_forced_flatten": [False] * 29 + [True],
            "same_bar_ambiguous": [False] * 28 + [True, False],
            "engine_exit_matches_path": [True] * 27 + [False, True, True],
            "warning_flags": [""] * 26 + ["engine_target_but_tick_stop_first"] + [""] * 3,
            "reviewer_status": ["Correct"] + [pd.NA] * 29,
        }
    )

    first_queue = build_review_queue(
        trades,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        sample_mode="First 20 trades chronologically",
        include_reviewed=False,
    )
    worst_queue = build_review_queue(
        trades,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        sample_mode="Worst 20 trades by R",
    )
    forced_queue = build_review_queue(
        trades,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        sample_mode="All forced-flatten trades",
    )
    mismatch_queue = build_review_queue(
        trades,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        sample_mode="All trades with mismatch warnings",
    )

    assert 1 not in first_queue["trade_id"].tolist()
    assert first_queue["trade_id"].iloc[0] == 2
    assert worst_queue["trade_id"].iloc[0] == 1
    assert forced_queue["trade_id"].tolist() == [30]
    assert set(mismatch_queue["trade_id"]) == {27, 28}


def test_build_review_queue_identifies_high_impact_edge_cases():
    entry_time = pd.Timestamp("2024-01-03 15:35", tz="America/New_York")
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "entry_time": entry_time,
                "entry_price": 100.0,
                "stop_price": 99.5,
                "target_price": 102.0,
                "r_multiple": 0.5,
            }
        ]
    )
    conditions = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "sweep_time": pd.Timestamp("2024-01-03 09:31:10", tz="America/New_York"),
                "reclaim_time": pd.Timestamp("2024-01-03 09:31:55", tz="America/New_York"),
                "reclaim_window_bars": 0,
                "volume_filter_pass": True,
                "delta_filter_pass": True,
                "raw_orderflow_values": '{"bar.volume": 105, "volume_threshold": 100, "absorption_bucket_delta": 305, "absorption_delta_threshold": 300}',
                "signal_report_fields": '{"signal_flatten_time": "15:55:00"}',
            }
        ]
    )
    exit_audits = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "same_bar_ambiguous": True,
                "tp_hit_on_exit_bar": True,
                "sl_hit_on_exit_bar": True,
            }
        ]
    )
    bar_windows = pd.DataFrame(
        [
            {"trade_id": 1, "timestamp": pd.Timestamp("2024-01-03 09:31", tz="America/New_York")},
            {"trade_id": 1, "timestamp": pd.Timestamp("2024-01-03 15:35", tz="America/New_York")},
        ]
    )

    queue = build_review_queue(
        trades,
        conditions,
        exit_audits,
        bar_windows,
        sample_mode="High-impact edge cases",
        tick_size=0.25,
    )
    reason = queue.loc[0, "review_reason"]

    assert "sweep and reclaim on same bar" in reason
    assert "entry near session cutoff" in reason
    assert "stop very close to entry" in reason
    assert "target and stop both touched in same bar" in reason
    assert "volume just above threshold" in reason
    assert "delta just above threshold" in reason


def test_dashboard_trade_table_filters_outcomes_and_debug_flags():
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "session_date": "2024-01-03",
                "direction": "long",
                "entry_time": pd.Timestamp("2024-01-03 09:31", tz="America/New_York"),
                "exit_time": pd.Timestamp("2024-01-03 09:33", tz="America/New_York"),
                "exit_reason": "target",
                "pnl_ticks": 4,
                "was_forced_flatten": False,
                "debug_flags": "",
            },
            {
                "trade_id": 2,
                "session_date": "2024-01-04",
                "direction": "short",
                "entry_time": pd.Timestamp("2024-01-04 10:00", tz="America/New_York"),
                "exit_time": pd.Timestamp("2024-01-04 10:03", tz="America/New_York"),
                "exit_reason": "forced_apex_flatten",
                "pnl_ticks": -2,
                "was_forced_flatten": True,
                "debug_flags": "same_bar_ambiguous=true",
            },
        ]
    )
    audits = pd.DataFrame(
        [
            {"trade_id": 1, "same_bar_ambiguous": False},
            {"trade_id": 2, "same_bar_ambiguous": True, "ambiguity_resolution": "pessimistic_stop_first"},
        ]
    )

    table = prepare_trade_table(trades, audits)
    filtered = filter_trade_table(
        table,
        directions=["short"],
        outcome="Losing",
        forced_flatten_only=True,
        ambiguous_only=True,
        suspicious_only=True,
    )

    assert len(filtered) == 1
    assert filtered.loc[0, "trade_id"] == 2
    assert bool(filtered.loc[0, "suspicious_debug"]) is True


def test_dashboard_checklist_and_raw_debug_handle_missing_fields():
    snapshot = pd.Series(
        {
            "trade_id": 1,
            "rth_filter_pass": True,
            "volume_filter_pass": False,
            "filter_pass_values": '{"metadata.reclaim_filter_pass": true, "metadata.sweep_filter_pass": true}',
            "raw_orderflow_values": '{"bar.signed_volume": 100}',
        }
    )

    checklist = checklist_rows(snapshot)
    raw = raw_debug_frame(snapshot)

    statuses = dict(zip(checklist["condition"], checklist["status"]))
    assert statuses["RTH filter"] == "PASS"
    assert statuses["Sweep filter"] == "PASS"
    assert statuses["Reclaim filter"] == "PASS"
    assert statuses["Volume filter"] == "FAIL"
    assert statuses["Delta filter"] == "N/A"
    assert "raw_orderflow_values" in set(raw["field"])


def test_dashboard_key_levels_include_trade_and_artifact_levels():
    trade = pd.Series({"stop_price": 99.0, "target_price": 102.0})
    condition = pd.Series({"swept_level_price": 100.0})
    bars = pd.DataFrame(
        [
            BarWindowRow(
                trade_id=1,
                timestamp=pd.Timestamp("2024-01-03 09:31", tz="America/New_York"),
                open=100,
                high=101,
                low=99,
                close=100.5,
                prev_rth_high=103.0,
                overnight_low=98.0,
            ).to_record()
        ]
    )

    levels = key_levels_from_artifacts(bars, condition, trade)
    by_label = {level["label"]: level["value"] for level in levels}

    assert by_label["Stop"] == 99.0
    assert by_label["Target"] == 102.0
    assert by_label["Swept level"] == 100.0
    assert by_label["Previous RTH high"] == 103.0
    assert by_label["Overnight low"] == 98.0


def test_price_chart_navigation_defaults_reduce_scroll_conflicts():
    config = price_chart_config()
    wheel_config = price_chart_config(scroll_zoom=True)

    assert config["scrollZoom"] is False
    assert wheel_config["scrollZoom"] is True
    assert config["displayModeBar"] is True
    assert config["doubleClick"] == "reset"
    assert "drawline" in config["modeBarButtonsToAdd"]
    assert "eraseshape" in config["modeBarButtonsToAdd"]


def test_price_chart_y_range_includes_stop_target_and_levels():
    trade = pd.Series({"entry_price": 100.0, "exit_price": 101.0, "stop_price": 97.5, "target_price": 104.0})
    condition = pd.Series({"swept_level_price": 98.25})
    bars = pd.DataFrame(
        [
            {"timestamp": pd.Timestamp("2024-01-03 09:31", tz="America/New_York"), "open": 100, "high": 101, "low": 99, "close": 100.5},
            {"timestamp": pd.Timestamp("2024-01-03 09:32", tz="America/New_York"), "open": 100.5, "high": 102, "low": 100, "close": 101.5},
        ]
    )

    y_range = chart_y_range(bars, trade, condition)

    assert y_range is not None
    assert y_range[0] < 97.5
    assert y_range[1] > 104.0


def test_price_chart_y_range_can_ignore_far_context_levels_and_zoom_vertically():
    trade = pd.Series({"entry_price": 100.0, "exit_price": 101.0, "stop_price": 99.0, "target_price": 102.0})
    condition = pd.Series({"swept_level_price": 100.25})
    bars = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2024-01-03 09:31", tz="America/New_York"),
                "open": 100,
                "high": 101,
                "low": 99.5,
                "close": 100.5,
                "overnight_low": 50.0,
            }
        ]
    )

    fit_levels = chart_y_range(bars, trade, condition, include_key_levels=True)
    tight = chart_y_range(bars, trade, condition, include_key_levels=False)
    zoomed = chart_y_range(bars, trade, condition, include_key_levels=False, y_zoom=2.0)

    assert fit_levels is not None
    assert tight is not None
    assert zoomed is not None
    assert fit_levels[0] < 60
    assert tight[0] > 98
    assert (zoomed[1] - zoomed[0]) < (tight[1] - tight[0])


def test_price_chart_lines_do_not_write_overlapping_plot_annotations():
    pytest.importorskip("plotly")
    trade = pd.Series(
        {
            "trade_id": 1,
            "entry_time": pd.Timestamp("2024-01-03 09:31", tz="America/New_York"),
            "entry_price": 100.0,
            "exit_time": pd.Timestamp("2024-01-03 09:32", tz="America/New_York"),
            "exit_price": 101.0,
            "stop_price": 99.0,
            "target_price": 102.0,
        }
    )
    condition = pd.Series(
        {
            "swept_level_price": 100.25,
            "sweep_time": pd.Timestamp("2024-01-03 09:31", tz="America/New_York"),
            "reclaim_time": pd.Timestamp("2024-01-03 09:32", tz="America/New_York"),
        }
    )
    bars = pd.DataFrame(
        [
            {"timestamp": pd.Timestamp("2024-01-03 09:31", tz="America/New_York"), "open": 100, "high": 101, "low": 99, "close": 100.5},
            {"timestamp": pd.Timestamp("2024-01-03 09:32", tz="America/New_York"), "open": 100.5, "high": 102, "low": 100, "close": 101.5},
        ]
    )

    fig = make_price_figure(trade, bars, condition, fit_key_levels=False, y_zoom=1.5)

    assert len(fig.layout.annotations or []) == 0
    assert fig.layout.yaxis.fixedrange is False


def test_exit_path_summary_and_figure_show_first_touch_without_annotations():
    pytest.importorskip("plotly")
    trade = pd.Series(
        {
            "trade_id": 1,
            "entry_time": pd.Timestamp("2024-01-03 09:31:00", tz="America/New_York"),
            "entry_price": 100.0,
            "stop_price": 99.0,
            "target_price": 101.0,
            "exit_time": pd.Timestamp("2024-01-03 09:31:02", tz="America/New_York"),
            "exit_price": 101.0,
            "exit_reason": "target",
        }
    )
    audit = pd.Series(
        {
            "trade_id": 1,
            "first_touch_tp_time": pd.Timestamp("2024-01-03 09:31:02", tz="America/New_York"),
            "first_touch_tp_price": 101.0,
            "first_touch_decision": "target",
            "engine_exit_matches_path": True,
            "mfe_ticks": 4,
            "mae_ticks": 0,
        }
    )
    ticks = pd.DataFrame(
        [
            {"trade_id": 1, "timestamp": pd.Timestamp("2024-01-03 09:31:00", tz="America/New_York"), "price": 100.0},
            {"trade_id": 1, "timestamp": pd.Timestamp("2024-01-03 09:31:02", tz="America/New_York"), "price": 101.0},
        ]
    )

    fig = make_exit_path_figure(trade, audit, ticks)
    summary = exit_path_summary_frame(audit)

    assert len(fig.layout.annotations or []) == 0
    assert "first_touch_decision" in set(summary["field"])
    assert "target" in set(summary["value"])


def test_orderflow_bar_table_marks_events_and_maps_footprint_maxes():
    first_bar = pd.Timestamp("2024-01-03 09:31", tz="America/New_York")
    second_bar = pd.Timestamp("2024-01-03 09:32", tz="America/New_York")
    bars = pd.DataFrame(
        [
            BarWindowRow(
                trade_id=1,
                timestamp=first_bar,
                open=100,
                high=101,
                low=99,
                close=100.5,
                volume=1000,
                bid_volume=400,
                ask_volume=600,
                delta=200,
            ).to_record(),
            BarWindowRow(
                trade_id=1,
                timestamp=second_bar,
                open=100.5,
                high=102,
                low=100,
                close=101.5,
                volume=900,
                bid_volume=500,
                ask_volume=400,
                delta=-100,
            ).to_record(),
        ]
    )
    ticks = pd.DataFrame(
        [
            TickWindowRow(
                trade_id=1,
                timestamp=first_bar + pd.Timedelta(seconds=10),
                price=100.0,
                volume=120,
                price_level=100.0,
                price_level_bid_volume=30,
                price_level_ask_volume=90,
            ).to_record(),
            TickWindowRow(
                trade_id=1,
                timestamp=second_bar + pd.Timedelta(seconds=5),
                price=101.0,
                volume=80,
                price_level=101.0,
                price_level_bid_volume=70,
                price_level_ask_volume=10,
            ).to_record(),
        ]
    )
    trade = pd.Series({"trade_id": 1, "entry_time": second_bar, "exit_time": second_bar + pd.Timedelta(minutes=1)})
    condition = pd.Series(
        {
            "trade_id": 1,
            "sweep_time": first_bar,
            "reclaim_time": second_bar,
            "signal_time": second_bar,
            "entry_execution_time": second_bar,
            "rth_filter_pass": True,
            "volume_filter_pass": True,
            "delta_filter_pass": True,
            "stacked_imbalance_pass": False,
            "final_entry_pass": True,
        }
    )

    table = prepare_orderflow_bar_table(bars, trade, condition, None, ticks)

    assert "sweep" in table.loc[0, "event_marker"]
    assert "reclaim" in table.loc[1, "event_marker"]
    assert "signal" in table.loc[1, "event_marker"]
    assert table.loc[0, "delta_pct"] == 20.0
    assert table.loc[0, "max_ask_volume_at_price"] == 90
    assert table.loc[1, "max_bid_volume_at_price"] == 70
    assert table.loc[1, "delta_filter_pass"] is True


def test_footprint_aggregation_and_selected_bar_detail():
    first_bar = pd.Timestamp("2024-01-03 09:31", tz="America/New_York")
    bars = pd.DataFrame([BarWindowRow(trade_id=1, timestamp=first_bar).to_record()])
    ticks = pd.DataFrame(
        [
            TickWindowRow(
                trade_id=1,
                timestamp=first_bar + pd.Timedelta(seconds=1),
                price=100.0,
                volume=120,
                price_level=100.0,
                price_level_bid_volume=30,
                price_level_ask_volume=90,
            ).to_record(),
            TickWindowRow(
                trade_id=1,
                timestamp=first_bar + pd.Timedelta(seconds=2),
                price=100.0,
                volume=10,
                price_level=100.0,
                price_level_bid_volume=5,
                price_level_ask_volume=5,
            ).to_record(),
        ]
    )

    footprint = aggregate_footprint_by_price(ticks, bars)
    detail = selected_bar_footprint_detail(footprint, first_bar)

    assert len(footprint) == 1
    assert footprint.loc[0, "total_volume"] == 130
    assert footprint.loc[0, "delta"] == 60
    assert detail.loc[0, "imbalance_marker"] == ""


def test_orderflow_filter_explanations_use_raw_snapshot_values():
    condition = pd.Series(
        {
            "trade_id": 1,
            "delta_filter_pass": True,
            "raw_orderflow_values": '{"bar.delta_pct": -14.2, "bar.volume": 1500}',
            "signal_report_fields": '{"min_delta_pct": -10, "delta_filter_rule": "delta_pct <= -10%"}',
        }
    )

    explanation = orderflow_filter_explanations(condition)
    delta_row = explanation[explanation["filter"] == "delta_filter"].iloc[0]

    assert delta_row["status"] == "PASS"
    assert delta_row["rule"] == "delta_pct <= -10%"
    assert delta_row["actual"] == "-14.2"
    assert delta_row["threshold"] == "-10"


def test_orderflow_warnings_flag_missing_and_misaligned_data():
    first_bar = pd.Timestamp("2024-01-03 09:31", tz="America/New_York")
    bars = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "timestamp": first_bar,
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100.5,
                "volume": 100,
                "delta": 20,
            }
        ]
    )
    condition = pd.Series(
        {
            "trade_id": 1,
            "sweep_time": first_bar + pd.Timedelta(hours=1),
            "delta_filter_pass": True,
            "volume_filter_pass": True,
            "final_entry_pass": True,
        }
    )

    warnings = orderflow_warnings(pd.Series({"trade_id": 1}), condition, bars, pd.DataFrame())

    assert any("bid/ask" in warning for warning in warnings)
    assert any("no footprint window" in warning for warning in warnings)
    assert any("Delta filter passed" in warning for warning in warnings)
    assert any("sweep timestamp" in warning for warning in warnings)


def test_orderflow_warnings_use_signed_volume_not_absorption_bucket_delta():
    first_bar = pd.Timestamp("2026-05-07 10:21", tz="America/New_York")
    bars = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "timestamp": first_bar,
                "open": 7394.75,
                "high": 7396.5,
                "low": 7392.25,
                "close": 7396.5,
                "volume": 11074,
                "bid_volume": 5169,
                "ask_volume": 5905,
                "delta": 736,
            }
        ]
    )
    condition = pd.Series(
        {
            "trade_id": 1,
            "bid_volume": 5169,
            "ask_volume": 5905,
            "delta_value": 300,
            "raw_orderflow_values": (
                '{"bar.signed_volume": 736, '
                '"metadata.absorption_bucket_delta": 300, '
                '"report.absorption_bucket_delta": 300}'
            ),
        }
    )

    warnings = orderflow_warnings(pd.Series({"trade_id": 1}), condition, bars)

    assert not any("does not reconcile" in warning for warning in warnings)


def test_orderflow_warnings_flag_signed_volume_reconciliation_mismatch():
    first_bar = pd.Timestamp("2026-05-07 10:21", tz="America/New_York")
    bars = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "timestamp": first_bar,
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100.5,
                "volume": 100,
                "bid_volume": 40,
                "ask_volume": 60,
                "delta": 20,
            }
        ]
    )
    condition = pd.Series(
        {
            "trade_id": 1,
            "bid_volume": 40,
            "ask_volume": 60,
            "raw_orderflow_values": '{"bar.signed_volume": 10}',
        }
    )

    warnings = orderflow_warnings(pd.Series({"trade_id": 1}), condition, bars)

    assert any("signed volume (bar.signed_volume)" in warning for warning in warnings)
