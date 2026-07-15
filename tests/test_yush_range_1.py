import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.entry import build_entry_module
from alphaquest.strategy_modules.entry.yush_range_1 import YushRange1Entry
from alphaquest.strategy_modules.entry.yush_range_2 import YushRange2Entry
from alphaquest.strategy_modules.entry.yush_range_3 import YushRange3Entry
from alphaquest.strategy_modules.entry.yush_range_4 import YushRange4Entry
from alphaquest.strategy_modules.entry.yush_range_5 import YushRange5Entry
from alphaquest.strategy_modules.entry.yush_range_6 import YushRange6Entry
from alphaquest.strategy_modules.entry.yush_range_7 import YushRange7Entry
from alphaquest.strategy_modules.entry.yush_range_8 import YushRange8Entry
from alphaquest.strategy_modules.entry.yush_range_9 import YushRange9Entry
from alphaquest.strategy_modules.entry.yush_range_10 import YushRange10Entry
from alphaquest.strategy_modules.entry.yush_range_11 import YushRange11Entry
from alphaquest.strategy_modules.entry.yush_range_12 import YushRange12Entry
from alphaquest.strategy_modules.entry.yush_range_13 import YushRange13Entry
from alphaquest.strategy_modules.entry.yush_range_14 import YushRange14Entry
from alphaquest.strategy_modules.entry.yush_range_17 import YushRange17Entry
from alphaquest.strategy_modules.entry.yush_range_18 import YushRange18Entry
from alphaquest.strategy_modules.entry.yush_range_19 import YushRange19Entry
from alphaquest.strategy_modules.entry.yush_range_20 import YushRange20Entry
from alphaquest.strategy_modules.entry.yush_range_21 import YushRange21Entry
from alphaquest.strategy_modules.entry.yush_range_22 import YushRange22Entry
from alphaquest.strategy_modules.entry.yush_range_23 import YushRange23Entry
from alphaquest.strategy_modules.entry.yush_range_24 import YushRange24Entry
from alphaquest.strategy_modules.entry.yush_range_25 import YushRange25Entry
from alphaquest.strategy_modules.entry.yush_range_26 import YushRange26Entry
from alphaquest.strategy_modules.entry.yush_range_27 import YushRange27Entry
from alphaquest.strategy_modules.entry.yush_range_28 import YushRange28Entry
from alphaquest.strategy_modules.entry.yush_range_29 import YushRange29Entry
from alphaquest.strategy_modules.entry.yush_range_30 import YushRange30Entry
from alphaquest.strategy_modules.entry.yush_range_31 import YushRange31Entry
from alphaquest.strategy_modules.entry.yush_trend_16 import YushTrend16Entry
from alphaquest.strategy_modules.entry.yush_trend_17 import YushTrend17Entry
from alphaquest.strategy_modules.entry.yush_trend_18 import YushTrend18Entry
from alphaquest.strategy_modules.entry.yush_trend_19 import YushTrend19Entry
from alphaquest.strategy_modules.entry.yush_trend_20 import YushTrend20Entry
from alphaquest.strategy_modules.entry.yush_trend_21 import YushTrend21Entry
from alphaquest.strategy_modules.entry.yush_trend_22 import YushTrend22Entry
from alphaquest.strategy_modules.entry.yush_trend_23 import YushTrend23Entry
from alphaquest.strategy_modules.entry.yush_trend_24 import YushTrend24Entry
from alphaquest.strategy_modules.entry.yush_trend_25 import YushTrend25Entry
from alphaquest.strategy_modules.entry.yush_trend_26 import YushTrend26Entry
from alphaquest.strategy_modules.entry.yush_trend_27 import YushTrend27Entry
from alphaquest.strategy_modules.entry.yush_trend_28 import YushTrend28Entry
from alphaquest.strategy_modules.entry.yush_trend_29 import YushTrend29Entry
from alphaquest.strategy_modules.entry.yush_trend_30 import YushTrend30Entry
from alphaquest.strategy_modules.entry.yush_trend_31 import YushTrend31Entry
from alphaquest.strategy_modules.entry.yush_trend_32 import YushTrend32Entry
from alphaquest.strategy_modules.entry.yush_trend_33 import YushTrend33Entry
from alphaquest.strategy_modules.entry.yush_trend_34 import YushTrend34Entry
from alphaquest.strategy_modules.entry.yush_trend_35 import YushTrend35Entry
from alphaquest.strategy_modules.entry.yush_trend_36 import YushTrend36Entry
from alphaquest.strategy_modules.entry.yush_trend_37 import YushTrend37Entry
from alphaquest.strategy_modules.entry.yush_trend_38 import YushTrend38Entry
from alphaquest.strategy_modules.entry.yush_trend_39 import YushTrend39Entry
from alphaquest.strategy_modules.entry.yush_trend_40 import YushTrend40Entry
from alphaquest.strategy_modules.entry.yush_trend_41 import YushTrend41Entry
from alphaquest.strategy_modules.entry.yush_trend_42 import YushTrend42Entry
from alphaquest.strategy_modules.entry.yush_trend_43 import YushTrend43Entry
from alphaquest.strategy_modules.entry.yush_trend_44 import YushTrend44Entry
from alphaquest.strategy_modules.entry.yush_trend_45 import YushTrend45Entry
from alphaquest.strategy_modules.entry.yush_trend_46 import YushTrend46Entry
from alphaquest.strategy_modules.entry.yush_trend_47 import YushTrend47Entry
from alphaquest.strategy_modules.entry.yush_trend_48 import YushTrend48Entry
from alphaquest.strategy_modules.entry.yush_trend_49 import YushTrend49Entry
from alphaquest.strategy_modules.entry.yush_trend_50 import YushTrend50Entry
from alphaquest.strategy_modules.entry.yush_trend_51 import YushTrend51Entry
from alphaquest.strategy_modules.entry.yush_trend_52 import YushTrend52Entry
from alphaquest.strategy_modules.entry.yush_trend_53 import YushTrend53Entry
from alphaquest.strategy_modules.entry.yush_trend_54 import YushTrend54Entry
from alphaquest.strategy_modules.entry.yush_trend_55 import YushTrend55Entry
from alphaquest.strategy_modules.entry.yush_trend_56 import YushTrend56Entry
from alphaquest.strategy_modules.entry.yush_trend_57 import YushTrend57Entry
from alphaquest.strategy_modules.entry.yush_trend_58 import YushTrend58Entry
from alphaquest.strategy_modules.entry.yush_trend_59 import YushTrend59Entry
from alphaquest.strategy_modules.entry.yush_trend_60 import YushTrend60Entry
from alphaquest.strategy_modules.entry.yush_trend_61 import YushTrend61Entry
from alphaquest.strategy_modules.entry.yush_trend_62 import YushTrend62Entry
from alphaquest.strategy_modules.entry.yush_trend_63 import YushTrend63Entry
from alphaquest.strategy_modules.entry.yush_trend_64 import YushTrend64Entry
from alphaquest.strategy_modules.entry.yush_trend_65 import YushTrend65Entry
from alphaquest.strategy_modules.entry.yush_trend_66 import YushTrend66Entry
from alphaquest.strategy_modules.entry.yush_trend_67 import YushTrend67Entry
from alphaquest.strategy_modules.entry.yush_trend_68 import YushTrend68Entry
from alphaquest.strategy_modules.entry.yush_trend_69 import YushTrend69Entry
from alphaquest.strategy_modules.entry.yush_trend_70 import YushTrend70Entry
from alphaquest.strategy_modules.entry.yush_trend_71 import YushTrend71Entry
from alphaquest.strategy_modules.entry.yush_trend_72 import YushTrend72Entry
from alphaquest.strategy_modules.entry.yush_trend_73 import YushTrend73Entry
from alphaquest.strategy_modules.entry.yush_trend_74 import YushTrend74Entry
from alphaquest.strategy_modules.entry.yush_trend_75 import YushTrend75Entry
from alphaquest.strategy_modules.entry.yush_trend_76 import YushTrend76Entry
from alphaquest.strategy_modules.entry.yush_trend_77 import YushTrend77Entry
from alphaquest.strategy_modules.entry.yush_trend_78 import YushTrend78Entry
from alphaquest.strategy_modules.entry.yush_trend_79 import YushTrend79Entry
from alphaquest.strategy_modules.entry.yush_trend_81 import YushTrend81Entry
from alphaquest.strategy_modules.entry.yush_trend_82 import YushTrend82Entry


TZ = "America/New_York"


def _bar(timestamp, **overrides):
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize(TZ)
    else:
        ts = ts.tz_convert(TZ)
    row = {
        "timestamp": ts,
        "session_date": ts.date(),
        "session_label": "RTH",
        "is_rth": True,
        "symbol": "ES",
        "open": 102.0,
        "high": 104.5,
        "low": 100.5,
        "close": 102.0,
        "volume": 1000,
        "prev_rth_high": 106.0,
        "prev_rth_low": 100.75,
        "prev_rth_close": 102.25,
        "overnight_high": 105.5,
        "overnight_low": 100.25,
    }
    row.update(overrides)
    return row


def _detail(timestamp, price, volume, buy=0, sell=0):
    return {
        "timestamp": pd.Timestamp(timestamp, tz=TZ),
        "open": price,
        "high": price,
        "low": price,
        "close": price,
        "volume": volume,
        "buy_volume": buy,
        "sell_volume": sell,
        "num_trades": 1,
        "execution_granularity": "scid_record",
    }


