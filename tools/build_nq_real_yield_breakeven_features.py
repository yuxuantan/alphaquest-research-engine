from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


DEFAULT_BARS_INPUT = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
DEFAULT_OUTPUT = "data/external/nq_real_yield_breakeven_features_20110103_20260612.csv"
DEFAULT_DFII10_INPUT = "data/external/fred_real_yield_dfii10_2003_2026.csv"
DEFAULT_T10YIE_INPUT = "data/external/fred_real_yield_t10yie_2003_2026.csv"
DEFAULT_DGS10_INPUT = "data/external/fred_real_yield_dgs10_2003_2026.csv"


def build_features(
    bars_input: str | Path,
    output_path: str | Path,
    *,
    dfii10_input: str | Path = DEFAULT_DFII10_INPUT,
    t10yie_input: str | Path = DEFAULT_T10YIE_INPUT,
    dgs10_input: str | Path = DEFAULT_DGS10_INPUT,
    rank_min_periods: int = 60,
) -> pd.DataFrame:
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

    rates = _load_rates(dfii10_input, t10yie_input, dgs10_input)
    rates = _add_features(rates)
    for column in [
        "dfii10",
        "t10yie",
        "real_yield_change_1d",
        "real_yield_change_5d",
        "breakeven_change_1d",
        "breakeven_change_5d",
        "nominal_real_gap_change_1d",
    ]:
        rates[f"{column}_rank_252"] = _rolling_last_percentile(
            rates[column], 252, rank_min_periods
        )

    # FRED daily observations are not assumed tradable during that same NQ RTH
    # session. Each futures session receives only the latest observation strictly
    # before the session date.
    merged = pd.merge_asof(
        sessions.sort_values("session_date_ts"),
        rates.sort_values("observation_date"),
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
            "dfii10",
            "t10yie",
            "dgs10",
            "real_yield_change_1d",
            "real_yield_change_5d",
            "breakeven_change_1d",
            "breakeven_change_5d",
            "nominal_real_gap_change_1d",
            "dfii10_rank_252",
            "t10yie_rank_252",
            "real_yield_change_1d_rank_252",
            "real_yield_change_5d_rank_252",
            "breakeven_change_1d_rank_252",
            "breakeven_change_5d_rank_252",
            "nominal_real_gap_change_1d_rank_252",
        ]
    ].copy()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(output_path, index=False)
    return out


def _load_rates(dfii10_input: str | Path, t10yie_input: str | Path, dgs10_input: str | Path) -> pd.DataFrame:
    frames = [
        _load_one(dfii10_input, "dfii10"),
        _load_one(t10yie_input, "t10yie"),
        _load_one(dgs10_input, "dgs10"),
    ]
    out = frames[0]
    for frame in frames[1:]:
        out = out.merge(frame, on="observation_date", how="outer")
    return (
        out.dropna(subset=["dfii10", "t10yie", "dgs10"], how="any")
        .sort_values("observation_date", kind="mergesort")
        .drop_duplicates("observation_date", keep="last")
        .reset_index(drop=True)
    )


def _load_one(path: str | Path, output_column: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    value_columns = [column for column in raw.columns if column.lower() != "observation_date"]
    if len(value_columns) != 1:
        raise ValueError(f"{path} must contain observation_date and exactly one value column.")
    out = raw.rename(columns={value_columns[0]: output_column}).copy()
    out["observation_date"] = pd.to_datetime(out["observation_date"])
    out[output_column] = pd.to_numeric(out[output_column], errors="coerce")
    return out[["observation_date", output_column]]


def _add_features(rates: pd.DataFrame) -> pd.DataFrame:
    out = rates.copy()
    out["real_yield_change_1d"] = out["dfii10"].diff()
    out["real_yield_change_5d"] = out["dfii10"] - out["dfii10"].shift(5)
    out["breakeven_change_1d"] = out["t10yie"].diff()
    out["breakeven_change_5d"] = out["t10yie"] - out["t10yie"].shift(5)
    out["nominal_real_gap_change_1d"] = (out["dgs10"] - out["dfii10"]).diff()
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
    parser.add_argument("--dfii10-input", default=DEFAULT_DFII10_INPUT)
    parser.add_argument("--t10yie-input", default=DEFAULT_T10YIE_INPUT)
    parser.add_argument("--dgs10-input", default=DEFAULT_DGS10_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    features = build_features(
        args.bars_input,
        args.output,
        dfii10_input=args.dfii10_input,
        t10yie_input=args.t10yie_input,
        dgs10_input=args.dgs10_input,
    )
    valid = features.dropna(subset=["real_yield_change_1d_rank_252", "breakeven_change_1d_rank_252"])
    print(f"wrote {args.output}")
    print(f"rows={len(features)} valid_rank_rows={len(valid)}")
    print(f"date_range={features['session_date'].min()}..{features['session_date'].max()}")


if __name__ == "__main__":
    main()
