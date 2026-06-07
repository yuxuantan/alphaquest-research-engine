from types import SimpleNamespace

import pandas as pd

from propstack.strategy_modules.entry.calendar_session_bias import CalendarSessionBiasEntry
from propstack.strategy_modules.entry.daily_time_series_momentum import DailyTimeSeriesMomentumEntry
from propstack.strategy_modules.entry.intraday_capitulation_mr import IntradayCapitulationMREntry
from propstack.strategy_modules.entry.late_day_intraday_momentum import LateDayIntradayMomentumEntry
from propstack.strategy_modules.entry.morning_intraday_momentum import MorningIntradayMomentumEntry
from propstack.strategy_modules.entry.opening_range_breakout import OpeningRangeBreakoutEntry
from propstack.strategy_modules.entry.opening_range_filtered_breakout import OpeningRangeFilteredBreakoutEntry
from propstack.strategy_modules.entry.opening_range_inverse_breakout import OpeningRangeInverseBreakoutEntry
from propstack.strategy_modules.entry.overnight_inventory_reversion import OvernightInventoryReversionEntry
from propstack.strategy_modules.entry.overnight_return_late_day_momentum import OvernightReturnLateDayMomentumEntry
from propstack.strategy_modules.entry.pdh_pdl_breakout_continuation import PdhPdlBreakoutContinuationEntry
from propstack.strategy_modules.entry.pdh_pdl_sweep_reclaim import PdhPdlSweepReclaimEntry
from propstack.strategy_modules.entry.rth_gap_fade import RthGapFadeEntry
from propstack.strategy_modules.entry.turn_of_month_bias import TurnOfMonthBiasEntry
from propstack.strategy_modules.entry.vwap_pullback_continuation import VwapPullbackContinuationEntry
from propstack.strategy_modules.sl.opening_range_edge import OpeningRangeEdgeStop
from propstack.strategy_modules.sl.opening_range_width import OpeningRangeWidthStop
from propstack.strategy_modules.sl.percent_from_entry import PercentFromEntryStop
from propstack.strategy_modules.sl.sweep_extreme import SweepExtremeStop
from propstack.strategy_modules.tp.cost_adjusted_fixed_r import CostAdjustedFixedRTarget
from propstack.strategy_modules.tp.fixed_r import FixedRTarget
from propstack.strategy_modules.tp.gap_fill_fraction import GapFillFractionTarget
from propstack.strategy_modules.tp.opening_range_extension import OpeningRangeExtensionTarget
from propstack.strategy_modules.tp.opening_range_opposite_edge import OpeningRangeOppositeEdgeTarget
from propstack.strategy_modules.tp.percent_from_entry import PercentFromEntryTarget


def test_fixed_r_target_module_long_and_short():
    target = FixedRTarget({"target_r_multiple": 2.0})

    assert target.price(entry_price=100.0, stop_price=98.0, direction="long") == 104.0
    assert target.price(entry_price=100.0, stop_price=102.0, direction="short") == 96.0


def test_cost_adjusted_fixed_r_target_module_long_and_short():
    target = CostAdjustedFixedRTarget(
        {
            "target_r_multiple": 2.0,
            "tick_size": 0.1,
            "tick_value": 10.0,
            "commission_per_contract": 5.0,
            "slippage_ticks": 1,
        }
    )

    assert round(target.price(entry_price=100.0, stop_price=99.0, direction="long"), 10) == 102.6
    assert round(target.price(entry_price=100.0, stop_price=101.0, direction="short"), 10) == 97.4


def test_sweep_extreme_stop_module_long_and_short():
    stop = SweepExtremeStop({"stop_offset_ticks": 2})
    signal = SimpleNamespace(sweep_low=99.0, sweep_high=101.0)

    assert stop.price(signal, direction="long", tick_size=0.25) == 98.5
    assert stop.price(signal, direction="short", tick_size=0.25) == 101.5


def test_opening_range_extension_target_module_long_and_short():
    target = OpeningRangeExtensionTarget({"extension_fraction": 0.5})
    signal = SimpleNamespace(opening_range_high=101.0, opening_range_low=99.0, opening_range_width=2.0)

    assert target.price(100.0, 99.0, "long", signal=signal) == 102.0
    assert target.price(100.0, 101.0, "short", signal=signal) == 98.0


def test_percent_from_entry_stop_and_target_round_to_tick():
    stop = PercentFromEntryStop({"stop_pct": 0.003})
    target = PercentFromEntryTarget({"target_pct": 0.0075, "tick_size": 0.25})

    assert stop.price(None, direction="long", tick_size=0.25, entry_price=100.0) == 99.5
    assert stop.price(None, direction="short", tick_size=0.25, entry_price=100.0) == 100.5
    assert target.price(100.0, 99.5, "long") == 100.75
    assert target.price(100.0, 100.5, "short") == 99.25


def test_opening_range_edge_stop_skips_when_natural_risk_exceeds_max():
    stop = OpeningRangeEdgeStop({"max_stop_points": 10, "stop_offset_ticks": 0})
    signal = SimpleNamespace(opening_range_high=111.0, opening_range_low=90.0)

    assert stop.price(signal, direction="long", tick_size=0.25, entry_price=105.0) is None
    assert stop.price(signal, direction="short", tick_size=0.25, entry_price=95.0) is None
    assert stop.price(signal, direction="long", tick_size=0.25, entry_price=99.0) == 90.0
    assert stop.price(signal, direction="short", tick_size=0.25, entry_price=101.0) == 111.0


def test_opening_range_width_stop_uses_entry_price_and_range_width():
    stop = OpeningRangeWidthStop({"max_stop_points": 10, "stop_offset_ticks": 0})
    signal = SimpleNamespace(opening_range_width=1.5, metadata={"confirmation_close": 99.0})

    assert stop.price(signal, direction="long", tick_size=0.25, entry_price=98.75) == 97.25
    assert stop.price(signal, direction="short", tick_size=0.25, entry_price=101.25) == 102.75


def test_opening_range_width_stop_skips_when_range_width_exceeds_max():
    stop = OpeningRangeWidthStop({"max_stop_points": 1.0, "stop_offset_ticks": 0})
    signal = SimpleNamespace(opening_range_width=1.5, metadata={"confirmation_close": 99.0})

    assert stop.price(signal, direction="long", tick_size=0.25, entry_price=98.75) is None


def test_opening_range_opposite_edge_target_module_long_and_short():
    target = OpeningRangeOppositeEdgeTarget({})
    signal = SimpleNamespace(opening_range_high=101.0, opening_range_low=99.0)

    assert target.price(98.75, 97.25, "long", signal=signal) == 101.0
    assert target.price(101.25, 102.75, "short", signal=signal) == 99.0


def test_gap_fill_fraction_target_long_and_short():
    target = GapFillFractionTarget({"fill_fraction": 0.5, "tick_size": 0.25})
    long_signal = SimpleNamespace(report_fields={"prev_rth_close": 104.0}, metadata={})
    short_signal = SimpleNamespace(report_fields={"prev_rth_close": 96.0}, metadata={})

    assert target.price(100.0, 98.0, "long", signal=long_signal) == 102.0
    assert target.price(100.0, 102.0, "short", signal=short_signal) == 98.0


def _cal_bar(timestamp, open_price=100.0, high=101.0, low=99.0, close=100.5, *, is_rth=True):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
        },
        name=ts.hour * 60 + ts.minute,
    )


def test_calendar_session_bias_emits_configured_weekday_direction():
    entry = CalendarSessionBiasEntry(
        {
            "bar_interval_minutes": 5,
            "signal_time": "09:35:00",
            "weekday_directions": {2: "long", 4: "short"},
        }
    )

    wednesday = entry.on_bar_close(_cal_bar("2024-01-03 09:30"))
    assert wednesday.direction == "long"
    assert wednesday.report_fields["calendar_weekday"] == 2
    assert wednesday.report_fields["academic_source_key"] == "floros_salvador_2014_calendar_anomalies_stock_index_futures"

    friday = entry.on_bar_close(_cal_bar("2024-01-05 09:30"))
    assert friday.direction == "short"
    assert friday.report_fields["calendar_weekday"] == 4


def test_calendar_session_bias_rejects_wrong_time_weekday_rth_and_trade_limit():
    entry = CalendarSessionBiasEntry(
        {
            "bar_interval_minutes": 5,
            "signal_time": "09:35:00",
            "weekday_directions": {"2": "long"},
        }
    )

    assert entry.on_bar_close(_cal_bar("2024-01-03 09:35")) is None
    assert entry.on_bar_close(_cal_bar("2024-01-04 09:30")) is None
    assert entry.on_bar_close(_cal_bar("2024-01-03 09:30", is_rth=False)) is None
    assert entry.on_bar_close(_cal_bar("2024-01-03 09:30"), trades_today=1) is None


def _tom_bar(timestamp, open_price=100.0, high=101.0, low=99.0, close=100.5, *, is_rth=True):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
        },
        name=ts.hour * 60 + ts.minute,
    )


def test_turn_of_month_bias_emits_for_first_and_last_calendar_days():
    entry = TurnOfMonthBiasEntry(
        {
            "setup_mode": "turn_window",
            "bar_interval_minutes": 5,
            "signal_time": "11:00:00",
            "first_calendar_days": 5,
            "last_calendar_days": 4,
        }
    )

    first_day = entry.on_bar_close(_tom_bar("2024-02-02 10:55"))
    assert first_day.direction == "long"
    assert first_day.level_type == "turn_of_month_bias_turn_window_long"
    assert first_day.report_fields["turn_of_month_calendar_day"] == 2
    assert (
        first_day.report_fields["academic_source_key"]
        == "carchano_pardo_2011_calendar_anomalies_stock_index_futures"
    )

    last_day = entry.on_bar_close(_tom_bar("2024-02-27 10:55"))
    assert last_day.direction == "long"
    assert last_day.report_fields["turn_of_month_days_to_month_end"] == 2


