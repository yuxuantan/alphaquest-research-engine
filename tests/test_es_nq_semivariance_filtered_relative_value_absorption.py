from pathlib import Path

import pandas as pd
import pytest

from alphaquest.strategy_modules.entry.es_nq_semivariance_filtered_relative_value_absorption import (
    EsNqSemivarianceFilteredRelativeValueAbsorptionEntry,
)


def test_semivariance_filter_allows_es_nq_absorption_signal_in_benign_regime(tmp_path):
    feature_csv = _feature_csv(tmp_path, rank=0.40)
    entry = EsNqSemivarianceFilteredRelativeValueAbsorptionEntry(
        _params(feature_csv, benign_rank_max=0.50)
    )

    signal = entry.on_bar_close(_bar("2024-01-03 10:29:00-05:00"))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:30:00-05:00")
    assert signal.report_fields["nq_minus_es_return_bps"] == 6.0
    assert signal.report_fields["semivariance_filter"] == "prior_session_benign_downside_semivariance"
    assert signal.report_fields["semivar_rank"] == 0.40
    assert signal.report_fields["benign_semivar_rank_max"] == 0.50
    assert signal.level_type.endswith("_low_semivariance_regime")


def test_semivariance_filter_blocks_absorption_signal_in_bad_vol_regime(tmp_path):
    feature_csv = _feature_csv(tmp_path, rank=0.80)
    entry = EsNqSemivarianceFilteredRelativeValueAbsorptionEntry(
        _params(feature_csv, benign_rank_max=0.50)
    )

    assert entry.on_bar_close(_bar("2024-01-03 10:29:00-05:00")) is None


def test_semivariance_filter_rejects_invalid_rank_cutoff(tmp_path):
    feature_csv = _feature_csv(tmp_path, rank=0.40)

    with pytest.raises(ValueError, match="benign_semivar_rank_max"):
        EsNqSemivarianceFilteredRelativeValueAbsorptionEntry(
            _params(feature_csv, benign_rank_max=0.0)
        )


def _params(feature_csv: Path, *, benign_rank_max: float) -> dict:
    return {
        "setup_mode": "two_sided_divergence_fade",
        "entry_time": "10:30:00",
        "start_time": "10:30:00",
        "end_time": "10:30:00",
        "flatten_time": "11:30:00",
        "bar_interval_minutes": 1,
        "lookback_minutes": 30,
        "orderflow_window_minutes": 30,
        "min_spread_bps": 3,
        "min_abs_es_return_bps": 0,
        "min_absorption_imbalance": 0.0,
        "stop_pct": 0.004,
        "target_r_multiple": 1.5,
        "feature_csv": str(feature_csv),
        "semivar_value_column": "prior_downside_semivariance_1d",
        "semivar_rank_column": "downside1_rank_252",
        "benign_semivar_rank_max": benign_rank_max,
    }


def _feature_csv(tmp_path: Path, *, rank: float) -> Path:
    path = tmp_path / "semivar.csv"
    path.write_text(
        "session_date,downside1_rank_252,prior_downside_semivariance_1d,prior_realized_variance,"
        "prior_upside_semivariance_1d,prior_downside_share_1d,prior_semivariance_balance_1d\n"
        f"2024-01-03,{rank},0.5,1.0,0.2,0.7,0.3\n",
        encoding="utf-8",
    )
    return path


def _bar(timestamp: str) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": True,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "es_return_bps_30": -5.0,
            "nq_return_bps_30": 1.0,
            "nq_minus_es_return_bps_30": 6.0,
            "es_signed_imbalance_30": 0.03,
        }
    )
