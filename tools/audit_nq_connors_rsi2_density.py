from __future__ import annotations

import copy
import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from propstack.data.pipeline import prepare_data
from propstack.strategy_modules.entry.connors_rsi2_mean_reversion import _rsi


CAMPAIGN_ID = "nq_connors_rsi2_mean_reversion"
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
    data_by_timeframe: dict[str, tuple[pd.DataFrame, dict]] = {}
    for timeframe in sorted({str(config["timeframe"]) for config in configs}):
        template = next(config for config in configs if str(config["timeframe"]) == timeframe)
        data, quality = prepare_data(
            template["data"],
            subset_config=template["core"]["data_subset"],
            timeframe=timeframe,
        )
        data = data.sort_values("timestamp").reset_index(drop=True)
        data["session_date"] = pd.to_datetime(data["session_date"]).dt.date
        data["_bar_seconds"] = _bar_seconds(pd.to_datetime(data["timestamp"]))
        data_by_timeframe[timeframe] = (data, quality)

    sessions = sorted(
        set().union(*(set(data["session_date"].dropna().unique()) for data, _quality in data_by_timeframe.values()))
    )
    if len(sessions) < 252:
        raise SystemExit(f"Expected at least 252 sessions, found {len(sessions)}.")
    full_start, full_end = sessions[0], sessions[-1]
    latest_sessions = set(sessions[-252:])
    latest_start, latest_end = sessions[-252], sessions[-1]

    rows = []
    indicator_cache: dict[tuple[str, int, int], pd.DataFrame] = {}
    for config in configs:
        variant_id = config["variant_id"]
        timeframe = str(config["timeframe"])
        data, quality = data_by_timeframe[timeframe]
        grid = _entry_grid(config["core_grid"]["parameters"])
        for entry_params in grid:
            params = copy.deepcopy(config["strategy"]["entry"]["params"])
            params.update(entry_params)
            signal_dates = _signal_dates(params, data, timeframe, indicator_cache)
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
                    "timeframe": config["timeframe"],
                    "setup_mode": params["setup_mode"],
                    "trend_filter": params["trend_filter"],
                    "oversold_rsi": params["oversold_rsi"],
                    "overbought_rsi": params["overbought_rsi"],
                    "moving_average_period": params["moving_average_period"],
                    "min_vwap_extension_ticks": params["min_vwap_extension_ticks"],
                    "earliest_entry_time": params["earliest_entry_time"],
                    "latest_entry_time": params["latest_entry_time"],
                    "prepared_rows": int(quality.get("strategy_rows", len(data))),
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
    machine_summary = _machine_summary(detail, summary, sessions, data_by_timeframe)
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


def _signal_dates(params: dict, data: pd.DataFrame, timeframe: str, indicator_cache: dict) -> list:
    moving_average_period = int(params["moving_average_period"])
    rsi_period = int(params.get("rsi_period", 2))
    key = (timeframe, moving_average_period, rsi_period)
    prepared = indicator_cache.get(key)
    if prepared is None:
        prepared = _with_indicators(data, moving_average_period, rsi_period)
        indicator_cache[key] = prepared
    close = pd.to_numeric(prepared["close"], errors="coerce")
    rsi = prepared["_rsi2"]
    ma = prepared["_ma"]
    base_mask = (
        prepared["is_rth"].fillna(False).astype(bool)
        & prepared["_bar_seconds"].between(_time_seconds(params["earliest_entry_time"]), _time_seconds(params["latest_entry_time"]))
        & rsi.notna()
        & ma.notna()
        & close.notna()
    )

    setup_mode = str(params["setup_mode"]).lower()
    long_mask = pd.Series(False, index=prepared.index)
    short_mask = pd.Series(False, index=prepared.index)
    if setup_mode in {"long_pullback_uptrend", "two_sided_trend_reversion"} and bool(params.get("allow_long", True)):
        long_mask = base_mask & rsi.le(float(params["oversold_rsi"])) & _trend_mask("long", params, close, ma, prepared)
    if setup_mode in {"short_bounce_downtrend", "two_sided_trend_reversion"} and bool(params.get("allow_short", True)):
        short_mask = base_mask & rsi.ge(float(params["overbought_rsi"])) & _trend_mask("short", params, close, ma, prepared)

    signals = prepared.loc[long_mask | short_mask, ["session_date", "timestamp"]]
    if signals.empty:
        return []
    first_per_session = signals.sort_values("timestamp").drop_duplicates("session_date", keep="first")
    return first_per_session["session_date"].tolist()