def test_turn_of_month_bias_rejects_middle_month_wrong_time_rth_trade_limit_and_duplicate():
    entry = TurnOfMonthBiasEntry(
        {
            "setup_mode": "turn_window",
            "bar_interval_minutes": 5,
            "signal_time": "11:00:00",
            "first_calendar_days": 5,
            "last_calendar_days": 4,
        }
    )

    assert entry.on_bar_close(_tom_bar("2024-02-14 10:55")) is None
    assert entry.on_bar_close(_tom_bar("2024-02-02 10:50")) is None
    assert entry.on_bar_close(_tom_bar("2024-02-02 10:55", is_rth=False)) is None
    assert entry.on_bar_close(_tom_bar("2024-02-02 10:55"), trades_today=1) is None
    assert entry.on_bar_close(_tom_bar("2024-02-02 10:55")) is not None
    assert entry.on_bar_close(_tom_bar("2024-02-02 10:55")) is None


def test_turn_of_month_bias_first_or_last_only_modes():
    first_only = TurnOfMonthBiasEntry(
        {
            "setup_mode": "early_month_strength",
            "bar_interval_minutes": 5,
            "signal_time": "11:00:00",
            "first_calendar_days": 5,
            "last_calendar_days": 4,
        }
    )
    last_only = TurnOfMonthBiasEntry(
        {
            "setup_mode": "month_end_strength",
            "bar_interval_minutes": 5,
            "signal_time": "11:00:00",
            "first_calendar_days": 5,
            "last_calendar_days": 4,
        }
    )

    assert first_only.on_bar_close(_tom_bar("2024-02-02 10:55")) is not None
    assert first_only.on_bar_close(_tom_bar("2024-02-27 10:55")) is None
    assert last_only.on_bar_close(_tom_bar("2024-02-02 10:55")) is None
    assert last_only.on_bar_close(_tom_bar("2024-02-27 10:55")) is not None


def _tsm_bar(timestamp, open_price, high, low, close, *, is_rth=True):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
        },
        name=ts.hour * 60 + ts.minute,
    )


def _tsm_record_close(entry, timestamp, close):
    assert entry.on_bar_close(_tsm_bar(timestamp, close - 1.0, close + 1.0, close - 1.5, close)) is None


def test_daily_time_series_momentum_emits_long_and_short_from_completed_prior_closes():
    long_entry = DailyTimeSeriesMomentumEntry(
        {
            "setup_mode": "close_to_close_trend",
            "bar_interval_minutes": 30,
            "signal_time": "10:00:00",
            "lookback_sessions": 2,
            "min_abs_trend_return_pct": 0.005,
        }
    )
    _tsm_record_close(long_entry, "2024-01-02 15:30", 100.0)
    _tsm_record_close(long_entry, "2024-01-03 15:30", 102.0)
    signal = long_entry.on_bar_close(_tsm_bar("2024-01-04 09:30", 102.0, 103.0, 101.5, 102.5))

    assert signal.direction == "long"
    assert signal.level_type == "daily_time_series_momentum_close_to_close_trend"
    assert signal.report_fields["trend_return_pct"] == 0.020000000000000018
    assert signal.report_fields["academic_source_key"] == "moskowitz_ooi_pedersen_2012_time_series_momentum"

    short_entry = DailyTimeSeriesMomentumEntry(
        {
            "setup_mode": "close_to_close_trend",
            "bar_interval_minutes": 30,
            "signal_time": "10:00:00",
            "lookback_sessions": 2,
            "min_abs_trend_return_pct": 0.005,
        }
    )
    _tsm_record_close(short_entry, "2024-01-02 15:30", 102.0)
    _tsm_record_close(short_entry, "2024-01-03 15:30", 100.0)
    signal = short_entry.on_bar_close(_tsm_bar("2024-01-04 09:30", 100.0, 100.5, 99.0, 99.5))

    assert signal.direction == "short"
    assert signal.report_fields["trend_return_pct"] < 0


def test_daily_time_series_momentum_rejects_incomplete_or_invalid_conditions():
    entry = DailyTimeSeriesMomentumEntry(
        {
            "bar_interval_minutes": 30,
            "signal_time": "10:00:00",
            "lookback_sessions": 3,
            "min_abs_trend_return_pct": 0.005,
        }
    )
    _tsm_record_close(entry, "2024-01-02 15:30", 100.0)
    assert entry.on_bar_close(_tsm_bar("2024-01-03 09:30", 100.0, 100.5, 99.5, 100.1)) is None

    small = DailyTimeSeriesMomentumEntry(
        {
            "bar_interval_minutes": 30,
            "signal_time": "10:00:00",
            "lookback_sessions": 2,
            "min_abs_trend_return_pct": 0.02,
        }
    )
    _tsm_record_close(small, "2024-01-02 15:30", 100.0)
    _tsm_record_close(small, "2024-01-03 15:30", 101.0)
    assert small.on_bar_close(_tsm_bar("2024-01-04 09:30", 101.0, 101.5, 100.5, 101.1)) is None

    outside_rth = DailyTimeSeriesMomentumEntry({"bar_interval_minutes": 30, "lookback_sessions": 2})
    _tsm_record_close(outside_rth, "2024-01-02 15:30", 100.0)
    _tsm_record_close(outside_rth, "2024-01-03 15:30", 102.0)
    assert outside_rth.on_bar_close(_tsm_bar("2024-01-04 09:30", 102.0, 102.5, 101.5, 102.2, is_rth=False)) is None
    assert outside_rth.on_bar_close(_tsm_bar("2024-01-04 09:30", 102.0, 102.5, 101.5, 102.2), trades_today=1) is None


def test_daily_time_series_momentum_volatility_normalized_mode_filters_zscore():
    params = {
        "setup_mode": "volatility_normalized_trend",
        "bar_interval_minutes": 30,
        "signal_time": "10:00:00",
        "lookback_sessions": 4,
        "min_abs_trend_return_pct": 0.0,
        "min_trend_zscore": 0.5,
    }
    passing = DailyTimeSeriesMomentumEntry(params)
    for day, close in [("2024-01-02", 100.0), ("2024-01-03", 101.0), ("2024-01-04", 103.0), ("2024-01-05", 106.0)]:
        _tsm_record_close(passing, f"{day} 15:30", close)
    signal = passing.on_bar_close(_tsm_bar("2024-01-08 09:30", 106.0, 107.0, 105.5, 106.5))

    assert signal.direction == "long"
    assert signal.report_fields["trend_zscore"] > 0.5

    blocked = DailyTimeSeriesMomentumEntry({**params, "min_trend_zscore": 100.0})
    for day, close in [("2024-01-02", 100.0), ("2024-01-03", 101.0), ("2024-01-04", 103.0), ("2024-01-05", 106.0)]:
        _tsm_record_close(blocked, f"{day} 15:30", close)
    assert blocked.on_bar_close(_tsm_bar("2024-01-08 09:30", 106.0, 107.0, 105.5, 106.5)) is None


def test_daily_time_series_momentum_short_term_alignment_requires_recent_agreement():
    params = {
        "setup_mode": "short_term_alignment",
        "bar_interval_minutes": 30,
        "signal_time": "10:00:00",
        "lookback_sessions": 4,
        "confirmation_sessions": 1,
        "min_abs_trend_return_pct": 0.0,
    }
    blocked = DailyTimeSeriesMomentumEntry(params)
    for day, close in [("2024-01-02", 100.0), ("2024-01-03", 104.0), ("2024-01-04", 103.0), ("2024-01-05", 102.0)]:
        _tsm_record_close(blocked, f"{day} 15:30", close)
    assert blocked.on_bar_close(_tsm_bar("2024-01-08 09:30", 102.0, 103.0, 101.5, 102.5)) is None

    passing = DailyTimeSeriesMomentumEntry(params)
    for day, close in [("2024-01-02", 100.0), ("2024-01-03", 101.0), ("2024-01-04", 102.0), ("2024-01-05", 103.0)]:
        _tsm_record_close(passing, f"{day} 15:30", close)
    signal = passing.on_bar_close(_tsm_bar("2024-01-08 09:30", 103.0, 104.0, 102.5, 103.5))

    assert signal.direction == "long"
    assert signal.report_fields["confirmation_return_pct"] > 0


def _idm_bar(
    timestamp,
    open_price,
    high,
    low,
    close,
    *,
    prev_close=100.0,
    volume=1000,
    volume_ratio=1.0,
    is_rth=True,
):
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize("America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "volume_ratio": volume_ratio,
            "prev_rth_close": prev_close,
        },
        name=ts.hour * 60 + ts.minute,
    )


def _idm_first_window_bars(timeframe_minutes=30, close=102.0, prev_close=100.0, volume_ratio=1.2, high=103.0, low=99.5):
    if timeframe_minutes == 30:
        return [_idm_bar("2024-01-03 09:30", 100.0, high, low, close, prev_close=prev_close, volume_ratio=volume_ratio)]
    if timeframe_minutes == 15:
        return [
            _idm_bar("2024-01-03 09:30", 100.0, 101.5, low, 101.0, prev_close=prev_close, volume_ratio=volume_ratio),
            _idm_bar("2024-01-03 09:45", 101.0, high, 100.8, close, prev_close=prev_close, volume_ratio=volume_ratio),
        ]
    return [
        _idm_bar(f"2024-01-03 09:{minute:02d}", 100.0 + idx * 0.3, high, low, close, prev_close=prev_close, volume_ratio=volume_ratio)
        for idx, minute in enumerate([30, 35, 40, 45, 50, 55])
    ]


