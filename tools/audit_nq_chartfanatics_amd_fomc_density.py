from __future__ import annotations

import itertools
from pathlib import Path

import pandas as pd
import yaml

from alphaquest.strategy_modules.entry.macro_event_amd_distribution import MacroEventAmdDistributionEntry


CAMPAIGN_ID = "nq_chartfanatics_amd_fomc_distribution"
ARTIFACT_STAMP = "20260701"
VARIANT_ROOT = Path("campaigns") / CAMPAIGN_ID / "variants"
ARTIFACT_ROOT = Path("research_artifacts")
DETAIL_CSV = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.csv"
SUMMARY_CSV = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_summary_{ARTIFACT_STAMP}.csv"
AUDIT_MD = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.md"
BAR_CACHE = Path("data/cache/orderflow/nq_sierra_trade_orderflow_1m_20110103_20260612_full_rth_ny.parquet")
FOMC_CALENDAR = Path("data/external/fomc_scheduled_decision_dates_20110101_20260609.csv")
LIMITED_START = pd.Timestamp("2011-02-22").date()
LIMITED_END = pd.Timestamp("2012-09-07").date()
MIN_SIGNALS_PER_YEAR = 5.0


def main() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    bars, all_session_dates = _load_event_bars()
    detail = _build_detail(bars, all_session_dates)
    summary = _build_summary(detail)
    detail.to_csv(DETAIL_CSV, index=False)
    summary.to_csv(SUMMARY_CSV, index=False)
    AUDIT_MD.write_text(_markdown(detail, summary), encoding="utf-8")
    print(f"{CAMPAIGN_ID}: density rows passing {int(detail['density_gate_pass'].sum())}/{len(detail)}")
    print(f"detail={DETAIL_CSV}")
    print(f"summary={SUMMARY_CSV}")
    print(f"audit={AUDIT_MD}")


def _load_event_bars() -> tuple[pd.DataFrame, list]:
    event_dates = _fomc_dates()
    df = pd.read_parquet(BAR_CACHE)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["session_date"] = df["timestamp"].dt.date
    if "is_rth" not in df.columns:
        df["is_rth"] = True
    df = df[df.get("is_rth", True).astype(bool)].copy()
    all_session_dates = sorted(set(df["session_date"]))
    event_df = df[df["session_date"].isin(event_dates)].copy()
    return event_df.sort_values(["timestamp"], kind="mergesort").reset_index(drop=True), all_session_dates


def _fomc_dates() -> set:
    cal = pd.read_csv(FOMC_CALENDAR)
    cal = cal[cal.get("scheduled", True).astype(str).str.lower().eq("true")]
    return set(pd.to_datetime(cal["event_date"]).dt.date)


def _build_detail(bars: pd.DataFrame, all_session_dates: list) -> pd.DataFrame:
    full_years = _year_count(pd.Series(all_session_dates))
    limited_dates = {d for d in all_session_dates if LIMITED_START <= d <= LIMITED_END}
    limited_years = len(limited_dates) / 252.0 if limited_dates else 0.0
    latest_cutoff = (pd.Timestamp(max(all_session_dates)) - pd.Timedelta(days=365)).date()
    latest_dates = {d for d in all_session_dates if d >= latest_cutoff}
    rows = []
    for cfg_path in sorted(VARIANT_ROOT.glob("*/config.yaml")):
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        variant_id = cfg["variant_id"]
        params = dict(cfg["strategy"]["entry"]["params"])
        grid = cfg["core_grid"]["parameters"]
        for min_sweep_ticks, min_displacement_ticks in itertools.product(
            grid["entry.params.min_sweep_ticks"],
            grid["entry.params.min_displacement_ticks"],
        ):
            test_params = dict(params)
            test_params["min_sweep_ticks"] = float(min_sweep_ticks)
            test_params["min_displacement_ticks"] = float(min_displacement_ticks)
            signal_dates = _signal_dates(bars, test_params)
            full_signals = len(signal_dates)
            limited_signals = sum(d in limited_dates for d in signal_dates)
            latest_signals = sum(d in latest_dates for d in signal_dates)
            full_rate = full_signals / full_years if full_years else 0.0
            limited_rate = limited_signals / limited_years if limited_years else 0.0
            rows.append(
                {
                    "campaign_id": CAMPAIGN_ID,
                    "variant_id": variant_id,
                    "setup_mode": params["setup_mode"],
                    "accumulation_start_time": params["accumulation_start_time"],
                    "accumulation_end_time": params["accumulation_end_time"],
                    "signal_start_time": params["signal_start_time"],
                    "last_entry_time": params["last_entry_time"],
                    "displacement_reference": params["displacement_reference"],
                    "min_sweep_ticks": float(min_sweep_ticks),
                    "min_displacement_ticks": float(min_displacement_ticks),
                    "signals": full_signals,
                    "signals_per_year": full_rate,
                    "limited_core_start": LIMITED_START.isoformat(),
                    "limited_core_end": LIMITED_END.isoformat(),
                    "limited_core_signals": limited_signals,
                    "limited_core_signals_per_year": limited_rate,
                    "latest_365d_signals": latest_signals,
                    "density_gate_pass": bool(full_rate >= MIN_SIGNALS_PER_YEAR),
                }
            )
    return pd.DataFrame(rows).sort_values(["variant_id", "min_sweep_ticks", "min_displacement_ticks"])


