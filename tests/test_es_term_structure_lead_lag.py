from __future__ import annotations

import pandas as pd
import pytest

from propstack.data.es_term_structure_lead_lag import build_es_term_structure_lead_lag_frame
from propstack.strategy_modules.entry.es_term_structure_lead_lag import EsTermStructureLeadLagEntry


def test_build_es_term_structure_features_use_completed_aligned_windows():
    front = _bars("ESH24", [100.0, 100.0, 100.5], [100.0, 101.0, 101.5])
    deferred = _bars("ESM24", [100.0, 100.0, 100.25], [100.0, 100.5, 100.75])

    out = build_es_term_structure_lead_lag_frame(front, deferred, windows=[2])

    assert len(out) == 3
    assert pd.isna(out.loc[0, "front_return_bps_2"])
    assert out.loc[1, "front_return_bps_2"] == pytest.approx(100.0)
    assert out.loc[1, "deferred_return_bps_2"] == pytest.approx(50.0)
    assert out.loc[1, "front_minus_deferred_return_bps_2"] == pytest.approx(50.0)


def test_term_structure_entry_emits_short_after_front_premium_dislocation():
    entry = EsTermStructureLeadLagEntry(
        {
            "setup_mode": "front_premium_reversion_short",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_front_return_bps": 8,
            "min_spread_gap_bps": 3,
        }
    )

    signal = entry.on_bar_close(_term_structure_bar("2024-01-03 09:59", front_return=12.0, deferred_return=5.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00")
    assert signal.report_fields["front_minus_deferred_return_bps"] == 7.0


def test_term_structure_entry_emits_long_after_front_discount_dislocation():
    entry = EsTermStructureLeadLagEntry(
        {
            "setup_mode": "front_discount_reversion_long",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_front_return_bps": 8,
            "min_spread_gap_bps": 3,
        }
    )

    signal = entry.on_bar_close(_term_structure_bar("2024-01-03 09:59", front_return=-12.0, deferred_return=-5.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["deferred_minus_front_return_bps"] == 7.0


def test_term_structure_entry_requires_configured_completed_bar_close():
    entry = EsTermStructureLeadLagEntry(
        {
            "setup_mode": "two_sided_spread_feedback",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_front_return_bps": 8,
            "min_spread_gap_bps": 3,
        }
    )

    assert entry.on_bar_close(_term_structure_bar("2024-01-03 09:58", front_return=12.0, deferred_return=5.0)) is None


def test_term_structure_confirmed_feedback_requires_same_sign_deferred_move():
    entry = EsTermStructureLeadLagEntry(
        {
            "setup_mode": "two_sided_confirmed_feedback",
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
            "lookback_minutes": 30,
            "min_front_return_bps": 8,
            "min_spread_gap_bps": 3,
        }
    )

    assert entry.on_bar_close(_term_structure_bar("2024-01-03 09:59", front_return=12.0, deferred_return=-1.0)) is None


def _bars(contract_symbol: str, opens: list[float], closes: list[float]) -> pd.DataFrame:
    rows = []
    for index, (open_price, close_price) in enumerate(zip(opens, closes, strict=True)):
        timestamp = pd.Timestamp("2024-01-03 09:30") + pd.Timedelta(minutes=index)
        rows.append(
            {
                "timestamp": timestamp,
                "symbol": "ES",
                "contract_symbol": contract_symbol,
                "open": open_price,
                "high": max(open_price, close_price) + 0.25,
                "low": min(open_price, close_price) - 0.25,
                "close": close_price,
                "volume": 1000,
            }
        )
    return pd.DataFrame(rows)


def _term_structure_bar(timestamp, *, front_return: float, deferred_return: float) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    front_minus_deferred = front_return - deferred_return
    deferred_minus_front = deferred_return - front_return
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": True,
            "contract_symbol": "ESH24",
            "deferred_contract_symbol": "ESM24",
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 100.5,
            "volume": 1000,
            "front_return_bps_30": front_return,
            "deferred_return_bps_30": deferred_return,
            "front_minus_deferred_return_bps_30": front_minus_deferred,
            "deferred_minus_front_return_bps_30": deferred_minus_front,
            "calendar_spread_change_points_30": 0.5,
        }
    )