def test_late_day_intraday_momentum_emits_long_and_short_from_first_half_hour_sign():
    long_entry = LateDayIntradayMomentumEntry(
        {
            "setup_mode": "first_half_hour_sign",
            "bar_interval_minutes": 30,
            "min_signal_return_ticks": 2,
            "tick_size": 0.25,
        }
    )
    for bar in _idm_first_window_bars(30, close=102.0):
        assert long_entry.on_bar_close(bar) is None
    signal = long_entry.on_bar_close(_idm_bar("2024-01-03 15:00", 102.0, 102.5, 101.5, 102.25))

    assert signal.direction == "long"
    assert signal.level_type == "late_day_intraday_momentum_first_half_hour_sign"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 15:30", tz="America/New_York")
    assert signal.report_fields["first_window_return_ticks"] == 8.0
    assert signal.report_fields["late_day_entry_window_start"] == pd.Timestamp(
        "2024-01-03 15:30", tz="America/New_York"
    )
    assert signal.report_fields["academic_source_key"] == "gao_han_li_zhou_2018_market_intraday_momentum"

    short_entry = LateDayIntradayMomentumEntry(
        {
            "setup_mode": "first_half_hour_sign",
            "bar_interval_minutes": 30,
            "min_signal_return_ticks": 2,
            "tick_size": 0.25,
        }
    )
    for bar in _idm_first_window_bars(30, close=98.0):
        assert short_entry.on_bar_close(bar) is None
    signal = short_entry.on_bar_close(_idm_bar("2024-01-03 15:00", 98.0, 98.5, 97.5, 97.75))

    assert signal.direction == "short"
    assert signal.report_fields["first_window_return_ticks"] == -8.0


def test_late_day_intraday_momentum_rejects_invalid_or_early_conditions():
    small = LateDayIntradayMomentumEntry({"bar_interval_minutes": 30, "min_signal_return_ticks": 2})
    for bar in _idm_first_window_bars(30, close=100.25):
        assert small.on_bar_close(bar) is None
    assert small.on_bar_close(_idm_bar("2024-01-03 15:00", 100.25, 100.5, 100.0, 100.25)) is None

    missing_prev = LateDayIntradayMomentumEntry({"bar_interval_minutes": 30})
    first = _idm_first_window_bars(30, close=102.0)[0]
    first["prev_rth_close"] = pd.NA
    assert missing_prev.on_bar_close(first) is None
    assert missing_prev.on_bar_close(_idm_bar("2024-01-03 15:00", 102.0, 102.5, 101.5, 102.25)) is None

    outside_rth = LateDayIntradayMomentumEntry({"bar_interval_minutes": 30})
    for bar in _idm_first_window_bars(30, close=102.0):
        bar["is_rth"] = False
        assert outside_rth.on_bar_close(bar) is None
    assert outside_rth.on_bar_close(_idm_bar("2024-01-03 15:00", 102.0, 102.5, 101.5, 102.25)) is None

    early = LateDayIntradayMomentumEntry({"bar_interval_minutes": 30})
    for bar in _idm_first_window_bars(30, close=102.0):
        assert early.on_bar_close(bar) is None
    assert early.on_bar_close(_idm_bar("2024-01-03 14:30", 102.0, 102.5, 101.5, 102.25)) is None
    assert early.on_bar_close(_idm_bar("2024-01-03 15:00", 102.0, 102.5, 101.5, 102.25), trades_today=1) is None


def test_late_day_intraday_momentum_volume_volatility_conditioned_filters():
    params = {
        "setup_mode": "volume_volatility_conditioned",
        "bar_interval_minutes": 30,
        "min_signal_return_ticks": 1,
        "min_first_window_volume_ratio": 1.5,
        "min_first_window_range_points": 2.0,
    }
    low_volume = LateDayIntradayMomentumEntry(params)
    for bar in _idm_first_window_bars(30, close=102.0, volume_ratio=1.2, high=103.0, low=99.5):
        assert low_volume.on_bar_close(bar) is None
    assert low_volume.on_bar_close(_idm_bar("2024-01-03 15:00", 102.0, 102.5, 101.5, 102.25)) is None

    low_range = LateDayIntradayMomentumEntry(params)
    for bar in _idm_first_window_bars(30, close=102.0, volume_ratio=1.6, high=102.1, low=100.5):
        assert low_range.on_bar_close(bar) is None
    assert low_range.on_bar_close(_idm_bar("2024-01-03 15:00", 102.0, 102.5, 101.5, 102.25)) is None

    passing = LateDayIntradayMomentumEntry(params)
    for bar in _idm_first_window_bars(30, close=102.0, volume_ratio=1.6, high=103.0, low=99.5):
        assert passing.on_bar_close(bar) is None
    signal = passing.on_bar_close(_idm_bar("2024-01-03 15:00", 102.0, 102.5, 101.5, 102.25))

    assert signal.direction == "long"
    assert signal.report_fields["first_window_avg_volume_ratio"] == 1.6
    assert signal.report_fields["first_window_range_points"] == 3.5


def test_late_day_intraday_momentum_alignment_requires_penultimate_agreement():
    params = {
        "setup_mode": "first_and_penultimate_alignment",
        "bar_interval_minutes": 30,
        "min_signal_return_ticks": 1,
        "min_penultimate_return_ticks": 1,
    }
    disagree = LateDayIntradayMomentumEntry(params)
    for bar in _idm_first_window_bars(30, close=102.0):
        assert disagree.on_bar_close(bar) is None
    assert disagree.on_bar_close(_idm_bar("2024-01-03 15:00", 102.0, 102.5, 100.75, 101.0)) is None

    agree = LateDayIntradayMomentumEntry(params)
    for bar in _idm_first_window_bars(30, close=102.0):
        assert agree.on_bar_close(bar) is None
    signal = agree.on_bar_close(_idm_bar("2024-01-03 15:00", 101.0, 102.5, 100.75, 102.0))

    assert signal.direction == "long"
    assert signal.report_fields["penultimate_window_return_ticks"] == 4.0


def test_late_day_intraday_momentum_signal_closes_at_last_half_hour_start_for_supported_timeframes():
    cases = [
        (5, "2024-01-03 15:25"),
        (15, "2024-01-03 15:15"),
        (30, "2024-01-03 15:00"),
    ]
    for timeframe_minutes, signal_bar_timestamp in cases:
        entry = LateDayIntradayMomentumEntry(
            {
                "setup_mode": "first_half_hour_sign",
                "bar_interval_minutes": timeframe_minutes,
                "min_signal_return_ticks": 1,
            }
        )
        for bar in _idm_first_window_bars(timeframe_minutes, close=102.0):
            assert entry.on_bar_close(bar) is None
        signal = entry.on_bar_close(_idm_bar(signal_bar_timestamp, 102.0, 102.5, 101.5, 102.25))

        assert signal.direction == "long"
        assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 15:30", tz="America/New_York")
        assert signal.report_fields["late_day_entry_window_start"] == pd.Timestamp(
            "2024-01-03 15:30", tz="America/New_York"
        )


def _mim_bar(
    timestamp,
    open_price,
    high,
    low,
    close,
    *,
    volume=1000,
    volume_ratio=1.0,
    is_rth=True,
):
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize("America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "volume_ratio": volume_ratio,
        },
        name=ts.hour * 60 + ts.minute,
    )


def _mim_source_window_bars(
    timeframe_minutes=30,
    *,
    start_open=100.0,
    close=102.0,
    high=103.0,
    low=99.5,
    volume_ratio=1.2,
    is_rth=True,
):
    minutes = list(range(30, 90, timeframe_minutes))
    bars = []
    for idx, minute_offset in enumerate(minutes):
        ts = pd.Timestamp("2024-01-03 09:00", tz="America/New_York") + pd.Timedelta(minutes=minute_offset)
        bar_open = start_open if idx == 0 else start_open + idx * 0.25
        bar_close = close if idx == len(minutes) - 1 else bar_open + 0.25
        bars.append(
            _mim_bar(
                ts,
                bar_open,
                high,
                low,
                bar_close,
                volume_ratio=volume_ratio,
                is_rth=is_rth,
            )
        )
    return bars


def test_morning_intraday_momentum_emits_long_and_short_from_rth_open_to_signal_return():
    long_entry = MorningIntradayMomentumEntry(
        {
            "setup_mode": "long_only_strength",
            "bar_interval_minutes": 30,
            "min_signal_return_ticks": 2,
            "tick_size": 0.25,
            "allow_short": False,
        }
    )
    signal = None
    for bar in _mim_source_window_bars(30, close=102.0):
        signal = long_entry.on_bar_close(bar)

    assert signal.direction == "long"
    assert signal.level_type == "morning_intraday_momentum_long_only_strength"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:30", tz="America/New_York")
    assert signal.report_fields["source_return_reference"] == "rth_open_to_signal_close"
    assert signal.report_fields["source_window_open"] == 100.0
    assert signal.report_fields["source_window_close"] == 102.0
    assert signal.report_fields["source_window_return_ticks"] == 8.0
    assert signal.report_fields["morning_momentum_entry_window_start"] == pd.Timestamp(
        "2024-01-03 10:30", tz="America/New_York"
    )
    assert signal.report_fields["academic_source_key"] == "gao_han_li_zhou_2018_market_intraday_momentum"

    short_entry = MorningIntradayMomentumEntry(
        {
            "setup_mode": "two_sided_continuation",
            "bar_interval_minutes": 30,
            "min_signal_return_ticks": 2,
            "tick_size": 0.25,
        }
    )
    signal = None
    for bar in _mim_source_window_bars(30, close=98.0):
        signal = short_entry.on_bar_close(bar)

    assert signal.direction == "short"
    assert signal.report_fields["source_window_return_ticks"] == -8.0


