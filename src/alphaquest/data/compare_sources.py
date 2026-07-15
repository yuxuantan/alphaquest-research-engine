from __future__ import annotations

from pathlib import Path

import pandas as pd

from alphaquest.data.clean import apply_continuous_contract, validate_ohlc
from alphaquest.data.load import (
    filter_timestamp_bounds,
    list_databento_dbn_files,
    load_databento_dbn,
    load_raw_csv,
    parse_dbn_file_dates,
)
from alphaquest.data.sessions import assign_sessions
from alphaquest.utils.config import write_json


PRICE_COLUMNS = ["open", "high", "low", "close"]
COMPARE_COLUMNS = [*PRICE_COLUMNS, "volume"]


def load_csv_bars(
    path: str | Path,
    config: dict,
    date_bounds: dict | None = None,
) -> pd.DataFrame:
    df = load_raw_csv(
        str(path),
        symbol=config.get("symbol", "ES"),
        timezone=config.get("timezone", "America/New_York"),
        csv_format=config.get("csv_format", "yyyymmdd_hhmmss_ohlcv"),
        has_header=bool(config.get("has_header", False)),
        timestamp_format=config.get("timestamp_format", "%Y%m%d %H%M%S"),
        date_bounds=date_bounds,
    )
    line_lookup = csv_line_lookup(path, config)
    df = df.merge(line_lookup, on="timestamp", how="left")
    df["csv_source_file"] = str(path)
    df = assign_sessions(df, config)
    df["source"] = "csv"
    return _prepare_for_compare(df, source_name="csv")


def load_databento_bars(
    config: dict,
    date_bounds: dict | None = None,
) -> pd.DataFrame:
    df = load_databento_dbn(config, date_bounds=date_bounds)
    df = assign_databento_files(df, config.get("raw_dir"))
    df = assign_sessions(df, config)
    df = apply_continuous_contract(df, config)
    df["source"] = "databento"
    return _prepare_for_compare(df, source_name="databento")


def load_databento_all_contract_bars(
    config: dict,
    date_bounds: dict | None = None,
) -> pd.DataFrame:
    df = load_databento_dbn(config, date_bounds=date_bounds)
    df = assign_databento_files(df, config.get("raw_dir"))
    df = assign_sessions(df, config)
    df["source"] = "databento_all_contracts"
    return df.sort_values(["timestamp", "contract_symbol"]).reset_index(drop=True)


