import pandas as pd

from propstack.data.clean import clean_data
from propstack.data.quality import tradingview_comparison_report
from propstack.data.features import (
    add_orderflow_recent_pocket_combo_features,
    add_trade_orderflow_features,
    build_features,
)
from propstack.data.sessions import assign_sessions

from tests.test_data_pipeline import DATA_CFG


def test_tradingview_comparison_columns():
    df, _, _ = clean_data(DATA_CFG)
    report = tradingview_comparison_report(build_features(df, DATA_CFG))
    assert "rth_open" in report.columns
    assert "overnight_high" in report.columns
    assert "previous_rth_low" in report.columns


def test_opening_range_feature_set_skips_global_features():
    df, _, _ = clean_data(DATA_CFG)
    features = build_features(df, {**DATA_CFG, "feature_set": "opening_range"})

    assert len(features) == len(df)
    assert "session_date" in features.columns
    assert "prev_rth_high" not in features.columns
    assert "overnight_high" not in features.columns
    assert "vwap" not in features.columns
    assert "volume_ratio" not in features.columns


def test_none_feature_set_can_add_gated_vpin_features():
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-02 09:30:00",
                    "2024-01-02 09:31:00",
                    "2024-01-02 09:32:00",
                    "2024-01-02 09:33:00",
                    "2024-01-02 09:34:00",
                ]
            ).tz_localize("America/New_York"),
            "symbol": "ES",
            "open": [100.0, 100.0, 101.0, 102.0, 101.0],
            "high": [101.0, 102.0, 103.0, 103.0, 102.0],
            "low": [99.0, 99.5, 100.5, 100.0, 100.0],
            "close": [100.5, 101.5, 102.0, 101.0, 101.5],
            "volume": [100, 110, 120, 130, 140],
        }
    )

    features = build_features(
        assign_sessions(df, DATA_CFG),
        {
            **DATA_CFG,
            "feature_set": "none",
            "vpin_toxicity_features": {
                "enabled": True,
                "entry_time": "09:34:00",
                "bucket_fraction": 0.50,
                "bucket_lookback": 1,
                "bucket_min_periods": 1,
            },
        },
    )

    assert "prev_rth_high" not in features.columns
    assert "vpin_proxy_b500_l1" in features.columns
    assert "vpin_session_ret" in features.columns


def test_trade_orderflow_features_use_completed_bars_through_signal_close():
    timestamps = pd.date_range(
        "2024-01-02 09:30:00",
        periods=6,
        freq="1min",
        tz="America/New_York",
    )
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "session_date": [timestamps[0].date()] * 6,
            "session_label": ["RTH"] * 6,
            "symbol": ["ES"] * 6,
            "is_rth": [True] * 6,
            "open": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0],
            "high": [101.0, 102.0, 103.0, 104.0, 105.0, 106.0],
            "low": [99.0, 100.0, 101.0, 102.0, 103.0, 104.0],
            "close": [100.5, 101.5, 102.5, 103.5, 104.5, 105.5],
            "volume": [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
            "trades": [10.0, 20.0, 30.0, 40.0, 50.0, 60.0],
            "signed_volume": [50.0, -20.0, 30.0, 60.0, -10.0, 90.0],
            "large20_signed_volume": [40.0, -10.0, 20.0, 50.0, -5.0, 70.0],
            "large20_volume": [80.0, 20.0, 40.0, 100.0, 10.0, 100.0],
        }
    )

    features = add_trade_orderflow_features(
        df,
        {
            "trade_orderflow_features": {
                "enabled": True,
                "windows": [3],
                "large_trade_sizes": [20],
                "tick_size": 0.25,
                "min_period_fraction": 1.0,
            }
        },
    )
    signal_bar = features.iloc[3]

    assert signal_bar["trade_orderflow_signed_volume_3"] == 70.0
    assert signal_bar["trade_orderflow_volume_3"] == 300.0
    assert signal_bar["trade_orderflow_trades_3"] == 90.0
    assert round(signal_bar["trade_orderflow_avg_trade_size_3"], 10) == round(300.0 / 90.0, 10)
    assert round(signal_bar["trade_orderflow_imbalance_3"], 10) == round(70.0 / 300.0, 10)
    assert round(signal_bar["trade_orderflow_abs_imbalance_3"], 10) == round(abs(70.0 / 300.0), 10)
    assert signal_bar["trade_orderflow_large20_signed_volume_3"] == 60.0
    assert signal_bar["trade_orderflow_large20_volume_3"] == 160.0
    assert signal_bar["trade_orderflow_return_points_3"] == 2.5
    assert signal_bar["trade_orderflow_return_ticks_3"] == 10.0
    assert signal_bar["trade_orderflow_effort_vs_result_3"] == 30.0
    assert pd.isna(features.iloc[1]["trade_orderflow_return_points_3"])


