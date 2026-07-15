import pandas as pd

from alphaquest.data.features import build_features
from alphaquest.data.footprint import add_footprint_imbalance_features, price_volume_from_prints
from tools.build_sierra_footprint_feature_cache import aggregate_base_bars, _floor_local_timestamp_to_rth_bar


def test_footprint_features_detect_sell_absorption_below_close():
    bars = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2024-01-03 10:00", tz="America/New_York"),
                "open": 100.0,
                "high": 100.75,
                "low": 99.75,
                "close": 100.5,
                "volume": 100,
            }
        ]
    )
    price_volume = pd.DataFrame(
        [
            {"timestamp": bars.iloc[0]["timestamp"], "price": 100.0, "bid_volume": 60, "ask_volume": 0},
            {"timestamp": bars.iloc[0]["timestamp"], "price": 100.25, "bid_volume": 0, "ask_volume": 10},
            {"timestamp": bars.iloc[0]["timestamp"], "price": 100.5, "bid_volume": 0, "ask_volume": 10},
        ]
    )

    out = add_footprint_imbalance_features(
        bars,
        price_volume,
        tick_size=0.25,
        imbalance_ratio=3.0,
        min_level_volume=20,
    )

    assert out.iloc[0]["footprint_sell_imbalance_count"] == 1
    assert out.iloc[0]["footprint_buy_imbalance_count"] == 0
    assert out.iloc[0]["footprint_highest_sell_imbalance_price"] == 100.0
    assert out.iloc[0]["footprint_sell_imbalance_below_close"] == 1.0
    assert out.iloc[0]["footprint_absorption_long"] == 1.0
    assert out.iloc[0]["footprint_absorption_short"] == 0.0


def test_footprint_builder_uses_rth_anchored_three_minute_buckets():
    timestamps = pd.DatetimeIndex(
        [
            pd.Timestamp("2024-01-03 09:30:00", tz="America/New_York"),
            pd.Timestamp("2024-01-03 09:32:59", tz="America/New_York"),
            pd.Timestamp("2024-01-03 09:33:00", tz="America/New_York"),
        ]
    )

    buckets = _floor_local_timestamp_to_rth_bar(timestamps, 3)

    assert list(buckets) == [
        pd.Timestamp("2024-01-03 09:30:00", tz="America/New_York"),
        pd.Timestamp("2024-01-03 09:30:00", tz="America/New_York"),
        pd.Timestamp("2024-01-03 09:33:00", tz="America/New_York"),
    ]


def test_footprint_builder_aggregates_base_bars_to_native_three_minute_cache_rows():
    timestamps = pd.date_range("2024-01-03 09:30:00", periods=3, freq="1min")
    base = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": ["ES"] * 3,
            "contract_symbol": ["ESH24"] * 3,
            "open": [100.0, 100.5, 101.0],
            "high": [100.75, 101.25, 101.5],
            "low": [99.75, 100.25, 100.75],
            "close": [100.5, 101.0, 101.25],
            "volume": [10, 20, 30],
            "signed_volume": [1, -2, 3],
            "buy_volume": [6, 9, 17],
            "sell_volume": [5, 11, 14],
            "large10_signed_volume": [0, 1, 0],
            "large20_signed_volume": [0, 0, 1],
            "large10_volume": [0, 2, 0],
            "large20_volume": [0, 0, 3],
            "trades": [1, 2, 3],
        }
    )

    out = aggregate_base_bars(base, bar_minutes=3)
    row = out.iloc[0]

    assert len(out) == 1
    assert row["timestamp"] == pd.Timestamp("2024-01-03 09:30:00")
    assert row["open"] == 100.0
    assert row["high"] == 101.5
    assert row["low"] == 99.75
    assert row["close"] == 101.25
    assert row["volume"] == 60
    assert row["timeframe_minutes"] == 3
    assert row["source_bar_count"] == 3


