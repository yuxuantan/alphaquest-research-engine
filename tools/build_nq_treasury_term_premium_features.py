from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlretrieve

import pandas as pd


DEFAULT_NQ_INPUT = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
DEFAULT_TERM_PREMIUM_CSV = "data/external/fred_treasury_term_premium/THREEFYTP10.csv"
DEFAULT_OUTPUT = "data/external/nq_treasury_term_premium_features_20110103_20260612.csv"
FRED_TERM_PREMIUM_DAILY_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=THREEFYTP10"


def build_features(
    nq_input_path: str | Path = DEFAULT_NQ_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    term_premium_csv_path: str | Path = DEFAULT_TERM_PREMIUM_CSV,
    publication_lag_calendar_days: int = 7,
    download_if_missing: bool = True,
) -> pd.DataFrame:
    if publication_lag_calendar_days < 0:
        raise ValueError("publication_lag_calendar_days must be non-negative.")

    sessions = _nq_sessions(nq_input_path)
    term_premium = _load_term_premium_daily(
        term_premium_csv_path,
        download_if_missing=download_if_missing,
    )
    term_premium = _add_term_premium_features(term_premium)

    sessions["availability_cutoff"] = sessions["session_date_ts"] - pd.to_timedelta(
        publication_lag_calendar_days,
        unit="D",
    )
    merged = pd.merge_asof(
        sessions.sort_values("availability_cutoff", kind="mergesort"),
        term_premium.sort_values("observation_date_ts", kind="mergesort"),
        left_on="availability_cutoff",
        right_on="observation_date_ts",
        direction="backward",
    ).sort_values("session_date_ts", kind="mergesort")

    merged["publication_lag_calendar_days"] = publication_lag_calendar_days
    merged["observation_age_days"] = (
        merged["session_date_ts"] - merged["observation_date_ts"]
    ).dt.days
    merged["availability_cutoff"] = merged["availability_cutoff"].dt.date.astype(str)
    merged["observation_date"] = merged["observation_date_ts"].dt.date.astype(str)

    columns = [
        "session_date",
        "observation_date",
        "availability_cutoff",
        "publication_lag_calendar_days",
        "observation_age_days",
        "term_premium_10y_1d",
        "term_premium_10y_5d",
        "term_premium_10y_21d",
        "term_premium_10y_5d_change",
        "term_premium_10y_21d_change",
        "term_premium_10y_1d_rank_252",
        "term_premium_10y_5d_rank_252",
        "term_premium_10y_21d_rank_252",
        "term_premium_10y_5d_change_rank_252",
        "term_premium_10y_21d_change_rank_252",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].reset_index(drop=True)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output, index=False)
    return out


def _nq_sessions(path: str | Path) -> pd.DataFrame:
    bars = pd.read_parquet(path, columns=["timestamp"])
    timestamps = pd.to_datetime(bars["timestamp"])
    sessions = (
        pd.DataFrame({"session_date": timestamps.dt.date.astype(str)})
        .drop_duplicates()
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])
    return sessions


def _load_term_premium_daily(path: str | Path, *, download_if_missing: bool) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        if not download_if_missing:
            raise FileNotFoundError(f"Treasury term-premium daily CSV not found: {csv_path}")
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        urlretrieve(FRED_TERM_PREMIUM_DAILY_URL, csv_path)

    frame = pd.read_csv(csv_path, parse_dates=["observation_date"])
    if "THREEFYTP10" not in frame.columns:
        raise ValueError("Treasury term-premium input is missing THREEFYTP10.")
    frame = frame.rename(
        columns={
            "observation_date": "observation_date_ts",
            "THREEFYTP10": "term_premium_10y_1d",
        }
    )
    frame["observation_date_ts"] = frame["observation_date_ts"].dt.normalize()
    frame["term_premium_10y_1d"] = pd.to_numeric(frame["term_premium_10y_1d"], errors="coerce")
    frame = frame.dropna(subset=["term_premium_10y_1d"])
    frame["observation_date"] = frame["observation_date_ts"].dt.date.astype(str)
    return (
        frame[["observation_date", "observation_date_ts", "term_premium_10y_1d"]]
        .sort_values("observation_date_ts", kind="mergesort")
        .reset_index(drop=True)
    )


def _add_term_premium_features(term_premium: pd.DataFrame) -> pd.DataFrame:
    out = term_premium.copy()
    out["term_premium_10y_5d"] = out["term_premium_10y_1d"].rolling(5, min_periods=5).mean()
    out["term_premium_10y_21d"] = out["term_premium_10y_1d"].rolling(21, min_periods=21).mean()
    out["term_premium_10y_5d_change"] = (
        out["term_premium_10y_5d"] - out["term_premium_10y_5d"].shift(5)
    )
    out["term_premium_10y_21d_change"] = (
        out["term_premium_10y_21d"] - out["term_premium_10y_21d"].shift(21)
    )
    for column in [
        "term_premium_10y_1d",
        "term_premium_10y_5d",
        "term_premium_10y_21d",
        "term_premium_10y_5d_change",
        "term_premium_10y_21d_change",
    ]:
        out[f"{column}_rank_252"] = _rolling_last_percentile(out[column], 252, 126)
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
    parser.add_argument("--nq-input", default=DEFAULT_NQ_INPUT)
    parser.add_argument("--term-premium-csv", default=DEFAULT_TERM_PREMIUM_CSV)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--publication-lag-calendar-days", type=int, default=7)
    args = parser.parse_args()
    features = build_features(
        args.nq_input,
        args.output,
        term_premium_csv_path=args.term_premium_csv,
        publication_lag_calendar_days=args.publication_lag_calendar_days,
    )
    valid = features.dropna(subset=["term_premium_10y_21d_rank_252"])
    print(f"source={FRED_TERM_PREMIUM_DAILY_URL}")
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")
    print(f"observation_range={features['observation_date'].min()}..{features['observation_date'].max()}")
    print(f"publication_lag_calendar_days={args.publication_lag_calendar_days}")


if __name__ == "__main__":
    main()