def _seed_profile_rows():
    rows = [
        _detail("2024-01-03 09:30:00", 100.5, 300, buy=150, sell=150),
        _detail("2024-01-03 09:30:01", 101.5, 800, buy=400, sell=400),
        _detail("2024-01-03 09:30:02", 102.5, 1500, buy=750, sell=750),
        _detail("2024-01-03 09:30:03", 103.5, 800, buy=400, sell=400),
        _detail("2024-01-03 09:30:04", 104.5, 100, buy=50, sell=50),
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _absorption_rows(include_confirmation=True, include_target=False):
    rows = [
        _detail("2024-01-03 10:00:00", 100.5, 400, buy=0, sell=400),
        _detail("2024-01-03 10:00:01", 101.25, 10, buy=10, sell=0),
    ]
    if include_confirmation:
        rows.append(_detail("2024-01-03 10:00:04", 101.25, 10, buy=10, sell=0))
    if include_target:
        rows.append(_detail("2024-01-03 10:00:05", 104.75, 10, buy=10, sell=0))
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _long_initiation_rows():
    rows = [
        _detail("2024-01-03 10:00:00", 100.5, 400, buy=400, sell=0),
        _detail("2024-01-03 10:00:01", 101.25, 10, buy=10, sell=0),
        _detail("2024-01-03 10:00:04", 101.25, 10, buy=10, sell=0),
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _long_failed_level_breakout_initiation_rows():
    rows = [
        _detail("2024-01-03 10:00:00", 100.0, 10, buy=0, sell=10),
        _detail("2024-01-03 10:00:01", 100.5, 400, buy=400, sell=0),
        _detail("2024-01-03 10:00:02", 101.25, 10, buy=10, sell=0),
        _detail("2024-01-03 10:00:03", 101.25, 10, buy=10, sell=0),
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _long_breakout_acceptance_initiation_rows():
    rows = [
        _detail("2024-01-03 10:00:00", 101.25, 400, buy=400, sell=0),
        _detail("2024-01-03 10:00:01", 102.25, 10, buy=10, sell=0),
        _detail("2024-01-03 10:00:02", 102.25, 10, buy=10, sell=0),
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _long_breakout_retest_initiation_rows():
    rows = [
        _detail("2024-01-03 10:00:00", 100.5, 400, buy=400, sell=0),
        _detail("2024-01-03 10:00:01", 101.75, 10, buy=10, sell=0),
        _detail("2024-01-03 10:00:02", 101.25, 10, buy=10, sell=0),
        _detail("2024-01-03 10:00:03", 101.25, 10, buy=10, sell=0),
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _long_value_area_acceptance_initiation_rows():
    rows = [
        _detail("2024-01-03 10:00:00", 104.5, 400, buy=400, sell=0),
        _detail("2024-01-03 10:00:01", 105.25, 10, buy=10, sell=0),
        _detail("2024-01-03 10:00:02", 105.25, 10, buy=10, sell=0),
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _long_opening_range_breakout_initiation_rows():
    rows = [
        _detail("2024-01-03 10:00:00", 105.25, 400, buy=400, sell=0),
        _detail("2024-01-03 10:00:01", 106.25, 10, buy=10, sell=0),
        _detail("2024-01-03 10:00:02", 106.25, 10, buy=10, sell=0),
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _long_exact_threshold_initiation_rows():
    rows = [
        _detail("2024-01-03 10:00:00", 100.5, 300, buy=300, sell=0),
        _detail("2024-01-03 10:00:01", 101.25, 10, buy=0, sell=0),
        _detail("2024-01-03 10:00:04", 101.25, 10, buy=0, sell=0),
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _short_exact_threshold_initiation_rows():
    rows = [
        _detail("2024-01-03 10:00:00", 103.5, 300, buy=0, sell=300),
        _detail("2024-01-03 10:00:01", 102.75, 10, buy=0, sell=0),
        _detail("2024-01-03 10:00:04", 102.75, 10, buy=0, sell=0),
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _short_absorption_rows_delta_fades_below_threshold():
    rows = [
        _detail("2024-01-03 10:00:00", 103.5, 300, buy=300, sell=0),
        _detail("2024-01-03 10:00:01", 103.5, 106, buy=0, sell=106),
        _detail("2024-01-03 10:00:02", 102.75, 1, buy=0, sell=1),
        _detail("2024-01-03 10:00:05", 102.75, 1, buy=0, sell=1),
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _long_absorption_rows_delta_fades_below_threshold():
    rows = [
        _detail("2024-01-03 10:00:00", 100.5, 300, buy=0, sell=300),
        _detail("2024-01-03 10:00:01", 100.5, 106, buy=106, sell=0),
        _detail("2024-01-03 10:00:02", 101.25, 1, buy=1, sell=0),
        _detail("2024-01-03 10:00:05", 101.25, 1, buy=1, sell=0),
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _short_absorption_rows():
    rows = [
        _detail("2024-01-03 10:00:00", 103.5, 400, buy=400, sell=0),
        _detail("2024-01-03 10:00:01", 102.75, 1, buy=0, sell=1),
        _detail("2024-01-03 10:00:04", 102.75, 1, buy=0, sell=1),
    ]
    detail = pd.DataFrame(rows)
    detail.attrs["detail_granularity"] = "scid_record"
    return detail


def _entry_params(**overrides):
    params = {
        "start_time": "10:00:00",
        "end_time": "15:00:00",
        "flatten_time": "15:55:00",
        "tick_size": 0.25,
        "bar_interval_minutes": 3,
        "profile_bucket_points": 1.0,
        "delta_bucket_points": 1.0,
        "value_area_fraction": 0.70,
        "lvn_poc_fraction": 0.20,
        "max_lvn_between_value_area": 1,
        "range_snapshot_minutes": 30,
        "max_range_change_pct": 0.20,
        "atr_period": 2,
        "atr_multiple": 2.0,
        "absorption_delta_threshold": 300,
        "absorption_hold_seconds": 3,
        "stop_offset_ticks": 2,
        "max_trades_per_day": 1,
        "min_profile_volume": 100,
        "min_profile_buckets": 3,
    }
    params.update(overrides)
    return params


def _trend_entry_params(**overrides):
    params = {
        "start_time": "10:00:00",
        "end_time": "15:00:00",
        "flatten_time": "15:53:00",
        "tick_size": 0.25,
        "bar_interval_minutes": 3,
        "value_area_fraction": 0.70,
        "lvn_quantile": 0.20,
        "min_prior_profile_bars": 10,
        "max_profile_distance_ticks": 64,
        "market_aoi_max_distance_ticks": 16,
        "aoi_reach_tolerance_ticks": 4,
        "min_probe_ticks": 1,
        "confirmation_ticks": 0,
        "min_absorption_volume": 20,
        "min_aoi_confluences": 2,
        "min_large200_record_volume": 200,
        "min_delta_activity_imbalance": 0.03,
        "min_directional_delta_imbalance": 0.0,
        "min_structure_bars": 10,
        "min_trend_move_ticks": 8,
        "max_signal_risk_points": 6.0,
        "delta_bucket_points": 1.0,
        "initiation_delta_threshold": 300.0,
        "initiation_hold_seconds": 3.0,
        "allow_opening_range_proxy": False,
        "profile_source": "cached_developing_vap",
        "min_developing_profile_bars": 10,
        "cached_profile_prefix": "developing_vap",
        "setup_mode": "model2_trend_lvn_short",
        "target_reference": "structural_or_midpoint",
        "stop_offset_ticks": 2,
        "max_trades_per_day": 1,
        "max_signals_per_session": 1,
        "allow_long": False,
        "allow_short": True,
    }
    params.update(overrides)
    return params


def _prime_entry(entry):
    entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 09:30:00")), _seed_profile_rows())
    for ts in ["2024-01-03 09:30:00", "2024-01-03 09:33:00", "2024-01-03 09:36:00", "2024-01-03 09:57:00"]:
        entry.on_bar_close(pd.Series(_bar(ts, low=100.5)))


def test_yush_range_1_enters_after_absorption_bucket_holds_for_three_seconds():
    entry = YushRange1Entry(_entry_params())
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _absorption_rows())

    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["entry_mode"] == "intrabar"
    assert signal.metadata["entry_reference_price"] == 101.25
    assert signal.metadata["intended_entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:04", tz=TZ)
    assert signal.metadata["signal_stop_price"] == 99.5
    assert signal.metadata["profile_poc"] == 102.5
    assert signal.metadata["profile_val"] == 101.0
    assert signal.metadata["profile_vah"] == 104.0
    assert signal.metadata["lvn_between_value_area_count"] <= 1
    assert signal.metadata["market_level_type"] == "PDL"
    assert signal.metadata["absorption_bucket_delta"] <= -300


def test_yush_range_1_rejects_absorption_without_full_hold_time():
    entry = YushRange1Entry(_entry_params())
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00")),
        _absorption_rows(include_confirmation=False),
    )

    assert signal is None


def test_yush_range_1_rejects_short_hold_when_bucket_delta_fades_below_threshold():
    entry = YushRange1Entry(_entry_params())
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_high=103.25, low=102.5)),
        _short_absorption_rows_delta_fades_below_threshold(),
    )

    assert signal is None


def test_yush_range_1_rejects_long_hold_when_bucket_delta_fades_below_threshold():
    entry = YushRange1Entry(_entry_params())
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00")),
        _long_absorption_rows_delta_fades_below_threshold(),
    )

    assert signal is None


def test_yush_range_2_uses_own_registered_setup_name():
    entry = YushRange2Entry(_entry_params(atr_multiple=0.5, start_time="09:30:00", end_time="11:30:00"))
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _absorption_rows())

    assert signal is not None
    assert entry.name == "yush_range_2"
    assert signal.metadata["setup_mode"] == "yush_range_2"
    assert signal.level_type.startswith("yush_range_2_")
    assert signal.metadata["atr_multiple"] == 0.5


def test_yush_range_5_keeps_bucket_stop_mechanics_with_own_setup_name():
    entry = YushRange5Entry(_entry_params(max_trades_per_day=100))
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _absorption_rows())

    assert signal is not None
    assert entry.name == "yush_range_5"
    assert signal.metadata["setup_mode"] == "yush_range_5"
    assert signal.level_type.startswith("yush_range_5_")
    assert signal.metadata["signal_stop_price"] == 99.5
    assert signal.metadata["target_points"] is None


def test_yush_range_6_can_filter_to_pdl_sweeps_only():
    entry = YushRange6Entry(_entry_params(allowed_market_level_types=["PDL"]))
    _prime_entry(entry)

    pdh_signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=None)),
        _absorption_rows(),
    )
    assert pdh_signal is None

    entry = YushRange6Entry(_entry_params(allowed_market_level_types=["PDL"]))
    _prime_entry(entry)
    pdl_signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _absorption_rows())

    assert pdl_signal is not None
    assert pdl_signal.metadata["setup_mode"] == "yush_range_6"
    assert pdl_signal.metadata["market_level_type"] == "PDL"


def test_yush_range_28_enters_after_failed_level_breakout_reclaim_and_initiation_hold():
    entry = YushRange28Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            confirmation_modes=["initiation"],
            absorption_hold_seconds=1.0,
            reclaim_hold_seconds=1.0,
            probe_ticks=2,
            reclaim_ticks=0,
            max_entry_distance_ticks=8,
        )
    )
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00")),
        _long_failed_level_breakout_initiation_rows(),
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["setup_mode"] == "yush_range_28"
    assert signal.metadata["market_level_type"] == "PDL"
    assert signal.metadata["market_sweep_source"] == "current_developing_scid_path"
    assert signal.metadata["orderflow_confirmation_type"] == "initiation"
    assert signal.metadata["orderflow_bucket_delta"] >= 300
    assert signal.metadata["reclaim_hold_seconds"] == 1.0
    assert signal.metadata["signal_stop_price"] == 99.5
    assert signal.sweep_low == 100.0
    assert signal.level_type.startswith("yush_range_28_")
    assert build_entry_module({"module": "yush_range_28", "params": _entry_params()}).name == "yush_range_28"


def test_yush_range_29_requires_balanced_profile_and_targets_opposite_value_edge():
    entry = YushRange29Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            confirmation_modes=["initiation"],
            absorption_hold_seconds=1.0,
            reclaim_hold_seconds=1.0,
            probe_ticks=2,
            reclaim_ticks=0,
            max_entry_distance_ticks=8,
            atr_multiple=2.0,
        )
    )
    _prime_entry(entry)
    assert (
        entry.on_bar_intrabar(
            pd.Series(_bar("2024-01-03 10:00:00")),
            _long_failed_level_breakout_initiation_rows(),
        )
        is None
    )

    entry = YushRange29Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            confirmation_modes=["initiation"],
            absorption_hold_seconds=1.0,
            reclaim_hold_seconds=1.0,
            probe_ticks=2,
            reclaim_ticks=0,
            max_entry_distance_ticks=8,
            atr_multiple=2.0,
            max_range_change_pct=1.0,
        )
    )
    _prime_entry(entry)
    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00")),
        _long_failed_level_breakout_initiation_rows(),
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["setup_mode"] == "yush_range_29"
    assert signal.metadata["market_level_type"] == "PDL"
    assert signal.metadata["target_reference"] == "opposite_developing_value_area_edge"
    assert signal.metadata["profile_val"] == 101.0
    assert signal.metadata["profile_vah"] == 104.0
    assert signal.metadata["signal_target_price"] == 104.0
    assert signal.metadata["signal_stop_price"] == 99.5
    assert signal.level_type.startswith("yush_range_29_")
    assert build_entry_module({"module": "yush_range_29", "params": _entry_params()}).name == "yush_range_29"


def test_yush_range_30_uses_absorption_for_value_area_reclaim():
    entry = YushRange30Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            confirmation_modes=["absorption"],
            absorption_hold_seconds=1.0,
            reclaim_hold_seconds=1.0,
            probe_ticks=2,
            reclaim_ticks=0,
            max_entry_distance_ticks=8,
            atr_multiple=2.0,
            max_range_change_pct=1.0,
        )
    )
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=101.0)),
        _absorption_rows(),
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["setup_mode"] == "yush_range_30"
    assert signal.metadata["market_level_type"] == "PDL"
    assert signal.metadata["orderflow_confirmation_type"] == "absorption"
    assert signal.metadata["orderflow_bucket_delta"] <= -300
    assert signal.metadata["target_reference"] == "opposite_developing_value_area_edge"
    assert signal.metadata["signal_target_price"] == 104.0
    assert signal.metadata["signal_stop_price"] == 100.0
    assert signal.level_type.startswith("yush_range_30_")
    assert build_entry_module({"module": "yush_range_30", "params": _entry_params()}).name == "yush_range_30"


