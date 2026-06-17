from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import BDay

try:
    from tools.build_es_sector_rotation_features import (
        DEFAULT_BARS_INPUT,
        DEFAULT_CACHE_DIR,
        SECTOR_SYMBOLS,
        _load_symbol_history,
        _rolling_last_percentile,
    )
except ModuleNotFoundError:
    from build_es_sector_rotation_features import (  # type: ignore[no-redef]
        DEFAULT_BARS_INPUT,
        DEFAULT_CACHE_DIR,
        SECTOR_SYMBOLS,
        _load_symbol_history,
        _rolling_last_percentile,
    )


DEFAULT_OUTPUT = "data/external/es_sector_dispersion_features_20110103_20260609.csv"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    input_paths: dict[str, str | Path] | None = None,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    start_date: str = "1998-12-01",
    end_date: str = "2026-06-10",
    rank_min_periods: int = 60,
    availability_lag_bdays: int = 1,
) -> pd.DataFrame:
    bars = pd.read_parquet(bars_input, columns=["timestamp"])
    bars = bars.sort_values("timestamp", kind="mergesort").reset_index(drop=True)
    sessions = (
        pd.DataFrame({"session_date": pd.to_datetime(bars["timestamp"]).dt.date.astype(str)})
        .drop_duplicates("session_date")
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])
    sessions["availability_cutoff"] = sessions["session_date_ts"] - BDay(int(availability_lag_bdays))

    close_frames = []
    for symbol in SECTOR_SYMBOLS:
        frame = _load_symbol_history(
            symbol,
            input_path=(input_paths or {}).get(symbol),
            cache_dir=cache_dir,
            start_date=start_date,
            end_date=end_date,
        )
        close_frames.append(frame.rename(columns={"adj_close": symbol.lower()}))
    prices = close_frames[0]
    for frame in close_frames[1:]:
        prices = prices.merge(frame, on="observation_date", how="outer")
    prices = prices.sort_values("observation_date", kind="mergesort").ffill().dropna()

    sector_symbols = [symbol.lower() for symbol in SECTOR_SYMBOLS if symbol != "SPY"]
    returns_1d = prices[sector_symbols].pct_change(1)
    returns_5d = prices[sector_symbols].pct_change(5)
    spy_return_1d = prices["spy"].pct_change(1)
    spy_return_5d = prices["spy"].pct_change(5)

    features = pd.DataFrame({"observation_date": prices["observation_date"]})
    features["sector_dispersion_1d"] = returns_1d.std(axis=1, ddof=0)
    features["sector_dispersion_5d"] = returns_5d.std(axis=1, ddof=0)
    features["sector_avg_abs_spy_gap_1d"] = returns_1d.sub(spy_return_1d, axis=0).abs().mean(axis=1)
    features["sector_avg_abs_spy_gap_5d"] = returns_5d.sub(spy_return_5d, axis=0).abs().mean(axis=1)
    features["sector_dispersion_change_1d"] = features["sector_dispersion_1d"] - features[
        "sector_dispersion_1d"
    ].shift(1)
    features["sector_dispersion_change_5d"] = features["sector_dispersion_5d"] - features[
        "sector_dispersion_5d"
    ].shift(5)

    rank_columns = [
        "sector_dispersion_1d",
        "sector_dispersion_5d",
        "sector_avg_abs_spy_gap_1d",
        "sector_avg_abs_spy_gap_5d",
        "sector_dispersion_change_1d",
        "sector_dispersion_change_5d",
    ]
    for column in rank_columns:
        features[f"{column}_rank_252"] = _rolling_last_percentile(
            features[column], 252, rank_min_periods
        )

    merged = pd.merge_asof(
        sessions.sort_values("availability_cutoff"),
        features.sort_values("observation_date"),
        left_on="availability_cutoff",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")
    merged["availability_lag_business_days"] = int(availability_lag_bdays)

    columns = [
        "session_date",
        "availability_cutoff",
        "observation_date",
        "availability_lag_business_days",
        *rank_columns,
        *[f"{column}_rank_252" for column in rank_columns],
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    for column in ["availability_cutoff", "observation_date"]:
        out[column] = pd.to_datetime(out[column]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-input", default=DEFAULT_BARS_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--start-date", default="1998-12-01")
    parser.add_argument("--end-date", default="2026-06-10")
    parser.add_argument("--availability-lag-bdays", type=int, default=1)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        cache_dir=args.cache_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        availability_lag_bdays=args.availability_lag_bdays,
    )
    valid = features.dropna(
        subset=[
            "sector_dispersion_1d_rank_252",
            "sector_dispersion_5d_rank_252",
            "sector_dispersion_change_1d_rank_252",
            "sector_dispersion_change_5d_rank_252",
        ],
        how="any",
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