def test_morning_intraday_momentum_rejects_invalid_wrong_time_rth_and_trade_limit():
    small = MorningIntradayMomentumEntry({"bar_interval_minutes": 30, "min_signal_return_ticks": 2})
    signal = None
    for bar in _mim_source_window_bars(30, close=100.25):
        signal = small.on_bar_close(bar)
    assert signal is None

    outside_rth = MorningIntradayMomentumEntry({"bar_interval_minutes": 30, "min_signal_return_ticks": 1})
    signal = None
    for bar in _mim_source_window_bars(30, close=102.0, is_rth=False):
        signal = outside_rth.on_bar_close(bar)
    assert signal is None

    early = MorningIntradayMomentumEntry({"bar_interval_minutes": 30, "min_signal_return_ticks": 1})
    assert early.on_bar_close(_mim_bar("2024-01-03 09:30", 100.0, 101.0, 99.5, 100.5)) is None

    limited = MorningIntradayMomentumEntry({"bar_interval_minutes": 30, "min_signal_return_ticks": 1})
    first, final = _mim_source_window_bars(30, close=102.0)
    assert limited.on_bar_close(first) is None
    assert limited.on_bar_close(final, trades_today=1) is None


def test_morning_intraday_momentum_volume_volatility_conditioned_filters():
    params = {
        "setup_mode": "volume_volatility_conditioned",
        "bar_interval_minutes": 30,
        "min_signal_return_ticks": 1,
        "min_source_window_volume_ratio": 1.5,
        "min_source_window_range_points": 2.0,
    }
    low_volume = MorningIntradayMomentumEntry(params)
    signal = None
    for bar in _mim_source_window_bars(30, close=102.0, volume_ratio=1.2, high=103.0, low=99.5):
        signal = low_volume.on_bar_close(bar)
    assert signal is None

    low_range = MorningIntradayMomentumEntry(params)
    signal = None
    for bar in _mim_source_window_bars(30, close=102.0, volume_ratio=1.6, high=102.1, low=100.5):
        signal = low_range.on_bar_close(bar)
    assert signal is None

    passing = MorningIntradayMomentumEntry(params)
    signal = None
    for bar in _mim_source_window_bars(30, close=102.0, volume_ratio=1.6, high=103.0, low=99.5):
        signal = passing.on_bar_close(bar)

    assert signal.direction == "long"
    assert signal.report_fields["source_window_avg_volume_ratio"] == 1.6
    assert signal.report_fields["source_window_range_points"] == 3.5


def test_morning_intraday_momentum_signal_close_aligns_entry_for_supported_timeframes():
    cases = [
        (5, "2024-01-03 10:25"),
        (15, "2024-01-03 10:15"),
        (30, "2024-01-03 10:00"),
    ]
    for timeframe_minutes, signal_bar_timestamp in cases:
        entry = MorningIntradayMomentumEntry(
            {
                "setup_mode": "long_only_strength",
                "bar_interval_minutes": timeframe_minutes,
                "min_signal_return_ticks": 1,
            }
        )
        signal = None
        for bar in _mim_source_window_bars(timeframe_minutes, close=102.0):
            signal = entry.on_bar_close(bar)

        assert signal.direction == "long"
        assert signal.sweep_timestamp == pd.Timestamp("2024-01-03 09:30", tz="America/New_York")
        assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 10:30", tz="America/New_York")
        assert signal.report_fields["morning_momentum_entry_window_start"] == pd.Timestamp(
            "2024-01-03 10:30", tz="America/New_York"
        )
        assert signal.report_fields["morning_momentum_entry_window_end"] == pd.Timestamp(
            "2024-01-03 10:30", tz="America/New_York"
        ) + pd.Timedelta(minutes=timeframe_minutes)
        assert pd.Timestamp(signal_bar_timestamp, tz="America/New_York") + pd.Timedelta(
            minutes=timeframe_minutes
        ) == signal.reclaim_timestamp


def test_morning_intraday_momentum_does_not_use_future_bars():
    entry = MorningIntradayMomentumEntry(
        {
            "setup_mode": "long_only_strength",
            "bar_interval_minutes": 30,
            "min_signal_return_ticks": 1,
        }
    )
    signal = None
    for bar in _mim_source_window_bars(30, close=102.0):
        signal = entry.on_bar_close(bar)
    assert signal.report_fields["source_window_close"] == 102.0

    future = entry.on_bar_close(_mim_bar("2024-01-03 10:30", 80.0, 81.0, 79.0, 79.5))

    assert future is None
    assert signal.report_fields["source_window_close"] == 102.0


def _orlm_bar(
    timestamp,
    open_price,
    high,
    low,
    close,
    *,
    prev_close=100.0,
    is_rth=True,
):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "prev_rth_close": prev_close,
        },
        name=ts.hour * 60 + ts.minute,
    )


def _orlm_first_window_bars(timeframe_minutes=30, open_price=102.0, close=101.0, prev_close=100.0):
    if timeframe_minutes == 30:
        return [_orlm_bar("2024-01-03 09:30", open_price, 103.0, 100.5, close, prev_close=prev_close)]
    if timeframe_minutes == 15:
        return [
            _orlm_bar("2024-01-03 09:30", open_price, 102.5, 101.0, 101.5, prev_close=prev_close),
            _orlm_bar("2024-01-03 09:45", 101.5, 102.0, 100.75, close, prev_close=prev_close),
        ]
    return [
        _orlm_bar(
            f"2024-01-03 09:{minute:02d}",
            open_price if idx == 0 else open_price - idx * 0.1,
            103.0,
            100.5,
            close,
            prev_close=prev_close,
        )
        for idx, minute in enumerate([30, 35, 40, 45, 50, 55])
    ]


def test_overnight_return_late_day_momentum_emits_long_and_short_from_overnight_sign():
    long_entry = OvernightReturnLateDayMomentumEntry(
        {
            "setup_mode": "overnight_sign_close_continuation",
            "bar_interval_minutes": 30,
            "min_overnight_return_ticks": 2,
            "tick_size": 0.25,
        }
    )
    for bar in _orlm_first_window_bars(30, open_price=102.0, close=101.5):
        assert long_entry.on_bar_close(bar) is None
    signal = long_entry.on_bar_close(_orlm_bar("2024-01-03 15:00", 101.5, 102.25, 101.0, 102.0))

    assert signal.direction == "long"
    assert signal.level_type == "overnight_return_late_day_momentum_overnight_sign_close_continuation"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 15:30", tz="America/New_York")
    assert signal.report_fields["overnight_return_ticks"] == 8.0
    assert signal.report_fields["academic_source_key"] == "liu_tse_2017_overnight_returns_indexes"

    short_entry = OvernightReturnLateDayMomentumEntry(
        {
            "setup_mode": "overnight_sign_close_continuation",
            "bar_interval_minutes": 30,
            "min_overnight_return_ticks": 2,
            "tick_size": 0.25,
        }
    )
    for bar in _orlm_first_window_bars(30, open_price=98.0, close=98.5):
        assert short_entry.on_bar_close(bar) is None
    signal = short_entry.on_bar_close(_orlm_bar("2024-01-03 15:00", 98.5, 99.0, 98.0, 98.25))

    assert signal.direction == "short"
    assert signal.report_fields["overnight_return_ticks"] == -8.0


def test_overnight_return_late_day_momentum_rejects_invalid_or_early_conditions():
    small = OvernightReturnLateDayMomentumEntry({"bar_interval_minutes": 30, "min_overnight_return_ticks": 2})
    for bar in _orlm_first_window_bars(30, open_price=100.25, close=100.0):
        assert small.on_bar_close(bar) is None
    assert small.on_bar_close(_orlm_bar("2024-01-03 15:00", 100.0, 100.5, 99.5, 100.25)) is None

    missing_prev = OvernightReturnLateDayMomentumEntry({"bar_interval_minutes": 30})
    first = _orlm_first_window_bars(30, open_price=102.0)[0]
    first["prev_rth_close"] = pd.NA
    assert missing_prev.on_bar_close(first) is None
    assert missing_prev.on_bar_close(_orlm_bar("2024-01-03 15:00", 102.0, 102.5, 101.5, 102.25)) is None

    outside_rth = OvernightReturnLateDayMomentumEntry({"bar_interval_minutes": 30})
    for bar in _orlm_first_window_bars(30, open_price=102.0):
        bar["is_rth"] = False
        assert outside_rth.on_bar_close(bar) is None
    assert outside_rth.on_bar_close(_orlm_bar("2024-01-03 15:00", 102.0, 102.5, 101.5, 102.25)) is None

    early = OvernightReturnLateDayMomentumEntry({"bar_interval_minutes": 30})
    for bar in _orlm_first_window_bars(30, open_price=102.0):
        assert early.on_bar_close(bar) is None
    assert early.on_bar_close(_orlm_bar("2024-01-03 14:30", 102.0, 102.5, 101.5, 102.25)) is None
    assert early.on_bar_close(_orlm_bar("2024-01-03 15:00", 102.0, 102.5, 101.5, 102.25), trades_today=1) is None


def test_overnight_return_late_day_momentum_opening_reversal_mode():
    params = {
        "setup_mode": "opening_reversal_confirmed",
        "bar_interval_minutes": 30,
        "min_overnight_return_ticks": 1,
        "min_opening_reversal_ticks": 2,
    }
    no_reversal = OvernightReturnLateDayMomentumEntry(params)
    for bar in _orlm_first_window_bars(30, open_price=102.0, close=102.75):
        assert no_reversal.on_bar_close(bar) is None
    assert no_reversal.on_bar_close(_orlm_bar("2024-01-03 15:00", 102.75, 103.0, 102.0, 102.5)) is None

    passing = OvernightReturnLateDayMomentumEntry(params)
    for bar in _orlm_first_window_bars(30, open_price=102.0, close=101.25):
        assert passing.on_bar_close(bar) is None
    signal = passing.on_bar_close(_orlm_bar("2024-01-03 15:00", 101.25, 102.0, 101.0, 101.75))

    assert signal.direction == "long"
    assert signal.report_fields["first_window_return_ticks"] == -3.0


