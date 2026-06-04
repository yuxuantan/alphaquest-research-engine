from types import SimpleNamespace

import pandas as pd

from propstack.strategy_modules.entry.intraday_capitulation_mr import IntradayCapitulationMREntry
from propstack.strategy_modules.entry.opening_range_breakout import OpeningRangeBreakoutEntry
from propstack.strategy_modules.entry.opening_range_inverse_breakout import OpeningRangeInverseBreakoutEntry
from propstack.strategy_modules.entry.pdh_pdl_sweep_reclaim import PdhPdlSweepReclaimEntry
from propstack.strategy_modules.sl.opening_range_edge import OpeningRangeEdgeStop
from propstack.strategy_modules.sl.opening_range_width import OpeningRangeWidthStop
from propstack.strategy_modules.sl.percent_from_entry import PercentFromEntryStop
from propstack.strategy_modules.sl.sweep_extreme import SweepExtremeStop
from propstack.strategy_modules.tp.cost_adjusted_fixed_r import CostAdjustedFixedRTarget
from propstack.strategy_modules.tp.fixed_r import FixedRTarget
from propstack.strategy_modules.tp.opening_range_extension import OpeningRangeExtensionTarget
from propstack.strategy_modules.tp.opening_range_opposite_edge import OpeningRangeOppositeEdgeTarget
from propstack.strategy_modules.tp.percent_from_entry import PercentFromEntryTarget


def test_fixed_r_target_module_long_and_short():
    target = FixedRTarget({"target_r_multiple": 2.0})

    assert target.price(entry_price=100.0, stop_price=98.0, direction="long") == 104.0
    assert target.price(entry_price=100.0, stop_price=102.0, direction="short") == 96.0


def test_cost_adjusted_fixed_r_target_module_long_and_short():
    target = CostAdjustedFixedRTarget(
        {
            "target_r_multiple": 2.0,
            "tick_size": 0.1,
            "tick_value": 10.0,
            "commission_per_contract": 5.0,
            "slippage_ticks": 1,
        }
    )

    assert round(target.price(entry_price=100.0, stop_price=99.0, direction="long"), 10) == 102.6
    assert round(target.price(entry_price=100.0, stop_price=101.0, direction="short"), 10) == 97.4


def test_sweep_extreme_stop_module_long_and_short():
    stop = SweepExtremeStop({"stop_offset_ticks": 2})
    signal = SimpleNamespace(sweep_low=99.0, sweep_high=101.0)

    assert stop.price(signal, direction="long", tick_size=0.25) == 98.5
    assert stop.price(signal, direction="short", tick_size=0.25) == 101.5


def test_opening_range_extension_target_module_long_and_short():
    target = OpeningRangeExtensionTarget({"extension_fraction": 0.5})
    signal = SimpleNamespace(opening_range_high=101.0, opening_range_low=99.0, opening_range_width=2.0)

    assert target.price(100.0, 99.0, "long", signal=signal) == 102.0
    assert target.price(100.0, 101.0, "short", signal=signal) == 98.0


def test_percent_from_entry_stop_and_target_round_to_tick():
    stop = PercentFromEntryStop({"stop_pct": 0.003})
    target = PercentFromEntryTarget({"target_pct": 0.0075, "tick_size": 0.25})

    assert stop.price(None, direction="long", tick_size=0.25, entry_price=100.0) == 99.5
    assert stop.price(None, direction="short", tick_size=0.25, entry_price=100.0) == 100.5
    assert target.price(100.0, 99.5, "long") == 100.75
    assert target.price(100.0, 100.5, "short") == 99.25


def test_opening_range_edge_stop_skips_when_natural_risk_exceeds_max():
    stop = OpeningRangeEdgeStop({"max_stop_points": 10, "stop_offset_ticks": 0})
    signal = SimpleNamespace(opening_range_high=111.0, opening_range_low=90.0)

    assert stop.price(signal, direction="long", tick_size=0.25, entry_price=105.0) is None
    assert stop.price(signal, direction="short", tick_size=0.25, entry_price=95.0) is None
    assert stop.price(signal, direction="long", tick_size=0.25, entry_price=99.0) == 90.0
    assert stop.price(signal, direction="short", tick_size=0.25, entry_price=101.0) == 111.0