def test_trade_orderflow_same_clock_ranks_use_prior_same_time_values():
    timestamps = pd.to_datetime(
        [
            "2024-01-02 09:59:00",
            "2024-01-02 10:29:00",
            "2024-01-03 09:59:00",
            "2024-01-03 10:29:00",
            "2024-01-04 09:59:00",
            "2024-01-04 10:29:00",
        ]
    ).tz_localize("America/New_York")
    df = pd.DataFrame(
        {
            "timestamp": timestamps,
            "session_date": [ts.date() for ts in timestamps],
            "session_label": ["RTH"] * 6,
            "symbol": ["ES"] * 6,
            "is_rth": [True] * 6,
            "open": [100.0] * 6,
            "high": [101.0] * 6,
            "low": [99.0] * 6,
            "close": [100.5] * 6,
            "volume": [100.0] * 6,
            "trades": [10.0] * 6,
            "signed_volume": [50.0, 10.0, 40.0, 20.0, 10.0, 90.0],
        }
    )

    features = add_trade_orderflow_features(
        df,
        {
            "trade_orderflow_features": {
                "enabled": True,
                "windows": [1],
                "tick_size": 0.25,
                "min_period_fraction": 1.0,
                "same_clock_ranks": {
                    "enabled": True,
                    "columns": ["trade_orderflow_abs_imbalance_1"],
                    "rank_windows": [2],
                    "rank_min_periods": 2,
                },
            }
        },
    )

    day_three_0959 = features[features["timestamp"] == timestamps[4]].iloc[0]
    day_three_1029 = features[features["timestamp"] == timestamps[5]].iloc[0]

    assert day_three_0959["trade_orderflow_abs_imbalance_1_rank2"] == 0.0
    assert day_three_1029["trade_orderflow_abs_imbalance_1_rank2"] == 1.0
    assert pd.isna(features.iloc[2]["trade_orderflow_abs_imbalance_1_rank2"])


def test_recent_pocket_combo_vwap_leg_uses_prior_same_clock_vwap_rank():
    def rows(prior_vwap_extension_ticks: float) -> pd.DataFrame:
        records = []
        for i in range(20):
            ts = pd.Timestamp(f"2024-01-{i + 2:02d} 13:29:00", tz="America/New_York")
            close = 100.0
            low = close - prior_vwap_extension_ticks * 0.75
            records.append(
                {
                    "timestamp": ts,
                    "session_date": ts.date(),
                    "session_label": "RTH",
                    "symbol": "ES",
                    "is_rth": True,
                    "open": 100.0,
                    "high": close,
                    "low": low,
                    "close": close,
                    "volume": 100.0,
                    "signed_volume": 5.0,
                    "trade_orderflow_imbalance_15": 0.0,
                    "trade_orderflow_imbalance_30": 0.01,
                    "trade_orderflow_abs_imbalance_30": 0.01,
                    "trade_orderflow_return_ticks_15": 0.0,
                    "trade_orderflow_return_ticks_30": 0.0,
                    "trade_orderflow_volume_15": 100.0,
                    "trade_orderflow_volume_30": 100.0,
                }
            )
        ts = pd.Timestamp("2024-01-31 13:29:00", tz="America/New_York")
        records.append(
            {
                "timestamp": ts,
                "session_date": ts.date(),
                "session_label": "RTH",
                "symbol": "ES",
                "is_rth": True,
                "open": 100.0,
                "high": 110.0,
                "low": 101.0,
                "close": 110.0,
                "volume": 200.0,
                "signed_volume": 12.0,
                "trade_orderflow_imbalance_15": 0.0,
                "trade_orderflow_imbalance_30": 0.06,
                "trade_orderflow_abs_imbalance_30": 0.06,
                "trade_orderflow_return_ticks_15": 0.0,
                "trade_orderflow_return_ticks_30": 0.0,
                "trade_orderflow_volume_15": 200.0,
                "trade_orderflow_volume_30": 200.0,
            }
        )
        return pd.DataFrame(records)

    eligible = add_orderflow_recent_pocket_combo_features(
        rows(prior_vwap_extension_ticks=4.0),
        {"orderflow_recent_pocket_combo_features": {"enabled": True, "tick_size": 0.25}},
    ).iloc[-1]
    blocked = add_orderflow_recent_pocket_combo_features(
        rows(prior_vwap_extension_ticks=20.0),
        {"orderflow_recent_pocket_combo_features": {"enabled": True, "tick_size": 0.25}},
    ).iloc[-1]

    assert eligible["of_combo_price_vs_vwap_ticks"] == 12.0
    assert eligible["of_combo_price_vs_vwap_ticks_rank42"] == 1.0
    assert bool(eligible["of_combo_signal_late_vwap_short_1330"])
    assert blocked["of_combo_price_vs_vwap_ticks"] == 12.0
    assert blocked["of_combo_price_vs_vwap_ticks_rank42"] == 0.0
    assert not bool(blocked["of_combo_signal_late_vwap_short_1330"])


