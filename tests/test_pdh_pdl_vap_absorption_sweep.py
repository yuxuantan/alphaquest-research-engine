from __future__ import annotations

import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.data.timeframe import aggregate_timeframe
from propstack.strategy_modules.entry.pdh_pdl_vap_absorption_sweep import (
    PdhPdlVapAbsorptionSweepEntry,
)
from tools.build_es_pdh_pdl_vap_absorption_sweep_cache import (
    _profile_from_cum_volume,
    intrabar_vap_absorption_features,
)


def _feature_bar(timestamp: str, **overrides) -> pd.Series:
    values = {
        "timestamp": pd.Timestamp(timestamp),
        "session_date": pd.Timestamp(timestamp).date(),
        "is_rth": True,
        "open": 101.75,
        "high": 102.25,
        "low": 101.25,
        "close": 101.75,
        "volume": 1000,
        "prev_rth_high": 102.0,
        "prev_rth_low": 98.0,
        "intrabar_short_release_price": 101.75,
        "intrabar_short_release_offset_seconds": 60.0,
        "intrabar_short_delta": 325.0,
        "intrabar_short_delta_zone_low": 102.0,
        "intrabar_short_delta_zone_high": 102.75,
        "intrabar_short_session_open": 100.0,
        "intrabar_short_session_high": 102.50,
        "intrabar_short_session_low": 98.0,
        "intrabar_short_session_range_pct": 0.045,
        "intrabar_short_vap_poc": 101.75,
        "intrabar_short_vap_vah": 101.75,
        "intrabar_short_vap_val": 100.25,
        "intrabar_short_vap_no_lvn_between_value_area": 1.0,
        "intrabar_long_release_price": pd.NA,
        "intrabar_long_release_offset_seconds": pd.NA,
        "intrabar_long_delta": pd.NA,
        "intrabar_long_delta_zone_low": pd.NA,
        "intrabar_long_delta_zone_high": pd.NA,
        "intrabar_long_session_open": pd.NA,
        "intrabar_long_session_high": pd.NA,
        "intrabar_long_session_low": pd.NA,
        "intrabar_long_session_range_pct": pd.NA,
        "intrabar_long_vap_poc": pd.NA,
        "intrabar_long_vap_vah": pd.NA,
        "intrabar_long_vap_val": pd.NA,
        "intrabar_long_vap_no_lvn_between_value_area": pd.NA,
    }
    values.update(overrides)
    return pd.Series(values)


def _entry() -> PdhPdlVapAbsorptionSweepEntry:
    entry = PdhPdlVapAbsorptionSweepEntry(
        {
            "start_time": "09:30:00",
            "end_time": "11:30:00",
            "bar_interval_minutes": 3,
            "min_pivots": 3,
            "min_range_pct": 0.002,
            "max_vap_distance_pct": 0.0005,
            "min_absorption_delta": 300,
        }
    )
    for bar in [
        _feature_bar("2024-01-03 09:30:00", high=100.0, low=99.0),
        _feature_bar("2024-01-03 09:33:00", high=102.0, low=100.0),
        _feature_bar("2024-01-03 09:36:00", high=101.0, low=98.0),
        _feature_bar("2024-01-03 09:39:00", high=103.0, low=99.0),
        _feature_bar("2024-01-03 09:42:00", high=102.0, low=100.0),
    ]:
        entry.on_bar_close(bar)
    return entry


