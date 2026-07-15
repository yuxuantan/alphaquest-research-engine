from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry import ENTRY_MODULES
from alphaquest.strategy_modules.entry.nq_manufacturing_orders_state import (
    NqManufacturingOrdersStateEntry,
)
from tools.build_nq_manufacturing_orders_state_features import build_features


def test_entry_module_is_registered():
    assert ENTRY_MODULES["nq_manufacturing_orders_state"] is NqManufacturingOrdersStateEntry


def test_total_orders_strength_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", total_orders_3m_rank=0.72)
    entry = NqManufacturingOrdersStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "total_orders_3m_strength_long",
            "rank_min": 0.60,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-04-03 09:58", close=18000.0)) is None
    signal = entry.on_bar_close(_bar("2024-04-03 09:59", close=18010.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-03 10:00")
    assert signal.report_fields["manufacturing_orders_driver_column"] == (
        "total_orders_change_3m_rank_120m"
    )
    assert "45 calendar days" in signal.report_fields["availability_rule"]


def test_total_orders_weakness_short_respects_rank_max(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", total_orders_3m_rank=0.48)
    entry = NqManufacturingOrdersStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "total_orders_3m_weakness_short",
            "rank_max": 0.40,
            "entry_time": "10:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-04-03 10:29", close=18010.0)) is None

    features = _feature_file(tmp_path, "2024-04-04", total_orders_3m_rank=0.22, name="weak.csv")
    entry = NqManufacturingOrdersStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "total_orders_3m_weakness_short",
            "rank_max": 0.40,
            "entry_time": "10:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-04 10:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"


def test_core_capgoods_strength_uses_core_capgoods_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", core_capgoods_3m_rank=0.82)
    entry = NqManufacturingOrdersStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "core_capgoods_3m_strength_long",
            "rank_min": 0.60,
            "entry_time": "11:30:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 11:29", close=18010.0))
    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["manufacturing_orders_driver_column"] == (
        "core_capgoods_orders_change_3m_rank_120m"
    )


def test_durables_weakness_short_uses_one_month_durables_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-03", durable_goods_1m_rank=0.18)
    entry = NqManufacturingOrdersStateEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "durables_1m_weakness_short",
            "rank_max": 0.35,
            "entry_time": "12:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-03 11:59", close=18010.0))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["manufacturing_orders_driver_column"] == (
        "durable_goods_orders_change_1m_rank_120m"
    )


def test_builder_uses_monthly_observations_at_least_45_calendar_days_old(tmp_path):
    sessions = pd.date_range("2024-03-18", periods=85, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame(
        [{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]
    ).to_parquet(bars_path)

    cache_dir = tmp_path / "fred"
    months = pd.date_range("2017-01-01", "2024-06-01", freq="MS")
    _write_fred_csv(cache_dir / "fred_amtmno_monthly.csv", "AMTMNO", months, 520000.0)
    _write_fred_csv(cache_dir / "fred_dgorder_monthly.csv", "DGORDER", months, 260000.0)
    _write_fred_csv(cache_dir / "fred_neworder_monthly.csv", "NEWORDER", months, 72000.0)
    _write_fred_csv(cache_dir / "fred_amxtno_monthly.csv", "AMXTNO", months, 410000.0)

    out_path = tmp_path / "features.csv"
    features = build_features(
        bars_path,
        out_path,
        cache_dir=cache_dir,
        availability_lag_days=45,
        rank_min_periods=6,
        start_session="2024-03-18",
    )

    first = features.loc[features["session_date"] == "2024-03-18"].iloc[0]
    later = features.loc[features["session_date"] == sessions[60].strftime("%Y-%m-%d")].iloc[0]
    assert first["observation_date"] == "2024-02-01"
    assert math.isfinite(later["total_orders_change_3m_rank_120m"])
    assert math.isfinite(later["durable_goods_orders_change_1m_rank_120m"])
    assert math.isfinite(later["core_capgoods_orders_change_3m_rank_120m"])
    assert math.isfinite(later["ex_transport_orders_change_3m_rank_120m"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    total_orders_3m_rank: float = 0.5,
    durable_goods_1m_rank: float = 0.5,
    core_capgoods_3m_rank: float = 0.5,
    ex_transport_3m_rank: float = 0.5,
    name: str = "manufacturing.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_cutoff,observation_date,availability_lag_days,"
        "total_orders,durable_goods_orders,core_capgoods_orders,ex_transport_orders,"
        "total_orders_change_1m,total_orders_change_3m,durable_goods_orders_change_1m,"
        "durable_goods_orders_change_3m,core_capgoods_orders_change_1m,"
        "core_capgoods_orders_change_3m,ex_transport_orders_change_1m,"
        "ex_transport_orders_change_3m,total_orders_change_1m_rank_120m,"
        "total_orders_change_3m_rank_120m,durable_goods_orders_change_1m_rank_120m,"
        "durable_goods_orders_change_3m_rank_120m,core_capgoods_orders_change_1m_rank_120m,"
        "core_capgoods_orders_change_3m_rank_120m,ex_transport_orders_change_1m_rank_120m,"
        "ex_transport_orders_change_3m_rank_120m\n"
        f"{session_date},2024-02-18,2024-02-01,45,520000,260000,72000,410000,"
        f"0.01,0.03,0.01,0.03,0.01,0.03,0.01,0.03,0.5,{total_orders_3m_rank},"
        f"{durable_goods_1m_rank},0.5,0.5,{core_capgoods_3m_rank},0.5,"
        f"{ex_transport_3m_rank}\n",
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


def _write_fred_csv(path, series_id: str, dates, start_value: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["observation_date," + series_id]
    for index, day in enumerate(dates):
        value = start_value + index * 0.1
        lines.append(f"{day:%Y-%m-%d},{value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