def test_opening_range_width_stop_uses_entry_price_and_range_width():
    stop = OpeningRangeWidthStop({"max_stop_points": 10, "stop_offset_ticks": 0})
    signal = SimpleNamespace(opening_range_width=1.5, metadata={"confirmation_close": 99.0})

    assert stop.price(signal, direction="long", tick_size=0.25, entry_price=98.75) == 97.25
    assert stop.price(signal, direction="short", tick_size=0.25, entry_price=101.25) == 102.75


def test_opening_range_width_stop_skips_when_range_width_exceeds_max():
    stop = OpeningRangeWidthStop({"max_stop_points": 1.0, "stop_offset_ticks": 0})
    signal = SimpleNamespace(opening_range_width=1.5, metadata={"confirmation_close": 99.0})

    assert stop.price(signal, direction="long", tick_size=0.25, entry_price=98.75) is None


def test_opening_range_opposite_edge_target_module_long_and_short():
    target = OpeningRangeOppositeEdgeTarget({})
    signal = SimpleNamespace(opening_range_high=101.0, opening_range_low=99.0)

    assert target.price(98.75, 97.25, "long", signal=signal) == 101.0
    assert target.price(101.25, 102.75, "short", signal=signal) == 99.0


def _cap_bar(timestamp, open_price, high, low, close, volume, vwap, session_date=None):
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize("America/New_York")
    else:
        ts = ts.tz_convert("America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": session_date or ts.date(),
            "is_rth": True,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "vwap": vwap,
        },
        name=ts.hour * 60 + ts.minute,
    )


def _cap_window(start, open_price, high, low, close, total_volume, vwap):
    start_ts = pd.Timestamp(start, tz="America/New_York")
    bars = []
    for minute in range(15):
        ts = start_ts + pd.Timedelta(minutes=minute)
        bars.append(
            _cap_bar(
                ts,
                open_price if minute == 0 else close,
                high,
                low,
                close,
                total_volume / 15,
                vwap,
            )
        )
    return bars


def test_intraday_capitulation_mr_entry_emits_on_completed_15m_bar():
    entry = IntradayCapitulationMREntry(
        {
            "timeframe_minutes": 15,
            "bar_interval_minutes": 1,
            "rsi_period": 1,
            "max_rsi": 35,
            "volume_avg_window": 1,
            "min_volume_avg_bars": 1,
            "min_volume_ratio": 1.5,
            "max_close_location_from_low": 0.25,
            "last_signal_time": "16:00:00",
        }
    )
    bars = [
        *_cap_window("2024-01-03 09:30", 100.0, 101.0, 99.0, 100.0, 1000, 100.0),
        *_cap_window("2024-01-03 09:45", 100.0, 100.2, 98.0, 98.2, 1600, 99.0),
    ]

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "long"
    assert signal.level_type == "intraday_capitulation_mr"
    assert signal.sweep_low == 98.0
    assert signal.report_fields["capitulation_bar_start_timestamp"] == pd.Timestamp(
        "2024-01-03 09:45", tz="America/New_York"
    )
    assert signal.report_fields["capitulation_bar_end_timestamp"] == pd.Timestamp(
        "2024-01-03 10:00", tz="America/New_York"
    )
    assert signal.report_fields["capitulation_rsi"] == 0.0
    assert round(signal.report_fields["capitulation_volume_ratio"], 2) == 1.6