def test_intrabar_feature_builder_detects_failed_positive_and_negative_delta_release():
    prints = pd.DataFrame(
        [
            {"timestamp": "2024-01-03 09:45:00", "price": 100.00, "volume": 100, "signed_volume": 0},
            {"timestamp": "2024-01-03 09:45:01", "price": 102.00, "volume": 150, "signed_volume": 110},
            {"timestamp": "2024-01-03 09:45:02", "price": 102.25, "volume": 150, "signed_volume": 110},
            {"timestamp": "2024-01-03 09:45:03", "price": 102.50, "volume": 150, "signed_volume": 110},
            {"timestamp": "2024-01-03 09:45:09", "price": 101.50, "volume": 100, "signed_volume": 0},
            {"timestamp": "2024-01-03 09:48:00", "price": 100.00, "volume": 100, "signed_volume": 0},
            {"timestamp": "2024-01-03 09:48:01", "price": 98.00, "volume": 150, "signed_volume": -110},
            {"timestamp": "2024-01-03 09:48:02", "price": 97.75, "volume": 150, "signed_volume": -110},
            {"timestamp": "2024-01-03 09:48:03", "price": 97.50, "volume": 150, "signed_volume": -110},
            {"timestamp": "2024-01-03 09:48:09", "price": 98.50, "volume": 100, "signed_volume": 0},
        ]
    )

    out = intrabar_vap_absorption_features(
        prints,
        bar_minutes=3,
        tick_size=0.25,
        delta_threshold=300,
        release_seconds=5,
        value_area_fraction=0.70,
        lvn_poc_fraction=0.30,
    )

    short_row = out.loc[out["timestamp"] == pd.Timestamp("2024-01-03 09:45:00")].iloc[0]
    long_row = out.loc[out["timestamp"] == pd.Timestamp("2024-01-03 09:48:00")].iloc[0]
    assert short_row["intrabar_short_release_price"] == 101.50
    assert short_row["intrabar_short_delta"] >= 300
    assert short_row["intrabar_short_release_offset_seconds"] == 9.0
    assert short_row["intrabar_short_vap_no_lvn_between_value_area"] == 1.0
    assert long_row["intrabar_long_release_price"] == 98.50
    assert long_row["intrabar_long_delta"] <= -300
    assert long_row["intrabar_long_release_offset_seconds"] == 9.0


def test_developing_vap_lvn_uses_inclusive_ten_percent_of_poc_threshold():
    profile = _profile_from_cum_volume(
        {
            100.00: 10.0,
            100.25: 100.0,
            100.50: 50.0,
        },
        session_high=100.50,
        session_low=100.00,
        value_area_fraction=1.0,
        lvn_poc_fraction=0.10,
    )

    assert profile["vap_poc"] == 100.25
    assert profile["vap_lvn_inside_value_area_count"] == 1
    assert profile["vap_no_lvn_between_value_area"] == 0.0


def test_aggregate_timeframe_preserves_intrabar_anchor_features():
    source = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2024-01-03 09:30:00"),
                "symbol": "ES",
                "session_date": pd.Timestamp("2024-01-03").date(),
                "session_label": "RTH",
                "is_rth": True,
                "is_eth": False,
                "open": 100.0,
                "high": 100.5,
                "low": 99.75,
                "close": 100.25,
                "volume": 10,
                "timeframe_minutes": 1,
                "intrabar_short_release_price": 100.25,
                "intrabar_short_delta": 325.0,
            },
            {
                "timestamp": pd.Timestamp("2024-01-03 09:31:00"),
                "symbol": "ES",
                "session_date": pd.Timestamp("2024-01-03").date(),
                "session_label": "RTH",
                "is_rth": True,
                "is_eth": False,
                "open": 100.25,
                "high": 101.0,
                "low": 100.0,
                "close": 100.75,
                "volume": 20,
                "timeframe_minutes": 1,
                "intrabar_short_release_price": pd.NA,
                "intrabar_short_delta": pd.NA,
            },
            {
                "timestamp": pd.Timestamp("2024-01-03 09:32:00"),
                "symbol": "ES",
                "session_date": pd.Timestamp("2024-01-03").date(),
                "session_label": "RTH",
                "is_rth": True,
                "is_eth": False,
                "open": 100.75,
                "high": 101.25,
                "low": 100.5,
                "close": 101.0,
                "volume": 30,
                "timeframe_minutes": 1,
                "intrabar_short_release_price": pd.NA,
                "intrabar_short_delta": pd.NA,
            },
        ]
    )

    out = aggregate_timeframe(source, {"rth_start": "09:30:00"}, "3m")

    assert len(out) == 1
    row = out.iloc[0]
    assert row["timeframe_minutes"] == 3
    assert row["source_bar_count"] == 3
    assert row["intrabar_short_release_price"] == 100.25
    assert row["intrabar_short_delta"] == 325.0


