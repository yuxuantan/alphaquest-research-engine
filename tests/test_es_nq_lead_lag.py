from __future__ import annotations

import pandas as pd
import pytest

from alphaquest.data.es_nq_lead_lag import build_es_nq_lead_lag_cache
from alphaquest.strategy_modules.entry.es_nq_lead_lag import EsNqLeadLagEntry


def test_build_es_nq_lead_lag_cache_uses_completed_aligned_windows(tmp_path):
    es_path = tmp_path / "es.parquet"
    nq_path = tmp_path / "nq.parquet"
    _write_cache(es_path, "ES", [100.0, 100.25, 100.5], [100.25, 100.5, 101.0])
    _write_cache(nq_path, "NQ", [200.0, 200.5, 300.0], [201.0, 202.0, 301.0])

    out = build_es_nq_lead_lag_cache(
        es_path=es_path,
        nq_path=nq_path,
        windows=[2],
    )

    assert len(out) == 3
    assert pd.isna(out.loc[0, "nq_return_bps_2"])
    assert out.loc[1, "es_return_bps_2"] == pytest.approx(50.0)
    assert out.loc[1, "nq_return_bps_2"] == pytest.approx(100.0)
    assert out.loc[1, "nq_minus_es_return_bps_2"] == pytest.approx(50.0)


def test_es_nq_lead_lag_entry_emits_long_on_completed_nq_up_es_lag():
    entry = EsNqLeadLagEntry(
        {
            "setup_mode": "nq_up_es_lag_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_nq_return_bps": 8,
            "min_lead_gap_bps": 4,
        }
    )

    signal = entry.on_bar_close(_lead_lag_bar("2024-01-03 09:59", nq_return=12.0, es_return=4.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["directional_lead_gap_bps"] == 8.0


def test_es_nq_lead_lag_entry_emits_short_on_completed_nq_down_es_lag():
    entry = EsNqLeadLagEntry(
        {
            "setup_mode": "nq_down_es_lag_short",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_nq_return_bps": 8,
            "min_lead_gap_bps": 4,
        }
    )

    signal = entry.on_bar_close(_lead_lag_bar("2024-01-03 09:59", nq_return=-12.0, es_return=-4.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["directional_lead_gap_bps"] == 8.0


def test_es_nq_lead_lag_entry_requires_signal_bar_close_time():
    entry = EsNqLeadLagEntry(
        {
            "setup_mode": "two_sided_es_lag_follow",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_nq_return_bps": 8,
            "min_lead_gap_bps": 4,
        }
    )

    assert entry.on_bar_close(_lead_lag_bar("2024-01-03 09:58", nq_return=12.0, es_return=4.0)) is None


def test_es_nq_lead_lag_confirmed_mode_rejects_opposite_es_move():
    entry = EsNqLeadLagEntry(
        {
            "setup_mode": "two_sided_confirmed_follow",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_nq_return_bps": 8,
            "min_lead_gap_bps": 4,
        }
    )

    assert entry.on_bar_close(_lead_lag_bar("2024-01-03 09:59", nq_return=12.0, es_return=-4.0)) is None


def _write_cache(path, symbol: str, opens: list[float], closes: list[float]) -> None:
    rows = []
    for index, (open_price, close_price) in enumerate(zip(opens, closes, strict=True)):
        timestamp = pd.Timestamp("2024-01-03 09:30") + pd.Timedelta(minutes=index)
        rows.append(
            {
                "timestamp": timestamp,
                "symbol": symbol,
                "open": open_price,
                "high": max(open_price, close_price) + 0.25,
                "low": min(open_price, close_price) - 0.25,
                "close": close_price,
                "volume": 1000,
                "signed_volume": 100 if close_price >= open_price else -100,
            }
        )
    pd.DataFrame(rows).to_parquet(path, index=False)


def _lead_lag_bar(timestamp, *, nq_return: float, es_return: float):
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
            "nq_return_bps_30": nq_return,
            "es_return_bps_30": es_return,
        }
    )
