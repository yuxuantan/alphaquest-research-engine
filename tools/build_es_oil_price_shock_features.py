from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pandas.tseries.offsets import BDay


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_WTI_CACHE = "data/external/eia_wti_spot_daily_1986_2026.csv"
DEFAULT_BRENT_CACHE = "data/external/eia_brent_spot_daily_1987_2026.csv"
DEFAULT_OUTPUT = "data/external/es_oil_price_shock_features_20110103_20260609.csv"
WTI_XLS_URL = "https://www.eia.gov/dnav/pet/hist_xls/RWTCd.xls"
BRENT_XLS_URL = "https://www.eia.gov/dnav/pet/hist_xls/RBRTEd.xls"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    wti_input: str | Path | None = None,
    brent_input: str | Path | None = None,
    wti_cache: str | Path = DEFAULT_WTI_CACHE,
    brent_cache: str | Path = DEFAULT_BRENT_CACHE,
    availability_lag_business_days: int = 2,
    rank_min_periods: int = 60,
) -> pd.DataFrame:
    if availability_lag_business_days < 0:
        raise ValueError("availability_lag_business_days must be non-negative.")

    sessions = _load_sessions(bars_input)
    oil = _load_oil_pair(
        wti_input=wti_input,
        brent_input=brent_input,
        wti_cache=wti_cache,
        brent_cache=brent_cache,
    )
    oil = _add_oil_features(oil)

    sessions["availability_cutoff"] = sessions["session_date_ts"] - BDay(availability_lag_business_days)
    merged = pd.merge_asof(
        sessions.sort_values("availability_cutoff"),
        oil.sort_values("observation_date"),
        left_on="availability_cutoff",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")

    for column in [
        "wti_return_1d",
        "brent_return_1d",
        "wti_return_5d",
        "brent_return_5d",
        "oil_composite_return_1d",
        "oil_abs_return_1d",
        "brent_wti_spread_change_1d",
    ]:
        merged[f"{column}_rank_252"] = _rolling_last_percentile(
            merged[column], 252, rank_min_periods
        )

    columns = [
        "session_date",
        "observation_date",
        "availability_cutoff",
        "availability_lag_business_days",
        "wti_spot",
        "brent_spot",
        "wti_return_1d",
        "brent_return_1d",
        "wti_return_5d",
        "brent_return_5d",
        "oil_composite_return_1d",
        "oil_abs_return_1d",
        "brent_wti_spread",
        "brent_wti_spread_change_1d",
        "wti_return_1d_rank_252",
        "brent_return_1d_rank_252",
        "wti_return_5d_rank_252",
        "brent_return_5d_rank_252",
        "oil_composite_return_1d_rank_252",
        "oil_abs_return_1d_rank_252",
        "brent_wti_spread_change_1d_rank_252",
    ]
    merged["availability_lag_business_days"] = availability_lag_business_days
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    for column in ["observation_date", "availability_cutoff"]:
        out[column] = pd.to_datetime(out[column]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_sessions(bars_input: str | Path) -> pd.DataFrame:
    bars = pd.read_parquet(bars_input, columns=["timestamp"])
    sessions = (
        pd.DataFrame({"session_date": pd.to_datetime(bars["timestamp"]).dt.date.astype(str)})
        .drop_duplicates("session_date")
        .sort_values("session_date", kind="mergesort")
        .reset_index(drop=True)
    )
    sessions["session_date_ts"] = pd.to_datetime(sessions["session_date"])
    return sessions


def _load_oil_pair(
    *,
    wti_input: str | Path | None,
    brent_input: str | Path | None,
    wti_cache: str | Path,
    brent_cache: str | Path,
) -> pd.DataFrame:
    wti = _load_or_download_oil(
        input_path=wti_input,
        cache_path=wti_cache,
        url=WTI_XLS_URL,
        value_name="wti_spot",
    )
    brent = _load_or_download_oil(
        input_path=brent_input,
        cache_path=brent_cache,
        url=BRENT_XLS_URL,
        value_name="brent_spot",
    )
    merged = pd.merge(wti, brent, on="observation_date", how="outer")
    return (
        merged.sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _load_or_download_oil(
    *,
    input_path: str | Path | None,
    cache_path: str | Path,
    url: str,
    value_name: str,
) -> pd.DataFrame:
    if input_path is not None:
        raw = pd.read_csv(input_path)
        out = _normalize_oil_frame(raw, value_name)
    else:
        cache = Path(cache_path)
        if cache.exists():
            raw = pd.read_csv(cache)
            out = _normalize_oil_frame(raw, value_name)
        else:
            out = _read_eia_xls(url, value_name)
            cache.parent.mkdir(parents=True, exist_ok=True)
            out.to_csv(cache, index=False)
    return out


def _read_eia_xls(url: str, value_name: str) -> pd.DataFrame:
    raw = pd.read_excel(url, sheet_name="Data 1", header=None, skiprows=3)
    raw = raw.iloc[:, :2].copy()
    raw.columns = ["observation_date", value_name]
    return _normalize_oil_frame(raw, value_name)


def _normalize_oil_frame(raw: pd.DataFrame, value_name: str) -> pd.DataFrame:
    column_map = {_normalize_column(column): column for column in raw.columns}
    date_col = _first_existing(column_map, ["observation date", "date"])
    value_col = _first_existing(
        column_map,
        [
            value_name.replace("_", " "),
            value_name,
            "cushing ok wti spot price fob dollars per barrel",
            "europe brent spot price fob dollars per barrel",
        ],
    )
    if date_col is None or value_col is None:
        raise ValueError(f"Could not find date and {value_name} columns in oil input.")
    out = raw.rename(columns={date_col: "observation_date", value_col: value_name}).copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"], errors="coerce")
    out[value_name] = pd.to_numeric(out[value_name], errors="coerce")
    return (
        out[["observation_date", value_name]]
        .dropna(subset=["observation_date", value_name])
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _add_oil_features(oil: pd.DataFrame) -> pd.DataFrame:
    out = oil.copy()
    out["wti_return_1d"] = out["wti_spot"].pct_change(fill_method=None)
    out["brent_return_1d"] = out["brent_spot"].pct_change(fill_method=None)
    out["wti_return_5d"] = out["wti_spot"] / out["wti_spot"].shift(5) - 1.0
    out["brent_return_5d"] = out["brent_spot"] / out["brent_spot"].shift(5) - 1.0
    out["oil_composite_return_1d"] = out[["wti_return_1d", "brent_return_1d"]].mean(axis=1)
    out["oil_abs_return_1d"] = out[["wti_return_1d", "brent_return_1d"]].abs().mean(axis=1)
    out["brent_wti_spread"] = out["brent_spot"] - out["wti_spot"]
    out["brent_wti_spread_change_1d"] = out["brent_wti_spread"].diff()
    return out


def _rolling_last_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    def percentile(values) -> float:
        clean = pd.Series(values).dropna()
        if clean.empty:
            return float("nan")
        return float(clean.rank(pct=True, method="average").iloc[-1])

    return series.rolling(window, min_periods=min_periods).apply(percentile, raw=False)


def _normalize_column(value: str) -> str:
    normalized = str(value).strip().lower().replace("_", " ")
    normalized = normalized.replace("(", "").replace(")", "").replace(",", "")
    return " ".join(normalized.split())


def _first_existing(column_map: dict[str, str], keys: list[str]) -> str | None:
    for key in keys:
        if key in column_map:
            return column_map[key]
    return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-input", default=DEFAULT_BARS_INPUT)
    parser.add_argument("--wti-input", default=None)
    parser.add_argument("--brent-input", default=None)
    parser.add_argument("--wti-cache", default=DEFAULT_WTI_CACHE)
    parser.add_argument("--brent-cache", default=DEFAULT_BRENT_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--availability-lag-business-days", type=int, default=2)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        wti_input=args.wti_input,
        brent_input=args.brent_input,
        wti_cache=args.wti_cache,
        brent_cache=args.brent_cache,
        availability_lag_business_days=args.availability_lag_business_days,
    )
    valid = features.dropna(subset=["wti_return_1d_rank_252", "brent_return_1d_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")
    print(
        "oil_observation_range="
        f"{features['observation_date'].min()}..{features['observation_date'].max()}"
    )


if __name__ == "__main__":
    main()
