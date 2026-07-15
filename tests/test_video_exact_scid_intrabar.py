import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry.video_exact_orderflow_playbook_scid_intrabar import (
    VideoExactOrderflowPlaybookScidIntrabarEntry,
)
from alphaquest.strategy_modules.entry.yush_trend_1 import YushTrend1Entry
from alphaquest.strategy_modules.entry.yush_trend_2 import YushTrend2Entry
from alphaquest.strategy_modules.entry.yush_trend_3 import YushTrend3Entry
from alphaquest.strategy_modules.entry.yush_trend_4 import YushTrend4Entry
from alphaquest.strategy_modules.entry.yush_trend_5 import YushTrend5Entry
from alphaquest.strategy_modules.entry.yush_trend_6 import YushTrend6Entry
from alphaquest.strategy_modules.entry.yush_trend_7 import YushTrend7Entry
from alphaquest.strategy_modules.entry.yush_trend_8 import YushTrend8Entry
from alphaquest.strategy_modules.entry.yush_trend_9 import YushTrend9Entry
from alphaquest.strategy_modules.entry.yush_trend_10 import YushTrend10Entry
from alphaquest.strategy_modules.entry.yush_trend_11 import YushTrend11Entry
from alphaquest.strategy_modules.entry.yush_trend_12 import YushTrend12Entry
from alphaquest.strategy_modules.entry.yush_trend_13 import YushTrend13Entry
from alphaquest.strategy_modules.entry.yush_trend_14 import YushTrend14Entry
from alphaquest.strategy_modules.entry.yush_trend_15 import YushTrend15Entry
from alphaquest.strategy_modules.entry.yush_range_15 import YushRange15Entry
from alphaquest.strategy_modules.entry.yush_range_16 import YushRange16Entry


def _bar(timestamp, **overrides):
    row = {
        "timestamp": pd.Timestamp(timestamp, tz="America/New_York"),
        "session_date": pd.Timestamp(timestamp).date(),
        "is_rth": True,
        "open": 100.0,
        "high": 100.5,
        "low": 99.5,
        "close": 100.0,
        "volume": 1000,
        "signed_volume": 0,
        "developing_vap_poc": 101.0,
        "developing_vap_vah": 102.0,
        "developing_vap_val": 100.0,
        "developing_vap_lvn_near_close": 101.0,
        "developing_vap_lvn_near_high": 101.5,
        "developing_vap_lvn_near_low": 100.25,
        "developing_vap_total_volume": 10000,
        "developing_vap_bars": 20,
        "overnight_low": 100.0,
        "overnight_high": 104.0,
    }
    row.update(overrides)
    return row


