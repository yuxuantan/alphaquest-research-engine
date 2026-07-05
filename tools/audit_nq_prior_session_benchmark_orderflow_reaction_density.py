from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

import pandas as pd
import yaml

from propstack.data.pipeline import prepare_data


CAMPAIGN_ID = "nq_prior_session_benchmark_orderflow_reaction"
SOURCE_CAMPAIGN_ID = "es_prior_session_benchmark_orderflow_reaction"
SOURCE_ROOT = Path("campaigns") / SOURCE_CAMPAIGN_ID / "variants"
AUDIT_DATE = "2026-06-30"
ARTIFACT_STAMP = "20260630"
ARTIFACT_ROOT = Path("research_artifacts")
ADAPTATION_NOTE = (
    "Official NQ plan uses the ES five-variant structure, but replaces the sparse "
    "prior_open_midday_large20_reclaim_reversion_1400 expression with a prior-open "
    "midday large10 expression before any PnL is inspected."
)

LIMITED_START = pd.Timestamp("2011-02-22").date()
LIMITED_END = pd.Timestamp("2012-09-07").date()
MIN_FULL_SIGNALS_PER_YEAR = 50.0
MIN_LIMITED_SIGNALS_PER_YEAR = 50.0
MIN_LATEST_252_SIGNALS = 50

ENTRY_MIN_PROBE_TICKS = [0, 1, 2]
ENTRY_MIN_ORDERFLOW_IMBALANCE = [0.0, 0.02, 0.04]

FLOW_COLUMNS = {
    "signed_volume": ("signed_volume", "volume"),
    "signed": ("signed_volume", "volume"),
    "large10": ("large10_signed_volume", "large10_volume"),
    "large10_imbalance": ("large10_signed_volume", "large10_volume"),
    "large20": ("large20_signed_volume", "large20_volume"),
    "large20_imbalance": ("large20_signed_volume", "large20_volume"),
}


