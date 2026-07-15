import pandas as pd

from alphaquest.strategy_modules.entry.mes_footprint_liquidity_sweep_reversion import (
    MesFootprintLiquiditySweepReversionEntry,
)


def test_mes_footprint_liquidity_sweep_reversion_emits_long_after_absorbed_sweep():
    entry = MesFootprintLiquiditySweepReversionEntry(
        {
            "start_time": "09:32:00",
            "end_time": "10:00:00",
            "lookback_bars": 2,
            "min_sweep_ticks": 1,
            "share_rank_min": 0.60,
            "min_mes_imbalance": 0.05,
            "direction": "long",
        }
    )

    assert entry.on_bar_close(_bar("2026-06-10 09:30", low=100.0, high=101.0, close=100.5)) is None
    assert entry.on_bar_close(_bar("2026-06-10 09:31", low=100.25, high=101.0, close=100.75)) is None
    signal = entry.on_bar_close(
        _bar(
            "2026-06-10 09:32",
            low=99.5,
            high=100.5,
            close=100.0,
            footprint_absorption_long=1,
            footprint_max_sell_imbalance_volume=30,
            footprint_highest_sell_imbalance_price=99.75,
            mes_participation_share_15_rank252=0.70,
            mes_trade_orderflow_imbalance_15=-0.20,
        )
    )

    assert signal is not None
    assert signal.direction == "long"
    assert signal.swept_level == 100.0
    assert signal.sweep_low == 99.5
    assert signal.report_fields["share_rank"] == 0.70
    assert signal.report_fields["mes_imbalance"] == -0.20


def test_mes_footprint_liquidity_sweep_reversion_emits_short_after_absorbed_sweep():
    entry = MesFootprintLiquiditySweepReversionEntry(
        {
            "start_time": "09:32:00",
            "end_time": "10:00:00",
            "lookback_bars": 2,
            "min_sweep_ticks": 1,
            "share_mode": "trade",
            "share_rank_min": 0.60,
            "mes_imbalance_column": "mes_trade_orderflow_large10_imbalance_15",
            "min_mes_imbalance": 0.05,
            "direction": "short",
        }
    )

    assert entry.on_bar_close(_bar("2026-06-10 09:30", low=100.0, high=101.0, close=100.5)) is None
    assert entry.on_bar_close(_bar("2026-06-10 09:31", low=100.25, high=101.0, close=100.75)) is None
    signal = entry.on_bar_close(
        _bar(
            "2026-06-10 09:32",
            low=100.5,
            high=101.5,
            close=101.0,
            footprint_absorption_short=1,
            footprint_max_buy_imbalance_volume=35,
            footprint_lowest_buy_imbalance_price=101.25,
            mes_trade_share_15_rank252=0.80,
            mes_trade_orderflow_large10_imbalance_15=0.15,
        )
    )

    assert signal is not None
    assert signal.direction == "short"
    assert signal.swept_level == 101.0
    assert signal.sweep_high == 101.5
    assert signal.report_fields["share_mode"] == "trade"


def test_mes_footprint_liquidity_sweep_reversion_rejects_without_footprint_absorption():
    entry = MesFootprintLiquiditySweepReversionEntry(
        {
            "start_time": "09:32:00",
            "end_time": "10:00:00",
            "lookback_bars": 2,
            "share_rank_min": 0.60,
            "direction": "long",
        }
    )

    assert entry.on_bar_close(_bar("2026-06-10 09:30", low=100.0, high=101.0, close=100.5)) is None
    assert entry.on_bar_close(_bar("2026-06-10 09:31", low=100.25, high=101.0, close=100.75)) is None
    assert (
        entry.on_bar_close(
            _bar(
                "2026-06-10 09:32",
                low=99.5,
                high=100.5,
                close=100.0,
                footprint_absorption_long=0,
                mes_participation_share_15_rank252=0.90,
                mes_trade_orderflow_imbalance_15=-0.20,
            )
        )
        is None
    )


def _bar(
    timestamp,
    *,
    open_=100.5,
    high=101.0,
    low=100.0,
    close=100.5,
    footprint_absorption_long=0,
    footprint_absorption_short=0,
    footprint_max_sell_imbalance_volume=0,
    footprint_max_buy_imbalance_volume=0,
    footprint_highest_sell_imbalance_price=0.0,
    footprint_lowest_buy_imbalance_price=999.0,
    mes_participation_share_15_rank252=0.0,
    mes_participation_share_30_rank252=0.0,
    mes_trade_share_15_rank252=0.0,
    mes_trade_share_30_rank252=0.0,
    mes_trade_orderflow_imbalance_15=0.0,
    mes_trade_orderflow_imbalance_30=0.0,
    mes_trade_orderflow_large10_imbalance_15=0.0,
    mes_trade_orderflow_large10_imbalance_30=0.0,
):
    ts = pd.Timestamp(timestamp, tz="America/New_York")
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date(),
            "is_rth": True,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "footprint_absorption_long": footprint_absorption_long,
            "footprint_absorption_short": footprint_absorption_short,
            "footprint_max_sell_imbalance_volume": footprint_max_sell_imbalance_volume,
            "footprint_max_buy_imbalance_volume": footprint_max_buy_imbalance_volume,
            "footprint_highest_sell_imbalance_price": footprint_highest_sell_imbalance_price,
            "footprint_lowest_buy_imbalance_price": footprint_lowest_buy_imbalance_price,
            "mes_participation_share_15_rank252": mes_participation_share_15_rank252,
            "mes_participation_share_30_rank252": mes_participation_share_30_rank252,
            "mes_trade_share_15_rank252": mes_trade_share_15_rank252,
            "mes_trade_share_30_rank252": mes_trade_share_30_rank252,
            "mes_trade_orderflow_imbalance_15": mes_trade_orderflow_imbalance_15,
            "mes_trade_orderflow_imbalance_30": mes_trade_orderflow_imbalance_30,
            "mes_trade_orderflow_large10_imbalance_15": mes_trade_orderflow_large10_imbalance_15,
            "mes_trade_orderflow_large10_imbalance_30": mes_trade_orderflow_large10_imbalance_30,
        }
    )
