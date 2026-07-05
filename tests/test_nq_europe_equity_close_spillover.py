from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry import ENTRY_MODULES
from propstack.strategy_modules.entry.nq_europe_equity_close_spillover import (
    NqEuropeEquityCloseSpilloverEntry,
)
from tools.build_nq_europe_equity_close_spillover_features import build_features


def test_entry_module_is_registered():
    assert (
        ENTRY_MODULES["nq_europe_equity_close_spillover"]
        is NqEuropeEquityCloseSpilloverEntry
    )


def test_dax_strength_emits_long_only_after_availability_time(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", dax_rank=0.78)
    entry = NqEuropeEquityCloseSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "dax_1d_strength_long",
            "rank_min": 0.65,
            "entry_time": "13:30:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-04-03 13:28", close=18000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-03 13:29", close=18010.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-03 13:30")
    assert signal.report_fields["availability_time_et"] == "13:30:00"


def test_same_day_europe_close_required(tmp_path):
    features = _feature_file(
        tmp_path, "2024-04-03", dax_rank=0.78, same_day_available=False
    )
    entry = NqEuropeEquityCloseSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "dax_1d_strength_long",
            "rank_min": 0.65,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 13:29", close=18010.0)) is None


def test_broad_weakness_requires_both_european_indexes(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", dax_rank=0.25, stoxx_rank=0.55)
    entry = NqEuropeEquityCloseSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "europe_broad_weakness_short",
            "rank_max": 0.40,
            "entry_time": "15:00:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 14:59", close=18010.0)) is None

    features = _feature_file(
        tmp_path,
        "2024-04-04",
        dax_rank=0.25,
        stoxx_rank=0.35,
        name="broad.csv",
    )
    entry = NqEuropeEquityCloseSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "europe_broad_weakness_short",
            "rank_max": 0.40,
            "entry_time": "15:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 14:59", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"


def test_rejects_entry_before_conservative_europe_close_availability(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", dax_rank=0.78)
    entry = NqEuropeEquityCloseSpilloverEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "dax_1d_strength_long",
            "entry_time": "12:30:00",
        }
    )
    try:
        entry.on_bar_close(_bar("2024-04-03 12:29", close=18010.0))
    except ValueError as exc:
        assert "13:30:00" in str(exc)
    else:
        raise AssertionError("Expected entry_time validation failure.")


def test_builder_requires_same_day_index_observation(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=95, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "yahoo"
    daily_dates = pd.date_range("2023-08-01", "2024-05-31", freq="B")
    _write_yahoo_csv(
        cache_dir / "yahoo_gdaxi_daily_2023-08-01_2024-05-31.csv",
        daily_dates,
        start_price=16000.0,
    )
    stoxx_dates = daily_dates[daily_dates != pd.Timestamp("2024-01-03")]
    _write_yahoo_csv(
        cache_dir / "yahoo_stoxx50e_daily_2023-08-01_2024-05-31.csv",
        stoxx_dates,
        start_price=4300.0,
    )

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        rank_min_periods=10,
        yahoo_start_date="2023-08-01",
        yahoo_end_date="2024-05-31",
    )

    missing = features.loc[features["session_date"] == "2024-01-03"].iloc[0]
    later = features.loc[features["session_date"] == sessions[20].strftime("%Y-%m-%d")].iloc[0]
    assert not bool(missing["same_day_europe_close_available"])
    assert math.isfinite(later["dax_return_1d_rank_252"])
    assert math.isfinite(later["stoxx50_return_1d_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    dax_rank: float = 0.5,
    stoxx_rank: float = 0.5,
    same_day_available: bool = True,
    name: str = "europe.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,availability_time_et,same_day_europe_close_available,"
        "dax,stoxx50,dax_return_1d,dax_return_3d,stoxx50_return_1d,stoxx50_return_3d,"
        "europe_composite_return_1d,europe_composite_return_3d,europe_abs_return_1d,"
        "dax_return_1d_rank_252,dax_return_3d_rank_252,stoxx50_return_1d_rank_252,"
        "stoxx50_return_3d_rank_252,europe_composite_return_1d_rank_252,"
        "europe_composite_return_3d_rank_252,europe_abs_return_1d_rank_252\n"
        f"{session_date},{session_date},13:30:00,{same_day_available},"
        "18000,5000,0.01,0.02,-0.003,-0.001,0.0035,0.009,0.0065,"
        f"{dax_rank},0.5,{stoxx_rank},0.5,0.5,0.5,0.5\n",
        encoding="utf-8",
    )
    return path


def _bar(timestamp: str, *, close: float, is_rth: bool = True) -> pd.Series:
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": close - 5.0,
            "high": close + 10.0,
            "low": close - 10.0,
            "close": close,
        }
    )


def _write_yahoo_csv(path, dates, *, start_price: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["Date,Open,High,Low,Close,Volume,Adj Close"]
    for index, day in enumerate(dates):
        price = start_price + index * 0.25
        lines.append(f"{day:%Y-%m-%d},{price},{price},{price},{price},0,{price}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