def test_yush_trend_74_enters_after_breakout_acceptance_and_initiation_hold():
    entry = YushTrend74Entry(
        _entry_params(
            allowed_market_level_types=["PDH"],
            confirmation_modes=["initiation"],
            absorption_hold_seconds=1.0,
            breakout_hold_seconds=1.0,
            breakout_hold_ticks=0,
            probe_ticks=2,
            max_signal_risk_points=4.0,
        )
    )
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_high=101.0)),
        _long_breakout_acceptance_initiation_rows(),
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["setup_mode"] == "yush_trend_74"
    assert signal.metadata["market_level_type"] == "PDH"
    assert signal.metadata["orderflow_confirmation_type"] == "initiation"
    assert signal.metadata["orderflow_bucket_delta"] >= 300
    assert signal.metadata["breakout_hold_seconds"] == 1.0
    assert signal.metadata["signal_stop_price"] == 100.5
    assert signal.metadata["signal_risk_points"] == 1.75
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00:02", tz=TZ)
    assert signal.level_type.startswith("yush_trend_74_")
    assert build_entry_module({"module": "yush_trend_74", "params": _entry_params()}).name == "yush_trend_74"


def test_yush_trend_75_rescue_uses_breakout_acceptance_logic_with_fixed_identity():
    entry = YushTrend75Entry(
        _entry_params(
            allowed_market_level_types=["PDH"],
            confirmation_modes=["initiation"],
            absorption_hold_seconds=1.0,
            breakout_hold_seconds=1.0,
            breakout_hold_ticks=0,
            probe_ticks=2,
            max_signal_risk_points=8.0,
        )
    )
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_high=101.0)),
        _long_breakout_acceptance_initiation_rows(),
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["setup_mode"] == "yush_trend_75"
    assert signal.metadata["orderflow_confirmation_type"] == "initiation"
    assert signal.metadata["signal_risk_points"] == 1.75
    assert signal.level_type.startswith("yush_trend_75_")
    assert build_entry_module({"module": "yush_trend_75", "params": _entry_params()}).name == "yush_trend_75"


def test_yush_trend_76_exports_opening_range_fields_for_or_breakout():
    entry = YushTrend76Entry(
        _entry_params(
            allowed_market_level_types=["ORH", "ORL"],
            confirmation_modes=["initiation"],
            absorption_hold_seconds=1.0,
            breakout_hold_seconds=1.0,
            breakout_hold_ticks=0,
            probe_ticks=2,
            max_signal_risk_points=4.0,
        )
    )
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(
        pd.Series(
            _bar(
                "2024-01-03 10:00:00",
                prev_rth_high=None,
                prev_rth_low=None,
                prev_rth_close=None,
                overnight_high=None,
                overnight_low=None,
            )
        ),
        _long_opening_range_breakout_initiation_rows(),
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["setup_mode"] == "yush_trend_76"
    assert signal.metadata["market_level_type"] == "ORH"
    assert signal.opening_range_high == 104.5
    assert signal.opening_range_low == 100.5
    assert signal.opening_range_width == 4.0
    assert signal.metadata["target_reference"] == "opening_range_extension"
    assert signal.metadata["stop_reference"] == "opening_range_retest_boundary"
    assert signal.metadata["signal_risk_points"] == 2.25
    assert build_entry_module({"module": "yush_trend_76", "params": _entry_params()}).name == "yush_trend_76"


def test_yush_trend_77_allows_only_directional_public_edge_breakouts():
    entry = YushTrend77Entry(
        _entry_params(
            allowed_market_level_types=["PDH", "PDL"],
            confirmation_modes=["initiation"],
            absorption_hold_seconds=1.0,
            breakout_hold_seconds=1.0,
            breakout_hold_ticks=0,
            probe_ticks=2,
            max_signal_risk_points=4.0,
        )
    )
    _prime_entry(entry)

    blocked_signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_high=None, prev_rth_low=101.0)),
        _long_breakout_acceptance_initiation_rows(),
    )
    assert blocked_signal is None

    entry = YushTrend77Entry(
        _entry_params(
            allowed_market_level_types=["PDH", "PDL"],
            confirmation_modes=["initiation"],
            absorption_hold_seconds=1.0,
            breakout_hold_seconds=1.0,
            breakout_hold_ticks=0,
            probe_ticks=2,
            max_signal_risk_points=4.0,
        )
    )
    _prime_entry(entry)
    allowed_signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_high=101.0, prev_rth_low=None)),
        _long_breakout_acceptance_initiation_rows(),
    )

    assert allowed_signal is not None
    assert allowed_signal.direction == "long"
    assert allowed_signal.metadata["setup_mode"] == "yush_trend_77"
    assert allowed_signal.metadata["market_level_type"] == "PDH"
    assert allowed_signal.metadata["directional_level_filter"] == "outside_public_edge_only"
    assert allowed_signal.level_type.startswith("yush_trend_77_")
    assert build_entry_module({"module": "yush_trend_77", "params": _entry_params()}).name == "yush_trend_77"


def test_yush_trend_78_enters_only_after_breakout_retest_holds():
    params = _entry_params(
        allowed_market_level_types=["PDH", "PDL"],
        confirmation_modes=["initiation"],
        absorption_hold_seconds=1.0,
        probe_ticks=2,
        retest_tolerance_ticks=2,
        retest_hold_seconds=1.0,
        max_signal_risk_points=4.0,
    )
    entry = YushTrend78Entry(params)
    _prime_entry(entry)

    no_retest_signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_high=101.0, prev_rth_low=None)),
        _long_breakout_acceptance_initiation_rows(),
    )
    assert no_retest_signal is None

    entry = YushTrend78Entry(params)
    _prime_entry(entry)
    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_high=101.0, prev_rth_low=None)),
        _long_breakout_retest_initiation_rows(),
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["setup_mode"] == "yush_trend_78"
    assert signal.metadata["market_level_type"] == "PDH"
    assert signal.metadata["entry_pattern"] == "breakout_retest_continuation"
    assert signal.metadata["retest_timestamp"] == pd.Timestamp("2024-01-03 10:00:02", tz=TZ)
    assert signal.metadata["retest_confirmed_at"] == pd.Timestamp("2024-01-03 10:00:03", tz=TZ)
    assert signal.metadata["signal_stop_price"] == 100.5
    assert signal.metadata["signal_risk_points"] == 0.75
    assert signal.level_type.startswith("yush_trend_78_")
    assert build_entry_module({"module": "yush_trend_78", "params": _entry_params()}).name == "yush_trend_78"


def test_yush_trend_79_breaks_and_accepts_above_developing_vah():
    entry = YushTrend79Entry(
        _entry_params(
            confirmation_modes=["initiation"],
            absorption_hold_seconds=1.0,
            acceptance_hold_seconds=1.0,
            acceptance_hold_ticks=0,
            probe_ticks=2,
            max_signal_risk_points=4.0,
            max_range_change_pct=10.0,
        )
    )
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00")),
        _long_value_area_acceptance_initiation_rows(),
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["setup_mode"] == "yush_trend_79"
    assert signal.metadata["profile_level_type"] == "VAH"
    assert signal.metadata["profile_level_price"] == 104.0
    assert signal.metadata["orderflow_confirmation_type"] == "initiation"
    assert signal.metadata["orderflow_bucket_delta"] >= 300
    assert signal.metadata["signal_stop_price"] == 103.5
    assert signal.metadata["signal_risk_points"] == 1.75
    assert signal.metadata["target_reference"] == "fixed_r_after_developing_value_area_acceptance"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:00:02", tz=TZ)
    assert signal.level_type.startswith("yush_trend_79_")
    assert build_entry_module({"module": "yush_trend_79", "params": _entry_params()}).name == "yush_trend_79"


def test_yush_range_7_is_pdl_short_only():
    entry = YushRange7Entry(_entry_params(allowed_market_level_types=["PDL"], allow_long=False, allow_short=True))
    _prime_entry(entry)

    long_signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _absorption_rows())
    assert long_signal is None

    entry = YushRange7Entry(_entry_params(allowed_market_level_types=["PDL"], allow_long=False, allow_short=True))
    _prime_entry(entry)
    short_signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=103.25, high=103.5, low=102.5)),
        _short_absorption_rows(),
    )

    assert short_signal is not None
    assert entry.name == "yush_range_7"
    assert short_signal.direction == "short"
    assert short_signal.metadata["setup_mode"] == "yush_range_7"
    assert short_signal.metadata["market_level_type"] == "PDL"


def test_yush_range_8_short_pdl_reclaim_failure_does_not_require_profile_prime():
    entry = YushRange8Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            allow_long=False,
            allow_short=True,
            level_atr_multiple=1.0,
        )
    )
    for ts in ["2024-01-03 09:30:00", "2024-01-03 09:33:00", "2024-01-03 09:36:00", "2024-01-03 09:57:00"]:
        entry.on_bar_close(pd.Series(_bar(ts, low=100.5)))

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=103.25, high=103.5, low=102.5)),
        _short_absorption_rows(),
    )

    assert signal is not None
    assert signal.direction == "short"
    assert entry.name == "yush_range_8"
    assert signal.metadata["setup_mode"] == "yush_range_8"
    assert signal.metadata["market_level_type"] == "PDL"
    assert signal.metadata["pdl_reclaim_failure_profile_filter"] == "disabled"
    assert signal.metadata["pdl_reclaim_failure_range_filter"] == "disabled"
    assert signal.metadata["orderflow_confirmation_type"] == "absorption"


def test_yush_range_9_uses_fixed_distance_signal_prices_on_pdl_reclaim_failure():
    entry = YushRange9Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            allow_long=False,
            allow_short=True,
            level_atr_multiple=1.0,
            stop_points=5.0,
            target_points=10.0,
        )
    )
    for ts in ["2024-01-03 09:30:00", "2024-01-03 09:33:00", "2024-01-03 09:36:00", "2024-01-03 09:57:00"]:
        entry.on_bar_close(pd.Series(_bar(ts, low=100.5)))

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=103.25, high=103.5, low=102.5)),
        _short_absorption_rows(),
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.metadata["setup_mode"] == "yush_range_9"
    assert signal.metadata["signal_stop_price"] == 107.75
    assert signal.metadata["signal_target_price"] == 92.75


def test_yush_range_10_reuses_pdl_reclaim_failure_entry_with_own_name():
    entry = YushRange10Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            allow_long=False,
            allow_short=True,
            level_atr_multiple=1.0,
        )
    )
    for ts in ["2024-01-03 09:30:00", "2024-01-03 09:33:00", "2024-01-03 09:36:00", "2024-01-03 09:57:00"]:
        entry.on_bar_close(pd.Series(_bar(ts, low=100.5)))

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=103.25, high=103.5, low=102.5)),
        _short_absorption_rows(),
    )

    assert signal is not None
    assert signal.direction == "short"
    assert entry.name == "yush_range_10"
    assert signal.metadata["setup_mode"] == "yush_range_10"
    assert signal.metadata["market_level_type"] == "PDL"
    assert signal.metadata["signal_target_r_multiple"] == 2.0


def test_yush_range_11_reuses_pdl_reclaim_failure_entry_with_own_name():
    entry = YushRange11Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            allow_long=False,
            allow_short=True,
            level_atr_multiple=1.0,
        )
    )
    for ts in ["2024-01-03 09:30:00", "2024-01-03 09:33:00", "2024-01-03 09:36:00", "2024-01-03 09:57:00"]:
        entry.on_bar_close(pd.Series(_bar(ts, low=100.5)))

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=103.25, high=103.5, low=102.5)),
        _short_absorption_rows(),
    )

    assert signal is not None
    assert signal.direction == "short"
    assert entry.name == "yush_range_11"
    assert signal.metadata["setup_mode"] == "yush_range_11"
    assert signal.metadata["market_level_type"] == "PDL"


def test_yush_range_12_reuses_pdl_reclaim_failure_entry_with_own_name():
    entry = YushRange12Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            allow_long=False,
            allow_short=True,
            level_atr_multiple=1.0,
        )
    )
    for ts in ["2024-01-03 09:30:00", "2024-01-03 09:33:00", "2024-01-03 09:36:00", "2024-01-03 09:57:00"]:
        entry.on_bar_close(pd.Series(_bar(ts, low=100.5)))

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=103.25, high=103.5, low=102.5)),
        _short_absorption_rows(),
    )

    assert signal is not None
    assert signal.direction == "short"
    assert entry.name == "yush_range_12"
    assert signal.metadata["setup_mode"] == "yush_range_12"
    assert signal.metadata["market_level_type"] == "PDL"