def test_tradingview_comparison_handles_minimal_feature_set():
    df, _, _ = clean_data(DATA_CFG)
    features = build_features(df, {**DATA_CFG, "feature_set": "opening_range"})

    report = tradingview_comparison_report(features)

    assert "overnight_high" in report.columns
    assert "previous_rth_low" in report.columns
    assert report["overnight_high"].isna().all()


def test_build_features_rejects_unknown_feature_set():
    df, _, _ = clean_data(DATA_CFG)

    try:
        build_features(df, {**DATA_CFG, "feature_set": "unknown"})
    except ValueError as exc:
        assert "data.feature_set" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown data.feature_set")


def test_previous_rth_levels_skip_eth_boundary_bar_over_weekend():
    cfg = {
        "rth_start": "09:30:00",
        "rth_end": "16:00:00",
        "eth_start": "16:00:00",
        "eth_end": "09:29:00",
        "rolling_volume_window": 3,
    }
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2022-12-16 09:30:00",
                    "2022-12-16 15:59:00",
                    "2022-12-16 16:00:00",
                    "2022-12-19 09:30:00",
                ]
            ).tz_localize("America/New_York"),
            "symbol": "ES",
            "open": [3900.0, 3882.0, 3877.5, 3880.0],
            "high": [3912.5, 3882.25, 3879.25, 3883.5],
            "low": [3895.0, 3877.25, 3875.75, 3875.25],
            "close": [3910.0, 3879.0, 3878.5, 3876.0],
            "volume": [100, 100, 100, 100],
        }
    )
    sessions = assign_sessions(df, cfg)
    features = build_features(sessions, cfg)
    monday_ts = pd.Timestamp("2022-12-19 09:30:00", tz="America/New_York")
    monday = features[features["timestamp"] == monday_ts].iloc[0]

    assert monday["prev_rth_high"] == 3912.5
    assert monday["prev_rth_low"] == 3877.25
    assert monday["prev_rth_close"] == 3879.0


def test_previous_rth_freshness_detects_overnight_breaches():
    cfg = {
        "rth_start": "09:30:00",
        "rth_end": "16:00:00",
        "eth_start": "16:00:00",
        "eth_end": "09:29:00",
        "rolling_volume_window": 3,
    }
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-02 09:30:00",
                    "2024-01-02 09:31:00",
                    "2024-01-02 16:00:00",
                    "2024-01-03 09:30:00",
                ]
            ).tz_localize("America/New_York"),
            "symbol": "ES",
            "open": [100.0, 100.0, 100.0, 100.0],
            "high": [101.0, 100.5, 101.25, 100.5],
            "low": [99.0, 99.5, 98.75, 99.25],
            "close": [100.5, 100.0, 100.0, 100.0],
            "volume": [100, 100, 100, 100],
        }
    )
    features = build_features(assign_sessions(df, cfg), cfg)
    overnight = features[
        features["timestamp"] == pd.Timestamp("2024-01-02 16:00:00", tz="America/New_York")
    ].iloc[0]
    next_rth = features[
        features["timestamp"] == pd.Timestamp("2024-01-03 09:30:00", tz="America/New_York")
    ].iloc[0]

    assert overnight["prev_rth_high_fresh"]
    assert overnight["prev_rth_low_fresh"]
    assert not next_rth["prev_rth_high_fresh"]
    assert not next_rth["prev_rth_low_fresh"]


def test_previous_rth_levels_can_reset_on_contract_change():
    cfg = {
        "rth_start": "09:30:00",
        "rth_end": "16:00:00",
        "eth_start": "16:00:00",
        "eth_end": "09:29:00",
        "rolling_volume_window": 3,
        "roll_boundary_policy": {"reset_previous_day_levels": True},
    }
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-03-11 09:30:00",
                    "2024-03-11 15:59:00",
                    "2024-03-12 09:30:00",
                ]
            ).tz_localize("America/New_York"),
            "symbol": ["ES", "ES", "ES"],
            "contract_symbol": ["ESH4", "ESH4", "ESM4"],
            "open": [100.0, 100.0, 105.0],
            "high": [101.0, 102.0, 106.0],
            "low": [99.0, 98.0, 104.0],
            "close": [100.5, 101.0, 105.5],
            "volume": [100, 100, 100],
        }
    )

    features = build_features(assign_sessions(df, cfg), cfg)
    first_new_contract_rth = features[
        features["timestamp"] == pd.Timestamp("2024-03-12 09:30:00", tz="America/New_York")
    ].iloc[0]

    assert pd.isna(first_new_contract_rth["prev_rth_high"])
    assert pd.isna(first_new_contract_rth["prev_rth_low"])
    assert pd.isna(first_new_contract_rth["prev_rth_close"])