def main() -> None:
    source_configs = _source_configs()
    data, quality = prepare_data(
        _nq_data_config(source_configs[0]["data"]),
        subset_config=_subset(),
        timeframe="5m",
    )
    data = data.sort_values("timestamp").reset_index(drop=True)
    data["session_date"] = pd.to_datetime(data["session_date"]).dt.date
    sessions = sorted(data["session_date"].dropna().unique())
    latest_sessions = set(sessions[-252:])

    rows = []
    for config in source_configs:
        base_params = copy.deepcopy(config["strategy"]["entry"]["params"])
        for min_probe_ticks, min_imbalance in itertools.product(
            ENTRY_MIN_PROBE_TICKS,
            ENTRY_MIN_ORDERFLOW_IMBALANCE,
        ):
            params = copy.deepcopy(base_params)
            params["min_probe_ticks"] = min_probe_ticks
            params["min_orderflow_imbalance"] = min_imbalance
            signal_dates = _signal_dates(data, params)
            full_count = len(signal_dates)
            limited_count = sum(LIMITED_START <= day <= LIMITED_END for day in signal_dates)
            latest_count = sum(day in latest_sessions for day in signal_dates)
            full_per_year = _per_year(full_count, sessions[0], sessions[-1])
            limited_per_year = _per_year(limited_count, LIMITED_START, LIMITED_END)
            pass_gate = (
                full_per_year >= MIN_FULL_SIGNALS_PER_YEAR
                and limited_per_year >= MIN_LIMITED_SIGNALS_PER_YEAR
                and latest_count >= MIN_LATEST_252_SIGNALS
            )
            rows.append(
                {
                    "campaign_id": CAMPAIGN_ID,
                    "source_campaign_id": SOURCE_CAMPAIGN_ID,
                    "variant_id": config["variant_id"],
                    "level_set": base_params["level_set"],
                    "flow_mode": base_params["flow_mode"],
                    "start_time": base_params["start_time"],
                    "end_time": base_params["end_time"],
                    "flatten_time": base_params["flatten_time"],
                    "min_probe_ticks": min_probe_ticks,
                    "reclaim_buffer_ticks": base_params.get("reclaim_buffer_ticks", 0),
                    "reclaim_window_bars": base_params.get("reclaim_window_bars", 2),
                    "min_orderflow_imbalance": min_imbalance,
                    "full_start_date": str(sessions[0]),
                    "full_end_date": str(sessions[-1]),
                    "full_signals": full_count,
                    "full_signals_per_year": full_per_year,
                    "limited_start_date": str(LIMITED_START),
                    "limited_end_date": str(LIMITED_END),
                    "limited_signals": limited_count,
                    "limited_signals_per_year": limited_per_year,
                    "latest_252_start_date": str(sessions[-252]),
                    "latest_252_end_date": str(sessions[-1]),
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


def _source_configs() -> list[dict]:
    paths = sorted(SOURCE_ROOT.glob("*/config.yaml"))
    if len(paths) != 5:
        raise SystemExit(f"Expected exactly 5 source configs, found {len(paths)} in {SOURCE_ROOT}.")
    configs = [yaml.safe_load(path.read_text()) for path in paths]
    for config in configs:
        if config["variant_id"] == "prior_open_midday_large20_reclaim_reversion_1400":
            config["variant_id"] = "prior_open_midday_large10_reclaim_reversion_1400"
            config["strategy"]["entry"]["params"]["flow_mode"] = "large10"
    return configs


def _nq_data_config(source_data: dict) -> dict:
    data = copy.deepcopy(source_data)
    data["dataset_id"] = "nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny"
    data["raw_parquet"] = "data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet"
    data["symbol"] = "NQ"
    data["timezone"] = "America/New_York"
    data["exchange_timezone"] = "America/New_York"
    data["rth_start"] = "09:30:00"
    data["rth_end"] = "15:59:00"
    data["warmup_days"] = 20
    data["feature_set"] = "full"
    return data


def _subset() -> dict:
    return {
        "start_date": "2011-01-03",
        "end_date": "2026-06-12",
        "session_labels": ["RTH"],
    }


def _signal_dates(data: pd.DataFrame, params: dict) -> list:
    start_seconds = _time_seconds(params.get("start_time", "09:35:00"))
    end_seconds = _time_seconds(params.get("end_time", "15:00:00"))
    bar_seconds = _bar_seconds(pd.to_datetime(data["timestamp"]))
    window = data.loc[bar_seconds.between(start_seconds, end_seconds)].copy()
    if window.empty:
        return []

    level_set = str(params.get("level_set", "previous_close")).lower()
    flow_mode = str(params.get("flow_mode", "signed_volume")).lower()
    signed_col, total_col = FLOW_COLUMNS[flow_mode]
    threshold = float(params.get("min_probe_ticks", 1)) * float(params.get("tick_size", 0.25))
    buffer = float(params.get("reclaim_buffer_ticks", 0)) * float(params.get("tick_size", 0.25))
    reclaim_window_bars = int(params.get("reclaim_window_bars", 2))
    min_imbalance = float(params.get("min_orderflow_imbalance", 0.02))
    allow_long = bool(params.get("allow_long", True))
    allow_short = bool(params.get("allow_short", True))

    dates = []
    columns = [
        "timestamp",
        "session_date",
        "high",
        "low",
        "close",
        "prev_rth_close",
        "prev_rth_open",
        signed_col,
        total_col,
    ]
    for session_date, group in window[columns].groupby("session_date", sort=True, dropna=False):
        sweeps: dict[str, dict] = {}
        traded_keys: set[str] = set()
        signaled = False
        for bar_index, row in enumerate(group.itertuples(index=False)):
            levels = _levels(row, level_set)
            for level_type, price in levels:
                for direction in _directions(allow_long, allow_short):
                    key = f"{level_type}:{direction}"
                    if key in traded_keys:
                        continue
                    sweep = sweeps.get(key)
                    high = float(row.high)
                    low = float(row.low)
                    close = float(row.close)
                    if sweep is not None:
                        sweep["sweep_low"] = min(sweep["sweep_low"], low)
                        sweep["sweep_high"] = max(sweep["sweep_high"], high)
                    if sweep is None:
                        if direction == "long" and low <= price - threshold:
                            sweep = {"bar_index": bar_index, "sweep_low": low, "sweep_high": high}
                            sweeps[key] = sweep
                        elif direction == "short" and high >= price + threshold:
                            sweep = {"bar_index": bar_index, "sweep_low": low, "sweep_high": high}
                            sweeps[key] = sweep
                    if sweep is None:
                        continue
                    if bar_index - int(sweep["bar_index"]) > reclaim_window_bars:
                        sweeps.pop(key, None)
                        continue
                    if direction == "long" and close < price + buffer:
                        continue
                    if direction == "short" and close > price - buffer:
                        continue
                    signed = _finite_float(getattr(row, signed_col))
                    total = _finite_float(getattr(row, total_col))
                    if signed is None or total is None or total <= 0:
                        continue
                    imbalance = signed / total
                    if direction == "long" and imbalance < min_imbalance:
                        continue
                    if direction == "short" and imbalance > -min_imbalance:
                        continue
                    traded_keys.add(key)
                    dates.append(session_date)
                    signaled = True
                    break
                if signaled:
                    break
            if signaled:
                break
    return dates


def _levels(row, level_set: str) -> list[tuple[str, float]]:
    levels = []
    if level_set in {"previous_close", "prev_close", "close", "both", "open_close"}:
        value = _finite_float(row.prev_rth_close)
        if value is not None:
            levels.append(("previous_rth_close", value))
    if level_set in {"previous_open", "prev_open", "open", "both", "open_close"}:
        value = _finite_float(row.prev_rth_open)
        if value is not None:
            levels.append(("previous_rth_open", value))
    return levels


def _directions(allow_long: bool, allow_short: bool) -> list[str]:
    out = []
    if allow_long:
        out.append("long")
    if allow_short:
        out.append("short")
    return out


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
        "source_campaign_id": SOURCE_CAMPAIGN_ID,
        "declared_entry_rows": int(len(detail)),
        "density_pass_rows": int(detail["density_gate_pass"].sum()),
        "density_fail_rows": int((~detail["density_gate_pass"]).sum()),
        "failed_variants": summary.loc[summary["verdict"] != "PASS", "variant_id"].tolist(),
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
        "prepared_rows": int(quality.get("strategy_rows", 0)),
        "adaptation_note": ADAPTATION_NOTE,
        "verdict": "PASS" if bool(detail["density_gate_pass"].all()) else "FAIL",
    }


def _markdown(summary: pd.DataFrame, machine_summary: dict, detail_path: Path, summary_path: Path) -> str:
    lines = [
        f"# {CAMPAIGN_ID} density audit",
        "",
        f"- Audit date: {AUDIT_DATE}",
        f"- Source campaign: {SOURCE_CAMPAIGN_ID}",
        f"- Adaptation: {ADAPTATION_NOTE}",
        f"- Full window: {machine_summary['full_start_date']} to {machine_summary['full_end_date']} ({machine_summary['full_sessions']} sessions)",
        f"- Limited-core window: {LIMITED_START} to {LIMITED_END}",
        f"- Latest-252 window: {machine_summary['latest_252_start_date']} to {machine_summary['latest_252_end_date']}",
        f"- Declared entry rows: {machine_summary['declared_entry_rows']}",
        f"- Density passes: {machine_summary['density_pass_rows']}",
        f"- Density failures: {machine_summary['density_fail_rows']}",
        "",
        "Gate: every declared entry row must produce at least 50 signals/year in full history, "
        "at least 50 signals/year in the limited-core window, and at least 50 signals in the latest 252 sessions before any PnL is inspected.",
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
            f"Verdict: {machine_summary['verdict']}.",
            "",
        ]
    )
    return "\n".join(lines)


def _bar_seconds(timestamp: pd.Series) -> pd.Series:
    return timestamp.dt.hour * 3600 + timestamp.dt.minute * 60 + timestamp.dt.second


def _time_seconds(value) -> int:
    parsed = pd.Timestamp(f"2000-01-01 {value}").time()
    return parsed.hour * 3600 + parsed.minute * 60 + parsed.second


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if pd.notna(out) else None


def _per_year(count: int, start_date, end_date) -> float:
    years = max((pd.Timestamp(end_date) - pd.Timestamp(start_date)).days / 365.25, 1 / 365.25)
    return float(count) / years


if __name__ == "__main__":
    main()