def test_overnight_return_late_day_momentum_alignment_requires_penultimate_agreement():
    params = {
        "setup_mode": "overnight_penultimate_alignment",
        "bar_interval_minutes": 30,
        "min_overnight_return_ticks": 1,
        "min_penultimate_return_ticks": 1,
    }
    disagree = OvernightReturnLateDayMomentumEntry(params)
    for bar in _orlm_first_window_bars(30, open_price=102.0, close=101.5):
        assert disagree.on_bar_close(bar) is None
    assert disagree.on_bar_close(_orlm_bar("2024-01-03 15:00", 102.0, 102.25, 101.0, 101.5)) is None

    agree = OvernightReturnLateDayMomentumEntry(params)
    for bar in _orlm_first_window_bars(30, open_price=102.0, close=101.5):
        assert agree.on_bar_close(bar) is None
    signal = agree.on_bar_close(_orlm_bar("2024-01-03 15:00", 101.5, 102.25, 101.0, 102.0))

    assert signal.direction == "long"
    assert signal.report_fields["penultimate_window_return_ticks"] == 2.0


def test_overnight_return_late_day_momentum_signal_closes_at_last_half_hour_start_for_supported_timeframes():
    cases = [
        (5, "2024-01-03 15:25"),
        (15, "2024-01-03 15:15"),
        (30, "2024-01-03 15:00"),
    ]
    for timeframe_minutes, signal_bar_timestamp in cases:
        entry = OvernightReturnLateDayMomentumEntry(
            {
                "setup_mode": "overnight_sign_close_continuation",
                "bar_interval_minutes": timeframe_minutes,
                "min_overnight_return_ticks": 1,
            }
        )
        for bar in _orlm_first_window_bars(timeframe_minutes, open_price=102.0, close=101.5):
            assert entry.on_bar_close(bar) is None
        signal = entry.on_bar_close(_orlm_bar(signal_bar_timestamp, 101.5, 102.0, 101.0, 101.75))

        assert signal.direction == "long"
        assert signal.reclaim_timestamp == pd.Timestamp("2024-01-03 15:30", tz="America/New_York")
        assert signal.report_fields["late_day_entry_window_start"] == pd.Timestamp(
            "2024-01-03 15:30", tz="America/New_York"
        )


def _on_bar(timestamp, open_price, high, low, close, volume=1000, vwap=100.0, is_rth=True, name=None):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "vwap": vwap,
            "overnight_high": 102.0,
            "overnight_low": 98.0,
        },
        name=name if name is not None else ts.hour * 60 + ts.minute,
    )


def test_overnight_inventory_reversion_emits_long_reclaim_with_report_fields():
    entry = OvernightInventoryReversionEntry(
        {
            "start_time": "09:30:00",
            "end_time": "10:30:00",
            "reclaim_window_bars": 2,
            "min_extension_points": 0.25,
            "min_overnight_range_points": 2.0,
            "confirmation_mode": "extreme_reclaim",
            "tick_size": 0.25,
            "max_trades_per_day": 1,
        }
    )

    assert entry.on_bar_close(_on_bar("2024-01-03 09:30", 99.0, 99.5, 97.5, 97.8, name=1)) is None
    signal = entry.on_bar_close(_on_bar("2024-01-03 09:31", 97.8, 98.4, 97.7, 98.25, name=2))

    assert signal.direction == "long"
    assert signal.level_type == "overnight_low_reclaim"
    assert signal.swept_level == 98.0
    assert signal.sweep_low == 97.5
    assert signal.report_fields["overnight_low"] == 98.0
    assert signal.report_fields["overnight_high"] == 102.0
    assert signal.report_fields["overnight_midpoint"] == 100.0
    assert signal.report_fields["overnight_reclaim_timestamp"] == pd.Timestamp(
        "2024-01-03 09:31", tz="America/New_York"
    )
    assert signal.metadata["confirmation_high"] == 98.4


def test_overnight_inventory_reversion_rejects_when_required_condition_fails():
    entry = OvernightInventoryReversionEntry(
        {
            "start_time": "09:30:00",
            "end_time": "10:30:00",
            "min_extension_points": 0.25,
            "min_overnight_range_points": 2.0,
        }
    )

    assert entry.on_bar_close(_on_bar("2024-01-03 09:30", 99.0, 99.5, 97.9, 98.2, name=1)) is None
    assert entry.on_bar_close(_on_bar("2024-01-03 09:31", 98.2, 98.4, 98.0, 98.3, is_rth=False, name=2)) is None

    missing = _on_bar("2024-01-03 09:32", 98.2, 98.4, 97.4, 98.3, name=3)
    missing["overnight_low"] = pd.NA
    assert entry.on_bar_close(missing) is None


def test_overnight_inventory_reversion_expires_reclaim_window():
    entry = OvernightInventoryReversionEntry(
        {
            "start_time": "09:30:00",
            "end_time": "10:30:00",
            "reclaim_window_bars": 0,
            "min_extension_points": 0.25,
            "min_overnight_range_points": 2.0,
        }
    )

    assert entry.on_bar_close(_on_bar("2024-01-03 09:30", 99.0, 99.5, 97.5, 97.8, name=1)) is None
    assert entry.on_bar_close(_on_bar("2024-01-03 09:31", 97.8, 97.9, 97.6, 97.7, name=2)) is None
    assert entry.on_bar_close(_on_bar("2024-01-03 09:32", 97.9, 98.5, 97.9, 98.25, name=3)) is None


def test_overnight_inventory_reversion_vwap_same_side_filter():
    entry = OvernightInventoryReversionEntry(
        {
            "start_time": "09:30:00",
            "end_time": "10:30:00",
            "reclaim_window_bars": 2,
            "min_extension_points": 0.25,
            "min_overnight_range_points": 2.0,
            "vwap_filter": "same_side",
        }
    )

    assert entry.on_bar_close(_on_bar("2024-01-03 09:30", 99.0, 99.5, 97.5, 97.8, vwap=99.0, name=1)) is None
    assert entry.on_bar_close(_on_bar("2024-01-03 09:31", 97.8, 98.4, 97.7, 98.25, vwap=98.0, name=2)) is None

    entry = OvernightInventoryReversionEntry(
        {
            "start_time": "09:30:00",
            "end_time": "10:30:00",
            "reclaim_window_bars": 2,
            "min_extension_points": 0.25,
            "min_overnight_range_points": 2.0,
            "vwap_filter": "same_side",
        }
    )
    assert entry.on_bar_close(_on_bar("2024-01-03 09:30", 99.0, 99.5, 97.5, 97.8, vwap=99.0, name=1)) is None
    signal = entry.on_bar_close(_on_bar("2024-01-03 09:31", 97.8, 98.4, 97.7, 98.25, vwap=99.0, name=2))

    assert signal.direction == "long"


def test_overnight_inventory_reversion_midpoint_confirmation_waits_for_midpoint():
    entry = OvernightInventoryReversionEntry(
        {
            "start_time": "09:30:00",
            "end_time": "10:30:00",
            "reclaim_window_bars": 3,
            "min_extension_points": 0.25,
            "min_overnight_range_points": 2.0,
            "confirmation_mode": "midpoint_reclaim",
        }
    )

    assert entry.on_bar_close(_on_bar("2024-01-03 09:30", 99.0, 99.5, 97.5, 97.8, name=1)) is None
    assert entry.on_bar_close(_on_bar("2024-01-03 09:31", 97.8, 99.5, 97.7, 99.0, name=2)) is None
    signal = entry.on_bar_close(_on_bar("2024-01-03 09:32", 99.0, 100.4, 98.8, 100.2, name=3))

    assert signal.direction == "long"
    assert signal.report_fields["overnight_confirmation_level"] == 100.0


def test_overnight_inventory_reversion_honors_max_trades_per_day_argument():
    entry = OvernightInventoryReversionEntry({"max_trades_per_day": 1})

    signal = entry.on_bar_close(_on_bar("2024-01-03 09:30", 99.0, 99.5, 97.5, 98.2, name=1), trades_today=1)

    assert signal is None


def _vwap_bar(timestamp, open_price, high, low, close, vwap=100.0, is_rth=True, name=None):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": is_rth,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000,
            "vwap": vwap,
        },
        name=name if name is not None else ts.hour * 60 + ts.minute,
    )


def test_vwap_pullback_continuation_emits_after_trend_pullback_reclaim():
    entry = VwapPullbackContinuationEntry(
        {
            "setup_mode": "trend_reclaim",
            "required_trend_closes": 2,
            "min_drive_points": 1.0,
            "reclaim_window_bars": 2,
            "pullback_tolerance_ticks": 1,
            "tick_size": 0.25,
        }
    )
    bars = [
        _vwap_bar("2024-01-03 09:30", 100.0, 101.5, 100.5, 101.0, vwap=100.5, name=1),
        _vwap_bar("2024-01-03 09:31", 101.0, 102.0, 101.0, 101.75, vwap=100.75, name=2),
        _vwap_bar("2024-01-03 09:32", 101.75, 102.0, 100.75, 101.2, vwap=101.0, name=3),
    ]

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "long"
    assert signal.level_type == "vwap_pullback_continuation"
    assert signal.sweep_low == 100.75
    assert signal.report_fields["vwap_at_signal"] == 101.0
    assert signal.report_fields["session_open"] == 100.0
    assert signal.report_fields["long_trend_count"] >= 1


def test_vwap_pullback_continuation_rejects_missing_vwap_and_no_context():
    entry = VwapPullbackContinuationEntry({"required_trend_closes": 2, "min_drive_points": 1.0})
    missing = _vwap_bar("2024-01-03 09:30", 100.0, 100.5, 99.5, 100.2, name=1)
    missing["vwap"] = pd.NA

    assert entry.on_bar_close(missing) is None
    assert entry.on_bar_close(_vwap_bar("2024-01-03 09:31", 100.0, 100.5, 99.8, 100.1, vwap=100.0, name=2)) is None


