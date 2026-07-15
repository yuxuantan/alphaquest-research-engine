from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd
import yaml

from alphaquest.data.pipeline import prepare_data


CAMPAIGN_ID = "nq_overnight_range_compression_orderflow_breakout"
CAMPAIGN_ROOT = Path("campaigns") / CAMPAIGN_ID
ARTIFACT_ROOT = Path("research_artifacts")
AUDIT_DATE = "2026-06-30"
ARTIFACT_STAMP = "20260630"
LIMITED_START = pd.Timestamp("2011-02-22").date()
LIMITED_END = pd.Timestamp("2012-09-07").date()
MIN_FULL_SIGNALS_PER_YEAR = 50.0
MIN_LIMITED_SIGNALS_PER_YEAR = 50.0
MIN_LATEST_252_SIGNALS = 50


def main() -> None:
    variant_paths = sorted((CAMPAIGN_ROOT / "variants").glob("*/config.yaml"))
    if len(variant_paths) != 5:
        raise SystemExit(f"Expected exactly 5 variant configs, found {len(variant_paths)}.")

    configs = [yaml.safe_load(path.read_text()) for path in variant_paths]
    data, quality = prepare_data(
        configs[0]["data"],
        subset_config=configs[0]["core"]["data_subset"],
        timeframe=configs[0]["timeframe"],
    )
    data = data.sort_values("timestamp").reset_index(drop=True)
    data["session_date"] = pd.to_datetime(data["session_date"]).dt.date
    data["_bar_seconds"] = _bar_seconds(pd.to_datetime(data["timestamp"]))
    feature_data = _load_feature_data(configs[0]["strategy"]["entry"]["params"]["feature_csv"])
    feature_columns = [column for column in feature_data.columns if column != "session_date"]
    data = data.drop(columns=[column for column in feature_columns if column in data.columns])
    data = data.merge(feature_data, on="session_date", how="left", validate="many_to_one")

    sessions = sorted(data["session_date"].dropna().unique())
    if len(sessions) < 252:
        raise SystemExit(f"Expected at least 252 sessions, found {len(sessions)}.")
    full_start, full_end = sessions[0], sessions[-1]
    latest_sessions = set(sessions[-252:])
    latest_start, latest_end = sessions[-252], sessions[-1]

    rows = []
    for config in configs:
        variant_id = config["variant_id"]
        base_params = config["strategy"]["entry"]["params"]
        grid = config["core_grid"]["parameters"]
        ranks = grid["entry.params.max_overnight_range_rank"]
        imbalances = grid["entry.params.min_orderflow_imbalance"]

        for max_rank in ranks:
            for min_imbalance in imbalances:
                params = copy.deepcopy(base_params)
                params["max_overnight_range_rank"] = max_rank
                params["min_orderflow_imbalance"] = min_imbalance
                signal_dates = _signal_dates(params, data)

                full_count = len(signal_dates)
                limited_count = sum(LIMITED_START <= day <= LIMITED_END for day in signal_dates)
                latest_count = sum(day in latest_sessions for day in signal_dates)
                full_per_year = _per_year(full_count, full_start, full_end)
                limited_per_year = _per_year(limited_count, LIMITED_START, LIMITED_END)
                pass_gate = (
                    full_per_year >= MIN_FULL_SIGNALS_PER_YEAR
                    and limited_per_year >= MIN_LIMITED_SIGNALS_PER_YEAR
                    and latest_count >= MIN_LATEST_252_SIGNALS
                )
                rows.append(
                    {
                        "campaign_id": CAMPAIGN_ID,
                        "variant_id": variant_id,
                        "max_overnight_range_rank": max_rank,
                        "min_orderflow_imbalance": min_imbalance,
                        "orderflow_mode": params["orderflow_mode"],
                        "min_flow_volume": params["min_flow_volume"],
                        "start_time": params["start_time"],
                        "end_time": params["end_time"],
                        "flatten_time": params["flatten_time"],
                        "full_start_date": str(full_start),
                        "full_end_date": str(full_end),
                        "full_signals": full_count,
                        "full_signals_per_year": full_per_year,
                        "limited_start_date": str(LIMITED_START),
                        "limited_end_date": str(LIMITED_END),
                        "limited_signals": limited_count,
                        "limited_signals_per_year": limited_per_year,
                        "latest_252_start_date": str(latest_start),
                        "latest_252_end_date": str(latest_end),
                        "latest_252_signals": latest_count,
                        "density_gate_pass": pass_gate,
                    }
                )

    detail = pd.DataFrame(rows)
    summary = _summary(detail)
    machine_summary = _machine_summary(detail, summary, sessions, quality)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    detail_path = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.csv"
    summary_path = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_summary_{ARTIFACT_STAMP}.csv"
    markdown_path = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.md"
    detail.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)
    markdown_path.write_text(_markdown(summary, machine_summary, detail_path, summary_path), encoding="utf-8")
    print(json.dumps(machine_summary, indent=2, sort_keys=True))