def test_yush_range_17_rejects_pdl_reclaim_failure_when_known_bucket_stop_risk_is_too_wide():
    params = _entry_params(
        allowed_market_level_types=["PDL"],
        allow_long=False,
        allow_short=True,
        level_atr_multiple=1.0,
    )
    tight_cap = YushRange17Entry({**params, "max_signal_risk_points": 1.0})
    for ts in ["2024-01-03 09:30:00", "2024-01-03 09:33:00", "2024-01-03 09:36:00", "2024-01-03 09:57:00"]:
        tight_cap.on_bar_close(pd.Series(_bar(ts, low=100.5)))

    assert tight_cap.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=103.25, high=103.5, low=102.5)),
        _short_absorption_rows(),
    ) is None

    entry = YushRange17Entry({**params, "max_signal_risk_points": 4.0})
    for ts in ["2024-01-03 09:30:00", "2024-01-03 09:33:00", "2024-01-03 09:36:00", "2024-01-03 09:57:00"]:
        entry.on_bar_close(pd.Series(_bar(ts, low=100.5)))

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=103.25, high=103.5, low=102.5)),
        _short_absorption_rows(),
    )

    assert signal is not None
    assert signal.direction == "short"
    assert entry.name == "yush_range_17"
    assert signal.metadata["setup_mode"] == "yush_range_17"
    assert signal.metadata["signal_risk_points"] == 1.75
    assert signal.metadata["max_signal_risk_points"] == 4.0


def test_yush_range_18_reuses_pdl_reclaim_known_risk_cap_with_own_name():
    entry = YushRange18Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            allow_long=False,
            allow_short=True,
            level_atr_multiple=1.0,
            max_signal_risk_points=4.0,
        )
    )
    for ts in ["2024-01-03 09:30:00", "2024-01-03 09:33:00", "2024-01-03 09:36:00", "2024-01-03 09:57:00"]:
        entry.on_bar_close(pd.Series(_bar(ts, low=100.5)))

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=103.25, high=103.5, low=102.5)),
        _short_absorption_rows(),
    )

    assert signal is not None
    assert signal.direction == "short"
    assert entry.name == "yush_range_18"
    assert signal.metadata["setup_mode"] == "yush_range_18"
    assert signal.metadata["signal_risk_points"] == 1.75


def test_yush_range_20_reuses_pdl_reclaim_known_risk_cap_with_own_name():
    entry = YushRange20Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            allow_long=False,
            allow_short=True,
            level_atr_multiple=2.0,
            max_signal_risk_points=4.0,
        )
    )
    for ts in ["2024-01-03 09:30:00", "2024-01-03 09:33:00", "2024-01-03 09:36:00", "2024-01-03 09:57:00"]:
        entry.on_bar_close(pd.Series(_bar(ts, low=100.5)))

    signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=103.25, high=103.5, low=102.5)),
        _short_absorption_rows(),
    )

    assert signal is not None
    assert signal.direction == "short"
    assert entry.name == "yush_range_20"
    assert signal.metadata["setup_mode"] == "yush_range_20"
    assert signal.metadata["signal_risk_points"] == 1.75


def test_yush_range_21_reuses_pdl_reclaim_fixed_target_entry_with_own_name():
    entry = YushRange21Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            allow_long=False,
            allow_short=True,
            level_atr_multiple=2.0,
            max_signal_risk_points=4.0,
        )
    )

    assert entry.name == "yush_range_21"
    built = build_entry_module({"module": "yush_range_21", "params": _entry_params()})
    assert isinstance(built, YushRange21Entry)


def test_yush_range_22_reuses_pdl_reclaim_negative_rr_entry_with_own_name():
    entry = YushRange22Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            allow_long=False,
            allow_short=True,
            level_atr_multiple=2.0,
            max_signal_risk_points=4.0,
        )
    )

    assert entry.name == "yush_range_22"
    built = build_entry_module({"module": "yush_range_22", "params": _entry_params()})
    assert isinstance(built, YushRange22Entry)


def test_yush_range_23_reuses_pdl_reclaim_morning_negative_rr_entry_with_own_name():
    entry = YushRange23Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            allow_long=False,
            allow_short=True,
            level_atr_multiple=2.0,
            max_signal_risk_points=4.0,
        )
    )

    assert entry.name == "yush_range_23"
    built = build_entry_module({"module": "yush_range_23", "params": _entry_params()})
    assert isinstance(built, YushRange23Entry)


def test_yush_range_24_reuses_pdl_reclaim_morning_strong_absorption_entry_with_own_name():
    entry = YushRange24Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            allow_long=False,
            allow_short=True,
            level_atr_multiple=2.0,
            absorption_delta_threshold=500,
            max_signal_risk_points=4.0,
        )
    )

    assert entry.name == "yush_range_24"
    assert entry.absorption_delta_threshold == 500
    built = build_entry_module({"module": "yush_range_24", "params": _entry_params()})
    assert isinstance(built, YushRange24Entry)


def test_yush_range_25_reuses_pdl_reclaim_morning_target_grid_entry_with_own_name():
    entry = YushRange25Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            allow_long=False,
            allow_short=True,
            level_atr_multiple=2.0,
            absorption_delta_threshold=300,
            max_signal_risk_points=4.0,
        )
    )

    assert entry.name == "yush_range_25"
    built = build_entry_module({"module": "yush_range_25", "params": _entry_params()})
    assert isinstance(built, YushRange25Entry)


def test_yush_range_26_reuses_pdl_reclaim_morning_multi_entry_with_own_name():
    entry = YushRange26Entry(
        _entry_params(
            allowed_market_level_types=["PDL"],
            allow_long=False,
            allow_short=True,
            level_atr_multiple=2.0,
            absorption_delta_threshold=300,
            max_signal_risk_points=4.0,
            max_trades_per_day=3,
        )
    )

    assert entry.name == "yush_range_26"
    assert entry.max_trades_per_day == 3
    built = build_entry_module({"module": "yush_range_26", "params": _entry_params()})
    assert isinstance(built, YushRange26Entry)


def test_yush_range_27_enters_stop_order_two_ticks_outside_aoi_box():
    entry = YushRange27Entry(
        _entry_params(
            start_time="09:00:00",
            end_time="11:00:00",
            flatten_time="11:00:00",
            allowed_market_level_types=["PDL", "ORL"],
            profile_bucket_points=1.0,
            delta_bucket_points=1.0,
            range_snapshot_minutes=30.0,
            max_range_change_pct=10.0,
            min_failed_breakouts=0,
            min_reversal_touches=0,
            max_trades_per_day=3,
            max_aoi_width_points=3.0,
            entry_offset_ticks=2,
            stop_offset_ticks=2,
            max_stop_points=5.0,
            bubble_delta_threshold=300,
            big_trade_threshold=10000,
        )
    )
    entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 09:30:00")), _seed_profile_rows())
    for ts in ["2024-01-03 09:30:00", "2024-01-03 09:33:00", "2024-01-03 09:36:00", "2024-01-03 09:57:00"]:
        entry.on_bar_close(pd.Series(_bar(ts, low=100.5)))
    rows = pd.DataFrame(
        [
            _detail("2024-01-03 10:00:00", 99.50, 250, buy=250, sell=0),
            _detail("2024-01-03 10:00:00", 100.75, 400, buy=0, sell=400),
            _detail("2024-01-03 10:00:01", 101.50, 1, buy=1, sell=0),
        ]
    )
    rows.attrs["detail_granularity"] = "scid_record"

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), rows)

    assert signal is not None
    assert signal.direction == "long"
    assert entry.name == "yush_range_27"
    assert signal.metadata["aoi_market_level_type"] == "PDL"
    assert signal.metadata["aoi_profile_level_type"] == "VAL"
    assert signal.metadata["aoi_box_low"] == 100.75
    assert signal.metadata["aoi_box_high"] == 101.0
    assert signal.metadata["entry_reference_price"] == 101.5
    assert signal.metadata["signal_stop_price"] == 100.25
    assert signal.metadata["signal_target_price"] == 104.0
    assert signal.metadata["dynamic_stop_trigger_price"] == 102.5
    assert signal.metadata["dynamic_stop_price"] == 102.75
    assert signal.metadata["bubble_type"] == "delta_profile"
    assert signal.metadata["bubble_delta"] == -400
    built = build_entry_module({"module": "yush_range_27", "params": _entry_params()})
    assert isinstance(built, YushRange27Entry)


def test_yush_range_27_rejects_when_delta_bubble_fades_before_entry_tick():
    entry = YushRange27Entry(
        _entry_params(
            start_time="09:00:00",
            end_time="11:00:00",
            flatten_time="11:00:00",
            allowed_market_level_types=["PDL", "ORL"],
            profile_bucket_points=1.0,
            delta_bucket_points=1.0,
            range_snapshot_minutes=30.0,
            max_range_change_pct=10.0,
            min_failed_breakouts=0,
            min_reversal_touches=0,
            max_trades_per_day=3,
            max_aoi_width_points=3.0,
            entry_offset_ticks=2,
            stop_offset_ticks=2,
            max_stop_points=5.0,
            bubble_delta_threshold=300,
            big_trade_threshold=10000,
        )
    )
    entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 09:30:00")), _seed_profile_rows())
    for ts in ["2024-01-03 09:30:00", "2024-01-03 09:33:00", "2024-01-03 09:36:00", "2024-01-03 09:57:00"]:
        entry.on_bar_close(pd.Series(_bar(ts, low=100.5)))
    rows = pd.DataFrame(
        [
            _detail("2024-01-03 10:00:00", 100.75, 400, buy=0, sell=400),
            _detail("2024-01-03 10:00:00.500", 100.75, 125, buy=125, sell=0),
            _detail("2024-01-03 10:00:01", 101.50, 1, buy=1, sell=0),
        ]
    )
    rows.attrs["detail_granularity"] = "scid_record"

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), rows)

    assert signal is None


def test_yush_range_27_can_rearm_when_delta_bubble_returns_before_entry_tick():
    entry = YushRange27Entry(
        _entry_params(
            delta_bucket_points=1.0,
            bubble_delta_threshold=300,
        )
    )
    candidate = {
        "box_high": 101.0,
        "bubble": {
            "bubble_type": "delta_profile",
            "bubble_bucket": 100.0,
            "bubble_delta": -400.0,
            "bubble_bucket_points": 1.0,
        },
    }

    entry.state.delta_by_bucket = {100.0: -275.0}
    assert entry._entry_tick_delta_bubble("long", candidate) is None

    entry.state.delta_by_bucket = {100.0: -375.0}
    bubble = entry._entry_tick_delta_bubble("long", candidate)

    assert bubble is not None
    assert bubble["bubble_type"] == "delta_profile"
    assert bubble["bubble_delta"] == -375
    assert bubble["bubble_delta_timing"] == "entry_tick"


def test_yush_trend_16_confirms_short_delta_bucket_initiation_with_known_risk_cap():
    entry = YushTrend16Entry(_trend_entry_params(max_signal_risk_points=4.0))
    state = {
        "open": 101.25,
        "high": 101.25,
        "low": 99.75,
        "price": 99.75,
        "volume": 650.0,
        "signed_volume": -420.0,
        "confirmed_short_initiation": {
            "bucket_bottom": 100.0,
            "bucket_top": 101.0,
            "delta": -420.0,
            "hold_start": pd.Timestamp("2024-01-03 10:00:01", tz=TZ),
            "confirmed_at": pd.Timestamp("2024-01-03 10:00:04", tz=TZ),
        },
    }

    assert entry._intrabar_trend_initiation_confirms("short", 100.0, state)
    assert entry._known_signal_risk_points("short", state) == 2.0

    tight_entry = YushTrend16Entry(_trend_entry_params(max_signal_risk_points=1.0))
    assert tight_entry._known_signal_risk_points("short", state) > tight_entry.max_signal_risk_points


