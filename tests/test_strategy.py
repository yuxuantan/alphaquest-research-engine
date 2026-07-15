from alphaquest.data.clean import clean_data
from alphaquest.data.features import build_features
from alphaquest.strategy import ModularStrategy

from tests.test_data_pipeline import DATA_CFG


def test_modular_strategy_composes_entry_tp_and_sl_modules():
    df, _, _ = clean_data(DATA_CFG)
    feat = build_features(df, DATA_CFG).reset_index(drop=True)
    strat = ModularStrategy(
        {
            "strategy_name": "pdh_pdl_sweep",
            "entry": {
                "module": "pdh_pdl_sweep_reclaim",
                "params": {
                    "reclaim_window_bars": 3,
                    "start_time": "08:30:00",
                    "end_time": "14:45:00",
                    "allow_long": True,
                    "allow_short": True,
                },
            },
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.5}},
            "sl": {"module": "sweep_extreme", "params": {"stop_offset_ticks": 1}},
        }
    )
    assert strat.entry.name == "pdh_pdl_sweep_reclaim"
    assert strat.tp.name == "fixed_r"
    assert strat.sl.name == "sweep_extreme"
    signals = []
    for _, bar in feat.iterrows():
        sig = strat.on_bar_close(bar)
        if sig:
            signals.append(sig)
    assert any(s.direction == "long" for s in signals)
    assert any(s.direction == "short" for s in signals)


def test_modular_strategy_composes_opening_range_modules():
    strat = ModularStrategy(
        {
            "strategy_name": "five_min_orb_vol_filter",
            "entry": {
                "module": "opening_range_breakout",
                "params": {
                    "rth_start": "09:30:00",
                    "opening_range_minutes": 5,
                    "confirmation_minutes": 5,
                    "bar_interval_minutes": 1,
                },
            },
            "tp": {"module": "opening_range_extension", "params": {"extension_fraction": 0.5}},
            "sl": {"module": "opening_range_edge", "params": {"max_stop_points": 14}},
        }
    )

    assert strat.entry.name == "opening_range_breakout"
    assert strat.tp.name == "opening_range_extension"
    assert strat.sl.name == "opening_range_edge"


def test_modular_strategy_composes_cost_adjusted_fixed_r_target():
    strat = ModularStrategy(
        {
            "strategy_name": "five_min_orb_vol_filter",
            "entry": {
                "module": "opening_range_breakout",
                "params": {
                    "rth_start": "09:30:00",
                    "opening_range_minutes": 5,
                    "confirmation_minutes": 5,
                    "bar_interval_minutes": 1,
                },
            },
            "tp": {
                "module": "cost_adjusted_fixed_r",
                "params": {
                    "target_r_multiple": 1.0,
                    "tick_size": 0.25,
                    "tick_value": 12.50,
                    "commission_per_contract": 2.50,
                    "slippage_ticks": 1,
                },
            },
            "sl": {"module": "opening_range_edge", "params": {"max_stop_points": 14}},
        }
    )

    assert strat.entry.name == "opening_range_breakout"
    assert strat.tp.name == "cost_adjusted_fixed_r"
    assert strat.sl.name == "opening_range_edge"


def test_modular_strategy_composes_filtered_opening_range_entry():
    strat = ModularStrategy(
        {
            "strategy_name": "opening_range_filtered_breakout",
            "entry": {
                "module": "opening_range_filtered_breakout",
                "params": {
                    "setup_mode": "continuation",
                    "vwap_filter": "trade_aligned",
                    "rth_start": "09:30:00",
                    "opening_range_minutes": 5,
                    "confirmation_minutes": 1,
                    "bar_interval_minutes": 1,
                    "min_volume_ratio": 1.25,
                },
            },
            "tp": {"module": "opening_range_extension", "params": {"extension_fraction": 1.0}},
            "sl": {"module": "opening_range_edge", "params": {"max_stop_points": 14}},
        }
    )

    assert strat.entry.name == "opening_range_filtered_breakout"
    assert strat.tp.name == "opening_range_extension"
    assert strat.sl.name == "opening_range_edge"


def test_modular_strategy_composes_inverse_opening_range_modules():
    strat = ModularStrategy(
        {
            "strategy_name": "five_min_orb_vol_filter_inverse",
            "entry": {
                "module": "opening_range_inverse_breakout",
                "params": {
                    "rth_start": "09:30:00",
                    "opening_range_minutes": 5,
                    "confirmation_minutes": 1,
                    "bar_interval_minutes": 1,
                },
            },
            "tp": {"module": "opening_range_opposite_edge", "params": {}},
            "sl": {"module": "opening_range_width", "params": {"max_stop_points": 14}},
        }
    )

    assert strat.entry.name == "opening_range_inverse_breakout"
    assert strat.tp.name == "opening_range_opposite_edge"
    assert strat.sl.name == "opening_range_width"


def test_modular_strategy_composes_intraday_capitulation_modules():
    strat = ModularStrategy(
        {
            "strategy_name": "intraday_capitulation_mr",
            "entry": {
                "module": "intraday_capitulation_mr",
                "params": {
                    "timeframe_minutes": 15,
                    "rsi_period": 14,
                    "min_volume_ratio": 1.5,
                    "max_trades_per_day": 1,
                },
            },
            "tp": {"module": "percent_from_entry", "params": {"target_pct": 0.0075, "tick_size": 0.25}},
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.003}},
        }
    )

    assert strat.entry.name == "intraday_capitulation_mr"
    assert strat.tp.name == "percent_from_entry"
    assert strat.sl.name == "percent_from_entry"


def test_modular_strategy_requires_entry_tp_and_sl_sections():
    try:
        ModularStrategy(
            {
                "entry": {
                    "module": "pdh_pdl_sweep_reclaim",
                    "params": {"reclaim_window_bars": 3},
                }
            }
        )
    except ValueError as exc:
        assert "Missing: tp, sl" in str(exc)
    else:
        raise AssertionError("Expected modular config validation to fail")