def test_intraday_capitulation_mr_entry_rejects_close_not_near_low():
    entry = IntradayCapitulationMREntry(
        {
            "timeframe_minutes": 15,
            "bar_interval_minutes": 1,
            "rsi_period": 1,
            "max_rsi": 35,
            "volume_avg_window": 1,
            "min_volume_avg_bars": 1,
            "min_volume_ratio": 1.5,
            "max_close_location_from_low": 0.25,
        }
    )
    bars = [
        *_cap_window("2024-01-03 09:30", 100.0, 101.0, 99.0, 100.0, 1000, 100.0),
        *_cap_window("2024-01-03 09:45", 100.0, 100.2, 98.0, 99.0, 1600, 99.5),
    ]

    signal = None
    for bar in bars:
        signal = entry.on_bar_close(bar)

    assert signal is None


def _orb_bar(timestamp, open_price, high, low, close, session_date=None):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": session_date or ts.date(),
            "is_rth": True,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume_ratio": 1.0,
        },
        name=ts.hour * 60 + ts.minute,
    )


def _orb_long_breakout_bars(date="2024-01-03"):
    return [
        _orb_bar(f"{date} 09:30", 100.0, 100.20, 99.90, 100.10),
        _orb_bar(f"{date} 09:31", 100.1, 100.30, 100.00, 100.20),
        _orb_bar(f"{date} 09:32", 100.2, 100.40, 100.10, 100.25),
        _orb_bar(f"{date} 09:33", 100.2, 100.25, 99.95, 100.05),
        _orb_bar(f"{date} 09:34", 100.0, 100.35, 100.05, 100.20),
        _orb_bar(f"{date} 09:35", 100.2, 100.30, 100.00, 100.10),
        _orb_bar(f"{date} 09:36", 100.1, 100.30, 100.00, 100.20),
        _orb_bar(f"{date} 09:37", 100.2, 100.35, 100.10, 100.30),
        _orb_bar(f"{date} 09:38", 100.3, 100.38, 100.20, 100.35),
        _orb_bar(f"{date} 09:39", 100.35, 100.55, 100.30, 100.50),
    ]


def test_opening_range_breakout_entry_emits_after_confirmation_window():
    entry = OpeningRangeBreakoutEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 5,
            "bar_interval_minutes": 1,
            "max_opening_range_pct_of_open": 0.0055,
            "allow_long": True,
            "allow_short": True,
        }
    )
    bars = _orb_long_breakout_bars()

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "long"
    assert signal.level_type == "opening_range_high"
    assert signal.swept_level == 100.40
    assert signal.opening_range_low == 99.90
    assert round(signal.opening_range_width, 2) == 0.50
    assert signal.reclaim_timestamp == bars[-1]["timestamp"]
    assert signal.report_fields["opening_range_start_timestamp"] == bars[0]["timestamp"]
    assert signal.report_fields["opening_range_end_timestamp"] == pd.Timestamp(
        "2024-01-03 09:35", tz="America/New_York"
    )
    assert signal.report_fields["confirmation_start_timestamp"] == bars[5]["timestamp"]
    assert signal.report_fields["confirmation_end_timestamp"] == pd.Timestamp(
        "2024-01-03 09:40", tz="America/New_York"
    )
    assert signal.report_fields["breakout_timestamp"] == pd.Timestamp("2024-01-03 09:40", tz="America/New_York")


def test_opening_range_breakout_entry_keeps_checking_later_confirmation_windows():
    entry = OpeningRangeBreakoutEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 5,
            "bar_interval_minutes": 1,
            "max_opening_range_pct_of_open": 0.0055,
            "allow_long": True,
            "allow_short": True,
        }
    )
    bars = _orb_long_breakout_bars()
    bars[-1] = _orb_bar("2024-01-03 09:39", 100.35, 100.38, 100.25, 100.35)
    bars.extend(
        [
            _orb_bar("2024-01-03 09:40", 100.35, 100.38, 100.20, 100.30),
            _orb_bar("2024-01-03 09:41", 100.30, 100.36, 100.18, 100.28),
            _orb_bar("2024-01-03 09:42", 100.28, 100.37, 100.22, 100.31),
            _orb_bar("2024-01-03 09:43", 100.31, 100.39, 100.24, 100.35),
            _orb_bar("2024-01-03 09:44", 100.35, 100.55, 100.30, 100.50),
        ]
    )

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "long"
    assert signal.reclaim_timestamp == bars[-1]["timestamp"]
    assert signal.report_fields["confirmation_start_timestamp"] == bars[10]["timestamp"]
    assert signal.report_fields["breakout_timestamp"] == pd.Timestamp("2024-01-03 09:45", tz="America/New_York")