def test_yush_trend_17_requires_market_level_confluence():
    entry = YushTrend17Entry(_trend_entry_params(required_aoi_criteria=["market_level"]))
    state = {
        "volume": 100.0,
        "signed_volume": -25.0,
        "large_record_max_volume": 0.0,
        "large_record_volume": 0.0,
        "large_record_signed_volume": 0.0,
        "large_record_count": 0.0,
    }

    filtered = entry._intrabar_aoi_confluence(
        pd.Series(_bar("2024-01-03 10:00:00")),
        {},
        "short",
        "trend",
        90.0,
        state,
    )

    assert filtered["criteria"] == []
    assert filtered["details"]["missing_required_aoi_criteria"] == "market_level"


def test_yush_trend_18_reuses_known_risk_cap_with_own_name():
    entry = YushTrend18Entry(_trend_entry_params(max_signal_risk_points=4.0))
    state = {
        "price": 100.0,
        "high": 104.0,
        "low": 99.5,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -100.0,
        "max_buy_imbalance_volume": 100.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_18"
    assert not entry._intrabar_trend_pullback_confirms("short", 100.0, state)


def test_yush_trend_19_reuses_stronger_trend_logic_with_morning_window():
    entry = YushTrend19Entry(
        _trend_entry_params(
            start_time="10:00:00",
            end_time="11:59:59",
            max_signal_risk_points=4.0,
        )
    )
    state = {
        "price": 100.0,
        "high": 104.0,
        "low": 99.5,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -100.0,
        "max_buy_imbalance_volume": 100.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_19"
    assert entry.end_time.strftime("%H:%M:%S") == "11:59:59"
    assert not entry._intrabar_trend_pullback_confirms("short", 100.0, state)


def test_yush_trend_20_reuses_original_riskcap_pullback_logic_with_own_name():
    entry = YushTrend20Entry(_trend_entry_params(max_signal_risk_points=4.0))
    state = {
        "price": 100.0,
        "high": 104.0,
        "low": 99.5,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -100.0,
        "max_buy_imbalance_volume": 100.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_20"
    assert not entry._intrabar_trend_pullback_confirms("short", 100.0, state)


def test_yush_trend_21_forbids_market_level_confluence():
    entry = YushTrend21Entry(_trend_entry_params(forbidden_aoi_criteria=["market_level"]))
    state = {
        "volume": 100.0,
        "signed_volume": -25.0,
        "large_record_max_volume": 0.0,
        "large_record_volume": 0.0,
        "large_record_signed_volume": 0.0,
        "large_record_count": 0.0,
    }
    profile = {
        "poc": 101.0,
        "value_area_high": 102.0,
        "value_area_low": 99.0,
        "lvn_levels": [100.0],
    }

    filtered = entry._intrabar_aoi_confluence(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=100.0)),
        profile,
        "short",
        "trend",
        100.0,
        state,
    )

    assert entry.name == "yush_trend_21"
    assert filtered["criteria"] == []
    assert filtered["details"]["forbidden_aoi_criteria"] == "market_level"


def test_yush_trend_22_reuses_no_market_filter_with_morning_window():
    entry = YushTrend22Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            start_time="10:00:00",
            end_time="10:59:59",
        )
    )

    assert entry.name == "yush_trend_22"
    assert entry.end_time.strftime("%H:%M:%S") == "10:59:59"
    assert entry.forbidden_aoi_criteria == {"market_level"}


def test_yush_trend_23_reuses_original_riskcap_entry_with_own_name():
    entry = YushTrend23Entry(_trend_entry_params(max_signal_risk_points=4.0))
    state = {
        "price": 100.0,
        "high": 104.0,
        "low": 99.5,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -100.0,
        "max_buy_imbalance_volume": 100.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_23"
    assert not entry._intrabar_trend_pullback_confirms("short", 100.0, state)


def test_yush_trend_24_reuses_no_market_filter_with_own_name():
    entry = YushTrend24Entry(_trend_entry_params(forbidden_aoi_criteria=["market_level"]))
    state = {
        "volume": 100.0,
        "signed_volume": -25.0,
        "large_record_max_volume": 0.0,
        "large_record_volume": 0.0,
        "large_record_signed_volume": 0.0,
        "large_record_count": 0.0,
    }
    profile = {
        "poc": 101.0,
        "value_area_high": 102.0,
        "value_area_low": 99.0,
        "lvn_levels": [100.0],
    }

    filtered = entry._intrabar_aoi_confluence(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_low=100.0)),
        profile,
        "short",
        "trend",
        100.0,
        state,
    )

    assert entry.name == "yush_trend_24"
    assert filtered["criteria"] == []
    assert filtered["details"]["forbidden_aoi_criteria"] == "market_level"


def test_yush_trend_25_allows_multiple_session_signals_with_no_market_filter():
    entry = YushTrend25Entry(
        _trend_entry_params(forbidden_aoi_criteria=["market_level"], max_signals_per_session=3)
    )

    assert entry.name == "yush_trend_25"
    assert entry.max_signals_per_session == 3
    assert entry.forbidden_aoi_criteria == {"market_level"}


def test_yush_trend_26_reuses_no_market_filter_with_own_name():
    entry = YushTrend26Entry(_trend_entry_params(forbidden_aoi_criteria=["market_level"]))

    assert entry.name == "yush_trend_26"
    assert entry.forbidden_aoi_criteria == {"market_level"}


def test_yush_trend_27_reuses_no_market_min_target_logic_with_later_start():
    entry = YushTrend27Entry(
        _trend_entry_params(forbidden_aoi_criteria=["market_level"], start_time="11:00:00")
    )

    assert entry.name == "yush_trend_27"
    assert entry.start_time.strftime("%H:%M:%S") == "11:00:00"
    assert entry.forbidden_aoi_criteria == {"market_level"}


def test_yush_trend_28_requires_minimum_known_signal_risk():
    params = _trend_entry_params(forbidden_aoi_criteria=["market_level"], min_signal_risk_points=5.0)
    entry = YushTrend28Entry(params)
    state = {
        "price": 100.0,
        "high": 104.0,
        "low": 99.5,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -100.0,
        "max_buy_imbalance_volume": 100.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_28"
    assert entry.min_signal_risk_points == 5.0
    assert not entry._intrabar_trend_pullback_confirms("short", 100.0, state)

    wide_state = dict(state, high=105.0)
    assert entry._intrabar_trend_pullback_confirms("short", 100.0, wide_state)


def test_yush_trend_29_reuses_high_risk_logic_with_10et_window():
    entry = YushTrend29Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_signal_risk_points=5.0,
            start_time="10:00:00",
            end_time="10:59:59",
        )
    )

    assert entry.name == "yush_trend_29"
    assert entry.min_signal_risk_points == 5.0
    assert entry.start_time.strftime("%H:%M:%S") == "10:00:00"
    assert entry.end_time.strftime("%H:%M:%S") == "10:59:59"


def test_yush_trend_30_requires_directional_signed_volume_threshold():
    entry = YushTrend30Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_signed_volume=250.0,
        )
    )
    weak_state = {
        "price": 100.0,
        "high": 104.0,
        "low": 99.5,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -100.0,
        "max_buy_imbalance_volume": 100.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_30"
    assert entry.min_directional_signed_volume == 250.0
    assert not entry._intrabar_trend_pullback_confirms("short", 100.0, weak_state)

    strong_state = dict(weak_state, signed_volume=-300.0)
    assert entry._intrabar_trend_pullback_confirms("short", 100.0, strong_state)


def test_yush_trend_31_uses_stricter_directional_delta_ratio():
    entry = YushTrend31Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
        )
    )
    weak_state = {
        "price": 100.0,
        "high": 104.0,
        "low": 99.5,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -75.0,
        "max_buy_imbalance_volume": 100.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_31"
    assert entry.min_directional_delta_imbalance == 0.10
    assert not entry._intrabar_trend_pullback_confirms("short", 100.0, weak_state)

    strong_state = dict(weak_state, signed_volume=-125.0)
    assert entry._intrabar_trend_pullback_confirms("short", 100.0, strong_state)


def test_yush_trend_32_reuses_delta_ratio_gate_with_own_name():
    entry = YushTrend32Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
        )
    )
    state = {
        "price": 100.0,
        "high": 104.0,
        "low": 99.5,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -125.0,
        "max_buy_imbalance_volume": 100.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_32"
    assert entry._intrabar_trend_pullback_confirms("short", 100.0, state)


def test_yush_trend_33_requires_one_point_short_displacement_when_configured():
    entry = YushTrend33Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            confirmation_ticks=4,
        )
    )
    base_state = {
        "high": 104.0,
        "low": 98.75,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -125.0,
        "max_buy_imbalance_volume": 100.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_33"
    assert not entry._intrabar_trend_pullback_confirms("short", 100.0, dict(base_state, price=99.25))
    assert entry._intrabar_trend_pullback_confirms("short", 100.0, dict(base_state, price=99.0))


def test_yush_trend_34_reuses_displacement_entry_with_own_name():
    entry = YushTrend34Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            confirmation_ticks=4,
        )
    )
    state = {
        "price": 99.0,
        "high": 104.0,
        "low": 98.75,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -125.0,
        "max_buy_imbalance_volume": 100.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_34"
    assert entry._intrabar_trend_pullback_confirms("short", 100.0, state)


def test_yush_trend_35_uses_long_side_delta_ratio_gate():
    entry = YushTrend35Entry(
        _trend_entry_params(
            setup_mode="model2_trend_lvn_long",
            allow_long=True,
            allow_short=False,
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
        )
    )
    weak_state = {
        "price": 101.0,
        "high": 101.5,
        "low": 96.0,
        "open": 99.0,
        "volume": 1000.0,
        "signed_volume": 75.0,
        "max_sell_imbalance_volume": 100.0,
        "highest_sell_absorption_price": 99.0,
    }

    assert entry.name == "yush_trend_35"
    assert entry.allow_long
    assert not entry.allow_short
    assert not entry._intrabar_trend_pullback_confirms("long", 100.0, weak_state)
    assert entry._intrabar_trend_pullback_confirms("long", 100.0, dict(weak_state, signed_volume=125.0))


def test_yush_trend_36_reuses_short_displacement_entry_with_own_name():
    entry = YushTrend36Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            confirmation_ticks=4,
        )
    )
    state = {
        "price": 99.0,
        "high": 104.0,
        "low": 98.75,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -125.0,
        "max_buy_imbalance_volume": 100.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_36"
    assert entry._intrabar_trend_pullback_confirms("short", 100.0, state)


def test_yush_trend_37_reuses_delta_ratio_with_compact_risk_cap():
    entry = YushTrend37Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_signal_risk_points=4.0,
        )
    )
    compact_state = {
        "price": 100.0,
        "high": 103.5,
        "low": 99.5,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -125.0,
        "max_buy_imbalance_volume": 100.0,
        "lowest_buy_absorption_price": 101.0,
    }
    wide_state = dict(compact_state, high=104.0)

    assert entry.name == "yush_trend_37"
    assert entry.max_signal_risk_points == 4.0
    assert entry._intrabar_trend_pullback_confirms("short", 100.0, compact_state)
    assert not entry._intrabar_trend_pullback_confirms("short", 100.0, wide_state)


def test_yush_trend_38_reuses_delta_ratio_entry_with_own_name():
    entry = YushTrend38Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
        )
    )
    state = {
        "price": 100.0,
        "high": 104.0,
        "low": 99.5,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -125.0,
        "max_buy_imbalance_volume": 100.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_38"
    assert entry._intrabar_trend_pullback_confirms("short", 100.0, state)


def test_yush_trend_39_blocks_lunch_entry_window():
    entry = YushTrend39Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            blocked_start_time="12:00:00",
            blocked_end_time="12:59:59",
        )
    )

    assert entry.name == "yush_trend_39"
    assert not entry._timestamp_is_blocked(pd.Timestamp("2024-01-03 11:59:59", tz=TZ))
    assert entry._timestamp_is_blocked(pd.Timestamp("2024-01-03 12:00:00", tz=TZ))
    assert entry._timestamp_is_blocked(pd.Timestamp("2024-01-03 12:59:59", tz=TZ))
    assert not entry._timestamp_is_blocked(pd.Timestamp("2024-01-03 13:00:00", tz=TZ))
    assert entry._bar_block_window(pd.Series(_bar("2024-01-03 11:54:00"))) == "outside"
    assert entry._bar_block_window(pd.Series(_bar("2024-01-03 11:57:00"))) == "overlap"
    assert entry._bar_block_window(pd.Series(_bar("2024-01-03 12:00:00"))) == "inside"
    assert entry._bar_block_window(pd.Series(_bar("2024-01-03 12:57:00"))) == "overlap"
    assert entry._bar_block_window(pd.Series(_bar("2024-01-03 13:00:00"))) == "outside"