def compare_ohlcv_sources(
    csv_df: pd.DataFrame,
    dbn_df: pd.DataFrame,
    out_dir: str | Path,
    price_tolerance: float = 0.0,
    volume_tolerance: float = 0.0,
    detail_limit: int = 100_000,
    dbn_all_contracts_df: pd.DataFrame | None = None,
) -> dict:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    csv_df = _prepare_for_compare(csv_df, source_name="csv")
    dbn_df = _prepare_for_compare(dbn_df, source_name="databento")

    source_summary = pd.DataFrame(
        [
            source_summary_row(csv_df, "csv"),
            source_summary_row(dbn_df, "databento"),
        ]
    )
    source_summary.to_csv(out / "source_summary.csv", index=False)

    aligned = csv_df.merge(
        dbn_df,
        on="timestamp",
        how="inner",
        suffixes=("_csv", "_databento"),
    )
    only_csv = csv_df[~csv_df["timestamp"].isin(dbn_df["timestamp"])].copy()
    only_dbn = dbn_df[~dbn_df["timestamp"].isin(csv_df["timestamp"])].copy()

    comparison = build_row_comparison(aligned, price_tolerance, volume_tolerance)
    column_summary = column_mismatch_summary(comparison, len(aligned), price_tolerance, volume_tolerance)
    column_summary.to_csv(out / "column_mismatch_summary.csv", index=False)

    session_summary = compare_session_summaries(csv_df, dbn_df)
    session_summary.to_csv(out / "session_summary.csv", index=False)

    selected_contracts = selected_contract_summary(dbn_df)
    selected_contracts.to_csv(out / "databento_selected_contracts.csv", index=False)

    only_csv.to_csv(out / "timestamps_only_in_csv.csv", index=False)
    only_dbn.to_csv(out / "timestamps_only_in_databento.csv", index=False)
    timestamp_gap_segments(only_csv).to_csv(out / "segments_only_in_csv.csv", index=False)
    timestamp_gap_segments(only_dbn).to_csv(out / "segments_only_in_databento.csv", index=False)

    mismatch_rows = comparison[comparison["any_ohlcv_mismatch"]].copy()
    mismatch_rows = mismatch_rows.sort_values(
        ["any_price_mismatch", "max_abs_price_diff", "abs_volume_diff"],
        ascending=[False, False, False],
    )
    mismatch_rows.head(detail_limit).to_csv(out / "mismatch_rows_sample.csv", index=False)

    price_mismatches = comparison[comparison["any_price_mismatch"]].copy()
    price_mismatches.head(detail_limit).to_csv(out / "price_mismatch_rows_sample.csv", index=False)

    volume_mismatches = comparison[comparison["volume_mismatch"]].copy()
    volume_mismatches.sort_values("abs_volume_diff", ascending=False).head(detail_limit).to_csv(
        out / "volume_mismatch_rows_sample.csv",
        index=False,
    )

    alternate_summary = {}
    alternate_matches = None
    if dbn_all_contracts_df is not None:
        alternate_summary, alternate_matches = alternate_contract_match_report(
            csv_df,
            dbn_all_contracts_df,
            comparison,
            out,
            price_tolerance=price_tolerance,
            volume_tolerance=volume_tolerance,
            detail_limit=detail_limit,
        )
    build_manual_review_rows(comparison, out, detail_limit=detail_limit, alternate_matches=alternate_matches)

    summary = {
        "csv_rows": int(len(csv_df)),
        "databento_rows": int(len(dbn_df)),
        "matched_timestamps": int(len(aligned)),
        "timestamps_only_in_csv": int(len(only_csv)),
        "timestamps_only_in_databento": int(len(only_dbn)),
        "rows_with_any_ohlcv_mismatch": int(comparison["any_ohlcv_mismatch"].sum()) if len(comparison) else 0,
        "rows_with_any_price_mismatch": int(comparison["any_price_mismatch"].sum()) if len(comparison) else 0,
        "rows_with_volume_mismatch": int(comparison["volume_mismatch"].sum()) if len(comparison) else 0,
        "mismatch_sample_limit": int(detail_limit),
        "mismatch_sample_truncated": bool(len(mismatch_rows) > detail_limit),
        "price_tolerance": price_tolerance,
        "volume_tolerance": volume_tolerance,
        "first_csv_timestamp": _timestamp_str(csv_df["timestamp"].min()) if len(csv_df) else None,
        "last_csv_timestamp": _timestamp_str(csv_df["timestamp"].max()) if len(csv_df) else None,
        "first_databento_timestamp": _timestamp_str(dbn_df["timestamp"].min()) if len(dbn_df) else None,
        "last_databento_timestamp": _timestamp_str(dbn_df["timestamp"].max()) if len(dbn_df) else None,
        "alternate_contract_check": alternate_summary,
    }
    if len(comparison):
        summary.update(
            {
                "mismatched_row_rate": float(comparison["any_ohlcv_mismatch"].mean()),
                "price_mismatch_row_rate": float(comparison["any_price_mismatch"].mean()),
                "volume_mismatch_row_rate": float(comparison["volume_mismatch"].mean()),
            }
        )
    write_json(out / "summary.json", summary)
    return summary


def infer_bounds_from_csv(csv_df: pd.DataFrame) -> dict:
    return {
        "start_timestamp": csv_df["timestamp"].min().isoformat(),
        "end_timestamp": csv_df["timestamp"].max().isoformat(),
    }


