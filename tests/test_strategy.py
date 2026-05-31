from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.strategy.pdh_pdl_sweep import PdhPdlSweepReclaim

from tests.test_data_pipeline import DATA_CFG


def test_pdh_pdl_sweep_signal_reclaim_within_n_bars():
    df, _, _ = clean_data(DATA_CFG)
    feat = build_features(df, DATA_CFG).reset_index(drop=True)
    strat = PdhPdlSweepReclaim(
        {
            "reclaim_window_bars": 3,
            "start_time": "08:30:00",
            "end_time": "14:45:00",
            "allow_long": True,
            "allow_short": True,
        }
    )
    signals = []
    for _, bar in feat.iterrows():
        sig = strat.on_bar_close(bar)
        if sig:
            signals.append(sig)
    assert any(s.direction == "long" for s in signals)
    assert any(s.direction == "short" for s in signals)