def test_yush_trend_40_reuses_no_lunch_delta_ratio_entry_with_own_name():
    entry = YushTrend40Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            blocked_start_time="12:00:00",
            blocked_end_time="12:59:59",
        )
    )

    assert entry.name == "yush_trend_40"
    assert entry._timestamp_is_blocked(pd.Timestamp("2024-01-03 12:30:00", tz=TZ))
    assert not entry._timestamp_is_blocked(pd.Timestamp("2024-01-03 13:00:00", tz=TZ))


def test_yush_trend_41_reuses_no_lunch_displacement_entry_with_own_name():
    entry = YushTrend41Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            confirmation_ticks=4,
            blocked_start_time="12:00:00",
            blocked_end_time="12:59:59",
        )
    )

    assert entry.name == "yush_trend_41"
    assert entry.confirmation_ticks == 4
    assert entry._timestamp_is_blocked(pd.Timestamp("2024-01-03 12:30:00", tz=TZ))


def test_yush_trend_42_reuses_no_lunch_negative_rr_entry_with_own_name():
    entry = YushTrend42Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            blocked_start_time="12:00:00",
            blocked_end_time="12:59:59",
            max_trades_per_day=4,
            max_signals_per_session=4,
        )
    )

    assert entry.name == "yush_trend_42"
    assert entry.max_trades_per_day == 4
    assert entry.max_signals_per_session == 4
    assert entry._timestamp_is_blocked(pd.Timestamp("2024-01-03 12:30:00", tz=TZ))


def test_yush_trend_43_reuses_no_lunch_negative_rr_entry_with_own_name():
    entry = YushTrend43Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            blocked_start_time="12:00:00",
            blocked_end_time="12:59:59",
            max_trades_per_day=4,
            max_signals_per_session=4,
        )
    )

    assert entry.name == "yush_trend_43"
    assert entry.max_trades_per_day == 4
    assert entry.max_signals_per_session == 4
    assert entry._timestamp_is_blocked(pd.Timestamp("2024-01-03 12:30:00", tz=TZ))


def test_yush_trend_44_reuses_no_lunch_negative_rr_entry_with_two_signal_cap():
    entry = YushTrend44Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            blocked_start_time="12:00:00",
            blocked_end_time="12:59:59",
            max_trades_per_day=2,
            max_signals_per_session=2,
        )
    )

    assert entry.name == "yush_trend_44"
    assert entry.max_trades_per_day == 2
    assert entry.max_signals_per_session == 2
    assert entry._timestamp_is_blocked(pd.Timestamp("2024-01-03 12:30:00", tz=TZ))


def test_yush_trend_45_reuses_no_lunch_fixed_1r_entry_with_own_name():
    entry = YushTrend45Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            blocked_start_time="12:00:00",
            blocked_end_time="12:59:59",
            max_trades_per_day=1,
            max_signals_per_session=1,
        )
    )

    assert entry.name == "yush_trend_45"
    assert entry.max_trades_per_day == 1
    assert entry.max_signals_per_session == 1
    assert entry._timestamp_is_blocked(pd.Timestamp("2024-01-03 12:30:00", tz=TZ))


def test_yush_trend_46_caps_same_bar_directional_signed_volume():
    entry = YushTrend46Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            blocked_start_time="12:00:00",
            blocked_end_time="12:59:59",
            max_directional_signed_volume=800.0,
        )
    )
    base_state = {
        "high": 105.0,
        "low": 95.0,
        "price": 100.0,
        "volume": 1000.0,
        "max_sell_imbalance_volume": 25.0,
        "highest_sell_absorption_price": 99.0,
        "max_buy_imbalance_volume": 25.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_46"
    assert entry._intrabar_trend_pullback_confirms(
        "short",
        100.0,
        {**base_state, "open": 101.0, "signed_volume": -700.0},
    )
    assert not entry._intrabar_trend_pullback_confirms(
        "short",
        100.0,
        {**base_state, "open": 101.0, "signed_volume": -900.0},
    )
    assert entry._intrabar_trend_pullback_confirms(
        "long",
        100.0,
        {**base_state, "open": 99.0, "signed_volume": 700.0},
    )
    assert not entry._intrabar_trend_pullback_confirms(
        "long",
        100.0,
        {**base_state, "open": 99.0, "signed_volume": 900.0},
    )


def test_yush_trend_47_reuses_signed_volume_cap_with_own_name():
    entry = YushTrend47Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=800.0,
        )
    )

    assert entry.name == "yush_trend_47"
    assert entry.max_directional_signed_volume == 800.0


def test_yush_trend_48_requires_minimum_signal_risk_points():
    entry = YushTrend48Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=800.0,
            min_signal_risk_points=3.0,
        )
    )
    base_state = {
        "low": 95.0,
        "price": 100.0,
        "open": 101.0,
        "volume": 1000.0,
        "signed_volume": -700.0,
        "max_sell_imbalance_volume": 25.0,
        "highest_sell_absorption_price": 99.0,
        "max_buy_imbalance_volume": 25.0,
        "lowest_buy_absorption_price": 101.0,
    }

    assert entry.name == "yush_trend_48"
    assert not entry._intrabar_trend_pullback_confirms(
        "short",
        100.0,
        {**base_state, "high": 102.0},
    )
    assert entry._intrabar_trend_pullback_confirms(
        "short",
        100.0,
        {**base_state, "high": 102.5},
    )


def test_yush_trend_49_reuses_prop_candidate_entry_with_own_name():
    entry = YushTrend49Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=800.0,
        )
    )

    assert entry.name == "yush_trend_49"
    assert entry.max_directional_signed_volume == 800.0