def test_opening_range_breakout_entry_rejects_confirmation_close_at_noon():
    entry = OpeningRangeBreakoutEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 5,
            "bar_interval_minutes": 1,
            "last_entry_time": "12:00:00",
            "allow_long": True,
            "allow_short": True,
        }
    )
    bars = [
        _orb_bar("2024-01-03 09:30", 100.0, 100.20, 99.90, 100.10),
        _orb_bar("2024-01-03 09:31", 100.1, 100.30, 100.00, 100.20),
        _orb_bar("2024-01-03 09:32", 100.2, 100.40, 100.10, 100.25),
        _orb_bar("2024-01-03 09:33", 100.2, 100.25, 99.95, 100.05),
        _orb_bar("2024-01-03 09:34", 100.0, 100.35, 100.05, 100.20),
        _orb_bar("2024-01-03 11:55", 100.2, 100.45, 100.10, 100.42),
        _orb_bar("2024-01-03 11:56", 100.4, 100.50, 100.20, 100.43),
        _orb_bar("2024-01-03 11:57", 100.4, 100.55, 100.30, 100.45),
        _orb_bar("2024-01-03 11:58", 100.4, 100.60, 100.35, 100.46),
        _orb_bar("2024-01-03 11:59", 100.4, 100.65, 100.35, 100.50),
    ]

    signal = None
    for bar in bars:
        signal = entry.on_bar_close(bar)

    assert signal is None


def test_opening_range_breakout_entry_skips_tuesday_longs():
    entry = OpeningRangeBreakoutEntry({"skip_tuesday_longs": True})
    bars = _orb_long_breakout_bars("2024-01-02")

    signal = None
    for bar in bars:
        signal = entry.on_bar_close(bar)

    assert signal is None


def test_opening_range_breakout_entry_skips_wide_opening_range():
    entry = OpeningRangeBreakoutEntry({"max_opening_range_pct_of_open": 0.0055})
    bars = [
        _orb_bar("2024-01-03 09:30", 100.0, 100.30, 99.90, 100.10),
        _orb_bar("2024-01-03 09:31", 100.1, 100.50, 100.00, 100.20),
        _orb_bar("2024-01-03 09:32", 100.2, 100.20, 100.00, 100.10),
        _orb_bar("2024-01-03 09:33", 100.1, 100.30, 100.00, 100.20),
        _orb_bar("2024-01-03 09:34", 100.2, 100.40, 100.10, 100.30),
        _orb_bar("2024-01-03 09:35", 100.3, 100.60, 100.20, 100.50),
        _orb_bar("2024-01-03 09:36", 100.5, 100.70, 100.40, 100.60),
        _orb_bar("2024-01-03 09:37", 100.6, 100.70, 100.50, 100.65),
        _orb_bar("2024-01-03 09:38", 100.6, 100.80, 100.50, 100.70),
        _orb_bar("2024-01-03 09:39", 100.7, 100.90, 100.60, 100.80),
    ]

    signal = None
    for bar in bars:
        signal = entry.on_bar_close(bar)

    assert signal is None