def _signal_dates(params: dict, data: pd.DataFrame) -> list:
    start_seconds = _time_seconds(params["start_time"])
    end_seconds = _time_seconds(params["end_time"])
    tick_size = float(params.get("tick_size", 0.25))
    buffer_points = int(params.get("breakout_buffer_ticks", 0)) * tick_size
    max_range_points = params.get("max_overnight_range_points")
    max_range_points = None if max_range_points is None else float(max_range_points)
    min_overnight_range_points = float(params.get("min_overnight_range_points", 0.0))
    max_overnight_range_rank = float(params["max_overnight_range_rank"])
    min_flow_volume = float(params.get("min_flow_volume", 0.0))
    min_imbalance = float(params["min_orderflow_imbalance"])

    signed, volume = _flow_columns(params["orderflow_mode"], data)
    imbalance = signed / volume

    mask = (
        data["is_rth"].fillna(False).astype(bool)
        & data["_bar_seconds"].between(start_seconds, end_seconds)
        & data["overnight_high"].notna()
        & data["overnight_low"].notna()
        & data["overnight_range_points"].ge(min_overnight_range_points)
        & data["overnight_range_rank_252"].le(max_overnight_range_rank)
        & volume.gt(0)
        & volume.ge(min_flow_volume)
        & imbalance.notna()
    )
    if max_range_points is not None:
        mask &= data["overnight_range_points"].le(max_range_points)

    long_mask = (
        bool(params.get("allow_long", True))
        & data["close"].ge(data["overnight_high"] + buffer_points)
        & imbalance.ge(min_imbalance)
    )
    short_mask = (
        bool(params.get("allow_short", True))
        & data["close"].le(data["overnight_low"] - buffer_points)
        & imbalance.le(-min_imbalance)
    )
    signals = data.loc[mask & (long_mask | short_mask), ["session_date", "timestamp"]]
    if signals.empty:
        return []
    first_per_session = signals.sort_values("timestamp").drop_duplicates("session_date", keep="first")
    return first_per_session["session_date"].tolist()


def _load_feature_data(path_value) -> pd.DataFrame:
    path = Path(path_value)
    if not path.exists():
        raise FileNotFoundError(f"overnight feature_csv not found: {path}")
    features = pd.read_csv(path, parse_dates=["session_date"])
    required = [
        "session_date",
        "overnight_high",
        "overnight_low",
        "overnight_midpoint",
        "overnight_range_points",
        "overnight_range_rank_252",
    ]
    missing = set(required).difference(features.columns)
    if missing:
        raise ValueError(f"overnight feature_csv missing columns: {sorted(missing)}")
    features = features[required].copy()
    features["session_date"] = pd.to_datetime(features["session_date"]).dt.date
    return features