def test_vwap_pullback_continuation_expires_reclaim_window():
    entry = VwapPullbackContinuationEntry(
        {
            "setup_mode": "trend_reclaim",
            "required_trend_closes": 1,
            "min_drive_points": 1.0,
            "reclaim_window_bars": 0,
            "pullback_tolerance_ticks": 1,
            "tick_size": 0.25,
        }
    )

    assert entry.on_bar_close(_vwap_bar("2024-01-03 09:30", 100.0, 101.5, 100.5, 101.2, vwap=100.5, name=1)) is None
    assert entry.on_bar_close(_vwap_bar("2024-01-03 09:31", 101.2, 101.3, 100.6, 100.8, vwap=100.8, name=2)) is None
    assert entry.on_bar_close(_vwap_bar("2024-01-03 09:32", 100.8, 100.9, 100.7, 100.7, vwap=100.8, name=3)) is None
    assert entry.on_bar_close(_vwap_bar("2024-01-03 09:33", 100.7, 101.2, 100.7, 101.0, vwap=100.8, name=4)) is None


def test_vwap_pullback_continuation_opening_drive_bias():
    entry = VwapPullbackContinuationEntry(
        {
            "setup_mode": "opening_drive_pullback",
            "opening_drive_minutes": 2,
            "bar_interval_minutes": 1,
            "min_drive_points": 1.0,
            "min_drive_close_location": 0.60,
            "pullback_tolerance_ticks": 1,
            "tick_size": 0.25,
        }
    )
    bars = [
        _vwap_bar("2024-01-03 09:30", 100.0, 101.0, 99.8, 100.8, vwap=100.2, name=1),
        _vwap_bar("2024-01-03 09:31", 100.8, 102.0, 100.7, 101.8, vwap=100.5, name=2),
        _vwap_bar("2024-01-03 09:32", 101.8, 102.0, 100.6, 101.0, vwap=100.8, name=3),
    ]

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "long"
    assert signal.report_fields["opening_drive_close"] == 101.8
    assert signal.report_fields["opening_drive_close_location"] > 0.60


def test_vwap_pullback_continuation_failed_vwap_break_can_signal_same_bar():
    entry = VwapPullbackContinuationEntry(
        {
            "setup_mode": "failed_vwap_break",
            "required_trend_closes": 1,
            "min_drive_points": 1.0,
            "failed_break_min_ticks": 1,
            "tick_size": 0.25,
        }
    )

    assert entry.on_bar_close(_vwap_bar("2024-01-03 09:30", 100.0, 101.5, 100.5, 101.2, vwap=100.5, name=1)) is None
    signal = entry.on_bar_close(_vwap_bar("2024-01-03 09:31", 101.2, 101.4, 100.4, 101.0, vwap=100.75, name=2))

    assert signal.direction == "long"
    assert signal.report_fields["pullback_low"] == 100.4


def test_vwap_pullback_continuation_honors_max_trades_per_day_argument():
    entry = VwapPullbackContinuationEntry({"max_trades_per_day": 1})

    signal = entry.on_bar_close(
        _vwap_bar("2024-01-03 09:30", 100.0, 101.0, 99.8, 100.8, vwap=100.2, name=1),
        trades_today=1,
    )

    assert signal is None


def _cap_bar(timestamp, open_price, high, low, close, volume, vwap, session_date=None):
    ts = pd.Timestamp(timestamp)
    if ts.tzinfo is None:
        ts = ts.tz_localize("America/New_York")
    else:
        ts = ts.tz_convert("America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": session_date or ts.date(),
            "is_rth": True,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "vwap": vwap,
        },
        name=ts.hour * 60 + ts.minute,
    )


def _cap_window(start, open_price, high, low, close, total_volume, vwap):
    start_ts = pd.Timestamp(start, tz="America/New_York")
    bars = []
    for minute in range(15):
        ts = start_ts + pd.Timedelta(minutes=minute)
        bars.append(
            _cap_bar(
                ts,
                open_price if minute == 0 else close,
                high,
                low,
                close,
                total_volume / 15,
                vwap,
            )
        )
    return bars


def test_intraday_capitulation_mr_entry_emits_on_completed_15m_bar():
    entry = IntradayCapitulationMREntry(
        {
            "timeframe_minutes": 15,
            "bar_interval_minutes": 1,
            "rsi_period": 1,
            "max_rsi": 35,
            "volume_avg_window": 1,
            "min_volume_avg_bars": 1,
            "min_volume_ratio": 1.5,
            "max_close_location_from_low": 0.25,
            "last_signal_time": "16:00:00",
        }
    )
    bars = [
        *_cap_window("2024-01-03 09:30", 100.0, 101.0, 99.0, 100.0, 1000, 100.0),
        *_cap_window("2024-01-03 09:45", 100.0, 100.2, 98.0, 98.2, 1600, 99.0),
    ]

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "long"
    assert signal.level_type == "intraday_capitulation_mr"
    assert signal.sweep_low == 98.0
    assert signal.report_fields["capitulation_bar_start_timestamp"] == pd.Timestamp(
        "2024-01-03 09:45", tz="America/New_York"
    )
    assert signal.report_fields["capitulation_bar_end_timestamp"] == pd.Timestamp(
        "2024-01-03 10:00", tz="America/New_York"
    )
    assert signal.report_fields["capitulation_rsi"] == 0.0
    assert round(signal.report_fields["capitulation_volume_ratio"], 2) == 1.6


def test_intraday_capitulation_mr_entry_rejects_close_not_near_low():
    entry = IntradayCapitulationMREntry(
        {
            "timeframe_minutes": 15,
            "bar_interval_minutes": 1,
            "rsi_period": 1,
            "max_rsi": 35,
            "volume_avg_window": 1,
            "min_volume_avg_bars": 1,
            "min_volume_ratio": 1.5,
            "max_close_location_from_low": 0.25,
        }
    )
    bars = [
        *_cap_window("2024-01-03 09:30", 100.0, 101.0, 99.0, 100.0, 1000, 100.0),
        *_cap_window("2024-01-03 09:45", 100.0, 100.2, 98.0, 99.0, 1600, 99.5),
    ]

    signal = None
    for bar in bars:
        signal = entry.on_bar_close(bar)

    assert signal is None


def _orb_bar(timestamp, open_price, high, low, close, session_date=None, volume_ratio=1.0, vwap=100.0):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": session_date or ts.date(),
            "is_rth": True,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume_ratio": volume_ratio,
            "vwap": vwap,
        },
        name=ts.hour * 60 + ts.minute,
    )


def _orb_long_breakout_bars(date="2024-01-03"):
    return [
        _orb_bar(f"{date} 09:30", 100.0, 100.20, 99.90, 100.10),
        _orb_bar(f"{date} 09:31", 100.1, 100.30, 100.00, 100.20),
        _orb_bar(f"{date} 09:32", 100.2, 100.40, 100.10, 100.25),
        _orb_bar(f"{date} 09:33", 100.2, 100.25, 99.95, 100.05),
        _orb_bar(f"{date} 09:34", 100.0, 100.35, 100.05, 100.20),
        _orb_bar(f"{date} 09:35", 100.2, 100.30, 100.00, 100.10),
        _orb_bar(f"{date} 09:36", 100.1, 100.30, 100.00, 100.20),
        _orb_bar(f"{date} 09:37", 100.2, 100.35, 100.10, 100.30),
        _orb_bar(f"{date} 09:38", 100.3, 100.38, 100.20, 100.35),
        _orb_bar(f"{date} 09:39", 100.35, 100.55, 100.30, 100.50),
    ]


def test_opening_range_breakout_entry_emits_after_confirmation_window():
    entry = OpeningRangeBreakoutEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 5,
            "bar_interval_minutes": 1,
            "max_opening_range_pct_of_open": 0.0055,
            "allow_long": True,
            "allow_short": True,
        }
    )
    bars = _orb_long_breakout_bars()

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "long"
    assert signal.level_type == "opening_range_high"
    assert signal.swept_level == 100.40
    assert signal.opening_range_low == 99.90
    assert round(signal.opening_range_width, 2) == 0.50
    assert signal.reclaim_timestamp == bars[-1]["timestamp"]
    assert signal.report_fields["opening_range_start_timestamp"] == bars[0]["timestamp"]
    assert signal.report_fields["opening_range_end_timestamp"] == pd.Timestamp(
        "2024-01-03 09:35", tz="America/New_York"
    )
    assert signal.report_fields["confirmation_start_timestamp"] == bars[5]["timestamp"]
    assert signal.report_fields["confirmation_end_timestamp"] == pd.Timestamp(
        "2024-01-03 09:40", tz="America/New_York"
    )
    assert signal.report_fields["breakout_timestamp"] == pd.Timestamp("2024-01-03 09:40", tz="America/New_York")


def test_opening_range_breakout_entry_keeps_checking_later_confirmation_windows():
    entry = OpeningRangeBreakoutEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 5,
            "bar_interval_minutes": 1,
            "max_opening_range_pct_of_open": 0.0055,
            "allow_long": True,
            "allow_short": True,
        }
    )
    bars = _orb_long_breakout_bars()
    bars[-1] = _orb_bar("2024-01-03 09:39", 100.35, 100.38, 100.25, 100.35)
    bars.extend(
        [
            _orb_bar("2024-01-03 09:40", 100.35, 100.38, 100.20, 100.30),
            _orb_bar("2024-01-03 09:41", 100.30, 100.36, 100.18, 100.28),
            _orb_bar("2024-01-03 09:42", 100.28, 100.37, 100.22, 100.31),
            _orb_bar("2024-01-03 09:43", 100.31, 100.39, 100.24, 100.35),
            _orb_bar("2024-01-03 09:44", 100.35, 100.55, 100.30, 100.50),
        ]
    )

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "long"
    assert signal.reclaim_timestamp == bars[-1]["timestamp"]
    assert signal.report_fields["confirmation_start_timestamp"] == bars[10]["timestamp"]
    assert signal.report_fields["breakout_timestamp"] == pd.Timestamp("2024-01-03 09:45", tz="America/New_York")