def _with_indicators(data: pd.DataFrame, moving_average_period: int, rsi_period: int) -> pd.DataFrame:
    out = data.copy()
    close = pd.to_numeric(out["close"], errors="coerce")
    out["_ma"] = close.rolling(moving_average_period, min_periods=moving_average_period).mean()
    if rsi_period == 2 and close.notna().all():
        out["_rsi2"] = _rolling_rsi2_bounded(close.to_numpy(dtype=float), moving_average_period)
        return out

    max_history = max(moving_average_period + 5, rsi_period + 5)
    history: list[float] = []
    rsi_values: list[float | None] = []
    for value in close.tolist():
        if pd.isna(value):
            history.append(float("nan"))
            rsi_values.append(None)
            continue
        history.append(float(value))
        if len(history) > max_history:
            history = history[-max_history:]
        if any(pd.isna(item) for item in history):
            rsi_values.append(None)
        else:
            rsi_values.append(_rsi(history, rsi_period))
    out["_rsi2"] = rsi_values
    return out


def _rolling_rsi2_bounded(close: np.ndarray, moving_average_period: int) -> np.ndarray:
    max_history = max(moving_average_period + 5, 7)
    max_changes = max_history - 1
    out = np.full(len(close), np.nan, dtype=float)
    if len(close) <= 2:
        return out

    changes = np.diff(close)
    gains = np.maximum(changes, 0.0)
    losses = np.maximum(-changes, 0.0)
    effective_max = min(max_changes, len(changes))

    for close_index in range(2, min(len(close), effective_max + 1)):
        m = close_index
        weights = _rsi2_weights(m)
        avg_gain = float(np.dot(gains[:m], weights))
        avg_loss = float(np.dot(losses[:m], weights))
        out[close_index] = _rsi_from_avgs(avg_gain, avg_loss)

    if len(changes) >= max_changes:
        weights = _rsi2_weights(max_changes)
        avg_gain = np.correlate(gains, weights, mode="valid")
        avg_loss = np.correlate(losses, weights, mode="valid")
        for offset, (gain_value, loss_value) in enumerate(zip(avg_gain, avg_loss)):
            close_index = offset + max_changes
            out[close_index] = _rsi_from_avgs(float(gain_value), float(loss_value))

    return out


def _rsi2_weights(change_count: int) -> np.ndarray:
    if change_count < 2:
        raise ValueError("RSI2 requires at least two changes.")
    if change_count == 2:
        return np.array([0.5, 0.5], dtype=float)
    weights = np.empty(change_count, dtype=float)
    weights[0] = 0.5 ** (change_count - 1)
    weights[1] = weights[0]
    for idx in range(2, change_count):
        weights[idx] = 0.5 ** (change_count - idx)
    return weights


def _rsi_from_avgs(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0 and avg_gain == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _trend_mask(direction: str, params: dict, close: pd.Series, ma: pd.Series, data: pd.DataFrame) -> pd.Series:
    trend_filter = str(params.get("trend_filter", "ma")).lower()
    mask = pd.Series(True, index=data.index)
    if trend_filter in {"ma", "ma_and_vwap"}:
        if direction == "long":
            mask &= close.ge(ma)
        else:
            mask &= close.le(ma)
    min_vwap_extension_ticks = float(params.get("min_vwap_extension_ticks", 0.0) or 0.0)
    if trend_filter in {"vwap", "ma_and_vwap"} or min_vwap_extension_ticks > 0:
        if "vwap" not in data.columns:
            raise ValueError("Prepared data is missing vwap for Connors RSI2 VWAP variant.")
        vwap = pd.to_numeric(data["vwap"], errors="coerce")
        extension = min_vwap_extension_ticks * float(params.get("tick_size", 0.25))
        if direction == "long":
            mask &= vwap.notna() & close.le(vwap - extension)
        else:
            mask &= vwap.notna() & close.ge(vwap + extension)
    return mask


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


def _machine_summary(detail: pd.DataFrame, summary: pd.DataFrame, sessions: list, data_by_timeframe: dict) -> dict:
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
        "prepared_rows_by_timeframe": {
            timeframe: int(quality.get("strategy_rows", len(data))) for timeframe, (data, quality) in data_by_timeframe.items()
        },
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
        "The signal count mirrors the entry module's completed-bar RSI2 state, MA/VWAP trend filters, "
        "configured entry window, and one-signal-per-session cap.",
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
