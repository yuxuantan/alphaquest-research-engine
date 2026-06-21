from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_CACHE_DIR = "data/external/yahoo_sector_etfs"
DEFAULT_OUTPUT = "data/external/es_sector_opening_breadth_features_20110103_20260609.csv"
SECTOR_SYMBOLS = ["XLK", "XLY", "XLF", "XLI", "XLV", "XLP", "XLU"]
CYCLICAL_SYMBOLS = ["XLK", "XLY", "XLF", "XLI"]
DEFENSIVE_SYMBOLS = ["XLV", "XLP", "XLU"]


def build_features(
    bars_input: str | Path = DEFAULT_BARS_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    start_session: str = "2011-01-03",
) -> pd.DataFrame:
    bars = pd.read_parquet(bars_input, columns=["timestamp"])
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    sessions = (
        pd.DataFrame({"session_date": bars["timestamp"].dt.date.astype(str)})
        .drop_duplicates("session_date")
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )

    features = None
    for symbol in SECTOR_SYMBOLS:
        history = _load_symbol_open_gap(symbol, cache_dir)
        features = history if features is None else features.merge(history, on="session_date", how="outer")

    assert features is not None
    gap_columns = [f"{symbol.lower()}_open_gap" for symbol in SECTOR_SYMBOLS]
    cyclical_columns = [f"{symbol.lower()}_open_gap" for symbol in CYCLICAL_SYMBOLS]
    defensive_columns = [f"{symbol.lower()}_open_gap" for symbol in DEFENSIVE_SYMBOLS]

    features = features.sort_values("session_date", kind="mergesort")
    features["sector_up_count_7"] = (features[gap_columns] > 0.0).sum(axis=1)
    features["sector_down_count_7"] = (features[gap_columns] < 0.0).sum(axis=1)
    features["sector_avg_open_gap_7"] = features[gap_columns].mean(axis=1)
    features["cyclical_up_count_4"] = (features[cyclical_columns] > 0.0).sum(axis=1)
    features["cyclical_down_count_4"] = (features[cyclical_columns] < 0.0).sum(axis=1)
    features["cyclical_avg_open_gap_4"] = features[cyclical_columns].mean(axis=1)
    features["defensive_avg_open_gap_3"] = features[defensive_columns].mean(axis=1)
    features["cyclical_minus_defensive_open_gap"] = (
        features["cyclical_avg_open_gap_4"] - features["defensive_avg_open_gap_3"]
    )

    out = sessions.merge(features, on="session_date", how="left")
    out = out[out["session_date"] >= start_session].copy()
    out.insert(1, "feature_observation_date", out["session_date"])
    out.insert(2, "feature_available_time", "09:30:00 America/New_York")

    columns = [
        "session_date",
        "feature_observation_date",
        "feature_available_time",
        *gap_columns,
        "sector_up_count_7",
        "sector_down_count_7",
        "sector_avg_open_gap_7",
        "cyclical_up_count_4",
        "cyclical_down_count_4",
        "cyclical_avg_open_gap_4",
        "defensive_avg_open_gap_3",
        "cyclical_minus_defensive_open_gap",
    ]
    out = out[columns]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    return out


def _load_symbol_open_gap(symbol: str, cache_dir: str | Path) -> pd.DataFrame:
    lower = symbol.lower()
    path = Path(cache_dir) / f"yahoo_{lower}_daily_1998-12-01_2026-06-10.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing local Yahoo sector ETF file for {symbol}: {path}. "
            "This builder does not download data."
        )
    raw = pd.read_csv(path, parse_dates=["Date"])
    required = {"Date", "Open", "Close"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"{path} is missing required columns: {sorted(missing)}")
    frame = raw[["Date", "Open", "Close"]].sort_values("Date", kind="mergesort").copy()
    frame["Open"] = pd.to_numeric(frame["Open"], errors="coerce")
    frame["Close"] = pd.to_numeric(frame["Close"], errors="coerce")
    frame[f"{lower}_open_gap"] = frame["Open"] / frame["Close"].shift(1) - 1.0
    out = frame[["Date", f"{lower}_open_gap"]].dropna(subset=[f"{lower}_open_gap"]).copy()
    out["session_date"] = out["Date"].dt.date.astype(str)
    return out[["session_date", f"{lower}_open_gap"]]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-input", default=DEFAULT_BARS_INPUT)
    parser.add_argument("--cache-dir", default=DEFAULT_CACHE_DIR)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--start-session", default="2011-01-03")
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        cache_dir=args.cache_dir,
        start_session=args.start_session,
    )
    valid = features.dropna(subset=["sector_avg_open_gap_7"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_open_breadth_rows={len(valid)}")
    if not valid.empty:
        print(f"period={valid['session_date'].min()}..{valid['session_date'].max()}")


if __name__ == "__main__":
    main()
