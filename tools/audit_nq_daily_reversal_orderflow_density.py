from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

import pandas as pd
import yaml

from alphaquest.data.pipeline import prepare_data


CAMPAIGN_ID = "nq_daily_reversal_orderflow_confirmation"
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
    data["_bar_close"] = pd.to_datetime(data["timestamp"]) + pd.Timedelta(minutes=5)
    data["_bar_close_seconds"] = _bar_seconds(data["_bar_close"])
    daily_close = _daily_closes(data)
    sessions = sorted(data["session_date"].dropna().unique())
    latest_sessions = set(sessions[-252:])

    rows = []
    for config in configs:
        for entry_params in _entry_grid(config["core_grid"]["parameters"]):
            params = copy.deepcopy(config["strategy"]["entry"]["params"])
            params.update(entry_params)
            signal_dates = _signal_dates(params, data, daily_close)
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
                    "variant_id": config["variant_id"],
                    "signal_time": params["signal_time"],
                    "lookback_sessions": params["lookback_sessions"],
                    "flow_window_bars": params["flow_window_bars"],
                    "min_abs_reversal_return_pct": params["min_abs_reversal_return_pct"],
                    "min_reversal_flow_imbalance": params["min_reversal_flow_imbalance"],
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


def _entry_grid(parameters: dict) -> list[dict]:
    entry_items = [(key.replace("entry.params.", ""), values) for key, values in parameters.items() if key.startswith("entry.params.")]
    keys = [key for key, _values in entry_items]
    values = [list(value) for _key, value in entry_items]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def _daily_closes(data: pd.DataFrame) -> pd.Series:
    close_rows = data.loc[data["_bar_close_seconds"].ge(_time_seconds("16:00:00")), ["session_date", "timestamp", "close"]]
    close_rows = close_rows.sort_values("timestamp").drop_duplicates("session_date", keep="first")
    return close_rows.set_index("session_date")["close"].astype(float).sort_index()


def _signal_dates(params: dict, data: pd.DataFrame, daily_close: pd.Series) -> list:
    signal_seconds = _time_seconds(params["signal_time"])
    signal_rows = data.loc[data["_bar_close_seconds"].eq(signal_seconds)].copy()
    if signal_rows.empty:
        return []

    daily = daily_close.rename("daily_close").reset_index()
    lookback = int(params["lookback_sessions"])
    daily["recent_close"] = daily["daily_close"].shift(1)
    daily["anchor_close"] = daily["daily_close"].shift(lookback + 1)
    signal_rows = signal_rows.merge(
        daily[["session_date", "recent_close", "anchor_close"]],
        on="session_date",
        how="left",
        validate="many_to_one",
    )
    signal_rows = signal_rows[(signal_rows["recent_close"] > 0) & (signal_rows["anchor_close"] > 0)].copy()
    if signal_rows.empty:
        return []

    ret = signal_rows["recent_close"] / signal_rows["anchor_close"] - 1.0
    min_abs_ret = float(params["min_abs_reversal_return_pct"])
    base = ret.abs().ge(min_abs_ret)

    suffix = str(int(params["flow_window_bars"]))
    imbalance = pd.to_numeric(signal_rows[f"trade_orderflow_imbalance_{suffix}"], errors="coerce")
    volume = pd.to_numeric(signal_rows[f"trade_orderflow_volume_{suffix}"], errors="coerce")
    min_flow_volume = float(params.get("min_flow_volume", 0.0))
    min_imbalance = float(params["min_reversal_flow_imbalance"])
    flow_ok = volume.ge(min_flow_volume) & imbalance.notna()

    direction_mode = str(params.get("direction_mode", "two_sided")).lower()
    long_ok = ret.lt(0) & imbalance.ge(min_imbalance)
    short_ok = ret.gt(0) & imbalance.le(-min_imbalance)
    if direction_mode == "loss_long":
        direction = long_ok
    elif direction_mode == "gain_short":
        direction = short_ok
    else:
        direction = long_ok | short_ok

    signals = signal_rows.loc[base & flow_ok & direction, ["session_date", "timestamp"]]
    if signals.empty:
        return []
    return signals.sort_values("timestamp").drop_duplicates("session_date", keep="first")["session_date"].tolist()


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
    }


def _markdown(summary: pd.DataFrame, machine_summary: dict, detail_path: Path, summary_path: Path) -> str:
    lines = [
        f"# {CAMPAIGN_ID} density audit",
        "",
        f"- Audit date: {AUDIT_DATE}",
        f"- Full window: {machine_summary['full_start_date']} to {machine_summary['full_end_date']} ({machine_summary['full_sessions']} sessions)",
        f"- Limited-core window: {LIMITED_START} to {LIMITED_END}",
        f"- Latest-252 window: {machine_summary['latest_252_start_date']} to {machine_summary['latest_252_end_date']}",
        f"- Declared entry rows: {machine_summary['declared_entry_rows']}",
        f"- Density passes: {machine_summary['density_pass_rows']}",
        f"- Density failures: {machine_summary['density_fail_rows']}",
        "",
        "Gate: each declared entry row must produce at least 50 signals/year in full history, "
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
    lines.extend(["", "Machine summary:", "", "```json", json.dumps(machine_summary, indent=2, sort_keys=True), "```", "", f"Detail CSV: `{detail_path}`", "", f"Summary CSV: `{summary_path}`", ""])
    return "\n".join(lines)


if __name__ == "__main__":
    main()