def _flow_columns(mode: str, data: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    mode = str(mode).lower()
    if mode in {"signed", "signed_volume", "all_volume"}:
        signed_column, volume_column = "signed_volume", "volume"
    elif mode in {"large10", "large10_imbalance"}:
        signed_column, volume_column = "large10_signed_volume", "large10_volume"
    elif mode in {"large20", "large20_imbalance"}:
        signed_column, volume_column = "large20_signed_volume", "large20_volume"
    else:
        raise ValueError(f"Unsupported orderflow_mode: {mode}")
    for column in [signed_column, volume_column]:
        if column not in data.columns:
            raise ValueError(f"Prepared data missing orderflow column: {column}")
    return pd.to_numeric(data[signed_column], errors="coerce"), pd.to_numeric(data[volume_column], errors="coerce")


def _bar_seconds(timestamp: pd.Series) -> pd.Series:
    return timestamp.dt.hour * 3600 + timestamp.dt.minute * 60 + timestamp.dt.second


def _time_seconds(value) -> int:
    if hasattr(value, "hour") and hasattr(value, "minute"):
        return int(value.hour) * 3600 + int(value.minute) * 60 + int(getattr(value, "second", 0))
    parsed = pd.Timestamp(f"2000-01-01 {value}").time()
    return parsed.hour * 3600 + parsed.minute * 60 + parsed.second


def _per_year(count: int, start_date, end_date) -> float:
    years = max((pd.Timestamp(end_date) - pd.Timestamp(start_date)).days / 365.25, 1 / 365.25)
    return float(count) / years


def _summary(detail: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for variant_id, group in detail.groupby("variant_id", sort=True):
        rows.append(
            {
                "variant_id": variant_id,
                "entry_rows": int(len(group)),
                "pass_rows": int(group["density_gate_pass"].sum()),
                "min_full_signals_per_year": float(group["full_signals_per_year"].min()),
                "median_full_signals_per_year": float(group["full_signals_per_year"].median()),
                "max_full_signals_per_year": float(group["full_signals_per_year"].max()),
                "min_limited_signals_per_year": float(group["limited_signals_per_year"].min()),
                "median_limited_signals_per_year": float(group["limited_signals_per_year"].median()),
                "max_limited_signals_per_year": float(group["limited_signals_per_year"].max()),
                "min_latest_252_signals": int(group["latest_252_signals"].min()),
                "median_latest_252_signals": float(group["latest_252_signals"].median()),
                "max_latest_252_signals": int(group["latest_252_signals"].max()),
                "verdict": "PASS" if bool(group["density_gate_pass"].all()) else "FAIL",
            }
        )
    return pd.DataFrame(rows)


def _machine_summary(detail: pd.DataFrame, summary: pd.DataFrame, sessions: list, quality: dict) -> dict:
    return {
        "all_rows_density_pass": bool(detail["density_gate_pass"].all()),
        "audit_date": AUDIT_DATE,
        "campaign_id": CAMPAIGN_ID,
        "declared_entry_rows": int(len(detail)),
        "density_pass_rows": int(detail["density_gate_pass"].sum()),
        "density_fail_rows": int((~detail["density_gate_pass"]).sum()),
        "full_start_date": str(sessions[0]),
        "full_end_date": str(sessions[-1]),
        "full_sessions": int(len(sessions)),
        "latest_252_start_date": str(sessions[-252]),
        "latest_252_end_date": str(sessions[-1]),
        "limited_start_date": str(LIMITED_START),
        "limited_end_date": str(LIMITED_END),
        "min_full_signals_per_year": float(detail["full_signals_per_year"].min()),
        "min_limited_signals_per_year": float(detail["limited_signals_per_year"].min()),
        "min_latest_252_signals": int(detail["latest_252_signals"].min()),
        "prepared_rows": int(quality.get("strategy_rows", len(detail))),
        "timeframe": quality.get("timeframe"),
    }


def _markdown(summary: pd.DataFrame, machine_summary: dict, detail_path: Path, summary_path: Path) -> str:
    lines = [
        f"# {CAMPAIGN_ID} density audit",
        "",
        f"- Audit date: {AUDIT_DATE}",
        f"- Full window: {machine_summary['full_start_date']} to {machine_summary['full_end_date']} "
        f"({machine_summary['full_sessions']} sessions)",
        f"- Limited-core window: {LIMITED_START} to {LIMITED_END}",
        f"- Latest-252 window: {machine_summary['latest_252_start_date']} to {machine_summary['latest_252_end_date']}",
        f"- Declared entry rows: {machine_summary['declared_entry_rows']}",
        f"- Density passes: {machine_summary['density_pass_rows']}",
        f"- Density failures: {machine_summary['density_fail_rows']}",
        "",
        "Gate: each declared entry row must produce at least 50 signals/year in full history, "
        "at least 50 signals/year in the limited-core window, and at least 50 signals in the latest "
        "252 sessions before any PnL is inspected.",
        "",
        "| variant | rows | pass rows | min full/year | min limited/year | min latest-252 | verdict |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary.to_dict("records"):
        lines.append(
            "| {variant_id} | {entry_rows} | {pass_rows} | {min_full_signals_per_year:.2f} | "
            "{min_limited_signals_per_year:.2f} | {min_latest_252_signals} | {verdict} |".format(**row)
        )
    lines.extend(
        [
            "",
            "Machine summary:",
            "",
            "```json",
            json.dumps(machine_summary, indent=2, sort_keys=True),
            "```",
            "",
            f"Detail CSV: `{detail_path}`",
            "",
            f"Summary CSV: `{summary_path}`",
            "",
        ]
    )
    return "\n".join(lines)


if __name__ == "__main__":
    main()
