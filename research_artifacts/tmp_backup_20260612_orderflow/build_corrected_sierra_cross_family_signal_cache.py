from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd


VC_PATH = Path("/private/tmp/corrected_sierra_volume_curve_flow_fast.py")
OUT = Path("/private/tmp/corrected_sierra_cross_family_top_signal_cache.parquet")


spec = importlib.util.spec_from_file_location("vcfast", VC_PATH)
vc = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(vc)


SIGNAL_COLUMNS = [
    "of_xfam_1000_short_180",
    "of_xfam_1030_short_120",
    "of_xfam_1330_long_120",
    "of_xfam_1330_short_120",
    "of_xfam_1430_long_60",
    "of_xfam_1430_short_60",
    "of_xfam_1500_long_60",
]


def mark(cache: pd.DataFrame, snap: pd.DataFrame, mask, column: str) -> None:
    signal_ts = pd.to_datetime(snap.loc[mask.fillna(False), "entry_ts"]) - pd.Timedelta(minutes=1)
    if signal_ts.empty:
        return
    cache.loc[cache["timestamp"].isin(set(signal_ts)), column] = True


def main() -> None:
    df = pd.read_parquet(vc.SOURCE)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    dates, data, minutes = vc.matrices(df)
    vc.ENTRY_TIMES = ["10:00", "10:30", "13:30", "14:30", "15:00"]
    vc.WINDOWS = [15, 30, 60]
    vc.HOLDS = [60, 120, 180]
    snap = vc.build_snapshots(dates, data, minutes)

    cache = df.copy()
    for col in SIGNAL_COLUMNS:
        cache[col] = False

    # 10:00 short, 180-minute hold: OR of same-direction flow continuation and VWAP-stretch fade.
    s = snap[(snap["entry_time"] == "10:00") & (snap["window"] == 30) & (snap["hold"] == 180)]
    m_cont_short = (
        (s["source_trades_rank63"] >= 0.8)
        & (s["source_large20_imbalance"] <= -0.1)
        & (s["source_return_ticks"] <= 0)
    )
    m_vwap_fade_short = (
        (s["source_volume_rank63"] >= 0.8)
        & (s["source_large20_imbalance"] >= 0.1)
        & (s["source_return_ticks"] >= 8)
        & (s["session_vwap_dist_ticks"] >= 8)
    )
    mark(cache, s, m_cont_short | m_vwap_fade_short, "of_xfam_1000_short_180")

    # 10:30 short, 120-minute hold: participation large20 composition continuation.
    s = snap[(snap["entry_time"] == "10:30") & (snap["window"] == 30) & (snap["hold"] == 120)]
    m = (s["source_large20_imbalance"] <= -0.1) & (s["source_avg_trade_size_rank63"] >= 0.7) & (
        s["source_return_ticks"] <= 0
    )
    mark(cache, s, m, "of_xfam_1030_short_120")

    # 13:30 long/short, 120-minute hold: no-price flow follow plus positive-flow continuation long.
    s15 = snap[(snap["entry_time"] == "13:30") & (snap["window"] == 15) & (snap["hold"] == 120)]
    m_np_long = (
        (s15["source_avg_trade_size_rank63"] >= 0.8)
        & (s15["source_large20_imbalance"] >= 0.1)
        & (s15["source_return_ticks"].abs() <= 8)
    )
    m_np_short = (
        (s15["source_avg_trade_size_rank63"] >= 0.8)
        & (s15["source_large20_imbalance"] <= -0.1)
        & (s15["source_return_ticks"].abs() <= 8)
    )
    mark(cache, s15, m_np_long, "of_xfam_1330_long_120")
    mark(cache, s15, m_np_short, "of_xfam_1330_short_120")
    s60 = snap[(snap["entry_time"] == "13:30") & (snap["window"] == 60) & (snap["hold"] == 120)]
    m_cont_long = (
        (s60["source_volume_rank63"] >= 0.9)
        & (s60["source_large20_imbalance"] >= 0.1)
        & (s60["source_return_ticks"] >= 0)
    )
    mark(cache, s60, m_cont_long, "of_xfam_1330_long_120")

    # 14:30 long/short, 60-minute hold: high trade-count flow continuation.
    s = snap[(snap["entry_time"] == "14:30") & (snap["window"] == 60) & (snap["hold"] == 60)]
    mark(
        cache,
        s,
        (s["source_trades_rank63"] >= 0.9) & (s["source_large20_imbalance"] >= 0.1) & (s["source_return_ticks"] >= 0),
        "of_xfam_1430_long_60",
    )
    mark(
        cache,
        s,
        (s["source_trades_rank63"] >= 0.9) & (s["source_large20_imbalance"] <= -0.1) & (s["source_return_ticks"] <= 0),
        "of_xfam_1430_short_60",
    )

    # 15:00 long, 60-minute hold: high average trade size flow continuation.
    s = snap[(snap["entry_time"] == "15:00") & (snap["window"] == 60) & (snap["hold"] == 60)]
    mark(
        cache,
        s,
        (s["source_avg_trade_size_rank63"] >= 0.8)
        & (s["source_large20_imbalance"] >= 0.1)
        & (s["source_return_ticks"] >= 0),
        "of_xfam_1500_long_60",
    )

    counts = {col: int(cache[col].sum()) for col in SIGNAL_COLUMNS}
    print(counts, flush=True)
    cache.to_parquet(OUT, index=False)
    print(OUT, len(cache), flush=True)


if __name__ == "__main__":
    main()