def _detail_rows():
    rows = [
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:00", tz="America/New_York"),
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 5,
            "buy_volume": 5,
            "sell_volume": 0,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:10", tz="America/New_York"),
            "open": 99.75,
            "high": 99.75,
            "low": 99.75,
            "close": 99.75,
            "volume": 60,
            "buy_volume": 0,
            "sell_volume": 60,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:20", tz="America/New_York"),
            "open": 100.0,
            "high": 100.0,
            "low": 100.0,
            "close": 100.0,
            "volume": 200,
            "buy_volume": 0,
            "sell_volume": 200,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:21", tz="America/New_York"),
            "open": 100.25,
            "high": 100.25,
            "low": 100.25,
            "close": 100.25,
            "volume": 1,
            "buy_volume": 1,
            "sell_volume": 0,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:03:05", tz="America/New_York"),
            "open": 101.0,
            "high": 101.0,
            "low": 101.0,
            "close": 101.0,
            "volume": 1,
            "buy_volume": 1,
            "sell_volume": 0,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _entry_params():
    return {
        "start_time": "10:00:00",
        "end_time": "15:00:00",
        "flatten_time": "15:55:00",
        "bar_interval_minutes": 3,
        "tick_size": 0.25,
        "market_aoi_max_distance_ticks": 16,
        "aoi_reach_tolerance_ticks": 4,
        "min_probe_ticks": 1,
        "confirmation_ticks": 0,
        "min_absorption_volume": 50,
        "min_aoi_confluences": 2,
        "min_large200_record_volume": 200,
        "min_delta_activity_imbalance": 0.03,
        "profile_source": "cached_developing_vap",
        "cached_profile_prefix": "developing_vap",
        "setup_mode": "model1_range_value_edge_two_sided",
        "target_reference": "value_midpoint",
        "allow_long": True,
        "allow_short": True,
    }


def _trend_entry_params(**overrides):
    params = _entry_params()
    params.update(
        {
            "setup_mode": "model2_trend_lvn_short",
            "target_reference": "structural_or_midpoint",
            "allow_long": False,
            "allow_short": True,
            "min_structure_bars": 1,
            "min_trend_move_ticks": 8,
            "min_directional_delta_imbalance": 0.1,
            "min_aoi_confluences": 3,
        }
    )
    params.update(overrides)
    return params


def _trend_context_bar(timestamp="2024-01-03 09:57:00"):
    return _bar(
        timestamp,
        open=105.0,
        high=105.0,
        low=98.75,
        close=99.0,
        signed_volume=-600,
        developing_vap_poc=101.0,
        developing_vap_vah=102.0,
        developing_vap_val=100.0,
        developing_vap_lvn_near_close=99.25,
        developing_vap_lvn_near_low=99.25,
        overnight_low=100.0,
    )


def _trend_long_context_bar(timestamp="2024-01-03 09:57:00"):
    return _bar(
        timestamp,
        open=95.0,
        high=101.25,
        low=95.0,
        close=101.0,
        signed_volume=600,
        developing_vap_poc=99.0,
        developing_vap_vah=100.0,
        developing_vap_val=98.0,
        developing_vap_lvn_near_close=100.75,
        developing_vap_lvn_near_high=100.75,
        overnight_high=100.0,
    )


def _trend_short_detail_rows():
    rows = [
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:00", tz="America/New_York"),
            "open": 99.5,
            "high": 99.5,
            "low": 99.5,
            "close": 99.5,
            "volume": 10,
            "buy_volume": 0,
            "sell_volume": 10,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:05", tz="America/New_York"),
            "open": 99.25,
            "high": 99.25,
            "low": 99.25,
            "close": 99.25,
            "volume": 60,
            "buy_volume": 60,
            "sell_volume": 0,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:08", tz="America/New_York"),
            "open": 99.0,
            "high": 99.0,
            "low": 99.0,
            "close": 99.0,
            "volume": 300,
            "buy_volume": 0,
            "sell_volume": 300,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:03:05", tz="America/New_York"),
            "open": 98.75,
            "high": 98.75,
            "low": 98.75,
            "close": 98.75,
            "volume": 1,
            "buy_volume": 0,
            "sell_volume": 1,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _trend_long_detail_rows():
    rows = [
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:00", tz="America/New_York"),
            "open": 100.5,
            "high": 100.5,
            "low": 100.5,
            "close": 100.5,
            "volume": 30,
            "buy_volume": 0,
            "sell_volume": 30,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:04", tz="America/New_York"),
            "open": 101.0,
            "high": 101.0,
            "low": 101.0,
            "close": 101.0,
            "volume": 60,
            "buy_volume": 60,
            "sell_volume": 0,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:08", tz="America/New_York"),
            "open": 101.25,
            "high": 101.25,
            "low": 101.25,
            "close": 101.25,
            "volume": 300,
            "buy_volume": 300,
            "sell_volume": 0,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _trend_short_low_absorption_detail_rows():
    rows = [
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:00", tz="America/New_York"),
            "open": 99.5,
            "high": 99.5,
            "low": 99.5,
            "close": 99.5,
            "volume": 10,
            "buy_volume": 0,
            "sell_volume": 10,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:05", tz="America/New_York"),
            "open": 99.25,
            "high": 99.25,
            "low": 99.25,
            "close": 99.25,
            "volume": 25,
            "buy_volume": 25,
            "sell_volume": 0,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
        {
            "timestamp": pd.Timestamp("2024-01-03 10:00:08", tz="America/New_York"),
            "open": 99.0,
            "high": 99.0,
            "low": 99.0,
            "close": 99.0,
            "volume": 100,
            "buy_volume": 0,
            "sell_volume": 100,
            "num_trades": 1,
            "execution_granularity": "scid_record",
        },
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def test_scid_intrabar_video_entry_detects_first_long_reclaim_tick():
    entry = VideoExactOrderflowPlaybookScidIntrabarEntry(_entry_params())
    entry.on_bar_close(pd.Series(_bar("2024-01-03 09:57:00")))

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _detail_rows())

    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["entry_mode"] == "intrabar"
    assert signal.metadata["entry_reference_price"] == 100.25
    assert signal.metadata["intended_entry_timestamp"] == pd.Timestamp(
        "2024-01-03 10:00:21", tz="America/New_York"
    )
    assert signal.metadata["aoi_confluence_criteria"] == "volume_profile,market_level,big_trades,delta_activity"


def test_yush_trend_2_accepts_scid_normalized_absorption_threshold():
    high_threshold = YushTrend1Entry(_trend_entry_params(min_absorption_volume=100, min_aoi_confluences=2))
    low_threshold = YushTrend2Entry(_trend_entry_params(min_absorption_volume=20, min_aoi_confluences=2))
    context = pd.Series(_trend_context_bar())
    bar = pd.Series(_bar("2024-01-03 10:00:00"))
    detail = _trend_short_low_absorption_detail_rows()
    high_threshold.on_bar_close(context)
    low_threshold.on_bar_close(context)

    assert high_threshold.on_bar_intrabar(bar, detail) is None
    signal = low_threshold.on_bar_intrabar(bar, detail)

    assert signal is not None
    assert signal.direction == "short"
    assert low_threshold.name == "yush_trend_2"
    assert signal.metadata["video_model"] == "model2_trend_scid_intrabar"
    assert signal.metadata["min_absorption_volume"] == 20


def test_yush_trend_7_reuses_short_lvn_rejection_with_own_name():
    entry = YushTrend7Entry(_trend_entry_params(min_absorption_volume=20, min_aoi_confluences=2))
    entry.on_bar_close(pd.Series(_trend_context_bar()))

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _trend_short_low_absorption_detail_rows())

    assert signal is not None
    assert signal.direction == "short"
    assert entry.name == "yush_trend_7"
    assert signal.metadata["video_model"] == "model2_trend_scid_intrabar"
    assert signal.metadata["min_absorption_volume"] == 20


def test_yush_trend_8_rejects_short_lvn_rejection_when_signal_risk_is_too_wide():
    wide_cap = YushTrend8Entry(
        _trend_entry_params(min_absorption_volume=20, min_aoi_confluences=2, max_signal_risk_points=0.5)
    )
    ok_cap = YushTrend8Entry(
        _trend_entry_params(min_absorption_volume=20, min_aoi_confluences=2, max_signal_risk_points=2.0)
    )
    context = pd.Series(_trend_context_bar())
    bar = pd.Series(_bar("2024-01-03 10:00:00"))
    wide_cap.on_bar_close(context)
    ok_cap.on_bar_close(context)

    assert wide_cap.on_bar_intrabar(bar, _trend_short_low_absorption_detail_rows()) is None
    signal = ok_cap.on_bar_intrabar(bar, _trend_short_low_absorption_detail_rows())

    assert signal is not None
    assert signal.direction == "short"
    assert ok_cap.name == "yush_trend_8"


def test_yush_trend_9_requires_market_level_and_delta_activity_confluence():
    entry = YushTrend9Entry(
        _trend_entry_params(min_absorption_volume=20, min_aoi_confluences=2, max_signal_risk_points=2.0)
    )
    context = pd.Series(_trend_context_bar())
    entry.on_bar_close(context)
    no_market_bar = pd.Series(_bar("2024-01-03 10:00:00", overnight_low=120.0, overnight_high=130.0))

    assert entry.on_bar_intrabar(no_market_bar, _trend_short_low_absorption_detail_rows()) is None

    entry = YushTrend9Entry(
        _trend_entry_params(min_absorption_volume=20, min_aoi_confluences=2, max_signal_risk_points=2.0)
    )
    entry.on_bar_close(context)
    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _trend_short_low_absorption_detail_rows())

    assert signal is not None
    assert signal.direction == "short"
    assert entry.name == "yush_trend_9"
    assert signal.metadata["aoi_confluence_criteria"] == "volume_profile,market_level,delta_activity"


def test_yush_trend_10_reuses_strict_confluence_with_own_name():
    entry = YushTrend10Entry(
        _trend_entry_params(min_absorption_volume=20, min_aoi_confluences=2, max_signal_risk_points=2.0)
    )
    entry.on_bar_close(pd.Series(_trend_context_bar()))

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 12:00:00")), _trend_short_low_absorption_detail_rows())

    assert signal is not None
    assert signal.direction == "short"
    assert entry.name == "yush_trend_10"
    assert signal.metadata["setup_mode"] == "model2_trend_lvn_short"
    assert signal.metadata["aoi_confluence_criteria"] == "volume_profile,market_level,delta_activity"


def test_yush_trend_11_reuses_risk_capped_short_lvn_with_own_name():
    entry = YushTrend11Entry(
        _trend_entry_params(min_absorption_volume=20, min_aoi_confluences=2, max_signal_risk_points=2.0)
    )
    entry.on_bar_close(pd.Series(_trend_context_bar()))

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:30:00")), _trend_short_low_absorption_detail_rows())

    assert signal is not None
    assert signal.direction == "short"
    assert entry.name == "yush_trend_11"
    assert signal.metadata["setup_mode"] == "model2_trend_lvn_short"


def test_yush_trend_3_detects_intrabar_long_lvn_pullback_rejection():
    entry = YushTrend3Entry(
        _trend_entry_params(
            setup_mode="model2_trend_lvn_long",
            allow_long=True,
            allow_short=False,
            min_absorption_volume=20,
            min_aoi_confluences=2,
            min_directional_delta_imbalance=0.0,
        )
    )
    entry.on_bar_close(pd.Series(_trend_long_context_bar()))

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _trend_long_detail_rows())

    assert signal is not None
    assert signal.direction == "long"
    assert entry.name == "yush_trend_3"
    assert signal.metadata["entry_mode"] == "intrabar"
    assert signal.metadata["setup_mode"] == "model2_trend_lvn_long"
    assert signal.metadata["video_model"] == "model2_trend_scid_intrabar"
    assert signal.metadata["profile_level_price"] == 100.75
    assert signal.metadata["entry_reference_price"] == 101.0
    assert signal.metadata["aoi_confluence_count"] >= 2


