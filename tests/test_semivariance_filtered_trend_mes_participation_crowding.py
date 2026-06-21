from pathlib import Path

import pandas as pd
import pytest

from propstack.strategy_modules.entry.semivariance_filtered_trend_mes_participation_crowding import (
    SemivarianceFilteredTrendMesParticipationCrowdingEntry,
)


def test_high_semivariance_mes_trend_pullback_emits_next_bar_long(tmp_path):
    entry = SemivarianceFilteredTrendMesParticipationCrowdingEntry(
        _params(_feature_csv(tmp_path, rank=0.70))
    )

    assert entry.on_bar_close(_bar("2024-01-03 09:44:00", close=100.0)) is None
    assert entry.on_bar_close(_bar("2024-01-03 10:14:00", close=102.0)) is None
    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:29:00",
            close=101.0,
            es_return_ticks_15=-4.0,
            mes_trade_rank_15=0.70,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:30:00")
    assert signal.report_fields["trend_return_ticks"] == 8.0
    assert signal.report_fields["semivar_rank"] == 0.70
    assert signal.report_fields["semivar_rank_min"] == 0.60
    assert signal.report_fields["intended_entry_timestamp"] == pd.Timestamp("2024-01-03 10:30:00")


def test_high_semivariance_mes_trend_pullback_blocks_low_semivariance_rank(tmp_path):
    entry = SemivarianceFilteredTrendMesParticipationCrowdingEntry(
        _params(_feature_csv(tmp_path, rank=0.40))
    )

    entry.on_bar_close(_bar("2024-01-03 09:44:00", close=100.0))
    entry.on_bar_close(_bar("2024-01-03 10:14:00", close=102.0))

    assert (
        entry.on_bar_close(
            _bar(
                "2024-01-03 10:29:00",
                close=101.0,
                es_return_ticks_15=-4.0,
                mes_trade_rank_15=0.70,
            )
        )
        is None
    )


def test_high_semivariance_mes_trend_pullback_rejects_invalid_semivar_cutoff(tmp_path):
    params = _params(_feature_csv(tmp_path, rank=0.70))
    params["semivar_rank_min"] = 1.1

    with pytest.raises(ValueError, match="semivar_rank_min"):
        SemivarianceFilteredTrendMesParticipationCrowdingEntry(params)


def _params(feature_csv: Path) -> dict:
    return {
        "setup_mode": "test_high_semivariance_mes_pullback",
        "signal_mode": "first_signal_in_window",
        "start_time": "10:00:00",
        "end_time": "11:30:00",
        "entry_time": "10:30:00",
        "flatten_time": "12:00:00",
        "bar_interval_minutes": 1,
        "lookback_minutes": 15,
        "trend_lookback_minutes": 30,
        "rank_window": 252,
        "share_mode": "trade",
        "direction": "both",
        "share_rank_min": 0.50,
        "min_abs_return_ticks": 4,
        "min_trend_return_ticks": 4,
        "feature_csv": str(feature_csv),
        "semivar_value_column": "prior_downside_semivariance_1d",
        "semivar_rank_column": "downside1_rank_252",
        "semivar_rank_min": 0.60,
        "max_trades_per_day": 1,
        "stop_pct": 0.003,
        "target_r_multiple": 1.5,
        "tick_size": 0.25,
    }


def _feature_csv(tmp_path: Path, *, rank: float) -> Path:
    path = tmp_path / "semivar.csv"
    path.write_text(
        "session_date,downside1_rank_252,prior_downside_semivariance_1d\n"
        f"2024-01-03,{rank},0.5\n",
        encoding="utf-8",
    )
    return path


def _bar(
    timestamp: str,
    *,
    close: float,
    es_return_ticks_15: float | None = None,
    mes_trade_rank_15: float | None = None,
) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": True,
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "es_return_ticks_15": es_return_ticks_15,
            "mes_trade_share_15": 0.10 if mes_trade_rank_15 is not None else None,
            "mes_trade_share_15_rank252": mes_trade_rank_15,
        }
    )