def test_opening_range_inverse_breakout_entry_goes_long_on_close_below_low():
    entry = OpeningRangeInverseBreakoutEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 1,
            "bar_interval_minutes": 1,
            "max_opening_range_pct_of_open": 0.0055,
            "allow_long": True,
            "allow_short": True,
            "skip_tuesday_longs": False,
        }
    )
    bars = _orb_long_breakout_bars()[:5]
    bars.append(_orb_bar("2024-01-03 09:35", 100.0, 100.05, 99.75, 99.80))

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "long"
    assert signal.level_type == "opening_range_low_inverse"
    assert signal.swept_level == 99.90
    assert signal.opening_range_high == 100.40
    assert round(signal.opening_range_width, 2) == 0.50
    assert signal.metadata["confirmation_close"] == 99.80
    assert signal.report_fields["breakout_timestamp"] == pd.Timestamp("2024-01-03 09:36", tz="America/New_York")


def test_opening_range_inverse_breakout_entry_goes_short_on_close_above_high():
    entry = OpeningRangeInverseBreakoutEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 1,
            "bar_interval_minutes": 1,
            "max_opening_range_pct_of_open": 0.0055,
            "allow_long": True,
            "allow_short": True,
        }
    )
    bars = _orb_long_breakout_bars()[:5]
    bars.append(_orb_bar("2024-01-03 09:35", 100.40, 100.55, 100.30, 100.50))

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "short"
    assert signal.level_type == "opening_range_high_inverse"
    assert signal.swept_level == 100.40
    assert signal.opening_range_low == 99.90


def test_pdh_pdl_entry_module_emits_long_reclaim_signal():
    entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 2,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": True,
            "allow_short": False,
        }
    )
    bars = [
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.75,
                "high": 100.0,
                "close": 98.9,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=0,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:31", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.9,
                "high": 100.0,
                "close": 99.25,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=1,
        ),
    ]

    assert entry.on_bar_close(bars[0]) is None
    signal = entry.on_bar_close(bars[1])

    assert signal.direction == "long"
    assert signal.level_type == "previous_rth_low"
    assert signal.swept_level == 99.0


def test_pdh_pdl_entry_keeps_first_sweep_timestamp_and_tracks_extreme_until_reclaim():
    entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": True,
            "allow_short": False,
        }
    )
    bars = [
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.75,
                "high": 100.0,
                "close": 98.9,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=0,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:31", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.25,
                "high": 99.25,
                "close": 98.8,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=1,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:32", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.8,
                "high": 100.0,
                "close": 99.25,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=2,
        ),
    ]

    assert entry.on_bar_close(bars[0]) is None
    assert entry.on_bar_close(bars[1]) is None
    signal = entry.on_bar_close(bars[2])

    assert signal.sweep_timestamp == bars[0]["timestamp"]
    assert signal.sweep_low == 98.25
    assert signal.sweep_high == 100.0
    assert signal.reclaim_timestamp == bars[2]["timestamp"]


def test_pdh_pdl_entry_reclaim_window_counts_bars_between_sweep_and_reclaim():
    entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": True,
            "allow_short": False,
        }
    )
    bars = [
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.75,
                "high": 100.0,
                "close": 98.9,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=0,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:31", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.25,
                "high": 99.0,
                "close": 98.5,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=1,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:32", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.5,
                "high": 98.75,
                "close": 98.6,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=2,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:33", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.6,
                "high": 98.9,
                "close": 98.75,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=3,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:34", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.75,
                "high": 100.0,
                "close": 99.25,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=4,
        ),
    ]

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.sweep_timestamp == bars[0]["timestamp"]
    assert signal.sweep_low == 98.25
    assert signal.reclaim_timestamp == bars[-1]["timestamp"]


def test_pdh_pdl_entry_does_not_rearm_continuous_sweep_after_window_expires():
    entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": True,
            "allow_short": False,
        }
    )
    bars = [
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.75,
                "high": 100.0,
                "close": 98.8,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=0,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:31", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.5,
                "high": 99.0,
                "close": 98.7,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=1,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:32", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.25,
                "high": 98.75,
                "close": 98.6,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=2,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:33", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.0,
                "high": 98.75,
                "close": 98.5,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=3,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:34", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.1,
                "high": 98.75,
                "close": 98.6,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=4,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:35", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.5,
                "high": 100.0,
                "close": 99.25,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=5,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:36", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.75,
                "high": 99.0,
                "close": 98.8,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=6,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:37", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 99.0,
                "high": 100.0,
                "close": 99.25,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=7,
        ),
    ]

    for bar in bars[:6]:
        assert entry.on_bar_close(bar) is None
    assert entry.on_bar_close(bars[6]) is None
    signal = entry.on_bar_close(bars[7])

    assert signal.sweep_timestamp == bars[6]["timestamp"]
    assert signal.reclaim_timestamp == bars[7]["timestamp"]