def test_yush_trend_4_accepts_long_only_high_confluence_rejection():
    entry = YushTrend4Entry(
        _trend_entry_params(
            setup_mode="model2_trend_lvn_long",
            allow_long=True,
            allow_short=False,
            min_absorption_volume=20,
            min_aoi_confluences=3,
            min_directional_delta_imbalance=0.0,
        )
    )
    entry.on_bar_close(pd.Series(_trend_long_context_bar()))

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _trend_long_detail_rows())

    assert signal is not None
    assert signal.direction == "long"
    assert entry.name == "yush_trend_4"
    assert signal.metadata["video_model"] == "model2_trend_scid_intrabar"
    assert signal.metadata["aoi_confluence_count"] >= 3
    assert "market_level" in signal.metadata["aoi_confluence_criteria"]
    assert "delta_activity" in signal.metadata["aoi_confluence_criteria"]


def test_yush_trend_5_reuses_high_confluence_long_rejection_with_own_name():
    entry = YushTrend5Entry(
        _trend_entry_params(
            setup_mode="model2_trend_lvn_long",
            allow_long=True,
            allow_short=False,
            min_absorption_volume=20,
            min_aoi_confluences=3,
            min_directional_delta_imbalance=0.0,
        )
    )
    entry.on_bar_close(pd.Series(_trend_long_context_bar()))

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _trend_long_detail_rows())

    assert signal is not None
    assert signal.direction == "long"
    assert entry.name == "yush_trend_5"
    assert signal.metadata["video_model"] == "model2_trend_scid_intrabar"
    assert signal.metadata["aoi_confluence_count"] >= 3


