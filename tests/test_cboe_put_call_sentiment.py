from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.cboe_put_call_sentiment import CboePutCallSentimentEntry
from tools.build_es_cboe_put_call_features import build_features


def test_low_equity_put_call_entry_emits_long_on_completed_bar(tmp_path):
    features = _feature_file(tmp_path, "2024-03-20", equity_rank=0.18)
    entry = CboePutCallSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "low_equity_pc_long",
            "pc_rank_max": 0.35,
            "entry_time": "10:00:00",
            "bar_interval_minutes": 1,
        }
    )

    signal = entry.on_bar_close(_bar("2024-03-20 09:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2024-03-20 10:00")
    assert signal.report_fields["put_call_driver_column"] == "equity_pc_ratio_rank_252"
    assert signal.report_fields["feature_session_date"] == "2024-03-20"


def test_high_equity_put_call_entry_emits_short(tmp_path):
    features = _feature_file(tmp_path, "2024-03-20", equity_rank=0.82)
    entry = CboePutCallSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_equity_pc_short",
            "pc_rank_min": 0.65,
            "entry_time": "10:30:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-03-20 10:29", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"


def test_index_vs_equity_spread_requires_rank_threshold(tmp_path):
    features = _feature_file(tmp_path, "2024-03-20", equity_rank=0.5, spread_rank=0.55)
    entry = CboePutCallSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_index_vs_equity_pc_short",
            "pc_spread_rank_min": 0.65,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-03-20 13:29", close=4801.0)) is None

    features = _feature_file(
        tmp_path,
        "2024-03-21",
        equity_rank=0.5,
        spread_rank=0.80,
        name="spread.csv",
    )
    entry = CboePutCallSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "high_index_vs_equity_pc_short",
            "pc_spread_rank_min": 0.65,
            "entry_time": "13:30:00",
        }
    )
    assert entry.on_bar_close(_bar("2024-03-21 13:29", close=4801.0)) is not None


def test_rising_total_put_call_entry_uses_total_change_rank(tmp_path):
    features = _feature_file(tmp_path, "2024-03-20", equity_rank=0.5, total_change_rank=0.82)
    entry = CboePutCallSentimentEntry(
        {
            "feature_csv": str(features),
            "setup_mode": "rising_total_pc_short",
            "pc_change_rank_min": 0.60,
            "entry_time": "12:00:00",
        }
    )

    signal = entry.on_bar_close(_bar("2024-03-20 11:59", close=4801.0))

    assert signal is not None
    assert signal.direction == "short"
    assert signal.report_fields["put_call_driver_column"] == "total_pc_change_1d_rank_252"


def test_builder_uses_latest_prior_cboe_observation_only(tmp_path):
    sessions = pd.date_range("2024-01-02", periods=90, freq="B")
    bars_path = tmp_path / "bars.parquet"
    pd.DataFrame([{"timestamp": pd.Timestamp(f"{session:%Y-%m-%d} 09:30")} for session in sessions]).to_parquet(
        bars_path
    )

    cboe_dates = pd.date_range("2023-08-01", "2024-05-31", freq="B")
    equity_path = tmp_path / "equity.csv"
    index_path = tmp_path / "index.csv"
    total_path = tmp_path / "total.csv"
    _write_cboe_csv(equity_path, cboe_dates, start_ratio=0.55)
    _write_cboe_csv(index_path, cboe_dates, start_ratio=1.20, trade_date_header=True)
    _write_cboe_csv(total_path, cboe_dates, start_ratio=0.90, calls_label="CALLS", puts_label="PUTS")
    out_path = tmp_path / "features.csv"

    features = build_features(
        bars_path,
        out_path,
        equity_input=equity_path,
        index_input=index_path,
        total_input=total_path,
        rank_min_periods=10,
    )

    first = features.loc[features["session_date"] == "2024-01-02"].iloc[0]
    second = features.loc[features["session_date"] == "2024-01-03"].iloc[0]
    later = features.loc[features["session_date"] == sessions[20].strftime("%Y-%m-%d")].iloc[0]
    assert first["observation_date"] == "2024-01-01"
    assert second["observation_date"] == "2024-01-02"
    assert math.isfinite(later["equity_pc_ratio_rank_252"])
    assert math.isfinite(later["index_minus_equity_pc_rank_252"])


def _feature_file(
    tmp_path,
    session_date: str,
    *,
    equity_rank: float,
    equity_change_rank: float = 0.2,
    index_change_rank: float = 0.8,
    total_change_rank: float = 0.6,
    spread_rank: float = 0.8,
    name: str = "put_call.csv",
):
    path = tmp_path / name
    path.write_text(
        "session_date,observation_date,equity_pc_ratio,index_pc_ratio,total_pc_ratio,"
        "equity_call_volume,equity_put_volume,index_call_volume,index_put_volume,"
        "total_call_volume,total_put_volume,equity_pc_change_1d,index_pc_change_1d,"
        "total_pc_change_1d,equity_pc_change_5d,index_pc_change_5d,total_pc_change_5d,"
        "index_minus_equity_pc,total_minus_equity_pc,equity_pc_ratio_rank_252,"
        "index_pc_ratio_rank_252,total_pc_ratio_rank_252,equity_pc_change_1d_rank_252,"
        "index_pc_change_1d_rank_252,total_pc_change_1d_rank_252,"
        "equity_pc_change_5d_rank_252,index_pc_change_5d_rank_252,"
        "total_pc_change_5d_rank_252,index_minus_equity_pc_rank_252,"
        "total_minus_equity_pc_rank_252\n"
        f"{session_date},2024-03-19,0.55,1.20,0.90,100,55,100,120,200,180,"
        f"-0.05,0.10,0.02,-0.08,0.12,0.04,0.65,0.35,{equity_rank},0.7,0.6,"
        f"{equity_change_rank},{index_change_rank},{total_change_rank},0.25,0.75,0.6,{spread_rank},0.7\n",
        encoding="utf-8",
    )
    return path


def _write_cboe_csv(
    path,
    dates,
    *,
    start_ratio: float,
    trade_date_header: bool = False,
    calls_label: str = "CALL",
    puts_label: str = "PUT",
):
    date_label = "Trade_date" if trade_date_header else "DATE"
    lines = [
        "Cboe disclaimer line,,,,",
        f"{date_label},{calls_label},{puts_label},TOTAL,P/C Ratio",
    ]
    for index, day in enumerate(dates):
        ratio = start_ratio + index * 0.001
        calls = 100000 + index
        puts = int(calls * ratio)
        lines.append(f"{day:%m/%d/%Y},{calls},{puts},{calls + puts},{ratio:.3f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _bar(timestamp, *, close: float, is_rth: bool = True):
    ts = pd.Timestamp(timestamp)
    return pd.Series(
        {
            "timestamp": ts,
            "session_date": ts.date().isoformat(),
            "is_rth": is_rth,
            "open": close - 0.5,
            "high": close + 0.25,
            "low": close - 0.25,
            "close": close,
            "volume": 1000,
        }
    )
