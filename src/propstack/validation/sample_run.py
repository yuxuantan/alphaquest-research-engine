"""Create a tiny synthetic validation run for dashboard smoke testing."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from propstack.validation import (
    BarWindowRow,
    ConditionSnapshot,
    ExitAudit,
    TickWindowRow,
    TradeSummary,
    ValidationMetadata,
    write_validation_run,
)

DEFAULT_OUTPUT_DIR = Path("examples/validation_runs/sample_core")
NY = "America/New_York"


def write_sample_validation_run(output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> Path:
    output_path = Path(output_dir)
    base = pd.Timestamp("2024-01-03 09:30:00", tz=NY)
    metadata = ValidationMetadata(
        run_id="sample_validation_run",
        campaign_id="sample_dashboard",
        strategy_id="synthetic_validation_strategy",
        variant_id="sample_fixture",
        symbol="ES",
        stage="core",
        timezone=NY,
        tick_size=0.25,
        tick_value=12.5,
        timeframe="1m",
        timeframe_minutes=1,
        notes="Synthetic dashboard smoke fixture. Not a backtest result.",
    )

    trades = [
        TradeSummary(
            run_id="sample_validation_run",
            trade_id=1,
            symbol="ES",
            session_date="2024-01-03",
            direction="long",
            entry_time=base + pd.Timedelta(minutes=2),
            entry_price=100.0,
            entry_order_type="next_bar_open",
            stop_price=99.0,
            target_price=102.0,
            exit_time=base + pd.Timedelta(minutes=6),
            exit_price=102.0,
            exit_reason="target",
            pnl_ticks=8,
            pnl_usd=100.0,
            r_multiple=2.0,
            bars_held=4,
            contracts=1,
            was_forced_flatten=False,
        ),
        TradeSummary(
            run_id="sample_validation_run",
            trade_id=2,
            symbol="ES",
            session_date="2024-01-03",
            direction="short",
            entry_time=base + pd.Timedelta(minutes=12),
            entry_price=101.5,
            entry_order_type="intrabar",
            stop_price=102.25,
            target_price=100.0,
            exit_time=base + pd.Timedelta(minutes=14),
            exit_price=102.25,
            exit_reason="stop",
            pnl_ticks=-3,
            pnl_usd=-37.5,
            r_multiple=-1.0,
            bars_held=2,
            contracts=1,
            was_forced_flatten=False,
            debug_flags="same_bar_ambiguous=true",
        ),
        TradeSummary(
            run_id="sample_validation_run",
            trade_id=3,
            symbol="ES",
            session_date="2024-01-03",
            direction="long",
            entry_time=pd.Timestamp("2024-01-03 15:50:00", tz=NY),
            entry_price=103.0,
            entry_order_type="next_bar_open",
            stop_price=102.0,
            target_price=105.0,
            exit_time=pd.Timestamp("2024-01-03 15:55:00", tz=NY),
            exit_price=103.25,
            exit_reason="forced_apex_flatten",
            pnl_ticks=1,
            pnl_usd=12.5,
            r_multiple=0.25,
            bars_held=5,
            contracts=1,
            was_forced_flatten=True,
        ),
    ]

    conditions = [
        ConditionSnapshot(
            trade_id=1,
            signal_time=base + pd.Timedelta(minutes=1),
            decision_bar_time=base + pd.Timedelta(minutes=1),
            entry_execution_time=base + pd.Timedelta(minutes=2),
            entry_mode="bar_close",
            swept_level_name="ONL",
            swept_level_price=99.5,
            sweep_time=base,
            reclaim_time=base + pd.Timedelta(minutes=1),
            reclaim_window_bars=2,
            volume_filter_pass=True,
            delta_value=220,
            delta_pct=12.5,
            delta_filter_pass=True,
            bid_volume=390,
            ask_volume=610,
            total_volume=1000,
            rth_filter_pass=True,
            final_entry_pass=True,
            raw_orderflow_values='{"bar.volume": 1000, "volume_threshold": 750, "delta_pct": 12.5, "min_delta_pct": 10}',
            signal_report_fields='{"signal_flatten_time": "15:55:00"}',
        ),
        ConditionSnapshot(
            trade_id=2,
            signal_time=base + pd.Timedelta(minutes=12),
            decision_bar_time=base + pd.Timedelta(minutes=12),
            entry_execution_time=base + pd.Timedelta(minutes=12),
            entry_mode="intrabar",
            swept_level_name="PDH",
            swept_level_price=102.0,
            sweep_time=base + pd.Timedelta(minutes=12),
            reclaim_time=base + pd.Timedelta(minutes=12),
            reclaim_window_bars=1,
            volume_filter_pass=True,
            delta_value=-180,
            delta_pct=-11.0,
            delta_filter_pass=True,
            bid_volume=540,
            ask_volume=360,
            total_volume=900,
            rth_filter_pass=True,
            final_entry_pass=True,
            raw_orderflow_values='{"bar.volume": 900, "volume_threshold": 800, "delta_pct": -11, "max_delta_pct": -10}',
            signal_report_fields='{"signal_flatten_time": "15:55:00"}',
        ),
        ConditionSnapshot(
            trade_id=3,
            signal_time=pd.Timestamp("2024-01-03 15:49:00", tz=NY),
            decision_bar_time=pd.Timestamp("2024-01-03 15:49:00", tz=NY),
            entry_execution_time=pd.Timestamp("2024-01-03 15:50:00", tz=NY),
            entry_mode="bar_close",
            volume_filter_pass=True,
            delta_filter_pass=True,
            rth_filter_pass=True,
            final_entry_pass=True,
            raw_orderflow_values='{"bar.volume": 700, "volume_threshold": 650, "delta_pct": 8, "min_delta_pct": 5}',
            signal_report_fields='{"signal_flatten_time": "15:55:00"}',
        ),
    ]

    bars = []
    for trade_id, start, prices in [
        (1, base, [99.5, 100.0, 100.75, 101.25, 101.75, 102.0, 102.25]),
        (2, base + pd.Timedelta(minutes=11), [101.75, 101.5, 100.75, 102.25]),
        (3, pd.Timestamp("2024-01-03 15:49:00", tz=NY), [102.75, 103.0, 103.25, 103.0, 103.25, 103.25]),
    ]:
        for offset, close in enumerate(prices):
            timestamp = start + pd.Timedelta(minutes=offset)
            bars.append(
                BarWindowRow(
                    trade_id=trade_id,
                    timestamp=timestamp,
                    open=close - 0.25,
                    high=close + 0.5,
                    low=close - 0.75,
                    close=close,
                    volume=800 + 25 * offset,
                    bid_volume=390 + 10 * offset,
                    ask_volume=410 + 15 * offset,
                    delta=20 + 5 * offset,
                    is_rth=True,
                    session_date=str(timestamp.date()),
                )
            )

    ticks = [
        TickWindowRow(trade_id=1, timestamp=base + pd.Timedelta(minutes=2, seconds=1), price=100.0, volume=5, price_level=100.0, bid_volume=2, ask_volume=3),
        TickWindowRow(trade_id=1, timestamp=base + pd.Timedelta(minutes=4, seconds=10), price=101.0, volume=8, price_level=101.0, bid_volume=2, ask_volume=6),
        TickWindowRow(trade_id=1, timestamp=base + pd.Timedelta(minutes=6), price=102.0, volume=12, price_level=102.0, bid_volume=2, ask_volume=10),
        TickWindowRow(trade_id=2, timestamp=base + pd.Timedelta(minutes=12, seconds=5), price=101.5, volume=6, price_level=101.5, bid_volume=4, ask_volume=2),
        TickWindowRow(trade_id=2, timestamp=base + pd.Timedelta(minutes=13), price=100.0, volume=10, price_level=100.0, bid_volume=8, ask_volume=2),
        TickWindowRow(trade_id=2, timestamp=base + pd.Timedelta(minutes=13, seconds=20), price=102.25, volume=10, price_level=102.25, bid_volume=2, ask_volume=8),
    ]

    exits = [
        ExitAudit(
            trade_id=1,
            entry_time=trades[0].entry_time,
            entry_price=100.0,
            stop_price=99.0,
            target_price=102.0,
            exit_time=trades[0].exit_time,
            exit_price=102.0,
            exit_reason="target",
            first_touch_tp_time=trades[0].exit_time,
            first_touch_tp_price=102.0,
            first_touch_decision="target",
            first_touch_exit_decision="target",
            same_bar_ambiguous=False,
            tick_count_checked=3,
        ),
        ExitAudit(
            trade_id=2,
            entry_time=trades[1].entry_time,
            entry_price=101.5,
            stop_price=102.25,
            target_price=100.0,
            exit_time=trades[1].exit_time,
            exit_price=102.25,
            exit_reason="stop",
            first_touch_tp_time=base + pd.Timedelta(minutes=13),
            first_touch_tp_price=100.0,
            first_touch_sl_time=base + pd.Timedelta(minutes=13, seconds=20),
            first_touch_sl_price=102.25,
            first_touch_decision="target",
            first_touch_exit_decision="stop",
            same_bar_ambiguous=True,
            ambiguity_resolution="sample_mismatch_for_review",
            tp_hit_on_exit_bar=True,
            sl_hit_on_exit_bar=True,
            tick_count_checked=3,
        ),
        ExitAudit(
            trade_id=3,
            entry_time=trades[2].entry_time,
            entry_price=103.0,
            stop_price=102.0,
            target_price=105.0,
            exit_time=trades[2].exit_time,
            exit_price=103.25,
            exit_reason="forced_apex_flatten",
            first_touch_exit_decision="forced_apex_flatten",
            forced_flatten_reason="forced_apex_flatten",
            tick_count_checked=0,
        ),
    ]

    write_validation_run(
        output_path,
        metadata,
        trades=trades,
        condition_snapshots=conditions,
        bar_windows=bars,
        tick_windows=ticks,
        exit_audits=exits,
    )
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a tiny synthetic validation-dashboard run.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()
    output_path = write_sample_validation_run(args.output_dir)
    print(output_path)


if __name__ == "__main__":
    main()
