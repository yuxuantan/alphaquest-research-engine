from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.oil_price_shock_spillover import OilPriceShockSpilloverEntry
from tools.build_es_oil_price_shock_features import build_features


def test_wti_down_entry_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-03-20", wti_rank=0.18)
    entry = OilPriceShockSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "wti_down_long",
            "oil_return_rank_max": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-03-20 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-03-20 10:00")
    assert signal.report_fields["oil_driver_column"] == "wti_return_1d_rank_252"
    assert signal.report_fields["feature_session_date"] == "2024-03-20"


def test_brent_up_entry_emits_short(tmp_path):
    features = _feature_file(tmp_path, "2024-03-20", brent_rank=0.82)
    entry = OilPriceShockSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "brent_up_short",
            "oil_return_rank_min": 0.65,
            "entry_time": "11:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-03-20 11:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["oil_driver_column"] == "brent_return_1d_rank_252"


def test_oil_vol_shock_requires_abs_rank_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-03-20", abs_rank=0.55)
    entry = OilPriceShockSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "oil_vol_shock_short",
            "oil_abs_rank_min": 0.65,
            "entry_time": "12:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-03-20 11:59", close=4801.0)) is None

    features = _feature_file(tmp_path, "2024-03-21", abs_rank=0.82, name="abs.csv")
    entry = OilPriceShockSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "oil_vol_shock_short",
            "oil_abs_rank_min": 0.65,
            "entry_time": "12:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-03-21 11:59", close=4801.0)) is not None


def test_oil_feature_builder_uses_configured_business_day_lag(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=90, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame([{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]).to_parquet(
        bars_path
    )
    oil_dates = pd.date_range("2023-08-01", "2024-05-31", freq="B")
    wti_path = tmp_path / "wti.csv"
    brent_path = tmp_path / "brent.csv"
    _write_oil_csv(wti_path, oil_dates, "wti_spot", start_price=70.0)
    _write_oil_csv(brent_path, oil_dates, "brent_spot", start_price=75.0)
    out_path = tmp_path / "features.csv"

    features = build_features(
        bars_path,
        out_path,
        wti_input=wti_path,
        brent_input=brent_path,
        availability_lag_business_days=2,
        rank_min_periods=10,
    )

    third = features.loc[features["session_date"] == sessions[2].strftime("%Y-%m-%d")].iloc[0]
    later = features.loc[features["session_date"] == sessions[30].strftime("%Y-%m-%d")].iloc[0]
    assert third["availability_cutoff"] == sessions[0].strftime("%Y-%m-%d")
    assert third["observation_date"] == sessions[0].strftime("%Y-%m-%d")
    assert math.isfinite(later["wti_return_1d_rank_252"])
    assert math.isfinite(later["brent_wti_spread_change_1d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    wti_rank: float = 0.5,
    brent_rank: float = 0.5,
    abs_rank: float = 0.5,
    spread_rank: float = 0.5,
    name: str = "oil.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,availability_cutoff,availability_lag_business_days,"
        "wti_spot,brent_spot,wti_return_1d,brent_return_1d,wti_return_5d,brent_return_5d,"
        "oil_composite_return_1d,oil_abs_return_1d,brent_wti_spread,"
        "brent_wti_spread_change_1d,wti_return_1d_rank_252,brent_return_1d_rank_252,"
        "wti_return_5d_rank_252,brent_return_5d_rank_252,"
        "oil_composite_return_1d_rank_252,oil_abs_return_1d_rank_252,"
        "brent_wti_spread_change_1d_rank_252\n"
        f"{session_date},2024-03-18,2024-03-18,2,80.0,84.0,-0.02,0.01,-0.04,0.02,"
        f"-0.005,0.015,4.0,0.5,{wti_rank},{brent_rank},0.4,0.6,0.5,{abs_rank},{spread_rank}\n",
        encoding="utf-8",
    )
    return path


def _write_oil_csv(path, dates, value_name: str, *, start_price: float):
    rows = [
        {
            "observation_date": day.strftime("%Y-%m-%d"),
            value_name: start_price + index * 0.1,
        }
        for index, day in enumerate(dates)
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def _bar(timestamp, *, close: float, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": close - 0.5,
            "high": close + 0.25,
            "low": close - 0.25,
            "close": close,
            "volume": 1000,
        }
    )
