from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path

import pandas as pd
import requests
import yfinance as yf


DEFAULT_BARS_INPUT = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
DEFAULT_RAW_OUTPUT = "data/external/yahoo_move_index_20100104_20260629.csv"
DEFAULT_OUTPUT = "data/external/nq_move_treasury_vol_features_20110103_20260612.csv"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    raw_output_path: str | Path = DEFAULT_RAW_OUTPUT,
    ticker: str = "^MOVE",
    start: str = "2010-01-01",
    end: str = "2026-06-30",
    rank_min_periods: int = 60,
) -> pd.DataFrame:
    sessions = _load_nq_sessions(bars_input)
    move = _download_move(ticker, start=start, end=end)
    raw_output_path = Path(raw_output_path)
    raw_output_path.parent.mkdir(parents=True, exist_ok=True)
    move.to_csv(raw_output_path, index=False)

    move = _add_features(move, rank_min_periods=rank_min_periods)
    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        move.sort_values("observation_date"),
        left_on="session_date_ts",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=False,
    ).drop(columns=["session_date_ts"])
    merged["observation_date"] = pd.to_datetime(merged["observation_date"]).dt.date.astype(str)
    out = merged[
        [
            "session_date",
            "observation_date",
            "move_close",
            "move_change_1d",
            "move_change_5d",
            "move_pct_change_1d",
            "move_pct_change_5d",
            "move_5d_mean",
            "move_close_rank_252",
            "move_change_1d_rank_252",
            "move_change_5d_rank_252",
            "move_5d_mean_rank_252",
        ]
    ].copy()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_nq_sessions(bars_input: str | Path) -> pd.DataFrame:
    bars = pd.read_parquet(bars_input, columns=["timestamp"])
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    if bars["timestamp"].dt.tz is None:
        bars["timestamp"] = bars["timestamp"].dt.tz_localize("America/New_York")
    else:
        bars["timestamp"] = bars["timestamp"].dt.tz_convert("America/New_York")
    bars = bars[
        (bars["timestamp"].dt.time >= pd.Timestamp("09:30").time())
        & (bars["timestamp"].dt.time <= pd.Timestamp("15:59").time())
    ].copy()
    sessions = (
        pd.DataFrame({"session_date": bars["timestamp"].dt.date.astype(str)})
        .drop_duplicates("session_date")
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])
    return sessions


def _download_move(ticker: str, *, start: str, end: str) -> pd.DataFrame:
    try:
        raw = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
    except Exception:
        raw = pd.DataFrame()
    if raw.empty:
        return _download_move_yahoo_chart(ticker, start=start, end=end)
    return _normalize_yahoo_frame(raw)


def _download_move_yahoo_chart(ticker: str, *, start: str, end: str) -> pd.DataFrame:
    start_ts = int(pd.Timestamp(start, tz="UTC").timestamp())
    end_ts = int(pd.Timestamp(end, tz="UTC").timestamp())
    encoded = ticker.replace("^", "%5E")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
        f"?period1={start_ts}&period2={end_ts}&interval=1d&events=history&includeAdjustedClose=true"
    )
    response = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    payload = response.json()
    result = ((payload.get("chart") or {}).get("result") or [None])[0]
    if not result:
        raise RuntimeError(f"No Yahoo chart result returned for {ticker}.")
    timestamps = result.get("timestamp") or []
    quote = (((result.get("indicators") or {}).get("quote") or [{}])[0])
    closes = quote.get("close") or []
    rows = []
    for timestamp, close in zip(timestamps, closes):
        if close is None:
            continue
        rows.append(
            {
                "observation_date": dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc).date().isoformat(),
                "move_close": close,
            }
        )
    raw = pd.DataFrame(rows)
    if raw.empty:
        raise RuntimeError(f"Yahoo chart data for {ticker} did not contain usable closes.")
    raw["observation_date"] = pd.to_datetime(raw["observation_date"])
    raw["move_close"] = pd.to_numeric(raw["move_close"], errors="coerce")
    return (
        raw.dropna(subset=["move_close"])
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _normalize_yahoo_frame(raw: pd.DataFrame) -> pd.DataFrame:
    if raw.empty:
        raise RuntimeError("No Yahoo data returned.")
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = [column[0] for column in raw.columns]
    raw = raw.reset_index().rename(columns={"Date": "observation_date", "Close": "move_close"})
    raw["observation_date"] = pd.to_datetime(raw["observation_date"])
    raw["move_close"] = pd.to_numeric(raw["move_close"], errors="coerce")
    raw = (
        raw.dropna(subset=["move_close"])
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )
    if raw.empty:
        raise RuntimeError("Yahoo data did not contain usable closes.")
    return raw[["observation_date", "move_close"]]


def _add_features(move: pd.DataFrame, *, rank_min_periods: int) -> pd.DataFrame:
    out = move.copy()
    out["move_change_1d"] = out["move_close"].diff()
    out["move_change_5d"] = out["move_close"] - out["move_close"].shift(5)
    out["move_pct_change_1d"] = out["move_close"].pct_change()
    out["move_pct_change_5d"] = out["move_close"].pct_change(5)
    out["move_5d_mean"] = out["move_close"].rolling(5, min_periods=5).mean()
    for column in ["move_close", "move_change_1d", "move_change_5d", "move_5d_mean"]:
        out[f"{column}_rank_252"] = _rolling_last_percentile(out[column], 252, rank_min_periods)
    return out


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
    parser.add_argument("--raw-output", default=DEFAULT_RAW_OUTPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--ticker", default="^MOVE")
    parser.add_argument("--start", default="2010-01-01")
    parser.add_argument("--end", default="2026-06-30")
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        raw_output_path=args.raw_output,
        ticker=args.ticker,
        start=args.start,
        end=args.end,
    )
    valid = features.dropna(subset=["move_close_rank_252", "move_change_1d_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")
    print(f"raw_move_output={args.raw_output}")


if __name__ == "__main__":
    main()
