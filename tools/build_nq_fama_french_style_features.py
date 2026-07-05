from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlretrieve
from zipfile import ZipFile

import pandas as pd


DEFAULT_NQ_INPUT = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
DEFAULT_FF_ZIP = "data/external/fama_french/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
DEFAULT_OUTPUT = "data/external/nq_fama_french_style_features_20110103_20260612.csv"
FAMA_FRENCH_5_DAILY_URL = (
    "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
    "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
)


def build_features(
    nq_input_path: str | Path = DEFAULT_NQ_INPUT,
    output_path: str | Path = DEFAULT_OUTPUT,
    *,
    ff_zip_path: str | Path = DEFAULT_FF_ZIP,
    publication_lag_calendar_days: int = 45,
    download_if_missing: bool = True,
) -> pd.DataFrame:
    if publication_lag_calendar_days < 0:
        raise ValueError("publication_lag_calendar_days must be non-negative.")

    sessions = _nq_sessions(nq_input_path)
    factors = _load_fama_french_5_daily(
        ff_zip_path,
        download_if_missing=download_if_missing,
    )
    factors = _add_style_state_features(factors)

    sessions["availability_cutoff"] = sessions["session_date_ts"] - pd.to_timedelta(
        publication_lag_calendar_days,
        unit="D",
    )
    merged = pd.merge_asof(
        sessions.sort_values("availability_cutoff", kind="mergesort"),
        factors.sort_values("observation_date_ts", kind="mergesort"),
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
        "mkt_rf_1d",
        "smb_1d",
        "hml_1d",
        "rmw_1d",
        "cma_1d",
        "rf_1d",
        "hml_21d",
        "hml_63d",
        "rmw_21d",
        "rmw_63d",
        "cma_21d",
        "cma_63d",
        "hml_z_63d",
        "rmw_z_63d",
        "cma_z_63d",
        "hml_1d_rank_252",
        "hml_21d_rank_252",
        "hml_63d_rank_252",
        "hml_z63_rank_252",
        "rmw_21d_rank_252",
        "rmw_63d_rank_252",
        "rmw_z63_rank_252",
        "cma_21d_rank_252",
        "cma_63d_rank_252",
        "cma_z63_rank_252",
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


def _load_fama_french_5_daily(
    path: str | Path,
    *,
    download_if_missing: bool,
) -> pd.DataFrame:
    zip_path = Path(path)
    if not zip_path.exists():
        if not download_if_missing:
            raise FileNotFoundError(f"Fama-French factor zip not found: {zip_path}")
        zip_path.parent.mkdir(parents=True, exist_ok=True)
        urlretrieve(FAMA_FRENCH_5_DAILY_URL, zip_path)

    with ZipFile(zip_path) as zf:
        names = [name for name in zf.namelist() if name.lower().endswith(".csv")]
        if not names:
            raise ValueError(f"No CSV found inside {zip_path}")
        text = zf.read(names[0]).decode("latin1")

    records: list[dict] = []
    for raw_line in text.splitlines():
        parts = [part.strip() for part in raw_line.split(",")]
        if not parts or len(parts[0]) != 8 or not parts[0].isdigit():
            continue
        try:
            observation_date = pd.to_datetime(parts[0], format="%Y%m%d")
            values = [float(value) / 100.0 for value in parts[1:7]]
        except (ValueError, TypeError):
            continue
        records.append(
            {
                "observation_date": observation_date.date().isoformat(),
                "observation_date_ts": observation_date.normalize(),
                "mkt_rf_1d": values[0],
                "smb_1d": values[1],
                "hml_1d": values[2],
                "rmw_1d": values[3],
                "cma_1d": values[4],
                "rf_1d": values[5],
            }
        )

    if not records:
        raise ValueError(f"No daily factor observations parsed from {zip_path}")
    return (
        pd.DataFrame(records)
        .sort_values("observation_date_ts", kind="mergesort")
        .reset_index(drop=True)
    )


def _add_style_state_features(factors: pd.DataFrame) -> pd.DataFrame:
    out = factors.copy()
    for factor in ("hml", "rmw", "cma"):
        series = out[f"{factor}_1d"].astype(float)
        out[f"{factor}_21d"] = series.rolling(21, min_periods=21).sum()
        out[f"{factor}_63d"] = series.rolling(63, min_periods=63).sum()
        out[f"{factor}_z_63d"] = _rolling_zscore(series, 63)
        out[f"{factor}_1d_rank_252"] = _rolling_last_percentile(
            out[f"{factor}_1d"],
            252,
            min_periods=126,
        )
        out[f"{factor}_21d_rank_252"] = _rolling_last_percentile(
            out[f"{factor}_21d"],
            252,
            min_periods=126,
        )
        out[f"{factor}_63d_rank_252"] = _rolling_last_percentile(
            out[f"{factor}_63d"],
            252,
            min_periods=126,
        )
        out[f"{factor}_z63_rank_252"] = _rolling_last_percentile(
            out[f"{factor}_z_63d"],
            252,
            min_periods=126,
        )
    return out


def _rolling_zscore(series: pd.Series, window: int) -> pd.Series:
    mean = series.rolling(window, min_periods=window).mean()
    std = series.rolling(window, min_periods=window).std(ddof=0)
    return (series - mean) / std


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
    parser.add_argument("--ff-zip", default=DEFAULT_FF_ZIP)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--publication-lag-calendar-days", type=int, default=45)
    args = parser.parse_args()
    features = build_features(
        args.nq_input,
        args.output,
        ff_zip_path=args.ff_zip,
        publication_lag_calendar_days=args.publication_lag_calendar_days,
    )
    valid = features.dropna(subset=["hml_21d_rank_252", "rmw_63d_rank_252", "cma_63d_rank_252"])
    print(f"source={FAMA_FRENCH_5_DAILY_URL}")
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")
    print(f"observation_range={features['observation_date'].min()}..{features['observation_date'].max()}")
    print(f"publication_lag_calendar_days={args.publication_lag_calendar_days}")


if __name__ == "__main__":
    main()
