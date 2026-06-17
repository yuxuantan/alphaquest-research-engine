from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/es_intraday_periodicity_features_20110103_20260609.csv"
DEFAULT_SLOTS = [
    ("slot_1000_1030", "10:00:00", "10:30:00"),
    ("slot_1030_1100", "10:30:00", "11:00:00"),
    ("slot_1130_1200", "11:30:00", "12:00:00"),
    ("slot_1330_1400", "13:30:00", "14:00:00"),
    ("slot_1430_1500", "14:30:00", "15:00:00"),
]


def build_features(
    input_path: str | Path,
    output_path: str | Path,
    *,
    slots: list[tuple[str, str, str]] | None = None,
    lookback_days: tuple[int, ...] = (10, 20, 40),
    min_period_fraction: float = 1.0,
) -> pd.DataFrame:
    bars = pd.read_parquet(input_path, columns=["timestamp", "open", "close"])
    bars = bars.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    bars["session_date"] = bars["timestamp"].dt.date.astype(str)
    bars["time"] = bars["timestamp"].dt.strftime("%H:%M:%S")

    rows: list[dict] = []
    for slot_id, entry_time, slot_end_time in slots or DEFAULT_SLOTS:
        slot_returns = _slot_returns(bars, slot_id, entry_time, slot_end_time)
        rows.extend(_lagged_features(slot_returns, lookback_days, min_period_fraction).to_dict("records"))

    out = pd.DataFrame(rows).sort_values(["session_date", "slot_id"], kind="mergesort").reset_index(drop=True)
    out = out.loc[out["session_date"] >= "2011-01-03"].copy()
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _slot_returns(bars: pd.DataFrame, slot_id: str, entry_time: str, slot_end_time: str) -> pd.DataFrame:
    entry_rows = (
        bars.loc[bars["time"] == entry_time, ["session_date", "timestamp", "open"]]
        .rename(columns={"timestamp": "entry_timestamp", "open": "slot_entry_open"})
        .copy()
    )
    end_ts = pd.to_datetime("2000-01-01 " + slot_end_time)
    prior_end_time = (end_ts - pd.Timedelta(minutes=1)).strftime("%H:%M:%S")
    end_rows = (
        bars.loc[bars["time"] == prior_end_time, ["session_date", "timestamp", "close"]]
        .rename(columns={"timestamp": "slot_last_bar_timestamp", "close": "slot_exit_close"})
        .copy()
    )
    merged = entry_rows.merge(end_rows, on="session_date", how="inner")
    merged = merged.loc[merged["slot_entry_open"] > 0].copy()
    merged["slot_id"] = slot_id
    merged["entry_time"] = entry_time
    merged["slot_end_time"] = slot_end_time
    merged["slot_return_bps"] = (merged["slot_exit_close"] / merged["slot_entry_open"] - 1.0) * 10_000.0
    return merged.sort_values("session_date", kind="mergesort").reset_index(drop=True)


def _lagged_features(slot_returns: pd.DataFrame, lookback_days: tuple[int, ...], min_period_fraction: float) -> pd.DataFrame:
    out = slot_returns[
        [
            "session_date",
            "slot_id",
            "entry_time",
            "slot_end_time",
        ]
    ].copy()
    prior = slot_returns["slot_return_bps"].shift(1)
    for lookback in lookback_days:
        min_periods = max(1, int(round(float(lookback) * float(min_period_fraction))))
        window = prior.rolling(int(lookback), min_periods=min_periods)
        out[f"prior_slot_return_mean_bps_{lookback}"] = window.mean()
        out[f"prior_slot_return_pos_rate_{lookback}"] = window.apply(lambda values: float((values > 0).mean()), raw=True)
        out[f"prior_slot_return_obs_{lookback}"] = window.count()
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(args.input, args.output)
    valid = features.dropna(subset=["prior_slot_return_mean_bps_20"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_mean20_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