def test_entry_emits_short_for_pdh_sweep_near_vah_with_failed_positive_delta():
    entry = _entry()

    signal = entry.on_bar_close(_feature_bar("2024-01-03 09:45:00"))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:46:00")
    assert signal.sweep_high == 102.5
    assert signal.metadata["entry_mode"] == "intrabar"
    assert signal.metadata["entry_reference_price"] == 101.75
    assert signal.report_fields["pivots_formed_before_entry"] == 3


def test_entry_emits_short_for_pdl_sweep_when_release_is_near_vah():
    entry = _entry()

    signal = entry.on_bar_close(
        _feature_bar(
            "2024-01-03 09:45:00",
            prev_rth_high=110.0,
            prev_rth_low=98.0,
            intrabar_short_session_high=102.50,
            intrabar_short_session_low=97.50,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.sweep_high == 102.5
    assert signal.metadata["sweep_reference"] == "previous_rth_low"
    assert signal.metadata["swept_pdh"] == 0.0
    assert signal.metadata["swept_pdl"] == 1.0


def test_entry_emits_long_for_pdl_sweep_near_val_with_failed_negative_delta():
    entry = _entry()
    bar = _feature_bar(
        "2024-01-03 09:45:00",
        intrabar_short_release_price=pd.NA,
        intrabar_short_release_offset_seconds=pd.NA,
        intrabar_short_delta=pd.NA,
        intrabar_long_release_price=98.25,
        intrabar_long_release_offset_seconds=75.0,
        intrabar_long_delta=-325.0,
        intrabar_long_delta_zone_low=97.25,
        intrabar_long_delta_zone_high=98.0,
        intrabar_long_session_open=100.0,
        intrabar_long_session_high=102.0,
        intrabar_long_session_low=97.50,
        intrabar_long_session_range_pct=0.045,
        intrabar_long_vap_poc=98.25,
        intrabar_long_vap_vah=100.0,
        intrabar_long_vap_val=98.25,
        intrabar_long_vap_no_lvn_between_value_area=1.0,
    )

    signal = entry.on_bar_close(bar)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 09:46:15")
    assert signal.sweep_low == 97.5
    assert signal.metadata["entry_reference_price"] == 98.25


def test_entry_emits_long_for_pdh_sweep_when_release_is_near_val():
    entry = _entry()
    bar = _feature_bar(
        "2024-01-03 09:45:00",
        prev_rth_high=101.0,
        prev_rth_low=90.0,
        intrabar_short_release_price=pd.NA,
        intrabar_short_release_offset_seconds=pd.NA,
        intrabar_short_delta=pd.NA,
        intrabar_long_release_price=98.25,
        intrabar_long_release_offset_seconds=75.0,
        intrabar_long_delta=-325.0,
        intrabar_long_delta_zone_low=97.25,
        intrabar_long_delta_zone_high=98.0,
        intrabar_long_session_open=100.0,
        intrabar_long_session_high=102.0,
        intrabar_long_session_low=97.50,
        intrabar_long_session_range_pct=0.045,
        intrabar_long_vap_poc=98.25,
        intrabar_long_vap_vah=100.0,
        intrabar_long_vap_val=98.25,
        intrabar_long_vap_no_lvn_between_value_area=1.0,
    )

    signal = entry.on_bar_close(bar)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.sweep_low == 97.5
    assert signal.metadata["sweep_reference"] == "previous_rth_high"
    assert signal.metadata["swept_pdh"] == 1.0
    assert signal.metadata["swept_pdl"] == 0.0


def test_engine_opens_intrabar_signal_at_signal_reference_price_not_next_bar_open():
    rows = []
    for index, timestamp in enumerate(pd.date_range("2024-01-03 09:30:00", periods=7, freq="3min")):
        row = _feature_bar(str(timestamp), high=100.0 + index, low=99.0, close=100.0, open=100.0)
        rows.append(row.to_dict())
    rows[1].update({"high": 102.0, "low": 100.0})
    rows[2].update({"high": 101.0, "low": 98.0})
    rows[3].update({"high": 103.0, "low": 99.0})
    rows[4].update({"high": 102.0, "low": 100.0})
    rows[5] = _feature_bar("2024-01-03 09:45:00", high=102.25, low=101.25, close=101.5).to_dict()
    rows[6].update({"open": 101.5, "high": 101.75, "low": 100.75, "close": 101.0})
    data = pd.DataFrame(rows)

    cfg = {
        "timeframe": "3m",
        "strategy_name": "pdh_pdl_vap_absorption_sweep",
        "strategy": {
            "entry": {
                "module": "pdh_pdl_vap_absorption_sweep",
                "params": {
                    "bar_interval_minutes": 3,
                    "start_time": "09:30:00",
                    "end_time": "11:30:00",
                    "flatten_time": "09:51:00",
                    "min_pivots": 3,
                    "min_range_pct": 0.002,
                    "max_vap_distance_pct": 0.0005,
                    "min_absorption_delta": 300,
                },
            },
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 0}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "10:30:00",
        },
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 0.0,
            "slippage_ticks": 0,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
        },
    }

    trades = BacktestEngine(cfg).run(data)["trades"]

    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["entry_timestamp"] == pd.Timestamp("2024-01-03 09:46:00")
    assert trade["entry_price"] == 101.75
    assert trade["stop_price"] == 102.5
    assert trade["target_price"] == 101.0
    assert trade["exit_reason"] == "target"