def test_yush_trend_50_reuses_prop_candidate_entry_with_own_name():
    entry = YushTrend50Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=800.0,
        )
    )

    assert entry.name == "yush_trend_50"
    assert entry.max_directional_signed_volume == 800.0
    built = build_entry_module({"module": "yush_trend_50", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend50Entry)


def test_yush_trend_51_reuses_prop_candidate_entry_with_own_name():
    entry = YushTrend51Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=800.0,
        )
    )

    assert entry.name == "yush_trend_51"
    assert entry.max_directional_signed_volume == 800.0
    built = build_entry_module({"module": "yush_trend_51", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend51Entry)


def test_yush_trend_52_reuses_prop_candidate_entry_with_own_name():
    entry = YushTrend52Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=800.0,
        )
    )

    assert entry.name == "yush_trend_52"
    assert entry.max_directional_signed_volume == 800.0
    built = build_entry_module({"module": "yush_trend_52", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend52Entry)


def test_yush_trend_53_reuses_prop_candidate_entry_with_own_name():
    entry = YushTrend53Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=800.0,
        )
    )

    assert entry.name == "yush_trend_53"
    assert entry.max_directional_signed_volume == 800.0
    built = build_entry_module({"module": "yush_trend_53", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend53Entry)


def test_yush_trend_54_reuses_prop_candidate_entry_with_own_name():
    entry = YushTrend54Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=800.0,
        )
    )

    assert entry.name == "yush_trend_54"
    assert entry.max_directional_signed_volume == 800.0
    built = build_entry_module({"module": "yush_trend_54", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend54Entry)


def test_yush_trend_55_reuses_prop_candidate_entry_with_own_name():
    entry = YushTrend55Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=800.0,
        )
    )

    assert entry.name == "yush_trend_55"
    assert entry.max_directional_signed_volume == 800.0
    built = build_entry_module({"module": "yush_trend_55", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend55Entry)


def test_yush_trend_56_reuses_no_lunch_structural_entry_with_own_name():
    entry = YushTrend56Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            blocked_start_time="12:00:00",
            blocked_end_time="12:59:59",
        )
    )

    assert entry.name == "yush_trend_56"
    assert entry.blocked_start_time.isoformat() == "12:00:00"
    built = build_entry_module({"module": "yush_trend_56", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend56Entry)


def test_yush_trend_57_reuses_prop_candidate_entry_with_own_name():
    entry = YushTrend57Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=800.0,
        )
    )

    assert entry.name == "yush_trend_57"
    assert entry.max_directional_signed_volume == 800.0
    built = build_entry_module({"module": "yush_trend_57", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend57Entry)


def test_yush_trend_58_reuses_prop_candidate_entry_with_own_name():
    entry = YushTrend58Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=800.0,
        )
    )

    assert entry.name == "yush_trend_58"
    assert entry.max_directional_signed_volume == 800.0
    built = build_entry_module({"module": "yush_trend_58", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend58Entry)


def test_yush_trend_59_reuses_min_target_entry_with_own_name():
    entry = YushTrend59Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.0,
        )
    )

    assert entry.name == "yush_trend_59"
    assert entry.forbidden_aoi_criteria == {"market_level"}
    built = build_entry_module({"module": "yush_trend_59", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend59Entry)


def test_yush_trend_60_reuses_prop_candidate_entry_with_own_name():
    entry = YushTrend60Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=500.0,
        )
    )

    assert entry.name == "yush_trend_60"
    assert entry.max_directional_signed_volume == 500.0
    built = build_entry_module({"module": "yush_trend_60", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend60Entry)


def test_yush_trend_61_reuses_prop_candidate_entry_with_own_name():
    entry = YushTrend61Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=500.0,
        )
    )

    assert entry.name == "yush_trend_61"
    assert entry.max_directional_signed_volume == 500.0
    built = build_entry_module({"module": "yush_trend_61", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend61Entry)


def test_yush_trend_62_reuses_no_lunch_structural_entry_with_own_name():
    entry = YushTrend62Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            blocked_start_time="12:00:00",
            blocked_end_time="12:59:59",
            min_directional_delta_imbalance=0.10,
        )
    )

    assert entry.name == "yush_trend_62"
    assert entry.forbidden_aoi_criteria == {"market_level"}
    built = build_entry_module({"module": "yush_trend_62", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend62Entry)


def test_yush_trend_63_requires_big_trade_and_delta_confluence():
    entry = YushTrend63Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=500.0,
        )
    )

    assert entry.name == "yush_trend_63"
    assert entry.max_directional_signed_volume == 500.0
    assert entry.required_aoi_criteria == {"big_trades", "delta_activity"}
    built = build_entry_module({"module": "yush_trend_63", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend63Entry)


def test_yush_trend_64_reuses_structural_grid_entry_with_own_name():
    entry = YushTrend64Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_signal_risk_points=6.0,
        )
    )

    assert entry.name == "yush_trend_64"
    assert entry.forbidden_aoi_criteria == {"market_level"}
    built = build_entry_module({"module": "yush_trend_64", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend64Entry)


def test_yush_trend_65_reuses_reversal_entry_with_own_name():
    entry = YushTrend65Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_signal_risk_points=6.0,
        )
    )

    assert entry.name == "yush_trend_65"
    assert entry.forbidden_aoi_criteria == {"market_level"}
    built = build_entry_module({"module": "yush_trend_65", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend65Entry)


def test_yush_trend_66_requires_held_lvn_rejection_before_entry():
    def prime(entry):
        context = pd.Series(
            _bar(
                "2024-01-03 09:57:00",
                open=102.0,
                high=101.0,
                low=97.75,
                close=98.0,
                developing_vap_poc=101.0,
                developing_vap_vah=103.0,
                developing_vap_val=99.0,
                developing_vap_lvn_near_close=100.0,
                developing_vap_total_volume=10000,
                developing_vap_bars=120,
            )
        )
        entry.current_session = context["session_date"]
        entry.current_session_bars = [context]

    params = _trend_entry_params(
        forbidden_aoi_criteria=[],
        min_aoi_confluences=2,
        min_structure_bars=1,
        min_directional_delta_imbalance=0.10,
        max_directional_signed_volume=500.0,
        entry_hold_seconds=3.0,
    )
    held_rows = pd.DataFrame(
        [
            _detail("2024-01-03 10:00:00", 100.0, 25, buy=25, sell=0),
            _detail("2024-01-03 10:00:01", 99.75, 125, buy=0, sell=125),
            _detail("2024-01-03 10:00:02", 99.75, 1, buy=0, sell=1),
            _detail("2024-01-03 10:00:04", 99.75, 1, buy=0, sell=1),
        ]
    )
    held_rows.attrs["detail_granularity"] = "scid_record"
    bar = pd.Series(
        _bar(
            "2024-01-03 10:00:00",
            prev_rth_high=None,
            prev_rth_low=None,
            prev_rth_close=None,
            overnight_high=None,
            overnight_low=None,
            high=100.25,
            low=99.5,
            close=99.75,
        )
    )

    entry = YushTrend66Entry(params)
    prime(entry)
    signal = entry.on_bar_intrabar(bar, held_rows)

    assert signal is not None
    assert signal.direction == "short"
    assert signal.metadata["entry_hold_seconds"] == 3.0
    assert signal.metadata["entry_hold_start"] == pd.Timestamp("2024-01-03 10:00:01", tz=TZ)
    assert signal.metadata["entry_hold_confirmed_at"] == pd.Timestamp("2024-01-03 10:00:04", tz=TZ)

    failed_rows = pd.DataFrame(
        [
            _detail("2024-01-03 10:00:00", 100.0, 25, buy=25, sell=0),
            _detail("2024-01-03 10:00:01", 99.75, 125, buy=0, sell=125),
            _detail("2024-01-03 10:00:02", 100.25, 1, buy=0, sell=1),
            _detail("2024-01-03 10:00:04", 99.75, 1, buy=0, sell=1),
        ]
    )
    failed_rows.attrs["detail_granularity"] = "scid_record"
    entry = YushTrend66Entry(params)
    prime(entry)

    assert entry.on_bar_intrabar(bar, failed_rows) is None
    built = build_entry_module({"module": "yush_trend_66", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend66Entry)


def test_yush_trend_67_holds_price_after_initial_orderflow_only():
    context = pd.Series(
        _bar(
            "2024-01-03 09:57:00",
            open=102.0,
            high=101.0,
            low=97.75,
            close=98.0,
            developing_vap_poc=101.0,
            developing_vap_vah=103.0,
            developing_vap_val=99.0,
            developing_vap_lvn_near_close=100.0,
            developing_vap_total_volume=10000,
            developing_vap_bars=120,
        )
    )
    entry = YushTrend67Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=[],
            min_aoi_confluences=2,
            min_structure_bars=1,
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=500.0,
            entry_hold_seconds=3.0,
        )
    )
    entry.current_session = context["session_date"]
    entry.current_session_bars = [context]
    rows = pd.DataFrame(
        [
            _detail("2024-01-03 10:00:00", 100.0, 25, buy=25, sell=0),
            _detail("2024-01-03 10:00:01", 99.75, 125, buy=0, sell=125),
            _detail("2024-01-03 10:00:04", 99.75, 1000, buy=0, sell=1000),
        ]
    )
    rows.attrs["detail_granularity"] = "scid_record"

    signal = entry.on_bar_intrabar(
        pd.Series(
            _bar(
                "2024-01-03 10:00:00",
                prev_rth_high=None,
                prev_rth_low=None,
                prev_rth_close=None,
                overnight_high=None,
                overnight_low=None,
                high=100.25,
                low=99.5,
                close=99.75,
            )
        ),
        rows,
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.metadata["entry_hold_policy"] == "price_only_after_initial_orderflow"
    assert signal.metadata["entry_hold_start"] == pd.Timestamp("2024-01-03 10:00:01", tz=TZ)
    assert signal.metadata["entry_hold_confirmed_at"] == pd.Timestamp("2024-01-03 10:00:04", tz=TZ)
    built = build_entry_module({"module": "yush_trend_67", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend67Entry)


def test_yush_trend_68_reuses_price_hold_entry_with_multi_signal_cap():
    entry = YushTrend68Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=500.0,
            entry_hold_seconds=3.0,
            max_trades_per_day=5,
            max_signals_per_session=3,
        )
    )

    assert entry.name == "yush_trend_68"
    assert entry.entry_hold_seconds == 3.0
    assert entry.max_trades_per_day == 5
    assert entry.max_signals_per_session == 3
    built = build_entry_module({"module": "yush_trend_68", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend68Entry)


def test_yush_trend_69_reuses_price_hold_entry_with_one_second_grid_neighbor():
    entry = YushTrend69Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=500.0,
            entry_hold_seconds=1.0,
        )
    )

    assert entry.name == "yush_trend_69"
    assert entry.entry_hold_seconds == 1.0
    built = build_entry_module({"module": "yush_trend_69", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend69Entry)


def test_yush_trend_70_reuses_price_hold_entry_for_fixed_dollar_branch():
    entry = YushTrend70Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=500.0,
            entry_hold_seconds=1.0,
        )
    )

    assert entry.name == "yush_trend_70"
    assert entry.entry_hold_seconds == 1.0
    built = build_entry_module({"module": "yush_trend_70", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend70Entry)


def test_yush_trend_71_reuses_price_hold_entry_for_fixed_100_target_branch():
    entry = YushTrend71Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=500.0,
            max_signal_risk_points=4.0,
            entry_hold_seconds=1.0,
        )
    )

    assert entry.name == "yush_trend_71"
    assert entry.entry_hold_seconds == 1.0
    assert entry.max_signal_risk_points == 4.0
    built = build_entry_module({"module": "yush_trend_71", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend71Entry)


def test_yush_trend_72_reuses_min_target_structural_entry_with_risk_cap_grid():
    entry = YushTrend72Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            max_signal_risk_points=4.0,
            target_reference="structural_min20r_or_3r_fallback_staged",
        )
    )

    assert entry.name == "yush_trend_72"
    assert entry.max_signal_risk_points == 4.0
    built = build_entry_module({"module": "yush_trend_72", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend72Entry)


def test_yush_trend_73_reuses_price_hold_entry_with_structural_target():
    entry = YushTrend73Entry(
        _trend_entry_params(
            forbidden_aoi_criteria=["market_level"],
            min_directional_delta_imbalance=0.10,
            max_directional_signed_volume=500.0,
            max_signal_risk_points=4.0,
            entry_hold_seconds=1.0,
            target_reference="structural_price_hold_min_target_staged",
        )
    )

    assert entry.name == "yush_trend_73"
    assert entry.entry_hold_seconds == 1.0
    assert entry.max_signal_risk_points == 4.0
    built = build_entry_module({"module": "yush_trend_73", "params": _trend_entry_params()})
    assert isinstance(built, YushTrend73Entry)


def test_yush_range_19_requires_market_level_confluence():
    entry = YushRange19Entry(
        _trend_entry_params(
            required_aoi_criteria=["market_level"],
            setup_mode="model1_range_value_edge_two_sided",
            allow_long=True,
            allow_short=False,
        )
    )
    state = {
        "volume": 100.0,
        "signed_volume": -25.0,
        "large_record_max_volume": 0.0,
        "large_record_volume": 0.0,
        "large_record_signed_volume": 0.0,
        "large_record_count": 0.0,
    }

    filtered = entry._intrabar_aoi_confluence(
        pd.Series(_bar("2024-01-03 10:00:00")),
        {},
        "long",
        "range",
        90.0,
        state,
    )

    assert filtered["criteria"] == []
    assert filtered["details"]["missing_required_aoi_criteria"] == "market_level"


def test_yush_range_1_does_not_accept_initiation_by_default():
    entry = YushRange1Entry(_entry_params())
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _long_initiation_rows())

    assert signal is None


def test_yush_range_3_accepts_initiation_with_one_tick_profile_and_fixed_exit_prices():
    entry = YushRange3Entry(
        _entry_params(
            confirmation_modes=["absorption", "initiation"],
            profile_bucket_points=0.25,
            stop_points=5.0,
            target_points=10.0,
            max_trades_per_day=100,
        )
    )
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _long_initiation_rows())

    assert signal is not None
    assert signal.direction == "long"
    assert entry.name == "yush_range_3"
    assert signal.metadata["setup_mode"] == "yush_range_3"
    assert signal.metadata["orderflow_confirmation_type"] == "initiation"
    assert signal.metadata["profile_bucket_points"] == 0.25
    assert signal.metadata["delta_bucket_points"] == 1.0
    assert signal.metadata["entry_reference_price"] == 101.25
    assert signal.metadata["signal_stop_price"] == 96.25
    assert signal.metadata["signal_target_price"] == 111.25


def test_yush_range_3_requires_strict_initiation_threshold():
    entry = YushRange3Entry(
        _entry_params(
            confirmation_modes=["initiation"],
            profile_bucket_points=0.25,
            stop_points=5.0,
            target_points=10.0,
            max_trades_per_day=100,
        )
    )
    _prime_entry(entry)

    long_signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00")),
        _long_exact_threshold_initiation_rows(),
    )
    assert long_signal is None

    entry = YushRange3Entry(
        _entry_params(
            confirmation_modes=["initiation"],
            profile_bucket_points=0.25,
            stop_points=5.0,
            target_points=10.0,
            max_trades_per_day=100,
        )
    )
    _prime_entry(entry)
    short_signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", prev_rth_high=103.25, low=102.5)),
        _short_exact_threshold_initiation_rows(),
    )

    assert short_signal is None


def test_yush_range_4_uses_developing_value_area_edge_sweep_without_public_level():
    entry = YushRange4Entry(
        _entry_params(
            confirmation_modes=["absorption", "initiation"],
            profile_bucket_points=1.0,
            stop_points=5.0,
            target_points=10.0,
            max_trades_per_day=100,
        )
    )
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(
        pd.Series(
            _bar(
                "2024-01-03 10:00:00",
                prev_rth_high=None,
                prev_rth_low=None,
                prev_rth_close=None,
                overnight_high=None,
                overnight_low=None,
            )
        ),
        _absorption_rows(),
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.metadata["setup_mode"] == "yush_range_4"
    assert signal.metadata["market_level_type"] == "VAL"
    assert signal.metadata["market_level_price"] == 101.0
    assert signal.metadata["market_sweep_source"] == "current_developing_value_area_edge"
    assert signal.metadata["orderflow_confirmation_type"] == "absorption"


def test_yush_range_13_uses_value_edge_sweep_with_bucket_stop_and_2r_target():
    entry = YushRange13Entry(
        _entry_params(
            confirmation_modes=["absorption"],
            profile_bucket_points=1.0,
            max_trades_per_day=100,
        )
    )
    _prime_entry(entry)

    signal = entry.on_bar_intrabar(
        pd.Series(
            _bar(
                "2024-01-03 10:00:00",
                prev_rth_high=None,
                prev_rth_low=None,
                prev_rth_close=None,
                overnight_high=None,
                overnight_low=None,
            )
        ),
        _absorption_rows(),
    )

    assert signal is not None
    assert signal.direction == "long"
    assert entry.name == "yush_range_13"
    assert signal.metadata["setup_mode"] == "yush_range_13"
    assert signal.metadata["market_level_type"] == "VAL"
    assert signal.metadata["signal_stop_price"] == 99.5
    assert signal.metadata["signal_target_r_multiple"] == 2.0
    assert "signal_target_price" not in signal.metadata


def test_yush_range_14_is_long_only_value_edge_absorption_bucket_setup():
    entry = YushRange14Entry(
        _entry_params(
            confirmation_modes=["absorption"],
            profile_bucket_points=1.0,
            max_trades_per_day=100,
            allow_long=True,
            allow_short=False,
        )
    )
    _prime_entry(entry)

    short_signal = entry.on_bar_intrabar(
        pd.Series(_bar("2024-01-03 10:00:00", high=103.5, low=102.5)),
        _short_absorption_rows(),
    )
    assert short_signal is None

    entry = YushRange14Entry(
        _entry_params(
            confirmation_modes=["absorption"],
            profile_bucket_points=1.0,
            max_trades_per_day=100,
            allow_long=True,
            allow_short=False,
        )
    )
    _prime_entry(entry)
    long_signal = entry.on_bar_intrabar(pd.Series(_bar("2024-01-03 10:00:00")), _absorption_rows())

    assert long_signal is not None
    assert long_signal.direction == "long"
    assert entry.name == "yush_range_14"
    assert long_signal.metadata["setup_mode"] == "yush_range_14"
    assert long_signal.metadata["market_level_type"] == "VAL"
    assert long_signal.metadata["signal_stop_price"] == 99.5
    assert long_signal.metadata["signal_target_r_multiple"] == 2.0


def test_engine_opens_yush_range_3_with_fixed_exits_from_actual_entry_price():
    cfg = {
        "timeframe": "3m",
        "strategy_name": "yush_range_3",
        "strategy": {
            "entry": {
                "module": "yush_range_3",
                "params": _entry_params(
                    confirmation_modes=["absorption", "initiation"],
                    profile_bucket_points=0.25,
                    stop_points=5.0,
                    target_points=10.0,
                    max_trades_per_day=100,
                ),
            },
            "sl": {"module": "points_from_entry", "params": {"stop_points": 5.0}},
            "tp": {"module": "points_from_entry", "params": {"target_points": 10.0, "tick_size": 0.25}},
            "flatten_time": "15:55:00",
        },
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.5,
            "commission_per_contract": 0.0,
            "slippage_ticks": 1,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "daily_loss_limit": 10000,
            "daily_profit_stop": 10000,
        },
    }
    bar_times = pd.date_range("2024-01-03 09:30:00", "2024-01-03 10:03:00", freq="3min", tz=TZ)
    bars = pd.DataFrame(
        [
            _bar(ts, high=112.0 if ts.minute == 0 and ts.hour == 10 else 104.5)
            for ts in bar_times
        ]
    )
    detail = pd.concat(
        [
            _seed_profile_rows(),
            _long_initiation_rows(),
            pd.DataFrame([_detail("2024-01-03 10:00:05", 111.5, 10, buy=10, sell=0)]),
        ],
        ignore_index=True,
    )
    detail.attrs["detail_granularity"] = "scid_record"

    result = BacktestEngine(cfg).run(bars, detail_data=detail)
    trades = result["trades"]

    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["entry_price"] == 101.5
    assert trade["stop_price"] == 96.5
    assert trade["target_price"] == 111.5
    assert trade["exit_reason"] == "target"


