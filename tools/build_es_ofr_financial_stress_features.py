from __future__ import annotations

import argparse
from io import BytesIO
from pathlib import Path
import time
from urllib.request import Request, urlopen

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/es_sierra_trade_orderflow_1m_20101214_20260610_full_rth_ny.parquet"
DEFAULT_OFR_CACHE = "data/external/ofr_financial_stress_index_2000_2026.csv"
DEFAULT_OUTPUT = "data/external/es_ofr_financial_stress_features_20110103_20260609.csv"
OFR_FSI_URL = "https://www.financialresearch.gov/financial-stress-index/data/fsi.csv"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    ofr_input: str | Path | None = None,
    ofr_cache: str | Path = DEFAULT_OFR_CACHE,
    rank_min_periods: int = 60,
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
    sessions["available_observation_cutoff"] = sessions["session_date_ts"] - pd.offsets.BDay(2)

    ofr = _load_ofr(ofr_input=ofr_input, ofr_cache=ofr_cache)
    ofr = _add_stress_features(ofr)

    # OFR states that the FSI publishes with data current from two business
    # days prior.  A session can only use the latest OFR observation on or
    # before session_date - 2 business days.
    merged = pd.merge_asof(
        sessions.sort_values("available_observation_cutoff"),
        ofr.sort_values("observation_date"),
        left_on="available_observation_cutoff",
        right_on="observation_date",
        direction="backward",
        allow_exact_matches=True,
    ).sort_values("session_date_ts", kind="mergesort")
    merged = merged.drop(columns=["session_date_ts", "available_observation_cutoff"])

    rank_columns = [
        "ofr_fsi",
        "credit",
        "funding",
        "volatility",
        "united_states",
        "ofr_fsi_change_1d",
        "credit_change_1d",
        "funding_change_1d",
        "volatility_change_1d",
        "united_states_change_1d",
        "ofr_fsi_change_5d",
        "credit_change_5d",
    ]
    for column in rank_columns:
        merged[f"{column}_rank_252"] = _rolling_last_percentile(
            merged[column], 252, rank_min_periods
        )

    columns = [
        "session_date",
        "observation_date",
        "ofr_fsi",
        "credit",
        "equity_valuation",
        "safe_assets",
        "funding",
        "volatility",
        "united_states",
        "other_advanced_economies",
        "emerging_markets",
        "ofr_fsi_change_1d",
        "credit_change_1d",
        "funding_change_1d",
        "volatility_change_1d",
        "united_states_change_1d",
        "ofr_fsi_change_5d",
        "credit_change_5d",
        "ofr_fsi_rank_252",
        "credit_rank_252",
        "funding_rank_252",
        "volatility_rank_252",
        "united_states_rank_252",
        "ofr_fsi_change_1d_rank_252",
        "credit_change_1d_rank_252",
        "funding_change_1d_rank_252",
        "volatility_change_1d_rank_252",
        "united_states_change_1d_rank_252",
        "ofr_fsi_change_5d_rank_252",
        "credit_change_5d_rank_252",
    ]
    out = merged.loc[merged["session_date"] >= "2011-01-03", columns].copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"]).dt.date.astype(str)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_ofr(*, ofr_input: str | Path | None, ofr_cache: str | Path) -> pd.DataFrame:
    if ofr_input is not None:
        raw = pd.read_csv(ofr_input)
    else:
        cache_path = Path(ofr_cache)
        if cache_path.exists():
            raw = pd.read_csv(cache_path)
        else:
            raw = _read_csv_with_retries(OFR_FSI_URL)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            raw.to_csv(cache_path, index=False)

    column_map = {_normalize_column(column): column for column in raw.columns}
    rename = {
        _required(column_map, "date"): "observation_date",
        _required(column_map, "ofr fsi"): "ofr_fsi",
        _required(column_map, "credit"): "credit",
        _required(column_map, "equity valuation"): "equity_valuation",
        _required(column_map, "safe assets"): "safe_assets",
        _required(column_map, "funding"): "funding",
        _required(column_map, "volatility"): "volatility",
        _required(column_map, "united states"): "united_states",
        _required(column_map, "other advanced economies"): "other_advanced_economies",
        _required(column_map, "emerging markets"): "emerging_markets",
    }
    out = raw.rename(columns=rename).copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"])
    for column in [
        "ofr_fsi",
        "credit",
        "equity_valuation",
        "safe_assets",
        "funding",
        "volatility",
        "united_states",
        "other_advanced_economies",
        "emerging_markets",
    ]:
        out[column] = pd.to_numeric(out[column], errors="coerce")
    return (
        out[list(rename.values())]
        .dropna(subset=["ofr_fsi", "credit", "funding", "volatility", "united_states"], how="any")
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _add_stress_features(ofr: pd.DataFrame) -> pd.DataFrame:
    out = ofr.copy()
    for column in ["ofr_fsi", "credit", "funding", "volatility", "united_states"]:
        out[f"{column}_change_1d"] = out[column].diff()
    out["ofr_fsi_change_5d"] = out["ofr_fsi"] - out["ofr_fsi"].shift(5)
    out["credit_change_5d"] = out["credit"] - out["credit"].shift(5)
    return out


def _read_csv_with_retries(url: str, attempts: int = 4, sleep_seconds: float = 2.0) -> pd.DataFrame:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urlopen(request, timeout=30) as response:
                return pd.read_csv(BytesIO(response.read()))
        except Exception as exc:  # pragma: no cover - exercised only on network failures.
            last_error = exc
            if attempt == attempts:
                break
            time.sleep(sleep_seconds * attempt)
    raise RuntimeError(f"Failed to download free OFR FSI CSV after {attempts} attempts: {url}") from last_error


def _rolling_last_percentile(series: pd.Series, window: int, min_periods: int) -> pd.Series:
    def percentile(values) -> float:
        clean = pd.Series(values).dropna()
        if clean.empty:
            return float("nan")
        return float(clean.rank(pct=True, method="average").iloc[-1])

    return series.rolling(window, min_periods=min_periods).apply(percentile, raw=False)


def _normalize_column(value: str) -> str:
    return " ".join(str(value).strip().lower().replace("_", " ").split())


def _required(column_map: dict[str, str], key: str) -> str:
    if key not in column_map:
        raise ValueError(f"OFR FSI input is missing required column: {key}")
    return column_map[key]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bars-input", default=DEFAULT_BARS_INPUT)
    parser.add_argument("--ofr-input", default=None)
    parser.add_argument("--ofr-cache", default=DEFAULT_OFR_CACHE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        ofr_input=args.ofr_input,
        ofr_cache=args.ofr_cache,
    )
    valid = features.dropna(
        subset=["ofr_fsi_change_1d_rank_252", "credit_rank_252", "funding_rank_252"]
    )
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
