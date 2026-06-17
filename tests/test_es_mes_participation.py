import pandas as pd

from propstack.data.es_mes_participation import build_es_mes_participation_features
from propstack.strategy_modules.entry.mes_participation_crowding import MesParticipationCrowdingEntry


def test_mes_participation_features_use_prior_same_clock_history_only():
    rows = []
    for day, mes_volume in [
        ("2024-01-02", 100),
        ("2024-01-03", 200),
        ("2024-01-04", 300),
    ]:
        rows.append(
            {
                "timestamp": f"{day} 10:00:00",
                "open": 100,
                "high": 101,
                "low": 99,
                "close": 100,
                "volume": 1000,
                "trades": 100,
                "mes_volume": mes_volume,
                "mes_trades": 20,
            }
        )
    features = build_es_mes_participation_features(
        pd.DataFrame(rows),
        windows=(1,),
        rank_window=2,
        rank_min_periods=1,
    )

    ranks = features["mes_participation_share_1_rank2"].tolist()
    assert pd.isna(ranks[0])
    assert ranks[1] == 1.0
    assert ranks[2] == 1.0


def test_mes_participation_entry_fades_high_share_down_move():
    entry = MesParticipationCrowdingEntry(
        {
            "entry_time": "10:30:00",
            "flatten_time": "12:00:00",
            "lookback_minutes": 30,
            "rank_window": 252,
            "share_mode": "notional",
            "direction": "long",
            "share_rank_min": 0.65,
            "min_abs_return_ticks": 4,
            "stop_pct": 0.0025,
            "target_r_multiple": 1.5,
        }
    )
    bar = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-03 10:29:00"),
            "is_rth": True,
            "open": 100.0,
            "high": 100.5,
            "low": 99.0,
            "close": 99.5,
            "mes_participation_share_30": 0.08,
            "mes_participation_share_30_rank252": 0.8,
            "es_return_ticks_30": -5.0,
        }
    )

    signal = entry.on_bar_close(bar)

    assert signal is not None
    assert signal.direction == "long"
    assert signal.report_fields["share_rank"] == 0.8


def test_mes_participation_entry_respects_direction_and_entry_time():
    entry = MesParticipationCrowdingEntry(
        {
            "entry_time": "10:30:00",
            "lookback_minutes": 30,
            "direction": "short",
            "share_rank_min": 0.65,
            "min_abs_return_ticks": 4,
        }
    )
    wrong_time = pd.Series(
        {
            "timestamp": pd.Timestamp("2024-01-03 10:28:00"),
            "is_rth": True,
            "open": 100.0,
            "high": 101.0,
            "low": 99.5,
            "close": 101.0,
            "mes_participation_share_30": 0.08,
            "mes_participation_share_30_rank252": 0.8,
            "es_return_ticks_30": 5.0,
        }
    )
    valid_time = wrong_time.copy()
    valid_time["timestamp"] = pd.Timestamp("2024-01-03 10:29:00")

    assert entry.on_bar_close(wrong_time) is None
    signal = entry.on_bar_close(valid_time)
    assert signal is not None
    assert signal.direction == "short"