def test_yush_trend_6_requires_big_trade_confluence():
    entry = YushTrend6Entry(
        _trend_entry_params(
            setup_mode="model2_trend_lvn_long",
            allow_long=True,
            allow_short=False,
            min_absorption_volume=20,
            min_aoi_confluences=3,
            min_directional_delta_imbalance=0.0,
            required_aoi_criteria=["big_trades"],
        )
    )
    entry.on_bar_close(pd.Series(_trend_long_context_bar()))

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _trend_long_detail_rows())

    assert signal is not None
    assert signal.direction == "long"
    assert entry.name == "yush_trend_6"
    assert "big_trades" in signal.metadata["aoi_confluence_criteria"]


def test_yush_trend_12_requires_big_trade_and_rejects_market_level_confluence():
    params = _trend_entry_params(
        setup_mode="model2_trend_lvn_long",
        allow_long=True,
        allow_short=False,
        min_absorption_volume=20,
        min_aoi_confluences=3,
        min_directional_delta_imbalance=0.0,
        required_aoi_criteria=["big_trades"],
        forbidden_aoi_criteria=["market_level"],
    )
    entry = YushTrend12Entry(params)
    entry.on_bar_close(pd.Series(_trend_long_context_bar()))

    assert entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _trend_long_detail_rows()) is None

    entry = YushTrend12Entry(params)
    entry.on_bar_close(pd.Series(_trend_long_context_bar()))
    no_market_bar = pd.Series(
        _bar(
            "2024-01-03 10:00:00",
            prev_rth_high=120.0,
            prev_rth_low=80.0,
            overnight_high=120.0,
            overnight_low=80.0,
        )
    )
    signal = entry.on_bar_intrabar(no_market_bar, _trend_long_detail_rows())

    assert signal is not None
    assert signal.direction == "long"
    assert entry.name == "yush_trend_12"
    assert signal.metadata["aoi_confluence_criteria"] == "volume_profile,big_trades,delta_activity"