def test_engine_does_not_use_pre_entry_part_of_signal_bar_for_intrabar_exit():
    rows = []
    for index, timestamp in enumerate(pd.date_range("2024-01-03 09:30:00", periods=7, freq="3min")):
        row = _feature_bar(str(timestamp), high=100.0 + index, low=99.0, close=100.0, open=100.0)
        rows.append(row.to_dict())
    rows[1].update({"high": 102.0, "low": 100.0})
    rows[2].update({"high": 101.0, "low": 98.0})
    rows[3].update({"high": 103.0, "low": 99.0})
    rows[4].update({"high": 102.0, "low": 100.0})
    rows[5] = _feature_bar("2024-01-03 09:45:00", high=102.75, low=101.25, close=101.5).to_dict()
    rows[6].update({"open": 101.5, "high": 102.0, "low": 101.25, "close": 101.5})
    data = pd.DataFrame(rows)
    detail = pd.DataFrame(
        [
            {"timestamp": pd.Timestamp("2024-01-03 09:45:00"), "open": 102.25, "high": 102.75, "low": 101.75, "close": 101.75},
            {"timestamp": pd.Timestamp("2024-01-03 09:46:00"), "open": 101.75, "high": 102.00, "low": 101.25, "close": 101.50},
            {"timestamp": pd.Timestamp("2024-01-03 09:47:00"), "open": 101.50, "high": 102.00, "low": 101.25, "close": 101.50},
            {"timestamp": pd.Timestamp("2024-01-03 09:48:00"), "open": 101.50, "high": 102.00, "low": 101.25, "close": 101.50},
            {"timestamp": pd.Timestamp("2024-01-03 09:49:00"), "open": 101.50, "high": 102.00, "low": 101.25, "close": 101.50},
            {"timestamp": pd.Timestamp("2024-01-03 09:50:00"), "open": 101.50, "high": 102.00, "low": 101.25, "close": 101.50},
        ]
    )

    cfg = {
        "timeframe": "3m",
        "strategy_name": "pdh_pdl_vap_absorption_sweep",
        "strategy": {
            "entry": {
                "module": "pdh_pdl_vap_absorption_sweep",
                "params": {
                    "bar_interval_minutes": 3,
                    "start_time": "09:30:00",
                    "end_time": "11:30:00",
                    "flatten_time": "09:51:00",
                    "min_pivots": 3,
                    "min_range_pct": 0.002,
                    "max_vap_distance_pct": 0.0005,
                    "min_absorption_delta": 300,
                },
            },
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 0}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "flatten_time": "09:51:00",
        },
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 0.0,
            "slippage_ticks": 0,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
        },
    }

    trades = BacktestEngine(cfg).run(data, detail_data=detail)["trades"]

    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["entry_timestamp"] == pd.Timestamp("2024-01-03 09:46:00")
    assert trade["exit_timestamp"] == pd.Timestamp("2024-01-03 09:51:00")
    assert trade["exit_reason"] == "eod_flatten"
