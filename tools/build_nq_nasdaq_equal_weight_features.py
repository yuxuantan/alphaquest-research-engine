from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd
from pandas.tseries.offsets import BDay


DEFAULT_BARS_INPUT = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/nq_nasdaq_equal_weight_features_20110103_20260612.csv"
DEFAULT_CACHE_DIR = "data/external/yahoo_nasdaq_equal_weight"


def build_features(
    bars_input: str | Path = DEFAULT_BARS_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
    rank_window: int = 252,
    rank_min_periods: int = 80,
    availability_lag_bdays: int = 1,
    start_session: str = "2011-01-03",
    yahoo_start_date: str = "1999-01-01",
    yahoo_end_date: str = "2026-06-12",
) -> pd.DataFrame:
    bars = pd.read_parquet(bars_input, columns=["timestamp"])
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    sessions = (
        pd.DataFrame({"session_date": bars["timestamp"].dt.date.astype(str)})
        .drop_duplicates("session_date")
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])
    sessions["availability_cutoff"] = sessions["session_date_ts"] - BDay(
        int(availability_lag_bdays)
    )

    qqq = _load_or_fetch_yahoo("QQQ", cache_dir, yahoo_start_date, yahoo_end_date, "qqq")
    qqqe = _load_or_fetch_yahoo("QQQE", cache_dir, yahoo_start_date, yahoo_end_date, "qqqe")
    daily = (
        qqq.merge(qqqe, on="observation_date", how="inner")
        .sort_values("observation_date", kind="mergesort")
        .reset_index(drop=True)
    )
    for symbol in ("qqq", "qqqe"):
        for lookback in (1, 5):
            daily[f"{symbol}_return_{lookback}d"] = daily[symbol].pct_change(lookback)
    daily["qqq_minus_qqqe_1d"] = daily["qqq_return_1d"] - daily["qqqe_return_1d"]
    daily["qqq_minus_qqqe_5d"] = daily["qqq_return_5d"] - daily["qqqe_return_5d"]
    daily["qqq_volume_median_20"] = daily["qqq_volume"].rolling(20, min_periods=10).median()
    daily["qqq_volume_ratio_20"] = daily["qqq_volume"] / daily["qqq_volume_median_20"]
    daily["concentration_pressure_1d"] = daily["qqq_minus_qqqe_1d"] * daily[
        "qqq_volume_ratio_20"
    ]

    rank_columns = [
        "qqq_minus_qqqe_1d",
        "qqq_minus_qqqe_5d",
        "qqq_volume_ratio_20",
        "concentration_pressure_1d",
    ]
    for column in rank_columns:
        daily[f"{column}_rank_252"] = _rolling_last_percentile(
            daily[column], rank_window, rank_min_periods
        )

    merged = pd.merge_asof(
        sessions.sort_values("availability_cutoff"),
        daily.sort_values("observation_date"),
        left_on="availability_cutoff",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")
    merged["availability_lag_business_days"] = int(availability_lag_bdays)
    out = merged[merged["session_date"] >= start_session].copy()
    out["availability_cutoff"] = pd.to_datetime(out["availability_cutoff"]).dt.date.astype(str)
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)
    columns = [
        "session_date",
        "availability_cutoff",
        "observation_date",
        "availability_lag_business_days",
        "qqq",
        "qqqe",
        "qqq_volume",
        "qqq_return_1d",
        "qqqe_return_1d",
        "qqq_minus_qqqe_1d",
        "qqq_return_5d",
        "qqqe_return_5d",
        "qqq_minus_qqqe_5d",
        "qqq_volume_ratio_20",
        "concentration_pressure_1d",
        "qqq_minus_qqqe_1d_rank_252",
        "qqq_minus_qqqe_5d_rank_252",
        "qqq_volume_ratio_20_rank_252",
        "concentration_pressure_1d_rank_252",
    ]
    out = out[columns]
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    return out


def _load_or_fetch_yahoo(
    symbol: str,
    cache_dir: str | Path,
    start_date: str,
    end_date: str,
    prefix: str,
) -> pd.DataFrame:
    cache_path = Path(cache_dir) / f"yahoo_{symbol.lower()}_daily_{start_date}_{end_date}.csv"
    if cache_path.exists():
        raw = pd.read_csv(cache_path)
    else:
        raw = _fetch_yahoo_chart(symbol, start_date=start_date, end_date=end_date)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        raw.to_csv(cache_path, index=False)
    required = {"Date", "Adj Close", "Volume"}
    missing = required.difference(raw.columns)
    if missing:
        raise ValueError(f"{cache_path} is missing required columns: {sorted(missing)}.")
    out = raw[["Date", "Adj Close", "Volume"]].copy()
    out["observation_date"] = pd.to_datetime(out["Date"])
    out[prefix] = pd.to_numeric(out["Adj Close"], errors="coerce")
    out[f"{prefix}_volume"] = pd.to_numeric(out["Volume"], errors="coerce")
    return (
        out[["observation_date", prefix, f"{prefix}_volume"]]
        .dropna(subset=[prefix, f"{prefix}_volume"])
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _fetch_yahoo_chart(symbol: str, *, start_date: str, end_date: str) -> pd.DataFrame:
    start_ts = int(pd.Timestamp(start_date, tz=timezone.utc).timestamp())
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
    parser.add_argument("--yahoo-start-date", default="1999-01-01")
    parser.add_argument("--yahoo-end-date", default="2026-06-12")
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        cache_dir=args.cache_dir,
        yahoo_start_date=args.yahoo_start_date,
        yahoo_end_date=args.yahoo_end_date,
    )
    valid = features.dropna(
        subset=["qqq_minus_qqqe_1d_rank_252", "qqq_minus_qqqe_5d_rank_252"]
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    if not valid.empty:
        print(f"period={valid['session_date'].min()}..{valid['session_date'].max()}")


if __name__ == "__main__":
    main()
