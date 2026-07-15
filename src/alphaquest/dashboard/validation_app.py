from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from alphaquest.validation import ManualReviewAnnotation, audit_trade_exit_path, load_tick_window_for_trade, load_validation_run, trade_path_from_ticks
from alphaquest.validation.schema import MANUAL_REVIEW_COLUMNS, MANUAL_REVIEW_FILENAME, METADATA_FILENAME, normalize_columns
from alphaquest.research.storage import display_path, load_storage_layout

DASHBOARD_VERSION = "validation-dashboard-review-v1"
DEFAULT_SEARCH_ROOT = os.environ.get(
    "PROPSTACK_VALIDATION_SEARCH_ROOT", display_path(load_storage_layout().evidence_roots[0])
)

REVIEW_STATUSES = [
    "Correct",
    "Bug suspected",
    "Data issue",
    "Needs deeper review",
    "False signal",
    "Exit issue",
    "Orderflow filter issue",
]

REVIEW_SAMPLE_MODES = [
    "Random 20 trades",
    "First 20 trades chronologically",
    "Last 20 trades chronologically",
    "Worst 20 trades by R",
    "Best 20 trades by R",
    "All forced-flatten trades",
    "All same-bar ambiguous trades",
    "All trades with mismatch warnings",
    "High-impact edge cases",
]

TRADE_TABLE_COLUMNS = [
    "trade_id",
    "session_date",
    "direction",
    "entry_time",
    "entry_price",
    "stop_price",
    "target_price",
    "exit_time",
    "exit_price",
    "exit_reason",
    "pnl_ticks",
    "r_multiple",
    "was_forced_flatten",
    "same_bar_ambiguous",
    "debug_flags",
    "reviewer_status",
    "reviewed_at",
    "check_error_count",
    "check_warning_count",
    "check_flags",
]

CHECKLIST_FIELDS = {
    "RTH filter": ("rth_filter_pass",),
    "Sweep filter": ("sweep_filter_pass", "sweep_pass"),
    "Reclaim filter": ("reclaim_filter_pass", "reclaim_pass"),
    "Volume filter": ("volume_filter_pass",),
    "Delta filter": ("delta_filter_pass",),
    "Imbalance filter": ("imbalance_filter_pass", "stacked_imbalance_pass"),
    "Final entry": ("final_entry_pass",),
}

ORDERFLOW_FLAG_COLUMNS = [
    "rth_filter_pass",
    "volume_filter_pass",
    "delta_filter_pass",
    "stacked_imbalance_pass",
    "final_entry_pass",
]

ORDERFLOW_BAR_COLUMNS = [
    "timestamp",
    "event_marker",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "bid_volume",
    "ask_volume",
    "delta",
    "delta_pct",
    "cumulative_delta",
    "imbalance_count",
    "max_bid_volume_at_price",
    "max_ask_volume_at_price",
    *ORDERFLOW_FLAG_COLUMNS,
]

FOOTPRINT_COLUMNS = [
    "bar_timestamp",
    "price_level",
    "bid_volume",
    "ask_volume",
    "total_volume",
    "delta",
]

CHECK_TABLE_COLUMNS = [
    "trade_id",
    "status",
    "category",
    "check_name",
    "description",
    "expected",
    "actual",
    "details",
]

SUSPICIOUS_TERMS = (
    "ambiguous",
    "unresolved",
    "violation",
    "missing",
    "reject",
    "fallback",
    "false",
    "warning",
    "error",
)

CHART_MODEBAR_BUTTONS = [
    "drawline",
    "drawopenpath",
    "drawrect",
    "eraseshape",
]


def price_chart_config(*, scroll_zoom: bool = False) -> dict[str, Any]:
    return {
        "scrollZoom": bool(scroll_zoom),
        "displayModeBar": True,
        "displaylogo": False,
        "doubleClick": "reset",
        "responsive": True,
        "modeBarButtonsToAdd": CHART_MODEBAR_BUTTONS,
        "toImageButtonOptions": {
            "format": "png",
            "filename": "validation_trade_chart",
            "height": 900,
            "width": 1600,
            "scale": 2,
        },
    }


def discover_validation_runs(search_root: str | Path, *, limit: int = 200) -> list[Path]:
    root = Path(search_root).expanduser()
    if not root.exists():
        return []
    paths = [path.parent for path in root.rglob(METADATA_FILENAME)]
    paths = sorted(set(paths), key=lambda path: path.stat().st_mtime, reverse=True)
    return paths[:limit]


def load_run_without_ticks(run_dir: str | Path):
    return load_validation_run(run_dir, include_tick_windows=False)


def run_summary(metadata: dict[str, Any], trades: pd.DataFrame) -> dict[str, Any]:
    entry_start = _min_timestamp(trades.get("entry_time")) if "entry_time" in trades else None
    exit_end = _max_timestamp(trades.get("exit_time")) if "exit_time" in trades else None
    return {
        "run_id": metadata.get("run_id"),
        "campaign_id": metadata.get("campaign_id"),
        "strategy_id": metadata.get("strategy_id"),
        "variant_id": metadata.get("variant_id"),
        "symbol": metadata.get("symbol"),
        "timeframe": metadata.get("timeframe"),
        "stage": metadata.get("stage"),
        "trade_count": int(len(trades)),
        "date_range": _date_range_text(entry_start, exit_end),
        "generated_at": metadata.get("created_at_utc") or metadata.get("generated_at"),
        "config_hash": metadata.get("config_hash"),
        "source_run_dir": metadata.get("source_run_dir"),
        "source_trade_log": metadata.get("source_trade_log"),
    }


def prepare_trade_table(
    trades: pd.DataFrame,
    exit_audits: pd.DataFrame | None = None,
    validation_checks: pd.DataFrame | None = None,
) -> pd.DataFrame:
    table = trades.copy()
    if exit_audits is not None and not exit_audits.empty and "trade_id" in table.columns:
        audit_cols = [
            column
            for column in [
                "trade_id",
                "same_bar_ambiguous",
                "ambiguity_resolution",
                "forced_flatten_reason",
                "engine_exit_matches_path",
                "warning_flags",
            ]
            if column in exit_audits.columns
        ]
        if len(audit_cols) > 1:
            table = table.merge(exit_audits[audit_cols], on="trade_id", how="left")
    check_summary = validation_checks_by_trade(validation_checks)
    if not check_summary.empty and "trade_id" in table.columns:
        table = table.merge(check_summary, on="trade_id", how="left")
    for column in ("entry_time", "exit_time"):
        if column in table.columns:
            table[column] = pd.to_datetime(table[column], errors="coerce")
    for column in ("check_error_count", "check_warning_count"):
        if column in table.columns:
            table[column] = pd.to_numeric(table[column], errors="coerce").fillna(0).astype(int)
    table["is_winner"] = _numeric_first(table, ["pnl_ticks", "r_multiple", "pnl_usd"]) > 0
    table["is_loser"] = _numeric_first(table, ["pnl_ticks", "r_multiple", "pnl_usd"]) < 0
    table["suspicious_debug"] = table.apply(has_suspicious_debug_flags, axis=1)
    for column in TRADE_TABLE_COLUMNS:
        if column not in table.columns:
            table[column] = pd.NA
    return table


def validation_check_summary(checks: pd.DataFrame) -> dict[str, Any]:
    if checks is None or checks.empty or "status" not in checks.columns:
        return {
            "total_checks": 0,
            "passed_checks": 0,
            "warnings": 0,
            "errors": 0,
            "affected_trade_ids": "",
            "affected_trade_count": 0,
        }
    status = checks["status"].fillna("").astype(str).str.upper()
    affected = checks.loc[status.isin(["WARNING", "ERROR"]), "trade_id"] if "trade_id" in checks.columns else pd.Series(dtype="object")
    affected = affected.dropna().astype(str)
    affected_ids = sorted(value for value in affected.unique() if value and value.lower() != "nan")
    return {
        "total_checks": int(len(checks)),
        "passed_checks": int((status == "PASS").sum()),
        "warnings": int((status == "WARNING").sum()),
        "errors": int((status == "ERROR").sum()),
        "affected_trade_ids": ", ".join(affected_ids),
        "affected_trade_count": int(len(affected_ids)),
    }