def test_engine_opens_yush_range_1_at_intrabar_tick_with_bucket_stop_and_2r_target():
    cfg = {
        "timeframe": "3m",
        "strategy_name": "yush_range_1",
        "strategy": {
            "entry": {"module": "yush_range_1", "params": _entry_params()},
            "sl": {"module": "signal_price", "params": {"metadata_key": "signal_stop_price"}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 2.0}},
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
    bar_times = pd.date_range("2024-01-03 09:30:00", "2024-01-03 10:03:00", freq="3min", tz=TZ)
    bars = pd.DataFrame(
        [
            _bar(
                ts,
                low=98.0 if ts.minute == 0 and ts.hour == 10 else 100.5,
                high=105.0 if ts.minute == 0 and ts.hour == 10 else 104.5,
            )
            for ts in bar_times
        ]
    )
    detail = pd.concat(
        [
            _seed_profile_rows(),
            _absorption_rows(include_target=True),
            pd.DataFrame([_detail("2024-01-03 10:00:06", 98.0, 10, buy=0, sell=10)]),
        ],
        ignore_index=True,
    )
    detail.attrs["detail_granularity"] = "scid_record"

    result = BacktestEngine(cfg).run(bars, detail_data=detail)
    trades = result["trades"]

    assert result["diagnostics"]["intrabar_signals_generated"] == 1
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["entry_timestamp"] == pd.Timestamp("2024-01-03 10:00:04", tz=TZ)
    assert trade["entry_price"] == 101.25
    assert trade["stop_price"] == 99.5
    assert trade["target_price"] == 104.75
    assert trade["exit_reason"] == "target"
    assert trade["max_favorable_excursion"] == 3.5
    assert trade["max_adverse_excursion"] == 0.0


def _range31_profile(**overrides):
    row = {
        "developing_vap_session_yyyymmdd": 20240103,
        "developing_vap_poc": 102.0,
        "developing_vap_vah": 104.0,
        "developing_vap_val": 100.5,
        "developing_vap_lvn_near_high": 103.25,
        "developing_vap_lvn_near_low": 101.0,
        "developing_vap_lvn_count": 1,
        "developing_vap_total_volume": 5000,
        "developing_vap_price_levels": 16,
    }
    row.update(overrides)
    return row


def _range31_entry(**overrides):
    params = {
        "setup_mode": "developing_value_large_record_trap_two_sided",
        "start_time": "09:33:00",
        "end_time": "11:00:00",
        "bar_interval_minutes": 3,
        "tick_size": 0.25,
        "range_snapshot_minutes": 6,
        "max_range_change_pct": 0.20,
        "min_probe_ticks": 1,
        "confirmation_ticks": 0,
        "stop_offset_ticks": 2,
        "max_signal_risk_points": 6.0,
        "min_profile_total_volume": 100,
        "min_profile_price_levels": 3,
        "max_lvn_count": 3,
        "min_large200_record_volume": 200,
        "min_large200_signed_share": 0.35,
        "min_bar_signed_imbalance": 0.05,
        "max_trades_per_day": 3,
    }
    params.update(overrides)
    return YushRange31Entry(params)


def _seed_range31_session(entry):
    assert entry.on_bar_close(
        _bar("2024-01-03 09:30:00", high=104.0, low=100.0, close=102.0, signed_volume=0, **_range31_profile())
    ) is None
    assert entry.on_bar_close(
        _bar("2024-01-03 09:33:00", high=104.0, low=100.0, close=102.0, signed_volume=0, **_range31_profile())
    ) is None


def test_yush_range_31_developing_value_large_record_trap_signal():
    entry = _range31_entry()
    _seed_range31_session(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:36:00",
            open=100.75,
            high=103.75,
            low=100.0,
            close=101.25,
            volume=1200,
            signed_volume=-600,
            large200_record_max_volume=500,
            large200_record_volume=800,
            large200_record_signed_volume=-600,
            large200_record_count=2,
            **_range31_profile(),
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "yush_range_31_val_trap"
    assert signal.metadata["entry_mode"] == "bar_close"
    assert signal.metadata["signal_timestamp"] == pd.Timestamp("2024-01-03 09:39:00", tz=TZ)
    assert signal.metadata["boundary_type"] == "val"
    assert signal.metadata["signal_stop_price"] == 99.5
    assert signal.metadata["signal_target_price"] == 104.0
    assert signal.metadata["large200_record_dominant_side"] == "sell"
    assert signal.metadata["profile_poc_middle_third"] is True
    assert signal.metadata["range_change_pct"] == 0.0


def test_yush_range_31_rejects_uncentered_poc():
    entry = _range31_entry()
    _seed_range31_session(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:36:00",
            open=100.75,
            high=103.75,
            low=100.0,
            close=101.25,
            volume=1200,
            signed_volume=-600,
            large200_record_max_volume=500,
            large200_record_volume=800,
            large200_record_signed_volume=-600,
            large200_record_count=2,
            **_range31_profile(developing_vap_poc=100.75),
        )
    )

    assert signal is None


def test_build_entry_module_registers_yush_range_31():
    entry = build_entry_module({"module": "yush_range_31", "params": {"range_snapshot_minutes": 6}})
    assert isinstance(entry, YushRange31Entry)


def test_yush_trend_81_acceptance_does_not_require_stable_range_or_centered_poc():
    entry = YushTrend81Entry(
        {
            "setup_mode": "developing_value_large_record_acceptance_two_sided",
            "start_time": "09:33:00",
            "end_time": "11:00:00",
            "bar_interval_minutes": 3,
            "tick_size": 0.25,
            "range_snapshot_minutes": 30,
            "max_lvn_count": 9999,
            "min_large200_record_volume": 200,
            "min_large200_signed_share": 0.35,
            "min_bar_signed_imbalance": 0.03,
            "max_signal_risk_points": 20.0,
        }
    )

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 10:30:00",
            open=101.0,
            high=104.75,
            low=99.0,
            close=104.25,
            volume=1200,
            signed_volume=600,
            large200_record_max_volume=500,
            large200_record_volume=800,
            large200_record_signed_volume=600,
            large200_record_count=2,
            **_range31_profile(
                developing_vap_poc=100.75,
                developing_vap_vah=103.75,
                developing_vap_val=100.0,
                developing_vap_lvn_count=12,
            ),
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "yush_trend_81_vah_acceptance"
    assert signal.metadata["trend_branch"] is True
    assert signal.metadata["range_condition_required"] is False
    assert signal.metadata["profile_poc_middle_third_required"] is False
    assert signal.metadata["profile_poc_middle_third"] is False


def test_build_entry_module_registers_yush_trend_81():
    entry = build_entry_module({"module": "yush_trend_81", "params": {"max_signal_risk_points": 20.0}})
    assert isinstance(entry, YushTrend81Entry)


def _trend82_entry(**overrides):
    params = {
        "setup_mode": "developing_value_large_record_acceptance_two_sided",
        "start_time": "09:33:00",
        "end_time": "11:00:00",
        "bar_interval_minutes": 3,
        "tick_size": 0.25,
        "max_lvn_count": 9999,
        "min_large200_record_volume": 200,
        "min_large200_signed_share": 0.35,
        "min_bar_signed_imbalance": 0.03,
        "max_signal_risk_points": 20.0,
        "compression_lookback_bars": 4,
        "min_compression_history": 3,
        "max_value_area_width_rank": 0.34,
    }
    params.update(overrides)
    return YushTrend82Entry(params)


def _seed_trend82_widths(entry):
    for index, (vah, val) in enumerate([(112.0, 100.0), (110.0, 100.0), (108.0, 100.0)]):
        assert entry.on_bar_close(
            _bar(
                f"2024-01-03 09:{30 + index * 3:02d}:00",
                open=101.0,
                high=104.0,
                low=100.0,
                close=102.0,
                signed_volume=0,
                **_range31_profile(
                    developing_vap_poc=(vah + val) / 2.0,
                    developing_vap_vah=vah,
                    developing_vap_val=val,
                    developing_vap_lvn_count=12,
                ),
            )
        ) is None


def test_yush_trend_82_requires_compressed_value_area_before_large_record_acceptance():
    entry = _trend82_entry()
    _seed_trend82_widths(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:39:00",
            open=101.0,
            high=104.75,
            low=99.0,
            close=104.25,
            volume=1200,
            signed_volume=600,
            large200_record_max_volume=500,
            large200_record_volume=800,
            large200_record_signed_volume=600,
            large200_record_count=2,
            **_range31_profile(
                developing_vap_poc=102.0,
                developing_vap_vah=103.75,
                developing_vap_val=100.0,
                developing_vap_lvn_count=12,
            ),
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.level_type == "yush_trend_82_vah_acceptance"
    assert signal.metadata["compression_branch"] is True
    assert signal.metadata["value_area_width"] == 3.75
    assert signal.metadata["value_area_width_rank"] == 0.0
    assert signal.metadata["max_value_area_width_rank"] == 0.34


def test_yush_trend_82_rejects_wide_value_area_breakout():
    entry = _trend82_entry()
    _seed_trend82_widths(entry)

    signal = entry.on_bar_close(
        _bar(
            "2024-01-03 09:39:00",
            open=101.0,
            high=116.75,
            low=99.0,
            close=116.25,
            volume=1200,
            signed_volume=600,
            large200_record_max_volume=500,
            large200_record_volume=800,
            large200_record_signed_volume=600,
            large200_record_count=2,
            **_range31_profile(
                developing_vap_poc=108.0,
                developing_vap_vah=115.75,
                developing_vap_val=100.0,
                developing_vap_lvn_count=12,
            ),
        )
    )

    assert signal is None


def test_build_entry_module_registers_yush_trend_82():
    entry = build_entry_module({"module": "yush_trend_82", "params": {"max_signal_risk_points": 20.0}})
    assert isinstance(entry, YushTrend82Entry)
