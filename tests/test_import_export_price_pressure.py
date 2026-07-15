from __future__ import annotations

import math

import pandas as pd
import pytest

from alphaquest.strategy_modules.entry.import_export_price_pressure import ImportExportPricePressureEntry
from tools.build_es_import_export_price_pressure_features import build_features


def test_core_import_relief_pullback_long_uses_completed_bar_and_flow(tmp_path):
    features = _feature_file(tmp_path, "2024-04-22", core_rank=0.18)
    entry = ImportExportPricePressureEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "core_import_relief_pullback_long",
            "macro_rank_max": 0.35,
            "min_session_return_bps": 2.0,
            "min_cumulative_flow": 100.0,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    assert entry.on_bar_close(_bar("2024-04-22 09:30", open_=5000, close=4999, signed_volume=40)) is None
    signal = entry.on_bar_close(_bar("2024-04-22 09:59", open_=4999, close=4998, signed_volume=90))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-04-22 10:00")
    assert signal.report_fields["macro_driver_column"] == "core_vs_headline_rank_120m"
    assert signal.report_fields["confirmation_mode"] == "long_pullback_absorption"
    assert signal.report_fields["cumulative_flow_to_signal"] == 130.0


def test_broad_import_pressure_short_requires_negative_flow_confirmation(tmp_path):
    features = _feature_file(tmp_path, "2024-04-22", import_rank=0.82)
    entry = ImportExportPricePressureEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "broad_import_pressure_short",
            "macro_rank_min": 0.65,
            "min_session_return_bps": 1.0,
            "min_cumulative_flow": 100.0,
            "entry_time": "10:00:00",
        }
    )

    assert entry.on_bar_close(_bar("2024-04-22 09:59", open_=5000, close=4999, signed_volume=90)) is None

    entry = ImportExportPricePressureEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "broad_import_pressure_short",
            "macro_rank_min": 0.65,
            "min_session_return_bps": 1.0,
            "min_cumulative_flow": 100.0,
            "entry_time": "10:00:00",
        }
    )
    signal = entry.on_bar_close(_bar("2024-04-22 09:59", open_=5000, close=4999, signed_volume=-150))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["macro_driver_column"] == "import_all_mom3_rank_120m"


def test_core_import_pressure_short_uses_core_vs_headline_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-04-22", import_rank=0.20, core_rank=0.86)
    entry = ImportExportPricePressureEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "core_import_pressure_short",
            "macro_rank_min": 0.80,
            "min_session_return_bps": 1.0,
            "min_cumulative_flow": 100.0,
            "entry_time": "10:00:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-04-22 09:59", open_=5000, close=4999, signed_volume=-150))
    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["macro_driver_column"] == "core_vs_headline_rank_120m"
    assert signal.report_fields["confirmation_mode"] == "short_weakness"


def test_target_r_multiple_below_one_rejected(tmp_path):
    features = _feature_file(tmp_path, "2024-04-22", import_rank=0.82)
    entry = ImportExportPricePressureEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "broad_import_pressure_short",
            "target_r_multiple": 0.75,
        }
    )
    with pytest.raises(ValueError, match="target_r_multiple must be >= 1.0"):
        entry.on_bar_close(_bar("2024-04-22 09:59", open_=5000, close=4999, signed_volume=-150))


def test_import_export_feature_builder_uses_conservative_monthly_availability(tmp_path):
    sessions = pd.date_range("2024-03-01", periods=90, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame([{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]).to_parquet(
        bars_path
    )
    months = pd.date_range("2022-01-01", "2024-05-01", freq="MS")
    import_all = tmp_path / "import_all.csv"
    import_exfuel = tmp_path / "import_exfuel.csv"
    export_all = tmp_path / "export_all.csv"
    _write_monthly(import_all, months, "IR", start=100.0)
    _write_monthly(import_exfuel, months, "IREXFUELS", start=99.0)
    _write_monthly(export_all, months, "IQ", start=101.0)
    out_path = tmp_path / "features.csv"

    features = build_features(
        bars_path,
        out_path,
        import_all_input=import_all,
        import_exfuel_input=import_exfuel,
        export_all_input=export_all,
        availability_lag_calendar_days_after_month=51,
        rank_min_periods=6,
    )

    early_april = features.loc[features["session_date"] == "2024-04-01"].iloc[0]
    late_april = features.loc[features["session_date"] == "2024-04-23"].iloc[0]
    assert early_april["observation_date"] == "2024-02-01"
    assert early_april["availability_date"] == "2024-03-23"
    assert late_april["observation_date"] == "2024-03-01"
    assert late_april["availability_date"] == "2024-04-21"
    assert math.isfinite(late_april["import_all_mom3_rank_120m"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    import_rank: float = 0.5,
    core_rank: float = 0.5,
    export_rank: float = 0.5,
    terms_rank: float = 0.5,
):
    path = tmp_path / "import_export.csv"
    path.write_text(
        "session_date,observation_date,availability_date,availability_lag_calendar_days_after_month,"
        "import_all_index,import_exfuel_index,export_all_index,import_all_mom1,import_all_mom3,"
        "import_exfuel_mom1,import_exfuel_mom3,export_all_mom1,export_all_mom3,"
        "core_vs_headline_mom3,import_vs_export_mom3,import_all_mom3_rank_120m,"
        "import_exfuel_mom3_rank_120m,export_all_mom3_rank_120m,core_vs_headline_rank_120m,"
        "import_vs_export_rank_120m\n"
        f"{session_date},2024-02-01,2024-03-23,51,140.0,130.0,150.0,0.01,0.03,"
        f"0.005,0.01,0.02,0.04,-0.02,-0.01,{import_rank},0.4,{export_rank},{core_rank},{terms_rank}\n",
        encoding="utf-8",
    )
    return path


def _write_monthly(path, months, value_name: str, *, start: float):
    rows = [
        {
            "observation_date": month.strftime("%Y-%m-%d"),
            value_name: start + index * 0.2,
        }
        for index, month in enumerate(months)
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def _bar(timestamp, *, open_: float, close: float, signed_volume: float, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": open_,
            "high": max(open_, close) + 0.25,
            "low": min(open_, close) - 0.25,
            "close": close,
            "volume": 1000,
            "signed_volume": signed_volume,
            "large10_signed_volume": signed_volume,
            "large20_signed_volume": signed_volume,
        }
    )
