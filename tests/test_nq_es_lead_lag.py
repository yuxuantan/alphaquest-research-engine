from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.nq_es_lead_lag import NqEsLeadLagEntry


def test_nq_es_lead_lag_entry_emits_long_on_completed_es_up_nq_lag():
    entry = NqEsLeadLagEntry(
        {
            "setup_mode": "es_up_nq_lag_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_es_return_bps": 8,
            "min_lead_gap_bps": 4,
        }
    )

    signal = entry.on_bar_close(_lead_lag_bar("2024-01-03 09:59", es_return=12.0, nq_return=4.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["leader_symbol"] == "ES"
    assert signal.report_fields["traded_symbol"] == "NQ"
    assert signal.report_fields["directional_lead_gap_bps"] == 8.0


def test_nq_es_lead_lag_entry_emits_short_on_completed_es_down_nq_lag():
    entry = NqEsLeadLagEntry(
        {
            "setup_mode": "es_down_nq_lag_short",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_es_return_bps": 8,
            "min_lead_gap_bps": 4,
        }
    )

    signal = entry.on_bar_close(_lead_lag_bar("2024-01-03 09:59", es_return=-12.0, nq_return=-4.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["directional_lead_gap_bps"] == 8.0


def test_nq_es_lead_lag_entry_requires_signal_bar_close_time():
    entry = NqEsLeadLagEntry(
        {
            "setup_mode": "two_sided_nq_lag_follow",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_es_return_bps": 8,
            "min_lead_gap_bps": 4,
        }
    )

    assert entry.on_bar_close(_lead_lag_bar("2024-01-03 09:58", es_return=12.0, nq_return=4.0)) is None


def test_nq_es_lead_lag_confirmed_mode_rejects_opposite_nq_move():
    entry = NqEsLeadLagEntry(
        {
            "setup_mode": "two_sided_confirmed_follow",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_es_return_bps": 8,
            "min_lead_gap_bps": 4,
        }
    )

    assert entry.on_bar_close(_lead_lag_bar("2024-01-03 09:59", es_return=12.0, nq_return=-4.0)) is None


def _lead_lag_bar(timestamp, *, es_return: float, nq_return: float):
    ts = pd.Timestamp(timestamp)
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
            "es_return_bps_30": es_return,
            "nq_return_bps_30": nq_return,
        }
    )
