from types import SimpleNamespace

import pandas as pd

from propstack.strategy_modules.entry.pdh_pdl_sweep_reclaim import PdhPdlSweepReclaimEntry
from propstack.strategy_modules.sl.sweep_extreme import SweepExtremeStop
from propstack.strategy_modules.tp.fixed_r import FixedRTarget


def test_fixed_r_target_module_long_and_short():
    target = FixedRTarget({"target_r_multiple": 2.0})

    assert target.price(entry_price=100.0, stop_price=98.0, direction="long") == 104.0
    assert target.price(entry_price=100.0, stop_price=102.0, direction="short") == 96.0


def test_sweep_extreme_stop_module_long_and_short():
    stop = SweepExtremeStop({"stop_offset_ticks": 2})
    signal = SimpleNamespace(sweep_low=99.0, sweep_high=101.0)

    assert stop.price(signal, direction="long", tick_size=0.25) == 98.5
    assert stop.price(signal, direction="short", tick_size=0.25) == 101.5


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


def test_pdh_pdl_entry_does_not_reclaim_on_sweep_bar():
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

    assert long_entry.on_bar_close(long_sweep_bar) is None
    long_signal = long_entry.on_bar_close(long_reclaim_bar)

    assert long_signal.direction == "long"
    assert long_signal.sweep_timestamp == long_sweep_bar["timestamp"]
    assert long_signal.reclaim_timestamp == long_reclaim_bar["timestamp"]

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

    assert short_entry.on_bar_close(short_sweep_bar) is None
    short_signal = short_entry.on_bar_close(short_reclaim_bar)

    assert short_signal.direction == "short"
    assert short_signal.sweep_timestamp == short_sweep_bar["timestamp"]
    assert short_signal.reclaim_timestamp == short_reclaim_bar["timestamp"]
