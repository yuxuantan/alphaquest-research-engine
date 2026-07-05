from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = "data/cache/databento/nq_databento_ohlcv_1m_20100606_20260531_eth_rth_explicit_roll.parquet"
DEFAULT_OUTPUT = "data/external/nq_overnight_range_features_20110103_20260529.csv"


def build_features(input_path: str | Path, output_path: str | Path) -> pd.DataFrame:
    bars = pd.read_parquet(input_path, columns=["timestamp", "open", "high", "low", "close", "volume"])
    bars = bars.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    timestamps = pd.to_datetime(bars["timestamp"])
    if timestamps.dt.tz is None:
        timestamps = timestamps.dt.tz_localize("America/New_York")
    else:
        timestamps = timestamps.dt.tz_convert("America/New_York")
    bars["timestamp"] = timestamps

    times = timestamps.dt.time
    rth_mask = (times >= pd.Timestamp("09:30").time()) & (times <= pd.Timestamp("15:59").time())
    session_dates = {ts.date() for ts in timestamps[rth_mask]}
    evening_mask = times >= pd.Timestamp("18:00").time()
    morning_mask = times <= pd.Timestamp("09:29").time()
    overnight = bars[evening_mask | morning_mask].copy()
    overnight_timestamps = overnight["timestamp"]
    overnight["overnight_session_date"] = overnight_timestamps.dt.normalize()
    overnight.loc[evening_mask[evening_mask | morning_mask].to_numpy(), "overnight_session_date"] += pd.Timedelta(days=1)
    overnight["overnight_session_date"] = overnight["overnight_session_date"].dt.date

    rows: list[dict] = []
    for session_date, group in overnight.groupby("overnight_session_date", sort=True):
        if session_date not in session_dates or len(group) < 300:
            continue
        overnight_open = float(group["open"].iloc[0])
        overnight_close = float(group["close"].iloc[-1])
        overnight_high = float(group["high"].max())
        overnight_low = float(group["low"].min())
        if overnight_high <= overnight_low:
            continue
        rows.append(
            {
                "session_date": session_date.isoformat(),
                "overnight_start": group["timestamp"].iloc[0].isoformat(),
                "overnight_end": group["timestamp"].iloc[-1].isoformat(),
                "overnight_open": overnight_open,
                "overnight_high": overnight_high,
                "overnight_low": overnight_low,
                "overnight_close": overnight_close,
                "overnight_range_points": overnight_high - overnight_low,
                "overnight_midpoint": (overnight_high + overnight_low) / 2.0,
                "overnight_return_points": overnight_close - overnight_open,
                "overnight_volume": int(group["volume"].sum()),
                "overnight_bars": int(len(group)),
            }
        )

    features = pd.DataFrame(rows).sort_values("session_date", kind="mergesort").reset_index(drop=True)
    ranges = features["overnight_range_points"].astype(float)
    features["overnight_range_rank_252"] = _rolling_current_percentile(ranges, window=252, min_periods=20)
    features["overnight_range_mean_252_prior"] = ranges.rolling(252, min_periods=20).mean().shift(1)
    features["overnight_range_median_252_prior"] = ranges.rolling(252, min_periods=20).median().shift(1)
    features = features[features["session_date"] >= "2011-01-03"].reset_index(drop=True)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(output_path, index=False)
    return features


def _rolling_current_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    def percentile(values) -> float:
        clean = pd.Series(values).dropna()
        if clean.empty:
            return float("nan")
        return float(clean.rank(pct=True, method="average").iloc[-1])

    return series.rolling(window, min_periods=min_periods).apply(percentile, raw=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(args.input, args.output)
    valid = features.dropna(subset=["overnight_range_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")
    print(f"min_bars={features['overnight_bars'].min()} max_bars={features['overnight_bars'].max()}")


if __name__ == "__main__":
    main()
