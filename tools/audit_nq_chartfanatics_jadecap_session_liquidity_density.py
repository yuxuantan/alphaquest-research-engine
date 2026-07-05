from __future__ import annotations

from itertools import product
from pathlib import Path

import pandas as pd
import yaml

from propstack.data.pipeline import prepare_data
from propstack.strategy_modules.entry.session_liquidity_fvg_reversal import SessionLiquidityFvgReversalEntry


CAMPAIGN_ID = "nq_chartfanatics_jadecap_session_liquidity_fvg"
CAMPAIGN_ROOT = Path("campaigns") / CAMPAIGN_ID
ARTIFACT_MD = Path("research_artifacts/nq_chartfanatics_jadecap_session_liquidity_fvg_density_audit_20260701.md")
ARTIFACT_CSV = Path("research_artifacts/nq_chartfanatics_jadecap_session_liquidity_fvg_density_audit_20260701.csv")
SUMMARY_CSV = Path("research_artifacts/nq_chartfanatics_jadecap_session_liquidity_fvg_density_summary_20260701.csv")
LIMITED_START = pd.Timestamp("2011-02-22").date()
LIMITED_END = pd.Timestamp("2012-09-07").date()
MIN_SIGNALS_PER_YEAR = 50.0
MIN_LATEST_SIGNALS = 50


def main() -> None:
    config_paths = sorted((CAMPAIGN_ROOT / "variants").glob("*/config.yaml"))
    if len(config_paths) != 5:
        raise SystemExit(f"expected exactly five variant configs, found {len(config_paths)}")
    configs = [_load_yaml(path) for path in config_paths]
    bars = _load_strategy_bars(configs[0])
    records = bars[
        ["timestamp", "session_date", "is_rth", "open", "high", "low", "close", "volume"]
    ].to_dict("records")
    session_dates = pd.to_datetime(bars["session_date"]).dt.date
    full_sessions = int(pd.Series(session_dates).nunique())
    limited_mask = (session_dates >= LIMITED_START) & (session_dates <= LIMITED_END)
    limited_sessions = int(pd.Series(session_dates[limited_mask]).nunique())
    latest_sessions = sorted(pd.Series(session_dates).drop_duplicates())[-252:]
    latest_set = set(latest_sessions)

    rows = []
    for config in configs:
        variant_id = str(config["variant_id"])
        base_params = dict(config["strategy"]["entry"]["params"])
        entry_grid = _entry_grid(config["core_grid"]["parameters"])
        for grid_params in _grid_rows(entry_grid):
            params = {**base_params, **grid_params}
            signal_dates = _signal_dates(params, records)
            full_count = len(signal_dates)
            limited_count = sum(LIMITED_START <= session_date <= LIMITED_END for session_date in signal_dates)
            latest_count = sum(session_date in latest_set for session_date in signal_dates)
            full_per_year = _annualized(full_count, full_sessions)
            limited_per_year = _annualized(limited_count, limited_sessions)
            verdict = (
                "PASS"
                if full_per_year >= MIN_SIGNALS_PER_YEAR
                and limited_per_year >= MIN_SIGNALS_PER_YEAR
                and latest_count >= MIN_LATEST_SIGNALS
                else "FAIL"
            )
            row = {
                "variant": variant_id,
                "setup_mode": params["setup_mode"],
                **{key: value for key, value in grid_params.items()},
                "full_signals": full_count,
                "full_signals_per_year": full_per_year,
                "limited_signals": limited_count,
                "limited_signals_per_year": limited_per_year,
                "latest_252_signals": latest_count,
                "verdict": verdict,
            }
            rows.append(row)

    detail = pd.DataFrame(rows).sort_values(["variant", *sorted(_all_entry_param_columns(rows))])
    summary = (
        detail.groupby("variant", sort=True)
        .agg(
            rows=("variant", "count"),
            pass_rows=("verdict", lambda values: int((values == "PASS").sum())),
            min_full_per_year=("full_signals_per_year", "min"),
            min_limited_per_year=("limited_signals_per_year", "min"),
            min_latest_252=("latest_252_signals", "min"),
            max_full_per_year=("full_signals_per_year", "max"),
        )
        .reset_index()
    )
    summary["verdict"] = summary.apply(lambda row: "PASS" if int(row["pass_rows"]) == int(row["rows"]) else "FAIL", axis=1)
    all_rows_pass = bool((detail["verdict"] == "PASS").all())
    ARTIFACT_MD.parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(ARTIFACT_CSV, index=False)
    summary.to_csv(SUMMARY_CSV, index=False)
    ARTIFACT_MD.write_text(_markdown(detail, summary, all_rows_pass, full_sessions, limited_sessions), encoding="utf-8")
    print(f"wrote {ARTIFACT_MD}")
    print(f"density rows passing {(detail['verdict'] == 'PASS').sum()}/{len(detail)}")
    print(f"variants passing {(summary['verdict'] == 'PASS').sum()}/{len(summary)}")
    print(f"decision {'PASS' if all_rows_pass else 'FAIL'}")


