from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlretrieve

import pandas as pd


DEFAULT_NQ_INPUT = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
DEFAULT_AI_GPR_CSV = "data/external/ai_gpr/ai_gpr_data_daily.csv"
DEFAULT_OUTPUT = "data/external/nq_ai_gpr_features_20110103_20260612.csv"
AI_GPR_DAILY_URL = "https://www.matteoiacoviello.com/ai_gpr_files/ai_gpr_data_daily.csv"


def build_features(
    nq_input_path: str | Path = DEFAULT_NQ_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    ai_gpr_csv_path: str | Path = DEFAULT_AI_GPR_CSV,
    publication_lag_calendar_days: int = 30,
    download_if_missing: bool = True,
) -> pd.DataFrame:
    if publication_lag_calendar_days < 0:
        raise ValueError("publication_lag_calendar_days must be non-negative.")

    sessions = _nq_sessions(nq_input_path)
    gpr = _load_ai_gpr_daily(ai_gpr_csv_path, download_if_missing=download_if_missing)
    gpr = _add_gpr_state_features(gpr)

    sessions["availability_cutoff"] = sessions["session_date_ts"] - pd.to_timedelta(
        publication_lag_calendar_days,
        unit="D",
    )
    merged = pd.merge_asof(
        sessions.sort_values("availability_cutoff", kind="mergesort"),
        gpr.sort_values("observation_date_ts", kind="mergesort"),
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
        "gpr_ai_1d",
        "gpr_aer_1d",
        "gpr_nonoil_1d",
        "threats_gpr_ai_1d",
        "acts_gpr_ai_1d",
        "gpr_ai_5d",
        "gpr_ai_21d",
        "gpr_ai_5d_change",
        "gpr_ai_21d_rank_252",
        "gpr_ai_5d_change_rank_252",
        "threats_gpr_ai_21d",
        "threats_gpr_ai_21d_rank_252",
        "acts_gpr_ai_5d",
        "acts_gpr_ai_5d_rank_252",
        "gpr_nonoil_21d",
        "gpr_nonoil_21d_rank_252",
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


def _load_ai_gpr_daily(path: str | Path, *, download_if_missing: bool) -> pd.DataFrame:
    csv_path = Path(path)
    if not csv_path.exists():
        if not download_if_missing:
            raise FileNotFoundError(f"AI-GPR daily CSV not found: {csv_path}")
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        urlretrieve(AI_GPR_DAILY_URL, csv_path)

    frame = pd.read_csv(csv_path, parse_dates=["Date"])
    rename = {
        "Date": "observation_date_ts",
        "GPR_AI": "gpr_ai_1d",
        "GPR_AER": "gpr_aer_1d",
        "GPR_NONOIL": "gpr_nonoil_1d",
        "THREATS_GPR_AI": "threats_gpr_ai_1d",
        "ACTS_GPR_AI": "acts_gpr_ai_1d",
    }
    missing = [source for source in rename if source not in frame.columns]
    if missing:
        raise ValueError(f"AI-GPR input is missing columns: {missing}")
    frame = frame.rename(columns=rename)
    frame["observation_date_ts"] = frame["observation_date_ts"].dt.normalize()
    frame["observation_date"] = frame["observation_date_ts"].dt.date.astype(str)
    keep = ["observation_date", "observation_date_ts"] + [
        column for column in rename.values() if column != "observation_date_ts"
    ]
    return (
        frame[keep]
        .sort_values("observation_date_ts", kind="mergesort")
        .reset_index(drop=True)
    )


def _add_gpr_state_features(gpr: pd.DataFrame) -> pd.DataFrame:
    out = gpr.copy()
    out["gpr_ai_5d"] = out["gpr_ai_1d"].rolling(5, min_periods=5).mean()
    out["gpr_ai_21d"] = out["gpr_ai_1d"].rolling(21, min_periods=21).mean()
    out["gpr_ai_5d_change"] = out["gpr_ai_5d"] - out["gpr_ai_5d"].shift(5)
    out["gpr_ai_21d_rank_252"] = _rolling_last_percentile(out["gpr_ai_21d"], 252, 126)
    out["gpr_ai_5d_change_rank_252"] = _rolling_last_percentile(
        out["gpr_ai_5d_change"],
        252,
        126,
    )

    out["threats_gpr_ai_21d"] = out["threats_gpr_ai_1d"].rolling(21, min_periods=21).mean()
    out["threats_gpr_ai_21d_rank_252"] = _rolling_last_percentile(
        out["threats_gpr_ai_21d"],
        252,
        126,
    )
    out["acts_gpr_ai_5d"] = out["acts_gpr_ai_1d"].rolling(5, min_periods=5).mean()
    out["acts_gpr_ai_5d_rank_252"] = _rolling_last_percentile(
        out["acts_gpr_ai_5d"],
        252,
        126,
    )
    out["gpr_nonoil_21d"] = out["gpr_nonoil_1d"].rolling(21, min_periods=21).mean()
    out["gpr_nonoil_21d_rank_252"] = _rolling_last_percentile(
        out["gpr_nonoil_21d"],
        252,
        126,
    )
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
    parser.add_argument("--ai-gpr-csv", default=DEFAULT_AI_GPR_CSV)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--publication-lag-calendar-days", type=int, default=30)
    args = parser.parse_args()
    features = build_features(
        args.nq_input,
        args.output,
        ai_gpr_csv_path=args.ai_gpr_csv,
        publication_lag_calendar_days=args.publication_lag_calendar_days,
    )
    valid = features.dropna(subset=["gpr_ai_21d_rank_252", "threats_gpr_ai_21d_rank_252"])
    print(f"source={AI_GPR_DAILY_URL}")
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")
    print(f"observation_range={features['observation_date'].min()}..{features['observation_date'].max()}")
    print(f"publication_lag_calendar_days={args.publication_lag_calendar_days}")


if __name__ == "__main__":
    main()