def test_yush_trend_13_adds_known_risk_cap_to_big_trade_no_market_setup():
    params = _trend_entry_params(
        setup_mode="model2_trend_lvn_long",
        allow_long=True,
        allow_short=False,
        min_absorption_volume=20,
        min_aoi_confluences=3,
        min_directional_delta_imbalance=0.0,
        required_aoi_criteria=["big_trades"],
        forbidden_aoi_criteria=["market_level"],
    )
    no_market_bar = pd.Series(
        _bar(
            "2024-01-03 10:00:00",
            prev_rth_high=120.0,
            prev_rth_low=80.0,
            overnight_high=120.0,
            overnight_low=80.0,
        )
    )

    tight_cap = YushTrend13Entry({**params, "max_signal_risk_points": 0.5})
    tight_cap.on_bar_close(pd.Series(_trend_long_context_bar()))
    assert tight_cap.on_bar_intrabar(no_market_bar, _trend_long_detail_rows()) is None

    ok_cap = YushTrend13Entry({**params, "max_signal_risk_points": 2.0})
    ok_cap.on_bar_close(pd.Series(_trend_long_context_bar()))
    signal = ok_cap.on_bar_intrabar(no_market_bar, _trend_long_detail_rows())

    assert signal is not None
    assert signal.direction == "long"
    assert ok_cap.name == "yush_trend_13"
    assert signal.metadata["aoi_confluence_criteria"] == "volume_profile,big_trades,delta_activity"


def test_yush_trend_14_applies_big_trade_no_market_filter_to_short_setup():
    params = _trend_entry_params(
        setup_mode="model2_trend_lvn_short",
        allow_long=False,
        allow_short=True,
        min_absorption_volume=20,
        min_aoi_confluences=3,
        min_directional_delta_imbalance=0.0,
        required_aoi_criteria=["big_trades"],
        forbidden_aoi_criteria=["market_level"],
    )

    missing_big_trade = YushTrend14Entry({**params, "min_large200_record_volume": 500})
    missing_big_trade.on_bar_close(pd.Series(_trend_context_bar()))
    no_market_bar = pd.Series(
        _bar(
            "2024-01-03 10:00:00",
            prev_rth_high=120.0,
            prev_rth_low=80.0,
            overnight_high=120.0,
            overnight_low=80.0,
        )
    )
    assert missing_big_trade.on_bar_intrabar(no_market_bar, _trend_short_detail_rows()) is None

    market_confluence = YushTrend14Entry(params)
    market_confluence.on_bar_close(pd.Series(_trend_context_bar()))
    assert market_confluence.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _trend_short_detail_rows()) is None

    entry = YushTrend14Entry(params)
    entry.on_bar_close(pd.Series(_trend_context_bar()))
    signal = entry.on_bar_intrabar(no_market_bar, _trend_short_detail_rows())

    assert signal is not None
    assert signal.direction == "short"
    assert entry.name == "yush_trend_14"
    assert signal.metadata["aoi_confluence_criteria"] == "volume_profile,big_trades,delta_activity"