def test_opening_range_breakout_entry_rejects_confirmation_close_at_noon():
    entry = OpeningRangeBreakoutEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 5,
            "bar_interval_minutes": 1,
            "last_entry_time": "12:00:00",
            "allow_long": True,
            "allow_short": True,
        }
    )
    bars = [
        _orb_bar("2024-01-03 09:30", 100.0, 100.20, 99.90, 100.10),
        _orb_bar("2024-01-03 09:31", 100.1, 100.30, 100.00, 100.20),
        _orb_bar("2024-01-03 09:32", 100.2, 100.40, 100.10, 100.25),
        _orb_bar("2024-01-03 09:33", 100.2, 100.25, 99.95, 100.05),
        _orb_bar("2024-01-03 09:34", 100.0, 100.35, 100.05, 100.20),
        _orb_bar("2024-01-03 11:55", 100.2, 100.45, 100.10, 100.42),
        _orb_bar("2024-01-03 11:56", 100.4, 100.50, 100.20, 100.43),
        _orb_bar("2024-01-03 11:57", 100.4, 100.55, 100.30, 100.45),
        _orb_bar("2024-01-03 11:58", 100.4, 100.60, 100.35, 100.46),
        _orb_bar("2024-01-03 11:59", 100.4, 100.65, 100.35, 100.50),
    ]

    signal = None
    for bar in bars:
        signal = entry.on_bar_close(bar)

    assert signal is None


def test_opening_range_breakout_entry_skips_tuesday_longs():
    entry = OpeningRangeBreakoutEntry({"skip_tuesday_longs": True})
    bars = _orb_long_breakout_bars("2024-01-02")

    signal = None
    for bar in bars:
        signal = entry.on_bar_close(bar)

    assert signal is None


def test_opening_range_breakout_entry_skips_wide_opening_range():
    entry = OpeningRangeBreakoutEntry({"max_opening_range_pct_of_open": 0.0055})
    bars = [
        _orb_bar("2024-01-03 09:30", 100.0, 100.30, 99.90, 100.10),
        _orb_bar("2024-01-03 09:31", 100.1, 100.50, 100.00, 100.20),
        _orb_bar("2024-01-03 09:32", 100.2, 100.20, 100.00, 100.10),
        _orb_bar("2024-01-03 09:33", 100.1, 100.30, 100.00, 100.20),
        _orb_bar("2024-01-03 09:34", 100.2, 100.40, 100.10, 100.30),
        _orb_bar("2024-01-03 09:35", 100.3, 100.60, 100.20, 100.50),
        _orb_bar("2024-01-03 09:36", 100.5, 100.70, 100.40, 100.60),
        _orb_bar("2024-01-03 09:37", 100.6, 100.70, 100.50, 100.65),
        _orb_bar("2024-01-03 09:38", 100.6, 100.80, 100.50, 100.70),
        _orb_bar("2024-01-03 09:39", 100.7, 100.90, 100.60, 100.80),
    ]

    signal = None
    for bar in bars:
        signal = entry.on_bar_close(bar)

    assert signal is None


def test_opening_range_filtered_breakout_requires_volume_and_trade_aligned_vwap():
    entry = OpeningRangeFilteredBreakoutEntry(
        {
            "setup_mode": "continuation",
            "vwap_filter": "trade_aligned",
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 1,
            "bar_interval_minutes": 1,
            "max_opening_range_pct_of_open": 0.0055,
            "min_volume_ratio": 1.25,
            "skip_tuesday_longs": False,
        }
    )
    bars = _orb_long_breakout_bars()[:5]
    bars.append(_orb_bar("2024-01-03 09:35", 100.40, 100.55, 100.35, 100.50, volume_ratio=1.0, vwap=100.20))
    bars.append(_orb_bar("2024-01-03 09:36", 100.50, 100.60, 100.45, 100.55, volume_ratio=1.5, vwap=100.25))

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "long"
    assert signal.level_type == "opening_range_high_filtered"
    assert signal.report_fields["confirmation_volume_ratio"] == 1.5
    assert signal.report_fields["confirmation_vwap"] == 100.25
    assert signal.report_fields["trigger_side"] == "upside"


def test_opening_range_filtered_inverse_fade_uses_breakout_side_vwap():
    entry = OpeningRangeFilteredBreakoutEntry(
        {
            "setup_mode": "inverse_fade",
            "vwap_filter": "breakout_side",
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 1,
            "bar_interval_minutes": 1,
            "max_opening_range_pct_of_open": 0.0055,
            "min_volume_ratio": 1.25,
            "skip_tuesday_longs": False,
        }
    )
    bars = _orb_long_breakout_bars()[:5]
    bars.append(_orb_bar("2024-01-03 09:35", 99.95, 100.00, 99.70, 99.75, volume_ratio=1.5, vwap=100.00))

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "long"
    assert signal.level_type == "opening_range_low_filtered_inverse"
    assert signal.swept_level == 99.90
    assert signal.metadata["vwap_filter"] == "breakout_side"
    assert signal.metadata["trigger_side"] == "downside"


def test_opening_range_inverse_breakout_entry_goes_long_on_close_below_low():
    entry = OpeningRangeInverseBreakoutEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 1,
            "bar_interval_minutes": 1,
            "max_opening_range_pct_of_open": 0.0055,
            "allow_long": True,
            "allow_short": True,
            "skip_tuesday_longs": False,
        }
    )
    bars = _orb_long_breakout_bars()[:5]
    bars.append(_orb_bar("2024-01-03 09:35", 100.0, 100.05, 99.75, 99.80))

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "long"
    assert signal.level_type == "opening_range_low_inverse"
    assert signal.swept_level == 99.90
    assert signal.opening_range_high == 100.40
    assert round(signal.opening_range_width, 2) == 0.50
    assert signal.metadata["confirmation_close"] == 99.80
    assert signal.report_fields["breakout_timestamp"] == pd.Timestamp("2024-01-03 09:36", tz="America/New_York")


def test_opening_range_inverse_breakout_entry_goes_short_on_close_above_high():
    entry = OpeningRangeInverseBreakoutEntry(
        {
            "rth_start": "09:30:00",
            "opening_range_minutes": 5,
            "confirmation_minutes": 1,
            "bar_interval_minutes": 1,
            "max_opening_range_pct_of_open": 0.0055,
            "allow_long": True,
            "allow_short": True,
        }
    )
    bars = _orb_long_breakout_bars()[:5]
    bars.append(_orb_bar("2024-01-03 09:35", 100.40, 100.55, 100.30, 100.50))

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.direction == "short"
    assert signal.level_type == "opening_range_high_inverse"
    assert signal.swept_level == 100.40
    assert signal.opening_range_low == 99.90


def test_pdh_pdl_entry_module_emits_long_reclaim_signal():
    entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 2,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": True,
            "allow_short": False,
        }
    )
    bars = [
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.75,
                "high": 100.0,
                "close": 98.9,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=0,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:31", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.9,
                "high": 100.0,
                "close": 99.25,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=1,
        ),
    ]

    assert entry.on_bar_close(bars[0]) is None
    signal = entry.on_bar_close(bars[1])

    assert signal.direction == "long"
    assert signal.level_type == "previous_rth_low"
    assert signal.swept_level == 99.0


def test_pdh_pdl_entry_keeps_first_sweep_timestamp_and_tracks_extreme_until_reclaim():
    entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": True,
            "allow_short": False,
        }
    )
    bars = [
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.75,
                "high": 100.0,
                "close": 98.9,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=0,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:31", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.25,
                "high": 99.25,
                "close": 98.8,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=1,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:32", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.8,
                "high": 100.0,
                "close": 99.25,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=2,
        ),
    ]

    assert entry.on_bar_close(bars[0]) is None
    assert entry.on_bar_close(bars[1]) is None
    signal = entry.on_bar_close(bars[2])

    assert signal.sweep_timestamp == bars[0]["timestamp"]
    assert signal.sweep_low == 98.25
    assert signal.sweep_high == 100.0
    assert signal.reclaim_timestamp == bars[2]["timestamp"]


def test_pdh_pdl_entry_reclaim_window_counts_bars_between_sweep_and_reclaim():
    entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": True,
            "allow_short": False,
        }
    )
    bars = [
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.75,
                "high": 100.0,
                "close": 98.9,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=0,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:31", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.25,
                "high": 99.0,
                "close": 98.5,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=1,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:32", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.5,
                "high": 98.75,
                "close": 98.6,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=2,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:33", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.6,
                "high": 98.9,
                "close": 98.75,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=3,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:34", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.75,
                "high": 100.0,
                "close": 99.25,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=4,
        ),
    ]

    for bar in bars[:-1]:
        assert entry.on_bar_close(bar) is None
    signal = entry.on_bar_close(bars[-1])

    assert signal.sweep_timestamp == bars[0]["timestamp"]
    assert signal.sweep_low == 98.25
    assert signal.reclaim_timestamp == bars[-1]["timestamp"]


def test_pdh_pdl_entry_does_not_rearm_continuous_sweep_after_window_expires():
    entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": True,
            "allow_short": False,
        }
    )
    bars = [
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.75,
                "high": 100.0,
                "close": 98.8,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=0,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:31", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.5,
                "high": 99.0,
                "close": 98.7,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=1,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:32", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.25,
                "high": 98.75,
                "close": 98.6,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=2,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:33", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.0,
                "high": 98.75,
                "close": 98.5,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=3,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:34", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.1,
                "high": 98.75,
                "close": 98.6,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=4,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:35", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.5,
                "high": 100.0,
                "close": 99.25,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=5,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:36", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 98.75,
                "high": 99.0,
                "close": 98.8,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=6,
        ),
        pd.Series(
            {
                "timestamp": pd.Timestamp("2024-01-02 08:37", tz="America/Chicago"),
                "session_date": "2024-01-02",
                "is_rth": True,
                "low": 99.0,
                "high": 100.0,
                "close": 99.25,
                "prev_rth_low": 99.0,
                "prev_rth_high": 101.0,
                "volume_ratio": 1.0,
            },
            name=7,
        ),
    ]

    for bar in bars[:6]:
        assert entry.on_bar_close(bar) is None
    assert entry.on_bar_close(bars[6]) is None
    signal = entry.on_bar_close(bars[7])

    assert signal.sweep_timestamp == bars[6]["timestamp"]
    assert signal.reclaim_timestamp == bars[7]["timestamp"]


