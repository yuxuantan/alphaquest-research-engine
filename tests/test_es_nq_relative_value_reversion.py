from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.es_nq_relative_value_reversion import EsNqRelativeValueReversionEntry


def test_es_nq_relative_value_reversion_emits_long_when_es_underperforms_nq():
    entry = EsNqRelativeValueReversionEntry(
        {
            "setup_mode": "two_sided_divergence_fade",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_spread_bps": 6,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", es_return=-8.0, nq_return=1.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["nq_minus_es_return_bps"] == 9.0


def test_es_nq_relative_value_reversion_emits_short_when_es_outperforms_nq():
    entry = EsNqRelativeValueReversionEntry(
        {
            "setup_mode": "two_sided_divergence_fade",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_spread_bps": 6,
        }
    )

    signal = entry.on_bar_close(_bar("2024-01-03 09:59", es_return=8.0, nq_return=-1.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["nq_minus_es_return_bps"] == -9.0


def test_es_nq_relative_value_reversion_rejects_plain_nq_follow_signal():
    entry = EsNqRelativeValueReversionEntry(
        {
            "setup_mode": "two_sided_divergence_fade",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_spread_bps": 6,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:59", es_return=4.0, nq_return=12.0)) is None


def test_es_nq_relative_value_reversion_requires_signal_bar_close_time():
    entry = EsNqRelativeValueReversionEntry(
        {
            "setup_mode": "two_sided_divergence_fade",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_spread_bps": 6,
        }
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:58", es_return=-8.0, nq_return=1.0)) is None


def test_es_nq_relative_value_reversion_honors_direction_modes():
    long_entry = EsNqRelativeValueReversionEntry(
        {
            "setup_mode": "es_underperform_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_spread_bps": 6,
        }
    )
    short_entry = EsNqRelativeValueReversionEntry(
        {
            "setup_mode": "es_outperform_short",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_spread_bps": 6,
        }
    )

    assert long_entry.on_bar_close(_bar("2024-01-03 09:59", es_return=8.0, nq_return=-1.0)) is None
    assert short_entry.on_bar_close(_bar("2024-01-03 09:59", es_return=-8.0, nq_return=1.0)) is None


def _bar(timestamp, *, es_return: float, nq_return: float):
    ts = pd.Timestamp(timestamp)
    lookback = 30
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": True,
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "volume": 1000,
            f"es_return_bps_{lookback}": es_return,
            f"nq_return_bps_{lookback}": nq_return,
            f"nq_minus_es_return_bps_{lookback}": nq_return - es_return,
        }
    )