def validation_checks_by_trade(checks: pd.DataFrame | None) -> pd.DataFrame:
    columns = ["trade_id", "check_error_count", "check_warning_count", "check_flags"]
    if checks is None or checks.empty or "trade_id" not in checks.columns or "status" not in checks.columns:
        return pd.DataFrame(columns=columns)
    rows = []
    scoped = checks.dropna(subset=["trade_id"]).copy()
    scoped["status"] = scoped["status"].fillna("").astype(str).str.upper()
    for trade_id, group in scoped.groupby("trade_id", dropna=False):
        failed = group[group["status"].isin(["WARNING", "ERROR"])]
        flags = [
            f"{row['status']}:{row.get('check_name', 'check')}"
            for _, row in failed.sort_values(["status", "category", "check_name"]).iterrows()
        ]
        rows.append(
            {
                "trade_id": trade_id,
                "check_error_count": int((group["status"] == "ERROR").sum()),
                "check_warning_count": int((group["status"] == "WARNING").sum()),
                "check_flags": "; ".join(flags),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def load_manual_reviews(run_dir: str | Path) -> pd.DataFrame:
    path = Path(run_dir) / MANUAL_REVIEW_FILENAME
    if not path.exists():
        return pd.DataFrame(columns=MANUAL_REVIEW_COLUMNS)
    return normalize_columns(pd.read_parquet(path), MANUAL_REVIEW_COLUMNS)


def write_manual_reviews(run_dir: str | Path, reviews: pd.DataFrame) -> None:
    path = Path(run_dir) / MANUAL_REVIEW_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    normalize_columns(reviews, MANUAL_REVIEW_COLUMNS).to_parquet(path, index=False)


def save_manual_review_annotation(
    run_dir: str | Path,
    trade_id: Any,
    reviewer_status: str,
    reviewer_notes: str | None = None,
    *,
    reviewed_at: Any = None,
    dashboard_version: str = DASHBOARD_VERSION,
) -> pd.DataFrame:
    reviews = load_manual_reviews(run_dir)
    if reviewed_at is None:
        reviewed_at = pd.Timestamp.now(tz="UTC").isoformat()
    record = ManualReviewAnnotation(
        trade_id=trade_id,
        reviewer_status=reviewer_status,
        reviewer_notes=reviewer_notes or None,
        reviewed_at=reviewed_at,
        dashboard_version=dashboard_version,
    ).to_record()
    if "trade_id" in reviews.columns and not reviews.empty:
        reviews = reviews[reviews["trade_id"].astype(str) != str(trade_id)]
    updated = pd.concat([reviews, pd.DataFrame([record])], ignore_index=True)
    write_manual_reviews(run_dir, updated)
    return updated


def add_review_annotations(table: pd.DataFrame, reviews: pd.DataFrame | None) -> pd.DataFrame:
    annotated = table.copy()
    existing_review_columns = [column for column in MANUAL_REVIEW_COLUMNS if column != "trade_id" and column in annotated.columns]
    if existing_review_columns:
        annotated = annotated.drop(columns=existing_review_columns)
    if reviews is not None and not reviews.empty and "trade_id" in annotated.columns:
        review_cols = [column for column in MANUAL_REVIEW_COLUMNS if column in reviews.columns]
        if "trade_id" in review_cols and len(review_cols) > 1:
            annotated = annotated.merge(reviews[review_cols], on="trade_id", how="left")
    for column in MANUAL_REVIEW_COLUMNS:
        if column not in annotated.columns:
            annotated[column] = pd.NA
    annotated["reviewer_status_display"] = annotated["reviewer_status"].fillna("Unreviewed")
    return annotated


def manual_review_summary(trades: pd.DataFrame, reviews: pd.DataFrame) -> dict[str, Any]:
    total = int(trades["trade_id"].nunique()) if "trade_id" in trades.columns else int(len(trades))
    if reviews.empty or "reviewer_status" not in reviews.columns:
        reviewed = pd.Series(dtype="object")
    else:
        reviewed = reviews["reviewer_status"].dropna().astype(str)
        reviewed = reviewed[reviewed.str.strip().ne("")]
    counts = reviewed.value_counts()
    reviewed_count = int(len(reviewed))
    return {
        "total_trades": total,
        "number_reviewed": reviewed_count,
        "number_correct": int(counts.get("Correct", 0)),
        "number_bug_suspected": int(counts.get("Bug suspected", 0)),
        "number_data_issue": int(counts.get("Data issue", 0)),
        "number_exit_issue": int(counts.get("Exit issue", 0)),
        "number_orderflow_issue": int(counts.get("Orderflow filter issue", 0)),
        "review_completion_pct": (100.0 * reviewed_count / total) if total else 0.0,
    }


def build_review_queue(
    trades: pd.DataFrame,
    conditions: pd.DataFrame,
    exit_audits: pd.DataFrame,
    bar_windows: pd.DataFrame,
    *,
    sample_mode: str,
    sample_size: int = 20,
    include_reviewed: bool = True,
    suspicious_only: bool = False,
    random_seed: int = 0,
    tick_size: float | None = None,
) -> pd.DataFrame:
    if trades.empty:
        return trades.copy()
    queue = trades.copy()
    queue["review_reason"] = sample_mode

    if sample_mode == "Random 20 trades":
        queue = queue.sample(n=min(sample_size, len(queue)), random_state=random_seed) if len(queue) else queue
        queue["review_reason"] = "random sample"
    elif sample_mode == "First 20 trades chronologically":
        queue = _sort_by_entry_time(queue).head(sample_size)
        queue["review_reason"] = "first chronological sample"
    elif sample_mode == "Last 20 trades chronologically":
        queue = _sort_by_entry_time(queue).tail(sample_size)
        queue["review_reason"] = "last chronological sample"
    elif sample_mode == "Worst 20 trades by R":
        score = _review_r_score(queue)
        queue = queue.assign(_review_score=score).sort_values("_review_score", na_position="last").head(sample_size)
        queue["review_reason"] = "worst R sample"
    elif sample_mode == "Best 20 trades by R":
        score = _review_r_score(queue)
        queue = queue.assign(_review_score=score).sort_values("_review_score", ascending=False, na_position="last").head(sample_size)
        queue["review_reason"] = "best R sample"
    elif sample_mode == "All forced-flatten trades":
        queue = queue[_forced_flatten_mask(queue)]
        queue["review_reason"] = "forced flatten"
    elif sample_mode == "All same-bar ambiguous trades":
        queue = queue[_boolean_mask(queue, "same_bar_ambiguous")]
        queue["review_reason"] = "same-bar TP/SL ambiguity"
    elif sample_mode == "All trades with mismatch warnings":
        queue = queue[_mismatch_warning_mask(queue)]
        queue["review_reason"] = "exit-path mismatch or warning flag"
    elif sample_mode == "High-impact edge cases":
        reasons = _edge_case_reasons_by_trade(queue, conditions, exit_audits, bar_windows, tick_size=tick_size)
        queue["review_reason"] = queue["trade_id"].map(lambda trade_id: "; ".join(reasons.get(str(trade_id), [])))
        queue = queue[queue["review_reason"].astype(str).str.strip().ne("")]

    queue = queue.drop(columns=[column for column in ["_review_score"] if column in queue.columns])
    if suspicious_only:
        queue = queue[queue.apply(_review_suspicious_mask_row, axis=1)]
    if not include_reviewed and "reviewer_status" in queue.columns:
        queue = queue[queue["reviewer_status"].isna() | queue["reviewer_status"].astype(str).str.strip().eq("")]
    return _sort_review_queue(queue).reset_index(drop=True)


def filter_trade_table(
    table: pd.DataFrame,
    *,
    date_range: tuple[Any, Any] | None = None,
    directions: list[str] | None = None,
    exit_reasons: list[str] | None = None,
    outcome: str = "All",
    forced_flatten_only: bool = False,
    ambiguous_only: bool = False,
    suspicious_only: bool = False,
) -> pd.DataFrame:
    filtered = table.copy()
    if date_range and "session_date" in filtered.columns and all(date_range):
        start, end = pd.Timestamp(date_range[0]).date(), pd.Timestamp(date_range[1]).date()
        sessions = pd.to_datetime(filtered["session_date"], errors="coerce").dt.date
        filtered = filtered[(sessions >= start) & (sessions <= end)]
    if directions:
        filtered = filtered[filtered["direction"].astype(str).isin(directions)]
    if exit_reasons:
        filtered = filtered[filtered["exit_reason"].astype(str).isin(exit_reasons)]
    if outcome == "Winning":
        filtered = filtered[filtered["is_winner"]]
    elif outcome == "Losing":
        filtered = filtered[filtered["is_loser"]]
    if forced_flatten_only and "was_forced_flatten" in filtered.columns:
        filtered = filtered[filtered["was_forced_flatten"].fillna(False).astype(bool)]
    if ambiguous_only and "same_bar_ambiguous" in filtered.columns:
        filtered = filtered[filtered["same_bar_ambiguous"].fillna(False).astype(bool)]
    if suspicious_only and "suspicious_debug" in filtered.columns:
        filtered = filtered[filtered["suspicious_debug"].fillna(False).astype(bool)]
    sort_cols = [column for column in ["entry_time", "trade_id"] if column in filtered.columns]
    return filtered.sort_values(sort_cols).reset_index(drop=True) if sort_cols else filtered.reset_index(drop=True)


def has_suspicious_debug_flags(row: pd.Series) -> bool:
    parts = []
    for column in ("debug_flags", "ambiguity_resolution", "warning_flags", "check_flags", "notes", "exit_reason"):
        value = row.get(column)
        if not _is_missing(value):
            parts.append(str(value))
    for column in ("check_error_count", "check_warning_count"):
        value = _numeric_or_none(row.get(column))
        if value is not None and value > 0:
            return True
    text = " ".join(parts).lower()
    return any(term in text for term in SUSPICIOUS_TERMS)


def row_for_trade(frame: pd.DataFrame, trade_id: Any) -> pd.Series | None:
    if frame.empty or "trade_id" not in frame.columns:
        return None
    rows = frame[frame["trade_id"] == trade_id]
    if rows.empty:
        rows = frame[frame["trade_id"].astype(str) == str(trade_id)]
    return None if rows.empty else rows.iloc[0]


def rows_for_trade(frame: pd.DataFrame, trade_id: Any) -> pd.DataFrame:
    if frame.empty or "trade_id" not in frame.columns:
        return frame.iloc[0:0]
    rows = frame[frame["trade_id"] == trade_id]
    if rows.empty:
        rows = frame[frame["trade_id"].astype(str) == str(trade_id)]
    return rows.copy()


def checklist_rows(snapshot: pd.Series | None) -> pd.DataFrame:
    if snapshot is None:
        return pd.DataFrame({"condition": list(CHECKLIST_FIELDS), "status": ["N/A"] * len(CHECKLIST_FIELDS)})
    json_sources = [
        parse_json_cell(snapshot.get("filter_pass_values")),
        parse_json_cell(snapshot.get("signal_metadata")),
        parse_json_cell(snapshot.get("signal_report_fields")),
    ]
    rows = []
    for label, aliases in CHECKLIST_FIELDS.items():
        value = _lookup_condition_value(snapshot, aliases, json_sources)
        rows.append({"condition": label, "status": status_text(value), "raw_value": value})
    return pd.DataFrame(rows)


def parse_json_cell(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if _is_missing(value):
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def raw_debug_frame(snapshot: pd.Series | None) -> pd.DataFrame:
    if snapshot is None:
        return pd.DataFrame(columns=["field", "value"])
    rows = []
    for key, value in snapshot.to_dict().items():
        if not _is_missing(value):
            rows.append({"field": key, "value": _format_value(value)})
    return pd.DataFrame(rows)


def prepare_orderflow_bar_table(
    bars: pd.DataFrame,
    trade: pd.Series | None,
    condition: pd.Series | None,
    exit_audit: pd.Series | None = None,
    ticks: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if bars.empty:
        return pd.DataFrame(columns=ORDERFLOW_BAR_COLUMNS)
    table = bars.copy().sort_values("timestamp").reset_index(drop=True)
    table["timestamp"] = pd.to_datetime(table["timestamp"], errors="coerce")
    for column in ("open", "high", "low", "close", "volume", "bid_volume", "ask_volume", "delta", "cumulative_delta"):
        if column not in table.columns:
            table[column] = pd.NA
        table[column] = pd.to_numeric(table[column], errors="coerce")
    table["delta_pct"] = _delta_pct_series(table)
    table["event_marker"] = _bar_event_marker_series(table, trade, condition, exit_audit)
    table["imbalance_count"] = _numeric_optional_column(table, "imbalance_count")
    table["max_bid_volume_at_price"] = pd.Series([pd.NA] * len(table), index=table.index, dtype="Float64")
    table["max_ask_volume_at_price"] = pd.Series([pd.NA] * len(table), index=table.index, dtype="Float64")

    if ticks is not None and not ticks.empty:
        footprint = aggregate_footprint_by_price(ticks, table)
        if not footprint.empty:
            footprint_bar_keys = _timestamp_key_series(footprint["bar_timestamp"]).rename("_bar_key")
            maxes = (
                footprint.groupby(footprint_bar_keys, dropna=False)
                .agg(
                    max_bid_volume_at_price=("bid_volume", "max"),
                    max_ask_volume_at_price=("ask_volume", "max"),
                )
                .reset_index()
            )
            table["_bar_key"] = _timestamp_key_series(table["timestamp"])
            table = table.merge(maxes, on="_bar_key", how="left", suffixes=("", "_from_ticks"))
            for column in ("max_bid_volume_at_price", "max_ask_volume_at_price"):
                tick_column = f"{column}_from_ticks"
                if tick_column in table.columns:
                    table[column] = pd.to_numeric(table[column], errors="coerce").fillna(
                        pd.to_numeric(table[tick_column], errors="coerce")
                    )
            table = table.drop(columns=[column for column in ("_bar_key", "max_bid_volume_at_price_from_ticks", "max_ask_volume_at_price_from_ticks") if column in table.columns])

    signal_mask = table["event_marker"].str.contains("signal|decision|entry_execution", case=False, na=False)
    for column in ORDERFLOW_FLAG_COLUMNS:
        value, _ = _lookup_condition_alias(condition, (column,))
        table[column] = pd.NA
        if not _is_missing(value):
            if signal_mask.any():
                table.loc[signal_mask, column] = value
            else:
                table[column] = value
    for column in ORDERFLOW_BAR_COLUMNS:
        if column not in table.columns:
            table[column] = pd.NA
    return table[ORDERFLOW_BAR_COLUMNS]


def aggregate_footprint_by_price(ticks: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    if ticks.empty or bars.empty or "timestamp" not in ticks.columns or "timestamp" not in bars.columns:
        return pd.DataFrame(columns=FOOTPRINT_COLUMNS)
    work = ticks.copy()
    work["bar_timestamp"] = _assign_timestamps_to_bars(work["timestamp"], bars["timestamp"])
    work["price_level"] = _numeric_first_available(work, ["price_level", "price"])
    work["bid_volume"] = _tick_side_volume(work, "bid")
    work["ask_volume"] = _tick_side_volume(work, "ask")
    work["total_volume"] = _numeric_first_available(work, ["volume"])
    side_total = work["bid_volume"].fillna(0) + work["ask_volume"].fillna(0)
    work["total_volume"] = work["total_volume"].fillna(side_total.where(side_total != 0))
    work["delta"] = _numeric_first_available(work, ["price_level_delta", "delta"])
    computed_delta = work["ask_volume"].fillna(0) - work["bid_volume"].fillna(0)
    work["delta"] = work["delta"].fillna(computed_delta.where(side_total != 0))
    work = work.dropna(subset=["bar_timestamp", "price_level"])
    if work.empty:
        return pd.DataFrame(columns=FOOTPRINT_COLUMNS)
    grouped = (
        work.groupby(["bar_timestamp", "price_level"], dropna=False)[["bid_volume", "ask_volume", "total_volume", "delta"]]
        .sum(min_count=1)
        .reset_index()
        .sort_values(["bar_timestamp", "price_level"])
        .reset_index(drop=True)
    )
    return grouped[FOOTPRINT_COLUMNS]


def selected_bar_footprint_detail(
    footprint: pd.DataFrame,
    selected_bar_timestamp: Any,
    *,
    imbalance_ratio: float = 3.0,
) -> pd.DataFrame:
    columns = [*FOOTPRINT_COLUMNS[1:], "imbalance_marker"]
    if footprint.empty or _is_missing(selected_bar_timestamp):
        return pd.DataFrame(columns=columns)
    selected_key = _timestamp_key(selected_bar_timestamp)
    detail = footprint[_timestamp_key_series(footprint["bar_timestamp"]) == selected_key].copy()
    if detail.empty:
        return pd.DataFrame(columns=columns)
    detail["imbalance_marker"] = [
        _display_imbalance_marker(bid, ask, ratio=imbalance_ratio)
        for bid, ask in zip(detail["bid_volume"], detail["ask_volume"], strict=False)
    ]
    return detail[columns].sort_values("price_level", ascending=False).reset_index(drop=True)


def orderflow_filter_explanations(condition: pd.Series | None) -> pd.DataFrame:
    specs = [
        (
            "rth_filter",
            ("rth_filter_pass",),
            ("is_rth", "rth_filter_pass"),
            (),
            ("rth_filter_rule", "rth_rule"),
        ),
        (
            "volume_filter",
            ("volume_filter_pass",),
            ("total_volume", "volume", "sweep_bar_volume"),
            ("min_volume", "volume_threshold", "avg_volume_reference", "rolling_volume", "min_volume_ratio"),
            ("volume_filter_rule", "volume_rule"),
        ),
        (
            "delta_filter",
            ("delta_filter_pass",),
            ("delta_pct", "delta_imbalance", "delta_value", "signed_volume", "absorption_bucket_delta"),
            (
                "min_delta_pct",
                "max_delta_pct",
                "min_delta_imbalance",
                "max_delta_imbalance",
                "min_orderflow_imbalance",
                "min_absorption_imbalance",
                "delta_threshold",
            ),
            ("delta_filter_rule", "delta_rule", "orderflow_rule", "orderflow_absorption_filter"),
        ),
        (
            "imbalance_filter",
            ("imbalance_filter_pass", "stacked_imbalance_pass"),
            (
                "imbalance_count",
                "footprint_buy_imbalance_count",
                "footprint_sell_imbalance_count",
                "footprint_imbalance_volume",
            ),
            (
                "min_imbalance_count",
                "stacked_imbalance_min_count",
                "min_footprint_imbalance_volume",
                "min_footprint_volume",
            ),
            ("imbalance_filter_rule", "stacked_imbalance_rule", "footprint_filter_rule"),
        ),
        (
            "final_entry",
            ("final_entry_pass",),
            ("final_entry_pass",),
            (),
            ("entry_rule", "final_entry_rule"),
        ),
    ]
    rows = []
    for name, pass_aliases, actual_aliases, threshold_aliases, rule_aliases in specs:
        passed, pass_field = _lookup_condition_alias(condition, pass_aliases)
        actual, actual_field = _lookup_condition_alias(condition, actual_aliases)
        threshold, threshold_field = _lookup_condition_alias(condition, threshold_aliases)
        rule, rule_field = _lookup_condition_alias(condition, rule_aliases)
        rows.append(
            {
                "filter": name,
                "status": status_text(passed) if not _is_missing(passed) else "N/A",
                "rule": _format_rule(rule, actual_field, threshold_field),
                "actual": _format_value(actual),
                "threshold": _format_value(threshold),
                "source_fields": _join_source_fields(pass_field, actual_field, threshold_field, rule_field),
            }
        )
    return pd.DataFrame(rows)


def orderflow_warnings(
    trade: pd.Series | None,
    condition: pd.Series | None,
    bars: pd.DataFrame,
    ticks: pd.DataFrame | None = None,
) -> list[str]:
    warnings: list[str] = []
    if bars.empty:
        warnings.append("Selected trade has no bar window artifact.")
    else:
        missing_bar_fields = [
            column
            for column in ("bid_volume", "ask_volume", "delta")
            if column not in bars.columns or pd.to_numeric(bars[column], errors="coerce").dropna().empty
        ]
        if missing_bar_fields:
            warnings.append(f"Orderflow bar fields missing or empty: {', '.join(missing_bar_fields)}.")
        if "delta" in bars.columns and not pd.to_numeric(bars["delta"], errors="coerce").dropna().empty:
            side_fields_missing = any(
                column not in bars.columns or pd.to_numeric(bars[column], errors="coerce").dropna().empty
                for column in ("bid_volume", "ask_volume")
            )
            if side_fields_missing:
                warnings.append("Delta exists but bid/ask side-volume fields are incomplete.")

    if ticks is not None:
        if ticks.empty:
            warnings.append("Selected trade has no footprint window rows in tick_windows.parquet.")
        else:
            has_side_volume = any(
                column in ticks.columns and pd.to_numeric(ticks[column], errors="coerce").dropna().any()
                for column in ("bid_volume", "ask_volume", "price_level_bid_volume", "price_level_ask_volume")
            )
            has_side_labels = "aggressor_side" in ticks.columns and ticks["aggressor_side"].dropna().astype(str).str.strip().ne("").any()
            if not has_side_volume and not has_side_labels:
                warnings.append("Footprint rows do not include usable bid/ask side data; only total-volume views may be meaningful.")

    delta_pass, _ = _lookup_condition_alias(condition, ("delta_filter_pass",))
    if _truthy(delta_pass):
        delta_actual, _ = _lookup_condition_alias(
            condition,
            ("delta_pct", "delta_imbalance", "delta_value", "signed_volume", "absorption_bucket_delta"),
        )
        if _is_missing(delta_actual):
            warnings.append("Delta filter passed but no raw delta value is present in the condition snapshot.")
    volume_pass, _ = _lookup_condition_alias(condition, ("volume_filter_pass",))
    if _truthy(volume_pass):
        volume_actual, _ = _lookup_condition_alias(condition, ("total_volume", "volume", "sweep_bar_volume"))
        if _is_missing(volume_actual):
            warnings.append("Volume filter passed but no raw volume value is present in the condition snapshot.")
    final_pass, _ = _lookup_condition_alias(condition, ("final_entry_pass",))
    if _truthy(final_pass):
        failed_filters = []
        for flag in ("rth_filter_pass", "volume_filter_pass", "delta_filter_pass", "stacked_imbalance_pass"):
            value, _ = _lookup_condition_alias(condition, (flag,))
            if not _is_missing(value) and not _truthy(value):
                failed_filters.append(flag)
        if failed_filters:
            warnings.append(f"Final entry passed while filter flags failed: {', '.join(failed_filters)}.")

    bid, _ = _lookup_condition_alias(condition, ("bid_volume", "sell_volume"))
    ask, _ = _lookup_condition_alias(condition, ("ask_volume", "buy_volume"))
    delta, delta_field = _condition_signed_volume_for_reconciliation(condition)
    try:
        if not any(_is_missing(value) for value in (bid, ask, delta)) and abs((float(ask) - float(bid)) - float(delta)) > 1e-6:
            field_text = f" ({delta_field})" if delta_field else ""
            warnings.append(f"Condition bid/ask volume does not reconcile to the exported signed volume{field_text}.")
    except (TypeError, ValueError):
        pass

    for label, timestamp in _orderflow_event_timestamps(trade, condition, None).items():
        if _is_missing(timestamp):
            continue
        if not bars.empty and _bar_index_for_timestamp(bars, timestamp) is None:
            warnings.append(f"{label} timestamp is not found in the displayed bar window: {_format_value(timestamp)}.")
        if ticks is not None and not ticks.empty and not _timestamp_in_window(ticks["timestamp"], timestamp):
            warnings.append(f"{label} timestamp is not found in the loaded tick window: {_format_value(timestamp)}.")
    return warnings


def key_levels_from_artifacts(
    bars: pd.DataFrame,
    condition: pd.Series | None,
    trade: pd.Series | None = None,
) -> list[dict[str, Any]]:
    levels: list[dict[str, Any]] = []
    level_specs = [
        ("stop_price", "Stop", "#d62728"),
        ("target_price", "Target", "#2ca02c"),
        ("swept_level_price", "Swept level", "#9467bd"),
        ("prev_rth_high", "Previous RTH high", "#7f7f7f"),
        ("prev_rth_low", "Previous RTH low", "#7f7f7f"),
        ("overnight_high", "Overnight high", "#17becf"),
        ("overnight_low", "Overnight low", "#17becf"),
        ("profile_poc", "Profile POC", "#bcbd22"),
        ("profile_vah", "Profile VAH", "#8c564b"),
        ("profile_val", "Profile VAL", "#8c564b"),
    ]
    for column, label, color in level_specs:
        value = None
        if trade is not None and column in trade.index and not _is_missing(trade[column]):
            value = trade[column]
        elif condition is not None and column in condition.index and not _is_missing(condition[column]):
            value = condition[column]
        elif column in bars.columns:
            value = _last_valid(bars[column])
        if value is not None:
            levels.append({"label": label, "value": float(value), "color": color})
    levels.extend(_json_level_values(condition))
    return levels


def chart_y_range(
    bars: pd.DataFrame,
    trade: pd.Series,
    condition: pd.Series | None = None,
    *,
    include_key_levels: bool = True,
    y_zoom: float = 1.0,
) -> list[float] | None:
    values: list[float] = []
    for column in ("high", "low", "open", "close"):
        if column in bars.columns:
            values.extend(pd.to_numeric(bars[column], errors="coerce").dropna().astype(float).tolist())
    for key in ("entry_price", "exit_price", "stop_price", "target_price"):
        value = trade.get(key)
        if not _is_missing(value):
            values.append(float(value))
    if include_key_levels:
        for level in key_levels_from_artifacts(bars, condition, trade):
            values.append(float(level["value"]))
    if not values:
        return None
    low = min(values)
    high = max(values)
    if low == high:
        pad = max(abs(low) * 0.001, 1.0)
    else:
        pad = (high - low) * 0.08
    return _scale_y_range([low - pad, high + pad], y_zoom)


def make_price_figure(
    trade: pd.Series,
    bars: pd.DataFrame,
    condition: pd.Series | None = None,
    exit_audit: pd.Series | None = None,
    *,
    dragmode: str = "pan",
    show_range_slider: bool = False,
    show_volume: bool = False,
    fit_key_levels: bool = False,
    y_zoom: float = 1.0,
    height: int = 720,
):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    has_volume = show_volume and "volume" in bars.columns and bars["volume"].notna().any()
    fig = (
        make_subplots(
            rows=2,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.78, 0.22],
        )
        if has_volume
        else go.Figure()
    )
    if bars.empty:
        fig.update_layout(title="No bar window artifact for selected trade")
        return fig
    x = pd.to_datetime(bars["timestamp"], errors="coerce")
    _add_chart_trace(
        fig,
        go.Candlestick(
            x=x,
            open=bars["open"],
            high=bars["high"],
            low=bars["low"],
            close=bars["close"],
            name="Price",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
            increasing_fillcolor="#26a69a",
            decreasing_fillcolor="#ef5350",
        ),
        has_volume,
        row=1,
    )
    if "vwap" in bars.columns and bars["vwap"].notna().any():
        _add_chart_trace(
            fig,
            go.Scatter(
                x=x,
                y=bars["vwap"],
                mode="lines",
                name="VWAP",
                line={"color": "#1f77b4", "width": 1.4},
            ),
            has_volume,
            row=1,
        )
    if has_volume:
        volume_colors = [
            "#26a69a" if close >= open_ else "#ef5350"
            for open_, close in zip(bars["open"], bars["close"], strict=False)
        ]
        fig.add_trace(
            go.Bar(
                x=x,
                y=bars["volume"],
                name="Volume",
                marker={"color": volume_colors, "opacity": 0.45},
                hovertemplate="%{x}<br>Volume=%{y}<extra></extra>",
            ),
            row=2,
            col=1,
        )
    for level in key_levels_from_artifacts(bars, condition, trade):
        fig.add_hline(
            y=level["value"],
            line_dash="dot",
            line_color=level["color"],
            row=1 if has_volume else "all",
            col=1 if has_volume else "all",
        )
    _add_trade_marker(
        fig,
        trade.get("entry_time"),
        trade.get("entry_price"),
        "Entry",
        "#2a9d8f",
        "triangle-up",
        row=1 if has_volume else None,
    )
    _add_trade_marker(
        fig,
        trade.get("exit_time"),
        trade.get("exit_price"),
        "Exit",
        "#d1495b",
        "x",
        row=1 if has_volume else None,
    )
    for timestamp, label, color in _vertical_markers(trade, condition, exit_audit):
        fig.add_vline(
            x=timestamp,
            line_dash="dash",
            line_color=color,
        )
    y_range = chart_y_range(bars, trade, condition, include_key_levels=fit_key_levels, y_zoom=y_zoom)
    fig.update_layout(
        title=None,
        template="plotly_white",
        hovermode="x unified",
        dragmode=dragmode,
        height=height,
        margin={"l": 20, "r": 54, "t": 30, "b": 28},
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.01,
            "xanchor": "left",
            "x": 0,
            "font": {"size": 11},
        },
        modebar={"orientation": "v"},
        newshape={"line": {"color": "#2962ff", "width": 1.5}},
        uirevision=f"trade-{trade.get('trade_id')}",
    )
    fig.update_xaxes(
        title_text=None,
        rangeslider={"visible": show_range_slider, "thickness": 0.06},
        tickmode="auto",
        nticks=7,
        tickformat="%H:%M",
        hoverformat="%Y-%m-%d %H:%M:%S",
        showspikes=True,
        spikecolor="#546e7a",
        spikethickness=1,
        spikedash="dot",
        spikemode="across",
        spikesnap="cursor",
        showline=True,
        mirror=True,
        gridcolor="#eeeeee",
        row=1 if has_volume else None,
        col=1 if has_volume else None,
    )
    fig.update_yaxes(
        title_text=None,
        side="right",
        fixedrange=False,
        tickmode="auto",
        nticks=8,
        tickformat=".2f",
        automargin=True,
        showspikes=True,
        spikecolor="#546e7a",
        spikethickness=1,
        spikedash="dot",
        spikesnap="cursor",
        showline=True,
        mirror=True,
        gridcolor="#eeeeee",
        range=y_range,
        row=1 if has_volume else None,
        col=1 if has_volume else None,
    )
    if has_volume:
        fig.update_yaxes(
            title_text=None,
            side="right",
            fixedrange=False,
            showgrid=False,
            showticklabels=False,
            ticks="",
            row=2,
            col=1,
        )
        fig.update_xaxes(
            showspikes=True,
            spikecolor="#546e7a",
            spikethickness=1,
            spikedash="dot",
            spikemode="across",
            spikesnap="cursor",
            showline=True,
            mirror=True,
            gridcolor="#eeeeee",
            row=2,
            col=1,
        )
    return fig


def make_footprint_heatmap(footprint: pd.DataFrame, value_column: str = "total_volume", *, height: int = 560):
    import plotly.graph_objects as go

    if footprint.empty or value_column not in footprint.columns:
        fig = go.Figure()
        fig.update_layout(title="No footprint rows for selected trade", height=height, template="plotly_white")
        return fig
    pivot = footprint.pivot_table(
        index="price_level",
        columns="bar_timestamp",
        values=value_column,
        aggfunc="sum",
        fill_value=0,
    ).sort_index(ascending=False)
    color_args: dict[str, Any] = {
        "colorscale": "RdBu" if value_column == "delta" else "Viridis",
        "colorbar": {"title": value_column},
    }
    if value_column == "delta":
        color_args["zmid"] = 0
    fig = go.Figure(
        data=go.Heatmap(
            x=[_format_value(value) for value in pivot.columns],
            y=[float(value) for value in pivot.index],
            z=pivot.to_numpy(),
            hovertemplate="bar=%{x}<br>price=%{y}<br>value=%{z}<extra></extra>",
            **color_args,
        )
    )
    fig.update_layout(
        title=f"Footprint Heatmap: {value_column}",
        template="plotly_white",
        height=height,
        margin={"l": 24, "r": 24, "t": 56, "b": 36},
        xaxis={"title": None, "tickangle": -30, "nticks": 7},
        yaxis={"title": "Price", "side": "right", "tickformat": ".2f"},
        dragmode="pan",
        uirevision=f"footprint-{value_column}",
    )
    return fig


def make_exit_path_figure(
    trade: pd.Series,
    exit_audit: pd.Series | dict[str, Any] | None,
    ticks: pd.DataFrame | None = None,
    bars: pd.DataFrame | None = None,
    *,
    height: int = 620,
):
    import plotly.graph_objects as go

    audit = _series_from_optional(exit_audit)
    path = trade_path_from_ticks(trade, ticks)
    path_source = "tick path"
    if path.empty and bars is not None and not bars.empty and {"timestamp", "close"}.issubset(bars.columns):
        path = (
            bars[["timestamp", "close"]]
            .rename(columns={"close": "price"})
            .dropna(subset=["timestamp", "price"])
            .sort_values("timestamp")
            .reset_index(drop=True)
        )
        path_source = "bar close fallback"
    fig = go.Figure()
    if path.empty:
        fig.update_layout(title="No tick or bar path artifact for selected trade", height=height, template="plotly_white")
        return fig
    fig.add_trace(
        go.Scatter(
            x=pd.to_datetime(path["timestamp"], errors="coerce"),
            y=pd.to_numeric(path["price"], errors="coerce"),
            mode="lines+markers",
            name=path_source,
            line={"color": "#263238", "width": 1.8},
            marker={"size": 5},
        )
    )
    x0 = pd.to_datetime(path["timestamp"], errors="coerce").min()
    x1 = pd.to_datetime(path["timestamp"], errors="coerce").max()
    _add_exit_level_line(fig, x0, x1, trade.get("entry_price"), "Entry", "#2a9d8f")
    _add_exit_level_line(fig, x0, x1, trade.get("stop_price"), "Stop", "#d62728")
    _add_exit_level_line(fig, x0, x1, trade.get("target_price"), "Target", "#2ca02c")
    _add_exit_touch_marker(
        fig,
        audit.get("first_touch_tp_time"),
        audit.get("first_touch_tp_price") if not _is_missing(audit.get("first_touch_tp_price")) else trade.get("target_price"),
        "First TP touch",
        "#2ca02c",
        "triangle-up",
    )
    _add_exit_touch_marker(
        fig,
        audit.get("first_touch_sl_time"),
        audit.get("first_touch_sl_price") if not _is_missing(audit.get("first_touch_sl_price")) else trade.get("stop_price"),
        "First SL touch",
        "#d62728",
        "triangle-down",
    )
    _add_exit_touch_marker(
        fig,
        trade.get("exit_time"),
        trade.get("exit_price"),
        "Engine exit",
        "#6d597a",
        "x",
    )
    y_values = pd.to_numeric(path["price"], errors="coerce").dropna().tolist()
    for level in (trade.get("entry_price"), trade.get("stop_price"), trade.get("target_price"), trade.get("exit_price")):
        if not _is_missing(level):
            y_values.append(float(level))
    y_range = _range_with_padding(y_values)
    fig.update_layout(
        title=None,
        template="plotly_white",
        hovermode="x unified",
        dragmode="pan",
        height=height,
        margin={"l": 20, "r": 54, "t": 30, "b": 32},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01, "xanchor": "left", "x": 0, "font": {"size": 11}},
        uirevision=f"exit-path-{trade.get('trade_id')}",
    )
    fig.update_xaxes(title_text=None, nticks=8, tickformat="%H:%M:%S", showspikes=True, spikemode="across")
    fig.update_yaxes(title_text=None, side="right", fixedrange=False, tickformat=".2f", range=y_range)
    return fig


def exit_path_summary_frame(exit_audit: pd.Series | dict[str, Any] | None) -> pd.DataFrame:
    audit = _series_from_optional(exit_audit)
    fields = [
        "entry_time",
        "entry_price",
        "stop_price",
        "target_price",
        "exit_time",
        "exit_price",
        "exit_reason",
        "first_touch_tp_time",
        "first_touch_tp_price",
        "first_touch_sl_time",
        "first_touch_sl_price",
        "first_touch_decision",
        "first_touch_exit_decision",
        "engine_exit_matches_path",
        "same_bar_ambiguous",
        "ambiguity_resolution",
        "mfe_ticks",
        "mae_ticks",
        "max_price_before_exit",
        "min_price_before_exit",
        "tick_count_checked",
        "path_source",
        "warning_flags",
    ]
    return pd.DataFrame(
        [{"field": field, "value": _format_value(audit.get(field))} for field in fields if not _is_missing(audit.get(field))]
    )


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="Validation Dashboard", layout="wide")
    st.title("Strategy Validation Dashboard")

    with st.sidebar:
        st.header("Run Selector")
        search_root = st.text_input("Search root", value=DEFAULT_SEARCH_ROOT)
        discovered = _cached_discover_validation_runs(search_root)
        discovered_labels = [str(path) for path in discovered]
        selected_label = st.selectbox("Discovered validation runs", discovered_labels, index=0 if discovered else None)
        manual_path = st.text_input("Validation run folder", value=selected_label or "")
        page = st.radio("Page", ["Trade Inspector", "Review Queue"], horizontal=False)

    if not manual_path:
        st.info("Select a validation run folder or generate a sample run with `make sample-validation-run`.")
        return
    run_dir = Path(manual_path).expanduser()
    if not (run_dir / METADATA_FILENAME).exists():
        st.error(f"No {METADATA_FILENAME} found in {run_dir}.")
        return

    try:
        with st.spinner("Loading validation artifacts..."):
            run = _cached_load_run(str(run_dir))
    except Exception as exc:  # pragma: no cover - defensive UI guard
        st.error("Could not load this validation run. Check that the folder contains valid validation artifacts.")
        st.caption(str(exc))
        return
    try:
        reviews = load_manual_reviews(run_dir)
    except Exception as exc:  # pragma: no cover - defensive UI guard
        st.warning("Manual review annotations could not be loaded; continuing without them.")
        st.caption(str(exc))
        reviews = pd.DataFrame(columns=MANUAL_REVIEW_COLUMNS)
    trades_table = add_review_annotations(prepare_trade_table(run.trades, run.exit_audits, run.validation_checks), reviews)
    summary = run_summary(run.metadata, run.trades)
    _render_run_summary(st, summary)

    if trades_table.empty:
        st.warning("This validation run has no trade rows.")
        return

    if page == "Review Queue":
        _render_review_queue_page(st, str(run_dir), run, trades_table, reviews)
        return

    filtered = _render_trade_filters(st, trades_table)
    st.subheader("Trade Table")
    st.dataframe(filtered[TRADE_TABLE_COLUMNS], use_container_width=True, hide_index=True)
    if filtered.empty:
        st.warning("No trades match the selected filters.")
        return

    selected_trade_id = _select_trade_id(st, "Selected trade", filtered["trade_id"].tolist(), key="validation_selected_trade_id")
    trade = row_for_trade(trades_table, selected_trade_id)
    condition = row_for_trade(run.condition_snapshots, selected_trade_id)
    exit_audit = row_for_trade(run.exit_audits, selected_trade_id)
    bars = rows_for_trade(run.bar_windows, selected_trade_id)
    _render_trade_review_tabs(
        st,
        str(run_dir),
        selected_trade_id,
        trade,
        bars,
        condition,
        exit_audit,
        run.validation_checks,
        run.metadata,
        reviews,
    )


def _render_review_queue_page(st, run_dir: str, run: Any, trades_table: pd.DataFrame, reviews: pd.DataFrame) -> None:
    st.subheader("Review Queue")
    summary = manual_review_summary(trades_table, reviews)
    metric_cols = st.columns(7)
    metric_cols[0].metric("Reviewed", summary["number_reviewed"])
    metric_cols[1].metric("Correct", summary["number_correct"])
    metric_cols[2].metric("Bug suspected", summary["number_bug_suspected"])
    metric_cols[3].metric("Data issue", summary["number_data_issue"])
    metric_cols[4].metric("Exit issue", summary["number_exit_issue"])
    metric_cols[5].metric("Orderflow issue", summary["number_orderflow_issue"])
    metric_cols[6].metric("Completion", f"{summary['review_completion_pct']:.1f}%")

    controls = st.columns([2, 1, 1, 1])
    sample_mode = controls[0].selectbox("Review sample", REVIEW_SAMPLE_MODES)
    sample_size = controls[1].number_input("Sample size", min_value=1, max_value=200, value=20, step=1)
    unreviewed_only = controls[2].checkbox("Unreviewed only", value=False)
    suspicious_only = controls[3].checkbox("Suspicious only", value=False)

    queue = build_review_queue(
        trades_table,
        run.condition_snapshots,
        run.exit_audits,
        run.bar_windows,
        sample_mode=sample_mode,
        sample_size=int(sample_size),
        include_reviewed=not unreviewed_only,
        suspicious_only=suspicious_only,
        tick_size=_numeric_or_none(run.metadata.get("tick_size")),
    )
    queue_columns = [
        "trade_id",
        "review_reason",
        "reviewer_status_display",
        "reviewed_at",
        "session_date",
        "direction",
        "entry_time",
        "exit_reason",
        "r_multiple",
        "pnl_ticks",
        "was_forced_flatten",
        "same_bar_ambiguous",
        "check_error_count",
        "check_warning_count",
        "warning_flags",
        "check_flags",
    ]
    for column in queue_columns:
        if column not in queue.columns:
            queue[column] = pd.NA
    st.dataframe(queue[queue_columns], use_container_width=True, hide_index=True)
    if queue.empty:
        st.warning("No trades match this review queue.")
        return

    selected_trade_id = _select_trade_id(st, "Review trade", queue["trade_id"].tolist(), key="validation_review_trade_id")
    trade = row_for_trade(trades_table, selected_trade_id)
    condition = row_for_trade(run.condition_snapshots, selected_trade_id)
    exit_audit = row_for_trade(run.exit_audits, selected_trade_id)
    bars = rows_for_trade(run.bar_windows, selected_trade_id)

    _render_trade_review_tabs(
        st,
        run_dir,
        selected_trade_id,
        trade,
        bars,
        condition,
        exit_audit,
        run.validation_checks,
        run.metadata,
        reviews,
    )


def _render_trade_review_tabs(
    st,
    run_dir: str,
    selected_trade_id: Any,
    trade: pd.Series | None,
    bars: pd.DataFrame,
    condition: pd.Series | None,
    exit_audit: pd.Series | None,
    validation_checks: pd.DataFrame,
    metadata: dict[str, Any],
    reviews: pd.DataFrame,
) -> None:
    overview_tab, price_tab, conditions_tab, orderflow_tab, exit_path_tab, checks_tab, manual_tab = st.tabs(
        ["Overview", "Price chart", "Conditions", "Orderflow", "Exit path", "Checks", "Manual review"]
    )
    with overview_tab:
        _render_trade_detail(st, trade, condition, exit_audit, None)
    with price_tab:
        _render_price_chart(st, trade, bars, condition, exit_audit)
    with conditions_tab:
        _render_condition_and_debug(st, condition)
    with orderflow_tab:
        _render_orderflow_tab(st, run_dir, selected_trade_id, trade, bars, condition, exit_audit)
    with exit_path_tab:
        _render_exit_path_tab(st, run_dir, selected_trade_id, trade, bars, exit_audit, metadata)
    with checks_tab:
        _render_checks_tab(st, validation_checks, selected_trade_id)
    with manual_tab:
        _render_manual_review_form(st, run_dir, selected_trade_id, reviews)


def _render_manual_review_form(st, run_dir: str, trade_id: Any, reviews: pd.DataFrame) -> None:
    existing = row_for_trade(reviews, trade_id)
    existing_status = None if existing is None else existing.get("reviewer_status")
    existing_notes = "" if existing is None or _is_missing(existing.get("reviewer_notes")) else str(existing.get("reviewer_notes"))
    status_index = REVIEW_STATUSES.index(existing_status) if existing_status in REVIEW_STATUSES else 0
    with st.form(f"manual_review_{trade_id}", clear_on_submit=False):
        cols = st.columns([1, 3])
        reviewer_status = cols[0].selectbox("Reviewer status", REVIEW_STATUSES, index=status_index)
        reviewer_notes = cols[1].text_area("Reviewer notes", value=existing_notes, height=90)
        submitted = st.form_submit_button("Save review annotation")
    if submitted:
        save_manual_review_annotation(run_dir, trade_id, reviewer_status, reviewer_notes)
        st.success(f"Saved review annotation for trade {trade_id}.")
        rerun = getattr(st, "rerun", None) or getattr(st, "experimental_rerun", None)
        if rerun is not None:
            rerun()


def _render_checks_tab(st, checks: pd.DataFrame, selected_trade_id: Any) -> None:
    st.subheader("Validation Checks")
    summary = validation_check_summary(checks)
    cols = st.columns(5)
    cols[0].metric("Total checks", summary["total_checks"])
    cols[1].metric("Passed", summary["passed_checks"])
    cols[2].metric("Warnings", summary["warnings"])
    cols[3].metric("Errors", summary["errors"])
    cols[4].metric("Affected trades", summary["affected_trade_count"])
    if summary["affected_trade_ids"]:
        st.caption(f"affected_trade_ids={summary['affected_trade_ids']}")
    if checks.empty:
        st.info("No validation_checks.parquet artifact was found for this run.")
        return

    selected_checks = checks[
        checks["trade_id"].astype(str).eq(str(selected_trade_id)) | checks["trade_id"].isna()
    ].copy()
    severity_filter = st.multiselect("Status", ["ERROR", "WARNING", "PASS"], default=["ERROR", "WARNING", "PASS"])
    if severity_filter:
        selected_checks = selected_checks[selected_checks["status"].fillna("").astype(str).str.upper().isin(severity_filter)]
    for column in CHECK_TABLE_COLUMNS:
        if column not in selected_checks.columns:
            selected_checks[column] = pd.NA
    st.markdown("**Selected Trade Checks**")
    st.dataframe(selected_checks[CHECK_TABLE_COLUMNS], use_container_width=True, hide_index=True)

    with st.expander("Full Run Checks", expanded=False):
        full = checks.copy()
        for column in CHECK_TABLE_COLUMNS:
            if column not in full.columns:
                full[column] = pd.NA
        st.dataframe(full[CHECK_TABLE_COLUMNS], use_container_width=True, hide_index=True)


def _render_run_summary(st, summary: dict[str, Any]) -> None:
    st.subheader("Run Metadata")
    cols = st.columns(5)
    cols[0].metric("Run", summary.get("run_id") or "N/A")
    cols[1].metric("Strategy", summary.get("strategy_id") or "N/A")
    cols[2].metric("Symbol", summary.get("symbol") or "N/A")
    cols[3].metric("Trades", summary.get("trade_count") or 0)
    cols[4].metric("Range", summary.get("date_range") or "N/A")
    st.caption(
        " | ".join(
            str(value)
            for value in [
                f"campaign={summary.get('campaign_id') or 'N/A'}",
                f"variant={summary.get('variant_id') or 'N/A'}",
                f"timeframe={summary.get('timeframe') or 'N/A'}",
                f"generated={summary.get('generated_at') or 'N/A'}",
                f"source_run={summary.get('source_run_dir') or 'N/A'}",
                f"source_trade_log={summary.get('source_trade_log') or 'N/A'}",
            ]
        )
    )


def _render_trade_filters(st, table: pd.DataFrame) -> pd.DataFrame:
    st.subheader("Filters")
    min_date, max_date = _session_date_bounds(table)
    cols = st.columns(6)
    date_range = cols[0].date_input("Session date", value=(min_date, max_date)) if min_date and max_date else None
    directions = cols[1].multiselect("Direction", sorted(_string_options(table, "direction")))
    exit_reasons = cols[2].multiselect("Exit reason", sorted(_string_options(table, "exit_reason")))
    outcome = cols[3].selectbox("Outcome", ["All", "Winning", "Losing"])
    forced_only = cols[4].checkbox("Forced flatten only")
    ambiguous_only = cols[5].checkbox("Ambiguous TP/SL only")
    suspicious_only = st.checkbox("Failed or suspicious debug flags only")
    if isinstance(date_range, tuple) and len(date_range) == 1:
        date_range = (date_range[0], date_range[0])
    return filter_trade_table(
        table,
        date_range=date_range if isinstance(date_range, tuple) and len(date_range) == 2 else None,
        directions=directions,
        exit_reasons=exit_reasons,
        outcome=outcome,
        forced_flatten_only=forced_only,
        ambiguous_only=ambiguous_only,
        suspicious_only=suspicious_only,
    )


def _render_trade_detail(st, trade: pd.Series | None, condition: pd.Series | None, exit_audit: pd.Series | None, tick_count: int | None) -> None:
    st.subheader("Overview")
    if trade is None:
        st.warning("Selected trade is missing from trades artifact.")
        return
    cols = st.columns(6)
    cols[0].metric("Direction", trade.get("direction") or "N/A")
    cols[1].metric("Entry", _format_value(trade.get("entry_price")))
    cols[2].metric("Stop", _format_value(trade.get("stop_price")))
    cols[3].metric("Target", _format_value(trade.get("target_price")))
    cols[4].metric("Exit", _format_value(trade.get("exit_price")))
    cols[5].metric("R", _format_value(trade.get("r_multiple")))
    st.caption(
        f"entry_time={_format_value(trade.get('entry_time'))} | "
        f"exit_time={_format_value(trade.get('exit_time'))} | "
        f"exit_reason={_format_value(trade.get('exit_reason'))} | "
        f"tick_rows_loaded={tick_count if tick_count is not None else 'not loaded'}"
    )
    with st.expander("Entry / SL / TP Calculation Details", expanded=True):
        details = {
            "entry_trigger_values": parse_json_cell(condition.get("entry_trigger_values")) if condition is not None else {},
            "stop_anchor_calculation": parse_json_cell(condition.get("stop_anchor_calculation")) if condition is not None else {},
            "target_calculation": parse_json_cell(condition.get("target_calculation")) if condition is not None else {},
        }
        st.json(details)
    with st.expander("Exit Audit Details", expanded=True):
        st.json({} if exit_audit is None else {key: _format_value(value) for key, value in exit_audit.to_dict().items() if not _is_missing(value)})


def _render_price_chart(st, trade: pd.Series | None, bars: pd.DataFrame, condition: pd.Series | None, exit_audit: pd.Series | None) -> None:
    st.subheader("Price Chart")
    if trade is None:
        return
    controls = st.columns([1, 1, 1, 1, 1, 1.5])
    drag_label = controls[0].radio("Drag", ["Pan", "Zoom"], horizontal=True, index=0)
    wheel_zoom = controls[1].checkbox("Wheel zoom", value=False)
    show_range_slider = controls[2].checkbox("Range slider", value=False)
    show_volume = controls[3].checkbox("Volume pane", value=False)
    fit_key_levels = controls[4].checkbox("Fit levels", value=False)
    y_zoom = controls[5].slider("Y zoom", min_value=0.5, max_value=5.0, value=1.6, step=0.1)
    chart_height = st.slider("Chart height", min_value=520, max_value=1200, value=760, step=40)
    try:
        fig = make_price_figure(
            trade,
            bars,
            condition,
            exit_audit,
            dragmode=drag_label.lower(),
            show_range_slider=show_range_slider,
            show_volume=show_volume,
            fit_key_levels=fit_key_levels,
            y_zoom=y_zoom,
            height=chart_height,
        )
    except ImportError:
        st.error('Plotly is not installed. Install dashboard dependencies with `python3 -m pip install -e ".[dashboard]"`.')
        return
    st.plotly_chart(fig, use_container_width=True, config=price_chart_config(scroll_zoom=wheel_zoom))


def _render_exit_path_tab(
    st,
    run_dir: str,
    selected_trade_id: Any,
    trade: pd.Series | None,
    bars: pd.DataFrame,
    exit_audit: pd.Series | None,
    metadata: dict[str, Any],
) -> None:
    st.subheader("TP/SL Sequence Audit")
    if trade is None:
        st.warning("Selected trade is missing from trades artifact.")
        return
    load_ticks = st.checkbox(
        "Load selected trade tick path",
        value=True,
        key=f"load_exit_path_{selected_trade_id}",
    )
    ticks = _load_tick_window_or_empty(st, run_dir, selected_trade_id) if load_ticks else pd.DataFrame()
    computed = audit_trade_exit_path(
        trade,
        ticks,
        tick_size=_numeric_or_none(metadata.get("tick_size")),
        existing_audit=exit_audit,
    )
    audit = _merge_audit_records(exit_audit, computed)
    warnings = _split_warning_flags(audit.get("warning_flags"))
    if _truthy(audit.get("same_bar_ambiguous")):
        st.warning("Same-bar TP/SL ambiguity was flagged by the engine.")
    for warning in warnings:
        st.warning(warning)
    cols = st.columns(5)
    cols[0].metric("Engine Exit", _format_value(audit.get("exit_reason") or trade.get("exit_reason")))
    cols[1].metric("Path First Touch", _format_value(audit.get("first_touch_decision")))
    cols[2].metric("Path Match", _format_value(audit.get("engine_exit_matches_path")))
    cols[3].metric("MFE ticks", _format_value(_first_non_missing(audit.get("mfe_ticks"), audit.get("max_favorable_excursion_ticks"))))
    cols[4].metric("MAE ticks", _format_value(_first_non_missing(audit.get("mae_ticks"), audit.get("max_adverse_excursion_ticks"))))
    try:
        fig = make_exit_path_figure(trade, audit, ticks, bars)
    except ImportError:
        st.error('Plotly is not installed. Install dashboard dependencies with `python3 -m pip install -e ".[dashboard]"`.')
        return
    st.plotly_chart(fig, use_container_width=True, config=price_chart_config(scroll_zoom=False))
    st.dataframe(exit_path_summary_frame(audit), use_container_width=True, hide_index=True)
    if not load_ticks:
        st.info("Enable the selected trade tick path to recompute TP/SL order from exported tick rows.")
        return
    with st.expander("Tick Path Rows", expanded=False):
        st.dataframe(trade_path_from_ticks(trade, ticks), use_container_width=True, hide_index=True)


def _render_orderflow_tab(
    st,
    run_dir: str,
    selected_trade_id: Any,
    trade: pd.Series | None,
    bars: pd.DataFrame,
    condition: pd.Series | None,
    exit_audit: pd.Series | None,
) -> None:
    st.subheader("Orderflow / Footprint")
    load_footprint = st.checkbox(
        "Load selected trade footprint window",
        value=False,
        key=f"load_footprint_{selected_trade_id}",
    )
    ticks = _load_tick_window_or_empty(st, run_dir, selected_trade_id) if load_footprint else None
    for warning in orderflow_warnings(trade, condition, bars, ticks):
        st.warning(warning)

    st.markdown("**Bar-Level Orderflow**")
    bar_table = prepare_orderflow_bar_table(bars, trade, condition, exit_audit, ticks)
    st.dataframe(bar_table, use_container_width=True, hide_index=True)

    st.markdown("**Filter Explanation**")
    st.dataframe(orderflow_filter_explanations(condition), use_container_width=True, hide_index=True)
    if condition is not None:
        with st.expander("Raw Orderflow Values", expanded=False):
            st.json(parse_json_cell(condition.get("raw_orderflow_values")))

    if not load_footprint:
        st.info("Enable the footprint window to load selected-trade tick rows and render price-level heatmaps.")
        return
    if ticks is None:
        return
    footprint = aggregate_footprint_by_price(ticks, bars)
    if footprint.empty:
        st.warning("No footprint rows are available for this selected trade window.")
        with st.expander("Raw Tick / Footprint Rows", expanded=False):
            st.dataframe(ticks, use_container_width=True, hide_index=True)
        return

    st.markdown("**Footprint / Cluster Heatmap**")
    controls = st.columns([1, 1, 2])
    metric = controls[0].selectbox("Heatmap", ["total_volume", "bid_volume", "ask_volume", "delta"])
    heatmap_height = controls[1].slider("Footprint height", min_value=420, max_value=900, value=560, step=40)
    try:
        fig = make_footprint_heatmap(footprint, metric, height=heatmap_height)
    except ImportError:
        st.error('Plotly is not installed. Install dashboard dependencies with `python3 -m pip install -e ".[dashboard]"`.')
        return
    st.plotly_chart(fig, use_container_width=True, config=price_chart_config(scroll_zoom=False))

    st.markdown("**Selected-Bar Detail**")
    bar_options = bar_table["timestamp"].dropna().tolist()
    selected_bar = controls[2].selectbox(
        "Selected bar",
        bar_options,
        format_func=lambda value: _format_value(value),
        index=0 if bar_options else None,
    )
    detail = selected_bar_footprint_detail(footprint, selected_bar)
    st.dataframe(detail, use_container_width=True, hide_index=True)
    with st.expander("Raw Tick / Footprint Rows", expanded=False):
        st.dataframe(ticks, use_container_width=True, hide_index=True)


def _render_condition_and_debug(st, condition: pd.Series | None) -> None:
    left, right = st.columns([1, 2])
    with left:
        st.subheader("Condition Checklist")
        checklist = checklist_rows(condition)
        st.dataframe(checklist[["condition", "status"]], use_container_width=True, hide_index=True)
    with right:
        st.subheader("Raw Debug Table")
        st.dataframe(raw_debug_frame(condition), use_container_width=True, hide_index=True)
    if condition is not None:
        with st.expander("Raw JSON Fields", expanded=False):
            st.json(
                {
                    "filter_pass_values": parse_json_cell(condition.get("filter_pass_values")),
                    "raw_orderflow_values": parse_json_cell(condition.get("raw_orderflow_values")),
                    "signal_metadata": parse_json_cell(condition.get("signal_metadata")),
                    "signal_report_fields": parse_json_cell(condition.get("signal_report_fields")),
                    "decision_context": parse_json_cell(condition.get("decision_context")),
                }
            )


def _cached_load_run(run_dir: str):
    import streamlit as st

    @st.cache_data(show_spinner="Loading validation artifacts")
    def _load(path: str):
        return load_run_without_ticks(path)

    return _load(run_dir)


def _cached_discover_validation_runs(search_root: str) -> list[Path]:
    import streamlit as st

    @st.cache_data(ttl=30, show_spinner="Scanning validation runs")
    def _discover(path: str) -> list[str]:
        return [str(run_path) for run_path in discover_validation_runs(path)]

    return [Path(path) for path in _discover(search_root)]


def _cached_load_tick_window(run_dir: str, trade_id: Any):
    import streamlit as st

    @st.cache_data(show_spinner="Loading selected tick window")
    def _load(path: str, selected_trade_id: str):
        return load_tick_window_for_trade(path, selected_trade_id)

    return _load(run_dir, trade_id)


def _load_tick_window_or_empty(st, run_dir: str, trade_id: Any) -> pd.DataFrame:
    try:
        with st.spinner("Loading selected trade tick window..."):
            return _cached_load_tick_window(run_dir, trade_id)
    except Exception as exc:  # pragma: no cover - defensive UI guard
        st.warning("Could not load the selected trade tick/footprint window. The dashboard will use bar-level artifacts only.")
        st.caption(str(exc))
        return pd.DataFrame()


def _select_trade_id(st, label: str, trade_ids: list[Any], *, key: str) -> Any:
    if not trade_ids:
        return None
    previous = st.session_state.get(key)
    index = _index_for_trade_id(trade_ids, previous)
    if index is None:
        index = 0
        st.session_state[key] = trade_ids[0]
    return st.selectbox(label, trade_ids, index=index, format_func=lambda value: f"Trade {value}", key=key)


def _index_for_trade_id(trade_ids: list[Any], value: Any) -> int | None:
    if value is None:
        return None
    for idx, trade_id in enumerate(trade_ids):
        if trade_id == value or str(trade_id) == str(value):
            return idx
    return None


def _sort_by_entry_time(frame: pd.DataFrame) -> pd.DataFrame:
    if "entry_time" not in frame.columns:
        return frame.sort_values("trade_id") if "trade_id" in frame.columns else frame
    sorted_frame = frame.copy()
    sorted_frame["_entry_sort"] = pd.to_datetime(sorted_frame["entry_time"], errors="coerce", utc=True)
    sort_cols = ["_entry_sort"]
    if "trade_id" in sorted_frame.columns:
        sort_cols.append("trade_id")
    return sorted_frame.sort_values(sort_cols, na_position="last").drop(columns=["_entry_sort"])


def _sort_review_queue(frame: pd.DataFrame) -> pd.DataFrame:
    if "review_reason" in frame.columns and frame["review_reason"].notna().any():
        sorted_frame = frame.copy()
        sorted_frame["_entry_sort"] = pd.to_datetime(sorted_frame.get("entry_time"), errors="coerce", utc=True)
        return sorted_frame.sort_values(["review_reason", "_entry_sort"], na_position="last").drop(columns=["_entry_sort"])
    return _sort_by_entry_time(frame)


def _review_r_score(frame: pd.DataFrame) -> pd.Series:
    return pd.to_numeric(_numeric_first(frame, ["r_multiple", "pnl_ticks", "pnl_usd"]), errors="coerce")


def _boolean_mask(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(False, index=frame.index)
    return frame[column].fillna(False).astype(bool)


def _forced_flatten_mask(frame: pd.DataFrame) -> pd.Series:
    mask = _boolean_mask(frame, "was_forced_flatten")
    if "forced_flatten_reason" in frame.columns:
        mask = mask | frame["forced_flatten_reason"].fillna("").astype(str).str.strip().ne("")
    return mask


def _mismatch_warning_mask(frame: pd.DataFrame) -> pd.Series:
    mask = pd.Series(False, index=frame.index)
    if "engine_exit_matches_path" in frame.columns:
        values = frame["engine_exit_matches_path"]
        mask = mask | values.map(lambda value: False if _is_missing(value) else not _truthy(value))
    if "warning_flags" in frame.columns:
        mask = mask | frame["warning_flags"].fillna("").astype(str).str.strip().ne("")
    return mask


def _review_suspicious_mask_row(row: pd.Series) -> bool:
    if has_suspicious_debug_flags(row):
        return True
    if not _is_missing(row.get("engine_exit_matches_path")) and not bool(row.get("engine_exit_matches_path")):
        return True
    if not _is_missing(row.get("warning_flags")) and str(row.get("warning_flags")).strip():
        return True
    return False


def _edge_case_reasons_by_trade(
    trades: pd.DataFrame,
    conditions: pd.DataFrame,
    exit_audits: pd.DataFrame,
    bar_windows: pd.DataFrame,
    *,
    tick_size: float | None = None,
) -> dict[str, list[str]]:
    reasons: dict[str, list[str]] = {}
    delta_values: dict[str, float] = {}
    for _, trade in trades.iterrows():
        trade_id = trade.get("trade_id")
        key = str(trade_id)
        condition = row_for_trade(conditions, trade_id)
        exit_audit = row_for_trade(exit_audits, trade_id)
        bars = rows_for_trade(bar_windows, trade_id)
        trade_reasons = _single_trade_edge_case_reasons(trade, condition, exit_audit, bars, tick_size=tick_size)
        delta_value = _condition_numeric(condition, ("delta_pct", "delta_imbalance", "delta_value", "signed_volume", "absorption_bucket_delta"))
        if delta_value is not None:
            delta_values[key] = delta_value
        reasons[key] = trade_reasons

    if delta_values:
        threshold = pd.Series([abs(value) for value in delta_values.values()]).quantile(0.9)
        for key, value in delta_values.items():
            if abs(value) >= threshold and threshold > 0:
                reasons.setdefault(key, []).append("large positive delta" if value > 0 else "large negative delta")
    return {key: _dedupe_reasons(value) for key, value in reasons.items() if value}


def _single_trade_edge_case_reasons(
    trade: pd.Series,
    condition: pd.Series | None,
    exit_audit: pd.Series | None,
    bars: pd.DataFrame,
    *,
    tick_size: float | None,
) -> list[str]:
    reasons: list[str] = []
    if condition is not None:
        if _timestamps_same_displayed_bar(condition.get("sweep_time"), condition.get("reclaim_time"), bars):
            reasons.append("sweep and reclaim on same bar")
        if _reclaim_on_last_allowed_bar(condition, bars):
            reasons.append("reclaim on last allowed bar")
        if _entry_near_session_cutoff(trade.get("entry_time"), condition):
            reasons.append("entry near session cutoff")
        volume_reason = _threshold_edge_reason(
            condition,
            actual_aliases=("total_volume", "volume", "sweep_bar_volume"),
            threshold_aliases=("min_volume", "volume_threshold", "avg_volume_reference", "rolling_volume", "min_volume_ratio"),
            label="volume",
        )
        if volume_reason:
            reasons.append(volume_reason)
        delta_reason = _threshold_edge_reason(
            condition,
            actual_aliases=("delta_pct", "delta_imbalance", "delta_value", "signed_volume", "absorption_bucket_delta"),
            threshold_aliases=(
                "min_delta_pct",
                "max_delta_pct",
                "min_delta_imbalance",
                "max_delta_imbalance",
                "delta_threshold",
                "absorption_delta_threshold",
            ),
            label="delta",
        )
        if delta_reason:
            reasons.append(delta_reason)
    if tick_size is not None and tick_size > 0:
        entry = _numeric_or_none(trade.get("entry_price"))
        stop = _numeric_or_none(trade.get("stop_price"))
        if entry is not None and stop is not None and abs(entry - stop) <= (2 * tick_size + 1e-9):
            reasons.append("stop very close to entry")
    if exit_audit is not None:
        if _truthy(exit_audit.get("same_bar_ambiguous")) or (
            _truthy(exit_audit.get("tp_hit_on_exit_bar")) and _truthy(exit_audit.get("sl_hit_on_exit_bar"))
        ):
            reasons.append("target and stop both touched in same bar")
    return reasons


def _dedupe_reasons(reasons: list[str]) -> list[str]:
    deduped: list[str] = []
    for reason in reasons:
        if reason and reason not in deduped:
            deduped.append(reason)
    return deduped


def _timestamps_same_displayed_bar(first: Any, second: Any, bars: pd.DataFrame) -> bool:
    if _is_missing(first) or _is_missing(second):
        return False
    first_idx = _bar_index_for_timestamp(bars, first) if not bars.empty else None
    second_idx = _bar_index_for_timestamp(bars, second) if not bars.empty else None
    if first_idx is not None and second_idx is not None:
        return first_idx == second_idx
    first_ts = _to_utc_timestamp(first)
    second_ts = _to_utc_timestamp(second)
    return bool(first_ts is not None and second_ts is not None and first_ts.floor("min") == second_ts.floor("min"))


def _reclaim_on_last_allowed_bar(condition: pd.Series, bars: pd.DataFrame) -> bool:
    allowed = _numeric_or_none(condition.get("reclaim_window_bars"))
    if allowed is None or allowed <= 0:
        return False
    sweep_idx = _bar_index_for_timestamp(bars, condition.get("sweep_time")) if not bars.empty else None
    reclaim_idx = _bar_index_for_timestamp(bars, condition.get("reclaim_time")) if not bars.empty else None
    if sweep_idx is None or reclaim_idx is None:
        return False
    return int(reclaim_idx - sweep_idx) >= int(allowed)


def _entry_near_session_cutoff(entry_time: Any, condition: pd.Series) -> bool:
    entry = _to_utc_timestamp(entry_time)
    if entry is None:
        return False
    flatten_text, _ = _lookup_condition_alias(condition, ("signal_flatten_time", "flatten_time", "forced_flatten_time"))
    flatten_text = "15:55:00" if _is_missing(flatten_text) else str(flatten_text)
    try:
        hour, minute, second = [int(part) for part in flatten_text.split(":")[:3]]
    except (TypeError, ValueError):
        return False
    entry_et = entry.tz_convert("America/New_York")
    flatten = entry_et.replace(hour=hour, minute=minute, second=second, microsecond=0)
    minutes_to_cutoff = (flatten - entry_et) / pd.Timedelta(minutes=1)
    return 0 <= minutes_to_cutoff <= 30


def _threshold_edge_reason(
    condition: pd.Series,
    *,
    actual_aliases: tuple[str, ...],
    threshold_aliases: tuple[str, ...],
    label: str,
) -> str | None:
    actual = _condition_numeric(condition, actual_aliases)
    threshold = _condition_numeric(condition, threshold_aliases)
    if actual is None or threshold is None or threshold == 0:
        return None
    margin = abs(actual) - abs(threshold)
    tolerance = max(abs(threshold) * 0.1, 1e-9)
    if 0 <= margin <= tolerance:
        return f"{label} just above threshold"
    if -tolerance <= margin < 0:
        return f"{label} borderline below threshold"
    return None


def _condition_numeric(condition: pd.Series | None, aliases: tuple[str, ...]) -> float | None:
    value, _ = _lookup_condition_alias(condition, aliases)
    return _numeric_or_none(value)


def _lookup_condition_value(snapshot: pd.Series, aliases: tuple[str, ...], json_sources: list[dict[str, Any]]) -> Any:
    for alias in aliases:
        if alias in snapshot.index and not _is_missing(snapshot[alias]):
            return snapshot[alias]
    for source in json_sources:
        for key, value in source.items():
            key_tail = str(key).split(".")[-1]
            if key_tail in aliases and not _is_missing(value):
                return value
    return None


def status_text(value: Any) -> str:
    if _is_missing(value):
        return "N/A"
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "pass", "passed"}:
            return "PASS"
        if lowered in {"false", "0", "no", "fail", "failed"}:
            return "FAIL"
    return "PASS" if bool(value) else "FAIL"


def _add_chart_trace(fig, trace, has_volume: bool, *, row: int = 1) -> None:
    if has_volume:
        fig.add_trace(trace, row=row, col=1)
    else:
        fig.add_trace(trace)


def _add_trade_marker(fig, timestamp, price, label: str, color: str, symbol: str, *, row: int | None = None) -> None:
    if _is_missing(timestamp) or _is_missing(price):
        return
    trace = {
        "type": "scatter",
        "x": [pd.Timestamp(timestamp)],
        "y": [float(price)],
        "mode": "markers+text",
        "text": [label],
        "textposition": "top center",
        "marker": {"color": color, "size": 12, "symbol": symbol},
        "name": label,
    }
    if row is not None:
        fig.add_trace(trace, row=row, col=1)
    else:
        fig.add_trace(trace)


def _add_exit_level_line(fig, x0, x1, price, label: str, color: str) -> None:
    if _is_missing(x0) or _is_missing(x1) or _is_missing(price):
        return
    fig.add_trace(
        {
            "type": "scatter",
            "x": [x0, x1],
            "y": [float(price), float(price)],
            "mode": "lines",
            "line": {"color": color, "width": 1.4, "dash": "dot"},
            "name": label,
            "hovertemplate": f"{label}=%{{y:.2f}}<extra></extra>",
        }
    )


def _add_exit_touch_marker(fig, timestamp, price, label: str, color: str, symbol: str) -> None:
    if _is_missing(timestamp) or _is_missing(price):
        return
    fig.add_trace(
        {
            "type": "scatter",
            "x": [pd.Timestamp(timestamp)],
            "y": [float(price)],
            "mode": "markers",
            "marker": {"color": color, "size": 12, "symbol": symbol},
            "name": label,
        }
    )


def _vertical_markers(trade: pd.Series, condition: pd.Series | None, exit_audit: pd.Series | None) -> list[tuple[pd.Timestamp, str, str]]:
    markers = []
    marker_specs = [
        (condition, "sweep_time", "Sweep", "#9467bd"),
        (condition, "reclaim_time", "Reclaim", "#8c564b"),
        (trade, "entry_time", "Entry", "#2a9d8f"),
        (trade, "exit_time", "Exit", "#d1495b"),
        (exit_audit, "first_touch_tp_time", "TP touch", "#2ca02c"),
        (exit_audit, "first_touch_sl_time", "SL touch", "#d62728"),
    ]
    for source, key, label, color in marker_specs:
        if source is not None and key in source.index and not _is_missing(source[key]):
            markers.append((pd.Timestamp(source[key]), label, color))
    return markers


def _json_level_values(condition: pd.Series | None) -> list[dict[str, Any]]:
    if condition is None:
        return []
    parsed_sources = [
        parse_json_cell(condition.get("entry_trigger_values")),
        parse_json_cell(condition.get("signal_metadata")),
        parse_json_cell(condition.get("signal_report_fields")),
    ]
    specs = [
        ("opening_range_high", "Opening range high", "#ff7f0e"),
        ("opening_range_low", "Opening range low", "#ff7f0e"),
        ("breakout_level", "Breakout level", "#e377c2"),
        ("swept_level", "Swept level", "#9467bd"),
        ("signal_stop_price", "Signal stop", "#d62728"),
        ("signal_target_price", "Signal target", "#2ca02c"),
    ]
    out = []
    for key, label, color in specs:
        for source in parsed_sources:
            value = source.get(key)
            if value is not None:
                try:
                    out.append({"label": label, "value": float(value), "color": color})
                    break
                except (TypeError, ValueError):
                    continue
    return out


def _scale_y_range(y_range: list[float] | None, y_zoom: float) -> list[float] | None:
    if y_range is None:
        return None
    try:
        zoom = max(float(y_zoom), 0.05)
    except (TypeError, ValueError):
        zoom = 1.0
    low, high = float(y_range[0]), float(y_range[1])
    if low >= high:
        return y_range
    midpoint = (low + high) / 2.0
    half_span = (high - low) / 2.0 / zoom
    return [midpoint - half_span, midpoint + half_span]


def _range_with_padding(values: list[float]) -> list[float] | None:
    cleaned = [float(value) for value in values if not _is_missing(value)]
    if not cleaned:
        return None
    low = min(cleaned)
    high = max(cleaned)
    if low == high:
        pad = max(abs(low) * 0.001, 1.0)
    else:
        pad = (high - low) * 0.08
    return [low - pad, high + pad]


def _delta_pct_series(table: pd.DataFrame) -> pd.Series:
    if "delta_pct" in table.columns:
        existing = pd.to_numeric(table["delta_pct"], errors="coerce")
        if existing.notna().any():
            return existing
    delta = pd.to_numeric(table.get("delta"), errors="coerce")
    volume = pd.to_numeric(table.get("volume"), errors="coerce").replace(0, pd.NA)
    return (delta / volume) * 100.0


def _numeric_optional_column(table: pd.DataFrame, column: str) -> pd.Series:
    if column not in table.columns:
        return pd.Series([pd.NA] * len(table), index=table.index)
    return pd.to_numeric(table[column], errors="coerce")


def _numeric_first_available(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    output = pd.Series([pd.NA] * len(frame), index=frame.index, dtype="Float64")
    for column in columns:
        if column in frame.columns:
            output = output.fillna(pd.to_numeric(frame[column], errors="coerce"))
    return output


def _tick_side_volume(frame: pd.DataFrame, side: str) -> pd.Series:
    if side == "bid":
        output = _numeric_first_available(frame, ["price_level_bid_volume", "bid_volume"])
        side_names = {"bid", "sell", "seller", "at_bid"}
    else:
        output = _numeric_first_available(frame, ["price_level_ask_volume", "ask_volume"])
        side_names = {"ask", "buy", "buyer", "at_ask"}
    if "aggressor_side" in frame.columns and "volume" in frame.columns:
        raw_volume = pd.to_numeric(frame["volume"], errors="coerce")
        labels = frame["aggressor_side"].astype(str).str.strip().str.lower()
        output = output.fillna(raw_volume.where(labels.isin(side_names)))
    return output


def _assign_timestamps_to_bars(timestamps: pd.Series, bar_timestamps: pd.Series) -> pd.Series:
    if timestamps.empty or bar_timestamps.empty:
        return pd.Series([pd.NaT] * len(timestamps), index=timestamps.index)
    bar_frame = pd.DataFrame(
        {
            "display_timestamp": pd.to_datetime(bar_timestamps, errors="coerce"),
            "utc_timestamp": pd.to_datetime(bar_timestamps, errors="coerce", utc=True),
        }
    ).dropna(subset=["utc_timestamp"]).sort_values("utc_timestamp")
    if bar_frame.empty:
        return pd.Series([pd.NaT] * len(timestamps), index=timestamps.index)
    bar_utc = pd.DatetimeIndex(bar_frame["utc_timestamp"])
    bar_display = bar_frame["display_timestamp"].tolist()
    deltas = bar_utc.to_series().diff().dropna()
    fallback_delta = deltas.median() if not deltas.empty else pd.Timedelta(minutes=1)
    assigned = []
    for timestamp in pd.to_datetime(timestamps, errors="coerce", utc=True):
        if pd.isna(timestamp):
            assigned.append(pd.NaT)
            continue
        position = int(bar_utc.searchsorted(timestamp, side="right")) - 1
        if position < 0:
            assigned.append(pd.NaT)
            continue
        next_timestamp = bar_utc[position + 1] if position + 1 < len(bar_utc) else bar_utc[position] + fallback_delta
        assigned.append(bar_display[position] if timestamp < next_timestamp else pd.NaT)
    return pd.Series(assigned, index=timestamps.index)


def _bar_event_marker_series(
    bars: pd.DataFrame,
    trade: pd.Series | None,
    condition: pd.Series | None,
    exit_audit: pd.Series | None,
) -> pd.Series:
    markers: list[list[str]] = [[] for _ in range(len(bars))]
    for label, timestamp in _orderflow_event_timestamps(trade, condition, exit_audit).items():
        index = _bar_index_for_timestamp(bars, timestamp)
        if index is not None and 0 <= index < len(markers):
            markers[index].append(label)
    return pd.Series(["; ".join(values) if values else "" for values in markers], index=bars.index)


def _orderflow_event_timestamps(
    trade: pd.Series | None,
    condition: pd.Series | None,
    exit_audit: pd.Series | None,
) -> dict[str, Any]:
    return {
        "sweep": _series_get(condition, "sweep_time"),
        "reclaim": _series_get(condition, "reclaim_time"),
        "signal": _series_get(condition, "signal_time"),
        "decision": _series_get(condition, "decision_bar_time"),
        "entry_execution": _series_get(condition, "entry_execution_time"),
        "entry": _series_get(trade, "entry_time"),
        "exit": _series_get(trade, "exit_time"),
        "exit_bar": _series_get(exit_audit, "exit_bar_timestamp"),
    }


def _bar_index_for_timestamp(bars: pd.DataFrame, timestamp: Any) -> int | None:
    if bars.empty or "timestamp" not in bars.columns or _is_missing(timestamp):
        return None
    assigned = _assign_timestamps_to_bars(pd.Series([timestamp]), bars["timestamp"])
    if assigned.empty or _is_missing(assigned.iloc[0]):
        return None
    assigned_key = _timestamp_key(assigned.iloc[0])
    keys = _timestamp_key_series(bars["timestamp"])
    matches = keys[keys == assigned_key]
    return None if matches.empty else int(matches.index[0])


def _timestamp_in_window(timestamps: pd.Series, timestamp: Any) -> bool:
    if timestamps.empty or _is_missing(timestamp):
        return False
    parsed = pd.to_datetime(timestamps, errors="coerce", utc=True).dropna()
    target = _to_utc_timestamp(timestamp)
    if parsed.empty or target is None:
        return False
    return bool(parsed.min() <= target <= parsed.max())


def _timestamp_key(value: Any) -> str | None:
    timestamp = _to_utc_timestamp(value)
    return None if timestamp is None else timestamp.isoformat()


def _timestamp_key_series(values: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(values, errors="coerce", utc=True)
    return parsed.map(lambda value: None if pd.isna(value) else value.isoformat())


def _to_utc_timestamp(value: Any) -> pd.Timestamp | None:
    if _is_missing(value):
        return None
    try:
        timestamp = pd.to_datetime(value, errors="coerce", utc=True)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(timestamp) else pd.Timestamp(timestamp)


def _lookup_condition_alias(condition: pd.Series | None, aliases: tuple[str, ...]) -> tuple[Any, str | None]:
    if condition is None:
        return None, None
    sources: list[dict[str, Any]] = [condition.to_dict()]
    for column in ("filter_pass_values", "raw_orderflow_values", "signal_metadata", "signal_report_fields", "decision_context", "entry_trigger_values"):
        parsed = parse_json_cell(condition.get(column))
        if parsed:
            sources.append(parsed)
    for alias in aliases:
        for source in sources:
            if alias in source and not _is_missing(source[alias]):
                return source[alias], alias
        for source in sources:
            for key, value in source.items():
                if str(key).split(".")[-1] == alias and not _is_missing(value):
                    return value, str(key)
    return None, None


def _condition_signed_volume_for_reconciliation(condition: pd.Series | None) -> tuple[Any, str | None]:
    signed_volume, signed_field = _lookup_condition_alias(condition, ("signed_volume",))
    if not _is_missing(signed_volume):
        return signed_volume, signed_field

    delta_value, delta_field = _lookup_condition_alias(condition, ("delta_value",))
    if _is_missing(delta_value) or _matches_strategy_specific_delta(condition, delta_value):
        return None, None
    return delta_value, delta_field


def _matches_strategy_specific_delta(condition: pd.Series | None, value: Any) -> bool:
    if condition is None or _is_missing(value):
        return False
    try:
        target = float(value)
    except (TypeError, ValueError):
        return False
    for column in (
        "filter_pass_values",
        "raw_orderflow_values",
        "signal_metadata",
        "signal_report_fields",
        "decision_context",
        "entry_trigger_values",
    ):
        parsed = parse_json_cell(condition.get(column))
        for key, candidate in parsed.items():
            if str(key).split(".")[-1] != "absorption_bucket_delta":
                continue
            try:
                if abs(float(candidate) - target) <= 1e-6:
                    return True
            except (TypeError, ValueError):
                continue
    return False


def _format_rule(rule: Any, actual_field: str | None, threshold_field: str | None) -> str:
    if not _is_missing(rule):
        return str(rule)
    if actual_field and threshold_field:
        return f"{actual_field} compared with {threshold_field}"
    if actual_field:
        return actual_field
    return "N/A"


def _join_source_fields(*fields: str | None) -> str:
    return ", ".join(field for field in fields if field) or "N/A"


def _display_imbalance_marker(bid_volume: Any, ask_volume: Any, *, ratio: float) -> str:
    try:
        bid = float(bid_volume) if not _is_missing(bid_volume) else 0.0
        ask = float(ask_volume) if not _is_missing(ask_volume) else 0.0
    except (TypeError, ValueError):
        return ""
    if ask > 0 and (bid <= 0 or ask >= ratio * bid):
        return f"ask>={ratio:g}x bid"
    if bid > 0 and (ask <= 0 or bid >= ratio * ask):
        return f"bid>={ratio:g}x ask"
    return ""


def _truthy(value: Any) -> bool:
    if _is_missing(value):
        return False
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "pass", "passed"}
    return bool(value)


def _series_get(series: pd.Series | None, key: str) -> Any:
    if series is None or key not in series.index:
        return None
    return series[key]


def _series_from_optional(value: pd.Series | dict[str, Any] | None) -> pd.Series:
    if value is None:
        return pd.Series(dtype="object")
    if isinstance(value, pd.Series):
        return value
    return pd.Series(dict(value))


def _merge_audit_records(existing: pd.Series | dict[str, Any] | None, computed: dict[str, Any]) -> pd.Series:
    merged = _series_from_optional(existing).to_dict()
    for key, value in computed.items():
        if key not in merged or not _is_missing(value):
            merged[key] = value
    return pd.Series(merged)


def _split_warning_flags(value: Any) -> list[str]:
    if _is_missing(value):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def _numeric_or_none(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_non_missing(*values: Any) -> Any:
    for value in values:
        if not _is_missing(value):
            return value
    return None


def _numeric_first(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    output = pd.Series([pd.NA] * len(frame), index=frame.index, dtype="Float64")
    for column in columns:
        if column in frame.columns:
            output = output.fillna(pd.to_numeric(frame[column], errors="coerce"))
    return output.fillna(0)


def _session_date_bounds(table: pd.DataFrame):
    if "session_date" not in table.columns or table.empty:
        return None, None
    dates = pd.to_datetime(table["session_date"], errors="coerce").dropna()
    if dates.empty:
        return None, None
    return dates.min().date(), dates.max().date()


def _string_options(table: pd.DataFrame, column: str) -> list[str]:
    if column not in table.columns:
        return []
    return [str(value) for value in table[column].dropna().unique() if str(value)]


def _min_timestamp(values) -> pd.Timestamp | None:
    parsed = pd.to_datetime(values, errors="coerce").dropna()
    return None if parsed.empty else parsed.min()


def _max_timestamp(values) -> pd.Timestamp | None:
    parsed = pd.to_datetime(values, errors="coerce").dropna()
    return None if parsed.empty else parsed.max()


def _date_range_text(start: pd.Timestamp | None, end: pd.Timestamp | None) -> str | None:
    if start is None and end is None:
        return None
    if start is None:
        return str(end.date())
    if end is None:
        return str(start.date())
    return f"{start.date()} to {end.date()}"


def _last_valid(values: pd.Series):
    valid = pd.to_numeric(values, errors="coerce").dropna()
    return None if valid.empty else valid.iloc[-1]


def _format_value(value: Any) -> str:
    if _is_missing(value):
        return "N/A"
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        result = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if isinstance(result, bool):
        return result
    return False


if __name__ == "__main__":
    main()