def test_pdh_pdl_entry_allows_reclaim_on_sweep_bar():
    long_entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": True,
            "allow_short": False,
        }
    )
    long_sweep_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
            "session_date": "2024-01-02",
            "is_rth": True,
            "low": 98.75,
            "high": 100.0,
            "close": 99.25,
            "prev_rth_low": 99.0,
            "prev_rth_high": 101.0,
            "volume_ratio": 1.0,
        },
        name=0,
    )
    long_reclaim_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-02 08:31", tz="America/Chicago"),
            "session_date": "2024-01-02",
            "is_rth": True,
            "low": 99.1,
            "high": 100.0,
            "close": 99.5,
            "prev_rth_low": 99.0,
            "prev_rth_high": 101.0,
            "volume_ratio": 1.0,
        },
        name=1,
    )

    long_signal = long_entry.on_bar_close(long_sweep_bar)
    assert long_entry.on_bar_close(long_reclaim_bar) is None

    assert long_signal.direction == "long"
    assert long_signal.sweep_timestamp == long_sweep_bar["timestamp"]
    assert long_signal.reclaim_timestamp == long_sweep_bar["timestamp"]

    short_entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": False,
            "allow_short": True,
        }
    )
    short_sweep_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
            "session_date": "2024-01-02",
            "is_rth": True,
            "low": 100.0,
            "high": 101.25,
            "close": 100.75,
            "prev_rth_low": 99.0,
            "prev_rth_high": 101.0,
            "volume_ratio": 1.0,
        },
        name=0,
    )
    short_reclaim_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-02 08:31", tz="America/Chicago"),
            "session_date": "2024-01-02",
            "is_rth": True,
            "low": 100.0,
            "high": 100.9,
            "close": 100.5,
            "prev_rth_low": 99.0,
            "prev_rth_high": 101.0,
            "volume_ratio": 1.0,
        },
        name=1,
    )

    short_signal = short_entry.on_bar_close(short_sweep_bar)
    assert short_entry.on_bar_close(short_reclaim_bar) is None

    assert short_signal.direction == "short"
    assert short_signal.sweep_timestamp == short_sweep_bar["timestamp"]
    assert short_signal.reclaim_timestamp == short_sweep_bar["timestamp"]


def test_pdh_pdl_entry_requires_fresh_previous_rth_level():
    long_entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": True,
            "allow_short": False,
        }
    )
    stale_low_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
            "session_date": "2024-01-02",
            "is_rth": True,
            "low": 98.75,
            "high": 100.0,
            "close": 99.25,
            "prev_rth_low": 99.0,
            "prev_rth_high": 101.0,
            "prev_rth_low_fresh": False,
            "prev_rth_high_fresh": True,
            "volume_ratio": 1.0,
        },
        name=0,
    )

    assert long_entry.on_bar_close(stale_low_bar) is None

    short_entry = PdhPdlSweepReclaimEntry(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": False,
            "allow_short": True,
        }
    )
    stale_high_bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-02 08:30", tz="America/Chicago"),
            "session_date": "2024-01-02",
            "is_rth": True,
            "low": 100.0,
            "high": 101.25,
            "close": 100.75,
            "prev_rth_low": 99.0,
            "prev_rth_high": 101.0,
            "prev_rth_low_fresh": True,
            "prev_rth_high_fresh": False,
            "volume_ratio": 1.0,
        },
        name=0,
    )

    assert short_entry.on_bar_close(stale_high_bar) is None


def _pdh_break_bar(timestamp, open_price, high, low, close, volume_ratio=1.0, name=None):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": True,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "prev_rth_low": 99.0,
            "prev_rth_high": 101.0,
            "prev_rth_low_fresh": True,
            "prev_rth_high_fresh": True,
            "volume_ratio": volume_ratio,
        },
        name=name if name is not None else ts.hour * 60 + ts.minute,
    )


def test_pdh_pdl_breakout_continuation_fresh_close_break_long():
    entry = PdhPdlBreakoutContinuationEntry(
        {
            "setup_mode": "fresh_close_break",
            "start_time": "09:30:00",
            "end_time": "10:30:00",
            "close_buffer_ticks": 1,
            "min_volume_ratio": 1.0,
            "tick_size": 0.25,
        }
    )
    bar = _pdh_break_bar("2024-01-03 09:35", 100.5, 101.8, 100.25, 101.25, volume_ratio=1.2, name=1)

    signal = entry.on_bar_close(bar)

    assert signal.direction == "long"
    assert signal.level_type == "previous_rth_high_breakout"
    assert signal.swept_level == 101.0
    assert signal.sweep_low == 100.25
    assert signal.report_fields["prev_rth_high"] == 101.0
    assert signal.report_fields["confirmation_volume_ratio"] == 1.2


def test_pdh_pdl_breakout_continuation_retest_waits_for_next_bar():
    entry = PdhPdlBreakoutContinuationEntry(
        {
            "setup_mode": "break_retest_hold",
            "start_time": "09:30:00",
            "end_time": "11:30:00",
            "close_buffer_ticks": 0,
            "retest_tolerance_ticks": 1,
            "retest_window_bars": 2,
            "tick_size": 0.25,
        }
    )
    breakout = _pdh_break_bar("2024-01-03 09:35", 100.5, 101.8, 100.9, 101.4, name=1)
    retest = _pdh_break_bar("2024-01-03 09:36", 101.4, 101.7, 100.9, 101.2, name=2)

    assert entry.on_bar_close(breakout) is None
    signal = entry.on_bar_close(retest)

    assert signal.direction == "long"
    assert signal.level_type == "previous_rth_high_retest"
    assert signal.sweep_low == 100.9
    assert signal.report_fields["breakout_timestamp"] == breakout["timestamp"]


def test_pdh_pdl_breakout_continuation_gap_hold_counts_bars():
    entry = PdhPdlBreakoutContinuationEntry(
        {
            "setup_mode": "gap_hold_continuation",
            "start_time": "09:30:00",
            "end_time": "10:00:00",
            "min_gap_points": 0.5,
            "gap_hold_bars": 2,
            "close_buffer_ticks": 0,
        }
    )
    first = _pdh_break_bar("2024-01-03 09:30", 101.6, 102.0, 101.2, 101.4, name=1)
    second = _pdh_break_bar("2024-01-03 09:31", 101.4, 101.8, 101.1, 101.3, name=2)

    assert entry.on_bar_close(first) is None
    signal = entry.on_bar_close(second)

    assert signal.direction == "long"
    assert signal.level_type == "previous_rth_high_gap_hold"
    assert signal.sweep_low == 101.1
    assert signal.report_fields["gap_open"] == 101.6


def test_pdh_pdl_breakout_continuation_rejects_stale_or_missing_level():
    entry = PdhPdlBreakoutContinuationEntry({"setup_mode": "fresh_close_break"})
    stale = _pdh_break_bar("2024-01-03 09:35", 100.5, 101.8, 100.25, 101.4, name=1)
    stale["prev_rth_high_fresh"] = False
    missing = _pdh_break_bar("2024-01-03 09:36", 100.5, 101.8, 100.25, 101.4, name=2)
    missing["prev_rth_high"] = pd.NA

    assert entry.on_bar_close(stale) is None
    assert entry.on_bar_close(missing) is None


def _gap_bar(timestamp, open_price, high, low, close, vwap=101.0, prev_close=100.0, name=None):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": True,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "vwap": vwap,
            "prev_rth_close": prev_close,
        },
        name=name if name is not None else ts.hour * 60 + ts.minute,
    )


def test_rth_gap_fade_open_reversal_short_signal():
    entry = RthGapFadeEntry(
        {
            "setup_mode": "open_reversal",
            "min_gap_points": 2.0,
            "confirmation_buffer_ticks": 1,
            "tick_size": 0.25,
        }
    )
    bar = _gap_bar("2024-01-03 09:30", 103.0, 103.5, 102.0, 102.75, prev_close=100.0, name=1)

    signal = entry.on_bar_close(bar)

    assert signal.direction == "short"
    assert signal.level_type == "rth_gap_open_reversal"
    assert signal.sweep_high == 103.5
    assert signal.report_fields["prev_rth_close"] == 100.0
    assert signal.report_fields["gap_points"] == 3.0


def test_rth_gap_fade_extension_reject_waits_for_extension():
    entry = RthGapFadeEntry(
        {
            "setup_mode": "extension_reject",
            "min_gap_points": 2.0,
            "min_extension_points": 1.0,
        }
    )
    first = _gap_bar("2024-01-03 09:30", 103.0, 103.5, 102.0, 102.8, prev_close=100.0, name=1)
    second = _gap_bar("2024-01-03 09:31", 102.8, 104.2, 102.2, 102.7, prev_close=100.0, name=2)

    assert entry.on_bar_close(first) is None
    signal = entry.on_bar_close(second)

    assert signal.direction == "short"
    assert signal.sweep_high == 104.2


def test_rth_gap_fade_vwap_reclaim_long_signal():
    entry = RthGapFadeEntry(
        {
            "setup_mode": "vwap_reclaim",
            "min_gap_points": 2.0,
            "confirmation_buffer_ticks": 0,
        }
    )
    signal = entry.on_bar_close(
        _gap_bar("2024-01-03 09:30", 97.0, 99.8, 96.5, 99.4, vwap=99.0, prev_close=100.0, name=1)
    )

    assert signal.direction == "long"
    assert signal.sweep_low == 96.5


def test_rth_gap_fade_rejects_missing_previous_close():
    entry = RthGapFadeEntry({"setup_mode": "open_reversal"})
    bar = _gap_bar("2024-01-03 09:30", 103.0, 103.5, 102.0, 102.75, name=1)
    bar["prev_rth_close"] = pd.NA

    assert entry.on_bar_close(bar) is None