def test_yush_trend_15_requires_big_trade_and_keeps_risk_cap_for_short_setup():
    params = _trend_entry_params(
        min_absorption_volume=20,
        min_aoi_confluences=2,
        min_directional_delta_imbalance=0.0,
        required_aoi_criteria=["big_trades"],
        max_signal_risk_points=2.0,
    )

    missing_big_trade = YushTrend15Entry({**params, "min_large200_record_volume": 500})
    missing_big_trade.on_bar_close(pd.Series(_trend_context_bar()))
    assert missing_big_trade.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _trend_short_detail_rows()) is None

    tight_cap = YushTrend15Entry({**params, "max_signal_risk_points": 0.5})
    tight_cap.on_bar_close(pd.Series(_trend_context_bar()))
    assert tight_cap.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _trend_short_detail_rows()) is None

    entry = YushTrend15Entry(params)
    entry.on_bar_close(pd.Series(_trend_context_bar()))
    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _trend_short_detail_rows())

    assert signal is not None
    assert signal.direction == "short"
    assert entry.name == "yush_trend_15"
    assert "big_trades" in signal.metadata["aoi_confluence_criteria"]
    assert signal.metadata["setup_mode"] == "model2_trend_lvn_short"


def test_yush_trend_1_detects_intrabar_short_lvn_pullback_rejection():
    entry = YushTrend1Entry(_trend_entry_params())
    entry.on_bar_close(pd.Series(_trend_context_bar()))

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _trend_short_detail_rows())

    assert signal is not None
    assert signal.direction == "short"
    assert signal.metadata["entry_mode"] == "intrabar"
    assert signal.metadata["setup_mode"] == "model2_trend_lvn_short"
    assert signal.metadata["video_model"] == "model2_trend_scid_intrabar"
    assert signal.metadata["profile_level_type"] == "lvn"
    assert signal.metadata["profile_level_price"] == 99.25
    assert signal.metadata["entry_reference_price"] == 99.0
    assert signal.metadata["intended_entry_timestamp"] == pd.Timestamp(
        "2024-01-03 10:00:08", tz="America/New_York"
    )
    assert signal.metadata["aoi_confluence_criteria"] == "volume_profile,market_level,big_trades,delta_activity"


def test_engine_opens_scid_intrabar_video_entry_at_tick_price():
    cfg = {
        "timeframe": "3m",
        "strategy_name": "video_exact_orderflow_playbook_scid_intrabar",
        "strategy": {
            "entry": {
                "module": "video_exact_orderflow_playbook_scid_intrabar",
                "params": _entry_params(),
            },
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 2}},
            "tp": {
                "module": "signal_price",
                "params": {"metadata_key": "signal_target_price", "fallback_target_r_multiple": 3.0},
            },
            "flatten_time": "15:55:00",
        },
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 0.0,
            "slippage_ticks": 0,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "daily_loss_limit": 10000,
            "daily_profit_stop": 10000,
        },
    }
    bars = pd.DataFrame(
        [
            _bar("2024-01-03 09:57:00", high=100.5, low=99.5, close=100.0),
            _bar("2024-01-03 10:00:00", high=100.5, low=99.75, close=100.25),
            _bar("2024-01-03 10:03:00", open=100.25, high=101.25, low=100.25, close=101.0),
        ]
    )

    result = BacktestEngine(cfg).run(bars, detail_data=_detail_rows())
    trades = result["trades"]

    assert result["diagnostics"]["intrabar_signals_generated"] == 1
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:21", tz="America/New_York")
    assert trade["entry_price"] == 100.25
    assert trade["target_price"] == 101.0


def test_engine_opens_yush_range_15_model1_range_at_tick_price():
    cfg = {
        "timeframe": "3m",
        "strategy_name": "yush_range_15",
        "strategy": {
            "entry": {
                "module": "yush_range_15",
                "params": _entry_params(),
            },
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 2}},
            "tp": {
                "module": "signal_price",
                "params": {"metadata_key": "signal_target_price", "fallback_target_r_multiple": 3.0},
            },
            "flatten_time": "15:55:00",
        },
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 0.0,
            "slippage_ticks": 0,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "daily_loss_limit": 10000,
            "daily_profit_stop": 10000,
        },
    }
    bars = pd.DataFrame(
        [
            _bar("2024-01-03 09:57:00", high=100.5, low=99.5, close=100.0),
            _bar("2024-01-03 10:00:00", high=100.5, low=99.75, close=100.25),
            _bar("2024-01-03 10:03:00", open=100.25, high=101.25, low=100.25, close=101.0),
        ]
    )

    result = BacktestEngine(cfg).run(bars, detail_data=_detail_rows())
    trades = result["trades"]

    assert result["diagnostics"]["intrabar_signals_generated"] == 1
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["strategy_name"] == "yush_range_15"
    assert trade["direction"] == "long"
    assert trade["setup_mode"] == "model1_range_value_edge_two_sided"
    assert trade["entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:21", tz="America/New_York")
    assert trade["entry_price"] == 100.25
    assert trade["target_price"] == 101.0


