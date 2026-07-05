from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlretrieve

import pandas as pd


DEFAULT_NQ_INPUT = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
DEFAULT_SOURCE_DIR = "data/external/fred_corporate_equity_supply"
DEFAULT_OUTPUT = "data/external/nq_corporate_equity_supply_features_20110103_20260612.csv"

FRED_SERIES = {
    "NCBCEBQ027S": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=NCBCEBQ027S",
    "BOGZ1FA104104005Q": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BOGZ1FA104104005Q",
    "NCBEILQ027S": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=NCBEILQ027S",
}


def build_features(
    nq_input_path: str | Path = DEFAULT_NQ_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    source_dir: str | Path = DEFAULT_SOURCE_DIR,
    publication_lag_calendar_days: int = 180,
    download_if_missing: bool = True,
) -> pd.DataFrame:
    if publication_lag_calendar_days < 0:
        raise ValueError("publication_lag_calendar_days must be non-negative.")

    sessions = _nq_sessions(nq_input_path)
    quarterly = _load_quarterly_sources(source_dir, download_if_missing=download_if_missing)
    quarterly = _add_supply_features(quarterly)

    sessions["availability_cutoff"] = sessions["session_date_ts"] - pd.to_timedelta(
        publication_lag_calendar_days,
        unit="D",
    )
    merged = pd.merge_asof(
        sessions.sort_values("availability_cutoff", kind="mergesort"),
        quarterly.sort_values("observation_date_ts", kind="mergesort"),
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
        "net_equity_issuance_1q",
        "debt_financing_1q",
        "equity_market_value",
        "net_equity_issuance_4q",
        "debt_financing_4q",
        "net_equity_to_market_1q",
        "net_equity_to_market_4q",
        "debt_minus_equity_to_market_4q",
        "equity_financing_share_4q",
        "net_equity_issuance_4q_change",
        "equity_share_4q_change",
        "net_equity_to_market_1q_rank_40q",
        "net_equity_to_market_4q_rank_40q",
        "debt_minus_equity_to_market_4q_rank_40q",
        "equity_financing_share_4q_rank_40q",
        "net_equity_issuance_4q_change_rank_40q",
        "equity_share_4q_change_rank_40q",
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


def _load_quarterly_sources(source_dir: str | Path, *, download_if_missing: bool) -> pd.DataFrame:
    frames = []
    for series_id, url in FRED_SERIES.items():
        path = Path(source_dir) / f"{series_id}.csv"
        if not path.exists():
            if not download_if_missing:
                raise FileNotFoundError(f"Corporate equity supply source CSV not found: {path}")
            path.parent.mkdir(parents=True, exist_ok=True)
            urlretrieve(url, path)
        frame = pd.read_csv(path, parse_dates=["observation_date"])
        if series_id not in frame.columns:
            raise ValueError(f"Corporate equity supply source is missing {series_id}: {path}")
        frame = frame.rename(columns={"observation_date": "observation_date_ts"})
        frame["observation_date_ts"] = frame["observation_date_ts"].dt.normalize()
        frame[series_id] = pd.to_numeric(frame[series_id], errors="coerce")
        frames.append(frame[["observation_date_ts", series_id]])

    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="observation_date_ts", how="outer")
    out = out.rename(
        columns={
            "NCBCEBQ027S": "net_equity_issuance_1q",
            "BOGZ1FA104104005Q": "debt_financing_1q",
            "NCBEILQ027S": "equity_market_value",
        }
    )
    return (
        out.dropna(
            subset=["net_equity_issuance_1q", "debt_financing_1q", "equity_market_value"]
        )
        .sort_values("observation_date_ts", kind="mergesort")
        .reset_index(drop=True)
    )


def _add_supply_features(quarterly: pd.DataFrame) -> pd.DataFrame:
    out = quarterly.copy()
    out["net_equity_issuance_4q"] = out["net_equity_issuance_1q"].rolling(
        4, min_periods=4
    ).sum()
    out["debt_financing_4q"] = out["debt_financing_1q"].rolling(4, min_periods=4).sum()
    out["net_equity_to_market_1q"] = out["net_equity_issuance_1q"] / out[
        "equity_market_value"
    ]
    out["net_equity_to_market_4q"] = out["net_equity_issuance_4q"] / out[
        "equity_market_value"
    ]
    out["debt_minus_equity_to_market_4q"] = (
        out["debt_financing_4q"] - out["net_equity_issuance_4q"]
    ) / out["equity_market_value"]
    out["equity_financing_share_4q"] = out["net_equity_issuance_4q"] / (
        out["net_equity_issuance_4q"].abs() + out["debt_financing_4q"].abs()
    )
    out["net_equity_issuance_4q_change"] = out["net_equity_issuance_4q"] - out[
        "net_equity_issuance_4q"
    ].shift(4)
    out["equity_share_4q_change"] = out["equity_financing_share_4q"] - out[
        "equity_financing_share_4q"
    ].shift(4)

    for column in [
        "net_equity_to_market_1q",
        "net_equity_to_market_4q",
        "debt_minus_equity_to_market_4q",
        "equity_financing_share_4q",
        "net_equity_issuance_4q_change",
        "equity_share_4q_change",
    ]:
        out[f"{column}_rank_40q"] = _rolling_last_percentile(out[column], 40, 20)
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
    parser.add_argument("--source-dir", default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--publication-lag-calendar-days", type=int, default=180)
    args = parser.parse_args()
    features = build_features(
        args.nq_input,
        args.output,
        source_dir=args.source_dir,
        publication_lag_calendar_days=args.publication_lag_calendar_days,
    )
    valid = features.dropna(subset=["net_equity_to_market_4q_rank_40q"])
    print(f"sources={','.join(FRED_SERIES.values())}")
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")
    print(f"observation_range={features['observation_date'].min()}..{features['observation_date'].max()}")
    print(f"publication_lag_calendar_days={args.publication_lag_calendar_days}")


if __name__ == "__main__":
    main()