def test_pdh_pdl_entry_allows_reclaim_on_sweep_bar():
    long_entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": True,
            "allow_short": False,
        }
    )
    long_sweep_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
            "session_date": "2024-01-02",
            "is_rth": True,
            "low": 98.75,
            "high": 100.0,
            "close": 99.25,
            "prev_rth_low": 99.0,
            "prev_rth_high": 101.0,
            "volume_ratio": 1.0,
        },
        name=0,
    )
    long_reclaim_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-02 08:31", tz="America/Chicago"),
            "session_date": "2024-01-02",
            "is_rth": True,
            "low": 99.1,
            "high": 100.0,
            "close": 99.5,
            "prev_rth_low": 99.0,
            "prev_rth_high": 101.0,
            "volume_ratio": 1.0,
        },
        name=1,
    )

    long_signal = long_entry.on_bar_close(long_sweep_bar)
    assert long_entry.on_bar_close(long_reclaim_bar) is None

    assert long_signal.direction == "long"
    assert long_signal.sweep_timestamp == long_sweep_bar["timestamp"]
    assert long_signal.reclaim_timestamp == long_sweep_bar["timestamp"]

    short_entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": False,
            "allow_short": True,
        }
    )
    short_sweep_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
            "session_date": "2024-01-02",
            "is_rth": True,
            "low": 100.0,
            "high": 101.25,
            "close": 100.75,
            "prev_rth_low": 99.0,
            "prev_rth_high": 101.0,
            "volume_ratio": 1.0,
        },
        name=0,
    )
    short_reclaim_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-02 08:31", tz="America/Chicago"),
            "session_date": "2024-01-02",
            "is_rth": True,
            "low": 100.0,
            "high": 100.9,
            "close": 100.5,
            "prev_rth_low": 99.0,
            "prev_rth_high": 101.0,
            "volume_ratio": 1.0,
        },
        name=1,
    )

    short_signal = short_entry.on_bar_close(short_sweep_bar)
    assert short_entry.on_bar_close(short_reclaim_bar) is None

    assert short_signal.direction == "short"
    assert short_signal.sweep_timestamp == short_sweep_bar["timestamp"]
    assert short_signal.reclaim_timestamp == short_sweep_bar["timestamp"]


def test_pdh_pdl_entry_requires_fresh_previous_rth_level():
    long_entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": True,
            "allow_short": False,
        }
    )
    stale_low_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
            "session_date": "2024-01-02",
            "is_rth": True,
            "low": 98.75,
            "high": 100.0,
            "close": 99.25,
            "prev_rth_low": 99.0,
            "prev_rth_high": 101.0,
            "prev_rth_low_fresh": False,
            "prev_rth_high_fresh": True,
            "volume_ratio": 1.0,
        },
        name=0,
    )

    assert long_entry.on_bar_close(stale_low_bar) is None

    short_entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": False,
            "allow_short": True,
        }
    )
    stale_high_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
            "session_date": "2024-01-02",
            "is_rth": True,
            "low": 100.0,
            "high": 101.25,
            "close": 100.75,
            "prev_rth_low": 99.0,
            "prev_rth_high": 101.0,
            "prev_rth_low_fresh": True,
            "prev_rth_high_fresh": False,
            "volume_ratio": 1.0,
        },
        name=0,
    )

    assert short_entry.on_bar_close(stale_high_bar) is None