def test_yush_range_15_reuses_scid_model1_range_with_own_name():
    entry = YushRange15Entry(_entry_params())
    entry.on_bar_close(pd.Series(_bar("2024-01-03 09:57:00", high=100.5, low=99.5, close=100.0)))

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", high=100.5, low=99.75, close=100.25)),
        _detail_rows(),
    )

    assert signal is not None
    assert entry.name == "yush_range_15"
    assert signal.direction == "long"
    assert signal.metadata["video_model"] == "model1_range_scid_intrabar"


def test_engine_opens_yush_range_16_long_only_model1_range_at_tick_price():
    params = {**_entry_params(), "allow_short": False, "flatten_time": "15:53:00"}
    cfg = {
        "timeframe": "3m",
        "strategy_name": "yush_range_16",
        "strategy": {
            "entry": {
                "module": "yush_range_16",
                "params": params,
            },
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 2}},
            "tp": {
                "module": "signal_price",
                "params": {"metadata_key": "signal_target_price", "fallback_target_r_multiple": 3.0},
            },
            "flatten_time": "15:53:00",
        },
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 0.0,
            "slippage_ticks": 0,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "daily_loss_limit": 10000,
            "daily_profit_stop": 10000,
        },
    }
    bars = pd.DataFrame(
        [
            _bar("2024-01-03 09:57:00", high=100.5, low=99.5, close=100.0),
            _bar("2024-01-03 10:00:00", high=100.5, low=99.75, close=100.25),
            _bar("2024-01-03 10:03:00", open=100.25, high=101.25, low=100.25, close=101.0),
        ]
    )

    result = BacktestEngine(cfg).run(bars, detail_data=_detail_rows())
    trades = result["trades"]

    assert result["diagnostics"]["intrabar_signals_generated"] == 1
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["strategy_name"] == "yush_range_16"
    assert trade["direction"] == "long"
    assert trade["entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:21", tz="America/New_York")
    assert trade["target_price"] == 101.0


def test_yush_range_16_reuses_scid_model1_range_long_only_with_own_name():
    entry = YushRange16Entry({**_entry_params(), "allow_short": False})
    entry.on_bar_close(pd.Series(_bar("2024-01-03 09:57:00", high=100.5, low=99.5, close=100.0)))

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", high=100.5, low=99.75, close=100.25)),
        _detail_rows(),
    )

    assert signal is not None
    assert entry.name == "yush_range_16"
    assert signal.direction == "long"
    assert signal.metadata["video_model"] == "model1_range_scid_intrabar"


def test_engine_opens_yush_trend_1_at_intrabar_tick_price():
    cfg = {
        "timeframe": "3m",
        "strategy_name": "yush_trend_1",
        "strategy": {
            "entry": {
                "module": "yush_trend_1",
                "params": _trend_entry_params(),
            },
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 2}},
            "tp": {
                "module": "signal_price",
                "params": {"metadata_key": "signal_target_price", "fallback_target_r_multiple": 3.0},
            },
            "flatten_time": "15:55:00",
        },
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 0.0,
            "slippage_ticks": 0,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "daily_loss_limit": 10000,
            "daily_profit_stop": 10000,
        },
    }
    bars = pd.DataFrame(
        [
            _trend_context_bar("2024-01-03 09:57:00"),
            _bar("2024-01-03 10:00:00", open=99.5, high=99.5, low=99.0, close=99.0),
            _bar("2024-01-03 10:03:00", open=99.0, high=99.0, low=98.5, close=98.75),
        ]
    )

    result = BacktestEngine(cfg).run(bars, detail_data=_trend_short_detail_rows())
    trades = result["trades"]

    assert result["diagnostics"]["intrabar_signals_generated"] == 1
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["strategy_name"] == "yush_trend_1"
    assert trade["direction"] == "short"
    assert trade["entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:08", tz="America/New_York")
    assert trade["entry_price"] == 99.0
    assert trade["stop_price"] == 100.0
    assert trade["target_price"] == 98.75
    assert trade["exit_reason"] == "target"