def _signal_dates(bars: pd.DataFrame, params: dict) -> set:
    entry = MacroEventAmdDistributionEntry(params)
    out = set()
    for row in bars.to_dict("records"):
        signal = entry.on_bar_close(pd.Series(row), trades_today=0)
        if signal is not None:
            out.add(pd.Timestamp(row["session_date"]).date())
    return out


def _build_summary(detail: pd.DataFrame) -> pd.DataFrame:
    summary = (
        detail.groupby("variant_id")
        .agg(
            declared_entry_rows=("density_gate_pass", "size"),
            passing_entry_rows=("density_gate_pass", "sum"),
            min_signals_per_year=("signals_per_year", "min"),
            min_limited_core_signals_per_year=("limited_core_signals_per_year", "min"),
            min_latest_365d_signals=("latest_365d_signals", "min"),
            max_signals=("signals", "max"),
        )
        .reset_index()
    )
    summary["variant_density_gate_pass"] = summary["passing_entry_rows"].eq(summary["declared_entry_rows"])
    summary["verdict"] = summary["variant_density_gate_pass"].map({True: "PASS", False: "FAIL"})
    return summary.sort_values(["variant_density_gate_pass", "variant_id"], ascending=[False, True])


def _year_count(session_dates: pd.Series) -> float:
    unique = pd.Series(sorted(set(session_dates)))
    return len(unique) / 252.0 if len(unique) else 0.0


def _markdown(detail: pd.DataFrame, summary: pd.DataFrame) -> str:
    verdict = "PASS" if bool(detail["density_gate_pass"].all()) else "FAIL"
    lines = [
        f"# {CAMPAIGN_ID} density audit",
        "",
        f"Verdict: {verdict}.",
        "",
        "This is a pre-PnL density audit. It counts only scheduled FOMC decision dates and completed NQ RTH bars through each configured signal window. It does not inspect stops, targets, trade outcomes, WFA, Monte Carlo, or prop-rule results.",
        "",
        f"- Detail CSV: `{DETAIL_CSV}`",
        f"- Summary CSV: `{SUMMARY_CSV}`",
        f"- FOMC calendar: `{FOMC_CALENDAR}`",
        f"- NQ bar cache: `{BAR_CACHE}`",
        f"- Sparse-event threshold: >= {MIN_SIGNALS_PER_YEAR:.0f} signals/year for every declared entry row",
        f"- Density rows passing: {int(detail['density_gate_pass'].sum())}/{len(detail)}",
        f"- Variants passing all declared rows: {int(summary['variant_density_gate_pass'].sum())}/{len(summary)}",
        "",
        "| variant | rows | pass rows | min signals/year | min limited/year | min latest 365d | verdict |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary.to_dict("records"):
        lines.append(
            "| {variant_id} | {declared_entry_rows} | {passing_entry_rows} | "
            "{min_signals_per_year:.2f} | {min_limited_core_signals_per_year:.2f} | "
            "{min_latest_365d_signals} | {verdict} |".format(**row)
        )
    lines.append("")
    if verdict == "FAIL":
        lines.append("Conclusion: reject before staged PnL. Do not drop sparse variants or loosen thresholds without an explicit rescue authorization.")
    else:
        lines.append("Conclusion: density is sufficient to proceed to preflight and staged validation. This is not evidence of profitability.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