def csv_line_lookup(path: str | Path, config: dict) -> pd.DataFrame:
    timestamp_format = config.get("timestamp_format", "%Y%m%d %H%M%S")
    timezone = config.get("timezone", "America/New_York")
    has_header = bool(config.get("has_header", False))
    header = 0 if has_header else None
    raw = pd.read_csv(path, header=header, usecols=[0], names=["timestamp"] if not has_header else None)
    if has_header:
        first_col = raw.columns[0]
        raw = raw.rename(columns={first_col: "timestamp"})
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], format=timestamp_format)
    if raw["timestamp"].dt.tz is None:
        raw["timestamp"] = raw["timestamp"].dt.tz_localize(timezone)
    else:
        raw["timestamp"] = raw["timestamp"].dt.tz_convert(timezone)
    raw["csv_line_number"] = raw.index + (2 if has_header else 1)
    return raw.drop_duplicates(subset=["timestamp"], keep="last")


def assign_databento_files(df: pd.DataFrame, raw_dir: str | Path | None) -> pd.DataFrame:
    out = df.copy()
    out["databento_file"] = None
    if not raw_dir or out.empty:
        return out

    timestamp_dates = out["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()
    for path in list_databento_dbn_files(raw_dir):
        bounds = parse_dbn_file_dates(path)
        if not bounds:
            continue
        start, end = bounds
        mask = (timestamp_dates >= start) & (timestamp_dates <= end)
        out.loc[mask, "databento_file"] = str(path)
    return out


def source_summary_row(df: pd.DataFrame, source: str) -> dict:
    duplicates = int(df.duplicated(subset=["timestamp"]).sum()) if len(df) else 0
    invalid = int((~validate_ohlc(df)).sum()) if len(df) else 0
    return {
        "source": source,
        "rows": int(len(df)),
        "unique_timestamps": int(df["timestamp"].nunique()) if len(df) else 0,
        "duplicate_timestamps": duplicates,
        "invalid_ohlcv_rows": invalid,
        "first_timestamp": _timestamp_str(df["timestamp"].min()) if len(df) else None,
        "last_timestamp": _timestamp_str(df["timestamp"].max()) if len(df) else None,
        "first_session_date": str(df["session_date"].min()) if len(df) else None,
        "last_session_date": str(df["session_date"].max()) if len(df) else None,
    }


def build_row_comparison(
    aligned: pd.DataFrame,
    price_tolerance: float,
    volume_tolerance: float,
) -> pd.DataFrame:
    if aligned.empty:
        return pd.DataFrame(
            columns=[
                "timestamp",
                "session_date_csv",
                "session_label_csv",
                "contract_symbol_databento",
                "any_price_mismatch",
                "volume_mismatch",
                "any_ohlcv_mismatch",
            ]
        )

    out = aligned[
        [
            "timestamp",
            "session_date_csv",
            "session_label_csv",
            "session_date_databento",
            "session_label_databento",
            "symbol_csv",
            "symbol_databento",
        ]
    ].copy()
    for col in ["csv_line_number", "csv_source_file", "databento_file"]:
        if col in aligned.columns:
            out[col] = aligned[col]
    if "contract_symbol_databento" in aligned.columns:
        out["contract_symbol_databento"] = aligned["contract_symbol_databento"]

    price_flags = []
    for col in PRICE_COLUMNS:
        out[f"{col}_csv"] = aligned[f"{col}_csv"]
        out[f"{col}_databento"] = aligned[f"{col}_databento"]
        out[f"{col}_diff"] = aligned[f"{col}_databento"] - aligned[f"{col}_csv"]
        out[f"abs_{col}_diff"] = out[f"{col}_diff"].abs()
        flag = out[f"abs_{col}_diff"] > price_tolerance
        out[f"{col}_mismatch"] = flag
        price_flags.append(flag)

    out["volume_csv"] = aligned["volume_csv"]
    out["volume_databento"] = aligned["volume_databento"]
    out["volume_diff"] = aligned["volume_databento"] - aligned["volume_csv"]
    out["abs_volume_diff"] = out["volume_diff"].abs()
    out["volume_mismatch"] = out["abs_volume_diff"] > volume_tolerance
    out["max_abs_price_diff"] = out[[f"abs_{col}_diff" for col in PRICE_COLUMNS]].max(axis=1)
    out["any_price_mismatch"] = pd.concat(price_flags, axis=1).any(axis=1)
    out["any_ohlcv_mismatch"] = out["any_price_mismatch"] | out["volume_mismatch"]
    return out


def column_mismatch_summary(
    comparison: pd.DataFrame,
    matched_count: int,
    price_tolerance: float,
    volume_tolerance: float,
) -> pd.DataFrame:
    rows = []
    for col in COMPARE_COLUMNS:
        diff_col = f"{col}_diff"
        abs_col = f"abs_{col}_diff"
        tolerance = volume_tolerance if col == "volume" else price_tolerance
        if comparison.empty or diff_col not in comparison:
            rows.append(
                {
                    "column": col,
                    "matched_rows": int(matched_count),
                    "mismatch_rows": 0,
                    "mismatch_rate": 0.0,
                    "tolerance": tolerance,
                    "max_abs_diff": 0.0,
                    "mean_abs_diff": 0.0,
                    "median_abs_diff": 0.0,
                    "p95_abs_diff": 0.0,
                }
            )
            continue
        mismatch = comparison[abs_col] > tolerance
        rows.append(
            {
                "column": col,
                "matched_rows": int(matched_count),
                "mismatch_rows": int(mismatch.sum()),
                "mismatch_rate": float(mismatch.mean()) if matched_count else 0.0,
                "tolerance": tolerance,
                "max_abs_diff": float(comparison[abs_col].max()),
                "mean_abs_diff": float(comparison[abs_col].mean()),
                "median_abs_diff": float(comparison[abs_col].median()),
                "p95_abs_diff": float(comparison[abs_col].quantile(0.95)),
            }
        )
    return pd.DataFrame(rows)


def compare_session_summaries(csv_df: pd.DataFrame, dbn_df: pd.DataFrame) -> pd.DataFrame:
    csv_summary = session_summary(csv_df, "csv")
    dbn_summary = session_summary(dbn_df, "databento")
    merged = csv_summary.merge(
        dbn_summary,
        on=["session_date", "session_label"],
        how="outer",
        suffixes=("_csv", "_databento"),
    )
    for col in ["row_count", "volume"]:
        merged[f"{col}_diff"] = merged[f"{col}_databento"].fillna(0) - merged[f"{col}_csv"].fillna(0)
    for col in PRICE_COLUMNS:
        merged[f"{col}_diff"] = merged[f"{col}_databento"] - merged[f"{col}_csv"]
    return merged.sort_values(["session_date", "session_label"]).reset_index(drop=True)


def session_summary(df: pd.DataFrame, source: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=[
                "session_date",
                "session_label",
                f"row_count_{source}",
                f"first_timestamp_{source}",
                f"last_timestamp_{source}",
                f"open_{source}",
                f"high_{source}",
                f"low_{source}",
                f"close_{source}",
                f"volume_{source}",
            ]
        )
    summary = (
        df.sort_values("timestamp")
        .groupby(["session_date", "session_label"], dropna=False)
        .agg(
            row_count=("timestamp", "count"),
            first_timestamp=("timestamp", "first"),
            last_timestamp=("timestamp", "last"),
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        )
        .reset_index()
    )
    return summary.rename(
        columns={col: f"{col}_{source}" for col in summary.columns if col not in {"session_date", "session_label"}}
    )


def selected_contract_summary(dbn_df: pd.DataFrame) -> pd.DataFrame:
    if dbn_df.empty or "contract_symbol" not in dbn_df.columns:
        return pd.DataFrame(columns=["session_date", "contract_symbol", "rows", "volume"])
    return (
        dbn_df.groupby(["session_date", "contract_symbol"], dropna=False)
        .agg(rows=("timestamp", "count"), volume=("volume", "sum"))
        .reset_index()
        .sort_values(["session_date", "volume"], ascending=[True, False])
        .reset_index(drop=True)
    )


def alternate_contract_match_report(
    csv_df: pd.DataFrame,
    dbn_all_contracts_df: pd.DataFrame,
    comparison: pd.DataFrame,
    out_dir: str | Path,
    price_tolerance: float = 0.0,
    volume_tolerance: float = 0.0,
    detail_limit: int = 100_000,
) -> tuple[dict, pd.DataFrame | None]:
    out = Path(out_dir)
    if comparison.empty or dbn_all_contracts_df.empty:
        empty = pd.DataFrame()
        empty.to_csv(out / "alternate_contract_matches.csv", index=False)
        empty.to_csv(out / "alternate_contract_match_summary.csv", index=False)
        return {}, None

    selected = comparison[comparison["any_price_mismatch"]][
        ["timestamp", "contract_symbol_databento", "max_abs_price_diff", "abs_volume_diff"]
    ].rename(
        columns={
            "contract_symbol_databento": "selected_contract_symbol",
            "max_abs_price_diff": "selected_max_abs_price_diff",
            "abs_volume_diff": "selected_abs_volume_diff",
        }
    )
    if selected.empty:
        empty = pd.DataFrame()
        empty.to_csv(out / "alternate_contract_matches.csv", index=False)
        empty.to_csv(out / "alternate_contract_match_summary.csv", index=False)
        return {}, None

    csv_slice = csv_df[csv_df["timestamp"].isin(selected["timestamp"])][
        [
            "timestamp",
            *[col for col in ["csv_line_number", "csv_source_file"] if col in csv_df.columns],
            *PRICE_COLUMNS,
            "volume",
        ]
    ].copy()
    candidates = csv_slice.merge(
        dbn_all_contracts_df[
            [
                "timestamp",
                "contract_symbol",
                *[col for col in ["databento_file"] if col in dbn_all_contracts_df.columns],
                *PRICE_COLUMNS,
                "volume",
            ]
        ],
        on="timestamp",
        how="inner",
        suffixes=("_csv", "_databento"),
    )
    if candidates.empty:
        empty = pd.DataFrame()
        empty.to_csv(out / "alternate_contract_matches.csv", index=False)
        empty.to_csv(out / "alternate_contract_match_summary.csv", index=False)
        return {}, None

    for col in PRICE_COLUMNS:
        candidates[f"{col}_diff"] = candidates[f"{col}_databento"] - candidates[f"{col}_csv"]
        candidates[f"abs_{col}_diff"] = candidates[f"{col}_diff"].abs()
        candidates[f"{col}_match"] = candidates[f"abs_{col}_diff"] <= price_tolerance
    candidates["volume_diff"] = candidates["volume_databento"] - candidates["volume_csv"]
    candidates["abs_volume_diff"] = candidates["volume_diff"].abs()
    candidates["volume_match"] = candidates["abs_volume_diff"] <= volume_tolerance
    candidates["matched_price_columns"] = candidates[[f"{col}_match" for col in PRICE_COLUMNS]].sum(axis=1)
    candidates["max_abs_price_diff"] = candidates[[f"abs_{col}_diff" for col in PRICE_COLUMNS]].max(axis=1)
    candidates["exact_price_match"] = candidates["max_abs_price_diff"] <= price_tolerance

    candidates = candidates.merge(selected, on="timestamp", how="left")
    candidates["selected_contract"] = candidates["contract_symbol"] == candidates["selected_contract_symbol"]
    candidates["better_than_selected"] = candidates["max_abs_price_diff"] < candidates["selected_max_abs_price_diff"]

    best = (
        candidates.sort_values(
            [
                "exact_price_match",
                "matched_price_columns",
                "max_abs_price_diff",
                "abs_volume_diff",
                "volume_databento",
            ],
            ascending=[False, False, True, True, False],
        )
        .groupby("timestamp", as_index=False)
        .first()
    )
    best = best.rename(columns={"contract_symbol": "best_contract_symbol"})
    best.head(detail_limit).to_csv(out / "alternate_contract_matches.csv", index=False)

    grouped = (
        best.groupby(["selected_contract_symbol", "best_contract_symbol"], dropna=False)
        .agg(
            rows=("timestamp", "count"),
            exact_price_matches=("exact_price_match", "sum"),
            better_than_selected=("better_than_selected", "sum"),
            median_best_max_abs_price_diff=("max_abs_price_diff", "median"),
            median_selected_max_abs_price_diff=("selected_max_abs_price_diff", "median"),
        )
        .reset_index()
        .sort_values(["rows", "exact_price_matches"], ascending=False)
    )
    grouped.to_csv(out / "alternate_contract_match_summary.csv", index=False)

    summary = {
        "price_mismatch_timestamps_checked": int(selected["timestamp"].nunique()),
        "timestamps_with_databento_candidates": int(best["timestamp"].nunique()),
        "exact_price_match_any_contract": int(best["exact_price_match"].sum()),
        "better_price_match_any_contract": int(best["better_than_selected"].sum()),
        "alternate_match_rows_written": int(min(len(best), detail_limit)),
        "alternate_match_sample_truncated": bool(len(best) > detail_limit),
    }
    return summary, best


def build_manual_review_rows(
    comparison: pd.DataFrame,
    out_dir: str | Path,
    detail_limit: int = 100_000,
    alternate_matches: pd.DataFrame | None = None,
) -> None:
    out = Path(out_dir)
    if comparison.empty:
        pd.DataFrame().to_csv(out / "manual_review_rows.csv", index=False)
        return

    rows = comparison[comparison["any_ohlcv_mismatch"]].copy()
    rows = rows.sort_values(
        ["any_price_mismatch", "max_abs_price_diff", "abs_volume_diff"],
        ascending=[False, False, False],
    )
    base_columns = [
        "timestamp",
        *[col for col in ["csv_source_file", "csv_line_number", "databento_file"] if col in rows.columns],
        "session_date_csv",
        "session_label_csv",
        "contract_symbol_databento",
        "any_price_mismatch",
        "volume_mismatch",
        "max_abs_price_diff",
        "abs_volume_diff",
        "open_csv",
        "open_databento",
        "high_csv",
        "high_databento",
        "low_csv",
        "low_databento",
        "close_csv",
        "close_databento",
        "volume_csv",
        "volume_databento",
    ]
    review = rows[[col for col in base_columns if col in rows.columns]].copy()

    if alternate_matches is not None and not alternate_matches.empty:
        alt_columns = [
            "timestamp",
            "best_contract_symbol",
            "exact_price_match",
            "better_than_selected",
            "matched_price_columns",
            "max_abs_price_diff",
            "selected_max_abs_price_diff",
        ]
        if "databento_file" in alternate_matches.columns:
            alt_columns.insert(2, "databento_file")
        alt = alternate_matches[[col for col in alt_columns if col in alternate_matches.columns]].copy()
        alt = alt.rename(
            columns={
                "databento_file": "alternate_databento_file",
                "max_abs_price_diff": "alternate_max_abs_price_diff",
                "exact_price_match": "alternate_exact_price_match",
                "better_than_selected": "alternate_better_than_selected",
                "matched_price_columns": "alternate_matched_price_columns",
            }
        )
        review = review.merge(alt, on="timestamp", how="left")

    review.head(detail_limit).to_csv(out / "manual_review_rows.csv", index=False)


def timestamp_gap_segments(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["segment_id", "start_timestamp", "end_timestamp", "row_count"])
    ordered = df.sort_values("timestamp").reset_index(drop=True)
    breaks = ordered["timestamp"].diff().gt(pd.Timedelta(minutes=1)).fillna(True)
    ordered["_segment"] = breaks.cumsum()
    segments = (
        ordered.groupby("_segment")
        .agg(
            start_timestamp=("timestamp", "first"),
            end_timestamp=("timestamp", "last"),
            row_count=("timestamp", "count"),
            first_session_date=("session_date", "first"),
            last_session_date=("session_date", "last"),
            first_session_label=("session_label", "first"),
            last_session_label=("session_label", "last"),
        )
        .reset_index(drop=True)
    )
    segments.insert(0, "segment_id", range(1, len(segments) + 1))
    return segments


def _prepare_for_compare(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    out = df.copy()
    out = out.sort_values("timestamp")
    out = out.drop_duplicates(subset=["timestamp"], keep="last")
    if "contract_symbol" not in out.columns:
        out["contract_symbol"] = ""
    for col in COMPARE_COLUMNS:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    if "session_date" not in out.columns or "session_label" not in out.columns:
        raise ValueError(f"{source_name} data must have session_date and session_label before comparison")
    return out.reset_index(drop=True)


def _timestamp_str(value) -> str | None:
    if pd.isna(value):
        return None
    return str(value)
