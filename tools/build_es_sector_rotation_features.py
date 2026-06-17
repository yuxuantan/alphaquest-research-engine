from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
from pandas.tseries.offsets import BDay


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/es_sector_rotation_features_20110103_20260609.csv"
DEFAULT_CACHE_DIR = "data/external/yahoo_sector_etfs"
SECTOR_SYMBOLS = ["SPY", "XLY", "XLP", "XLK", "XLU", "XLV", "XLI", "XLF"]


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

    lower_symbols = [symbol.lower() for symbol in SECTOR_SYMBOLS]
    one_day_returns = prices[lower_symbols].pct_change(1)
    five_day_returns = prices[lower_symbols].pct_change(5)
    features = pd.DataFrame({"observation_date": prices["observation_date"]})
    for symbol in lower_symbols:
        features[f"{symbol}_return_1d"] = one_day_returns[symbol]
        features[f"{symbol}_return_5d"] = five_day_returns[symbol]

    cyclicals = ["xly", "xlf", "xli", "xlk"]
    defensives = ["xlp", "xlu", "xlv"]
    growth = ["xlk", "xly"]
    financial_industrial = ["xlf", "xli"]
    features["cyclical_return_1d"] = one_day_returns[cyclicals].mean(axis=1)
    features["defensive_return_1d"] = one_day_returns[defensives].mean(axis=1)
    features["cyclical_minus_defensive_1d"] = (
        features["cyclical_return_1d"] - features["defensive_return_1d"]
    )
    features["cyclical_return_5d"] = five_day_returns[cyclicals].mean(axis=1)
    features["defensive_return_5d"] = five_day_returns[defensives].mean(axis=1)
    features["cyclical_minus_defensive_5d"] = (
        features["cyclical_return_5d"] - features["defensive_return_5d"]
    )
    features["growth_minus_defensive_5d"] = (
        five_day_returns[growth].mean(axis=1) - five_day_returns[defensives].mean(axis=1)
    )
    features["financial_industrial_minus_spy_1d"] = (
        one_day_returns[financial_industrial].mean(axis=1) - one_day_returns["spy"]
    )

    rank_columns = [
        "cyclical_minus_defensive_1d",
        "cyclical_minus_defensive_5d",
        "growth_minus_defensive_5d",
        "financial_industrial_minus_spy_1d",
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
        "cyclical_return_1d",
        "defensive_return_1d",
        "cyclical_minus_defensive_1d",
        "cyclical_return_5d",
        "defensive_return_5d",
        "cyclical_minus_defensive_5d",
        "growth_minus_defensive_5d",
        "financial_industrial_minus_spy_1d",
        "cyclical_minus_defensive_1d_rank_252",
        "cyclical_minus_defensive_5d_rank_252",
        "growth_minus_defensive_5d_rank_252",
        "financial_industrial_minus_spy_1d_rank_252",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    for column in ["availability_cutoff", "observation_date"]:
        out[column] = pd.to_datetime(out[column]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_symbol_history(
    symbol: str,
    *,
    input_path: str | Path | None,
    cache_dir: str | Path,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    if input_path is not None:
        raw = pd.read_csv(input_path)
    else:
        cache_path = Path(cache_dir) / f"yahoo_{symbol.lower()}_daily_{start_date}_{end_date}.csv"
        if cache_path.exists():
            raw = pd.read_csv(cache_path)
        else:
            raw = _fetch_yahoo_chart(symbol, start_date=start_date, end_date=end_date)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            raw.to_csv(cache_path, index=False)
    date_col = "Date" if "Date" in raw.columns else "date"
    adj_col = "Adj Close" if "Adj Close" in raw.columns else "adj_close"
    if adj_col not in raw.columns:
        adj_col = "Close" if "Close" in raw.columns else "close"
    out = raw[[date_col, adj_col]].copy()
    out.columns = ["observation_date", "adj_close"]
    out["observation_date"] = pd.to_datetime(out["observation_date"])
    out["adj_close"] = pd.to_numeric(out["adj_close"], errors="coerce")
    return (
        out.dropna(subset=["adj_close"])
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _fetch_yahoo_chart(symbol: str, *, start_date: str, end_date: str) -> pd.DataFrame:
    start_ts = int(pd.Timestamp(start_date, tz=timezone.utc).timestamp())
    # Yahoo's period2 is exclusive. Add one day so end_date is included when present.
    end_ts = int((pd.Timestamp(end_date, tz=timezone.utc) + pd.Timedelta(days=1)).timestamp())
    query = urlencode(
        {
            "period1": start_ts,
            "period2": end_ts,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
    )
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?{query}"
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    result = (payload.get("chart", {}).get("result") or [None])[0]
    if not result:
        error = payload.get("chart", {}).get("error")
        raise ValueError(f"Yahoo chart returned no result for {symbol}: {error}")
    timestamps = result.get("timestamp") or []
    quote = (result.get("indicators", {}).get("quote") or [{}])[0]
    adj_close = (result.get("indicators", {}).get("adjclose") or [{}])[0].get("adjclose")
    if not timestamps or adj_close is None:
        raise ValueError(f"Yahoo chart result for {symbol} is missing timestamps or adjusted close.")
    return pd.DataFrame(
        {
            "Date": [datetime.fromtimestamp(ts, timezone.utc).date().isoformat() for ts in timestamps],
            "Open": quote.get("open"),
            "High": quote.get("high"),
            "Low": quote.get("low"),
            "Close": quote.get("close"),
            "Volume": quote.get("volume"),
            "Adj Close": adj_close,
        }
    )


def _rolling_last_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    def percentile(values) -> float:
        clean = pd.Series(values).dropna()
        if clean.empty:
            return float("nan")
        return float(clean.rank(pct=True, method="average").iloc[-1])

    return series.rolling(window, min_periods=min_periods).apply(percentile, raw=False)


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
            "cyclical_minus_defensive_1d_rank_252",
            "cyclical_minus_defensive_5d_rank_252",
            "growth_minus_defensive_5d_rank_252",
            "financial_industrial_minus_spy_1d_rank_252",
        ],
        how="any",
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