def _load_strategy_bars(config: dict) -> pd.DataFrame:
    data_cfg = dict(config["data"])
    subset = dict(config["core"]["data_subset"])
    bars, _ = prepare_data(data_cfg, subset_config=subset, timeframe=config["timeframe"])
    return bars.sort_values("timestamp").reset_index(drop=True)


def _signal_dates(params: dict, records: list[dict]) -> list:
    entry = SessionLiquidityFvgReversalEntry(params)
    dates = []
    for bar in records:
        signal = entry.on_bar_close(bar, trades_today=0)
        if signal is None:
            continue
        dates.append(pd.Timestamp(bar["session_date"]).date())
    return dates


def _entry_grid(parameters: dict) -> dict:
    return {key: values for key, values in parameters.items() if str(key).startswith("entry.params.")}


def _grid_rows(grid: dict) -> list[dict]:
    keys = list(grid)
    return [dict(zip(keys, values, strict=False)) for values in product(*(grid[key] for key in keys))]


def _annualized(count: int, sessions: int) -> float:
    if sessions <= 0:
        return 0.0
    return float(count) / (float(sessions) / 252.0)


def _all_entry_param_columns(rows: list[dict]) -> set[str]:
    return {key for row in rows for key in row if key.startswith("entry.params.")}


def _markdown(detail: pd.DataFrame, summary: pd.DataFrame, all_rows_pass: bool, full_sessions: int, limited_sessions: int) -> str:
    lines = [
        "# NQ ChartFanatics JadeCap session-liquidity FVG density audit - 2026-07-01",
        "",
        "Scope: pre-PnL signal-density check only. This audit counted completed-bar entry signals using the actual `session_liquidity_fvg_reversal` entry module. It did not inspect trade PnL, stops, targets, equity curves, WFA, monkey, Monte Carlo, or holdout results.",
        "",
        "Data:",
        "- RTH source: `data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet`",
        "- Session-level source: `data/external/nq_asia_london_session_levels_20110103_20260529.csv`",
        "- Strategy timeframe: `5m`",
        f"- Full configured sessions: `{full_sessions}`",
        f"- Limited-core proxy window: `{LIMITED_START}` through `{LIMITED_END}` (`{limited_sessions}` sessions)",
        "",
        "Gate: every declared entry-grid row must produce at least 50 signals/year in full history, at least 50 signals/year in the limited-core proxy window, and at least 50 signals in the latest 252 sessions before any staged PnL is inspected.",
        "",
        "| Variant | Rows | Pass rows | Min full/year | Min limited/year | Min latest-252 | Verdict |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in summary.to_dict("records"):
        lines.append(
            f"| `{row['variant']}` | {int(row['rows'])} | {int(row['pass_rows'])} | "
            f"{float(row['min_full_per_year']):.2f} | {float(row['min_limited_per_year']):.2f} | "
            f"{int(row['min_latest_252'])} | {row['verdict']} |"
        )
    lines.extend(
        [
            "",
            f"Decision: {'approve for staged testing' if all_rows_pass else 'reject before staged PnL'}.",
            f"Detail CSV: `{ARTIFACT_CSV}`",
            f"Summary CSV: `{SUMMARY_CSV}`",
            "",
            "Verdict: " + ("PASS" if all_rows_pass else "FAIL") + ".",
            "",
        ]
    )
    return "\n".join(lines)


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
