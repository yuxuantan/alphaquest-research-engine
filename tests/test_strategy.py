from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.strategy.pdh_pdl_sweep import PdhPdlSweepReclaim

from tests.test_data_pipeline import DATA_CFG


def test_pdh_pdl_sweep_signal_reclaim_within_n_bars():
    df, _, _ = clean_data(DATA_CFG)
    feat = build_features(df, DATA_CFG).reset_index(drop=True)
    strat = PdhPdlSweepReclaim(
        {
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


def test_pdh_pdl_strategy_requires_modular_config():
    try:
        PdhPdlSweepReclaim(
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