def test_footprint_features_detect_buy_absorption_above_close():
    bars = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2024-01-03 10:00", tz="America/New_York"),
                "open": 100.5,
                "high": 101.0,
                "low": 100.0,
                "close": 100.25,
                "volume": 100,
            }
        ]
    )
    price_volume = pd.DataFrame(
        [
            {"timestamp": bars.iloc[0]["timestamp"], "price": 100.25, "bid_volume": 15, "ask_volume": 0},
            {"timestamp": bars.iloc[0]["timestamp"], "price": 100.5, "bid_volume": 0, "ask_volume": 70},
            {"timestamp": bars.iloc[0]["timestamp"], "price": 100.75, "bid_volume": 0, "ask_volume": 20},
        ]
    )

    out = add_footprint_imbalance_features(
        bars,
        price_volume,
        tick_size=0.25,
        imbalance_ratio=3.0,
        min_level_volume=20,
    )

    assert out.iloc[0]["footprint_buy_imbalance_count"] == 1
    assert out.iloc[0]["footprint_lowest_buy_imbalance_price"] == 100.5
    assert out.iloc[0]["footprint_buy_imbalance_above_close"] == 1.0
    assert out.iloc[0]["footprint_absorption_short"] == 1.0
    assert out.iloc[0]["footprint_absorption_long"] == 0.0


def test_footprint_features_ignore_zero_opposite_diagonal_at_bar_extremes():
    bars = pd.DataFrame(
        [
            {
                "timestamp": pd.Timestamp("2024-01-03 10:00", tz="America/New_York"),
                "open": 100.0,
                "high": 100.5,
                "low": 100.0,
                "close": 100.25,
                "volume": 100,
            }
        ]
    )
    price_volume = pd.DataFrame(
        [
            {"timestamp": bars.iloc[0]["timestamp"], "price": 100.0, "bid_volume": 0, "ask_volume": 35},
            {"timestamp": bars.iloc[0]["timestamp"], "price": 100.25, "bid_volume": 2, "ask_volume": 0},
            {"timestamp": bars.iloc[0]["timestamp"], "price": 100.5, "bid_volume": 40, "ask_volume": 10},
        ]
    )

    out = add_footprint_imbalance_features(
        bars,
        price_volume,
        tick_size=0.25,
        imbalance_ratio=3.0,
        min_level_volume=20,
    )

    assert out.iloc[0]["footprint_sell_imbalance_count"] == 0
    assert out.iloc[0]["footprint_buy_imbalance_count"] == 0
    assert out.iloc[0]["footprint_max_sell_imbalance_ratio"] == 0.0
    assert out.iloc[0]["footprint_max_buy_imbalance_ratio"] == 0.0
    assert out.iloc[0]["footprint_highest_sell_imbalance_price"] == 0.0
    assert out.iloc[0]["footprint_lowest_buy_imbalance_price"] == 0.0
    assert out.iloc[0]["footprint_absorption_long"] == 0.0
    assert out.iloc[0]["footprint_absorption_short"] == 0.0


def test_price_volume_from_prints_groups_by_minute_and_tick_price():
    ts = pd.Timestamp("2024-01-03 10:00:01", tz="America/New_York")
    prints = pd.DataFrame(
        [
            {"timestamp": ts, "close": 100.01, "volume": 3, "bid_volume": 3, "ask_volume": 0},
            {"timestamp": ts + pd.Timedelta(seconds=5), "close": 100.0, "volume": 2, "bid_volume": 0, "ask_volume": 2},
            {"timestamp": ts + pd.Timedelta(minutes=1), "close": 100.25, "volume": 1, "bid_volume": 1, "ask_volume": 0},
        ]
    )

    out = price_volume_from_prints(prints, tick_size=0.25)

    assert len(out) == 2
    first = out.iloc[0]
    assert first["timestamp"] == pd.Timestamp("2024-01-03 10:00", tz="America/New_York")
    assert first["price"] == 100.0
    assert first["volume"] == 5
    assert first["bid_volume"] == 3
    assert first["ask_volume"] == 2


def test_build_features_preserves_existing_footprint_columns_when_feature_set_none():
    timestamp = pd.Timestamp("2024-01-03 10:00", tz="America/New_York")
    df = pd.DataFrame(
        [
            {
                "timestamp": timestamp,
                "symbol": "ES",
                "open": 100.0,
                "high": 100.75,
                "low": 99.75,
                "close": 100.5,
                "volume": 100,
                "is_rth": True,
                "session_date": timestamp.date(),
                "session_label": "RTH",
                "footprint_absorption_long": 1.0,
            }
        ]
    )

    out = build_features(df, {"feature_set": "none"})

    assert out.iloc[0]["footprint_absorption_long"] == 1.0
