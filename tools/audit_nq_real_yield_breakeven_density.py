from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml


CAMPAIGN_ID = "nq_real_yield_breakeven_state"
ARTIFACT_STAMP = "20260630"
FEATURE_CSV = Path("data/external/nq_real_yield_breakeven_features_20110103_20260612.csv")
VARIANT_ROOT = Path("campaigns") / CAMPAIGN_ID / "variants"
ARTIFACT_ROOT = Path("research_artifacts")
DETAIL_CSV = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.csv"
SUMMARY_CSV = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_summary_{ARTIFACT_STAMP}.csv"
AUDIT_MD = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.md"

LIMITED_START = pd.Timestamp("2011-02-22").date()
LIMITED_END = pd.Timestamp("2012-09-07").date()
MIN_FULL_SIGNALS_PER_YEAR = 50.0
MIN_LIMITED_SIGNALS_PER_YEAR = 50.0
MIN_LATEST_252_SIGNALS = 50


def main() -> None:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    features = _load_features()
    detail = _build_detail(features)
    summary = _build_summary(detail)
    detail.to_csv(DETAIL_CSV, index=False)
    summary.to_csv(SUMMARY_CSV, index=False)
    AUDIT_MD.write_text(_markdown(detail, summary), encoding="utf-8")
    print(f"{CAMPAIGN_ID}: density rows passing {int(detail['density_gate_pass'].sum())}/{len(detail)}")
    print(f"detail={DETAIL_CSV}")
    print(f"summary={SUMMARY_CSV}")
    print(f"audit={AUDIT_MD}")


def _load_features() -> pd.DataFrame:
    df = pd.read_csv(FEATURE_CSV)
    df["session_date"] = pd.to_datetime(df["session_date"]).dt.date
    return df.sort_values("session_date", kind="mergesort").reset_index(drop=True)


def _build_detail(features: pd.DataFrame) -> pd.DataFrame:
    session_dates = list(features["session_date"])
    full_years = len(session_dates) / 252.0
    limited_dates = {d for d in session_dates if LIMITED_START <= d <= LIMITED_END}
    limited_years = len(limited_dates) / 252.0
    latest_dates = set(session_dates[-252:])
    rows = []
    for cfg_path in sorted(VARIANT_ROOT.glob("*/config.yaml")):
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        variant_id = cfg["variant_id"]
        params = cfg["strategy"]["entry"]["params"]
        rank_column = params["rank_column"]
        direction_mode = params["direction_mode"]
        for threshold in cfg["core_grid"]["parameters"]["entry.params.state_rank_threshold"]:
            signal_dates = _signal_dates(features, rank_column, direction_mode, float(threshold))
            full_signals = len(signal_dates)
            limited_signals = sum(d in limited_dates for d in signal_dates)
            latest_signals = sum(d in latest_dates for d in signal_dates)
            full_rate = full_signals / full_years if full_years else 0.0
            limited_rate = limited_signals / limited_years if limited_years else 0.0
            density_gate_pass = (
                full_rate >= MIN_FULL_SIGNALS_PER_YEAR
                and limited_rate >= MIN_LIMITED_SIGNALS_PER_YEAR
                and latest_signals >= MIN_LATEST_252_SIGNALS
            )
            rows.append(
                {
                    "campaign_id": CAMPAIGN_ID,
                    "variant_id": variant_id,
                    "rank_column": rank_column,
                    "direction_mode": direction_mode,
                    "state_rank_threshold": float(threshold),
                    "full_signals": full_signals,
                    "full_signals_per_year": full_rate,
                    "limited_core_start": LIMITED_START.isoformat(),
                    "limited_core_end": LIMITED_END.isoformat(),
                    "limited_core_signals": limited_signals,
                    "limited_core_signals_per_year": limited_rate,
                    "latest_252_signals": latest_signals,
                    "density_gate_pass": bool(density_gate_pass),
                }
            )
    return pd.DataFrame(rows).sort_values(["variant_id", "state_rank_threshold"])


def _signal_dates(features: pd.DataFrame, rank_column: str, direction_mode: str, threshold: float) -> set:
    rank = features[rank_column].astype(float)
    low_tail = 1.0 - threshold
    if direction_mode.startswith("high_"):
        condition = rank >= threshold
    elif direction_mode.startswith("low_"):
        condition = rank <= low_tail
    elif direction_mode == "two_sided_high_short":
        condition = (rank >= threshold) | (rank <= low_tail)
    else:
        raise ValueError(f"Unsupported direction_mode: {direction_mode}")
    return set(features.loc[condition, "session_date"])


def _build_summary(detail: pd.DataFrame) -> pd.DataFrame:
    summary = (
        detail.groupby("variant_id")
        .agg(
            declared_entry_rows=("density_gate_pass", "size"),
            passing_entry_rows=("density_gate_pass", "sum"),
            min_full_signals_per_year=("full_signals_per_year", "min"),
            min_limited_core_signals_per_year=("limited_core_signals_per_year", "min"),
            min_latest_252_signals=("latest_252_signals", "min"),
        )
        .reset_index()
    )
    summary["variant_density_gate_pass"] = summary["passing_entry_rows"].eq(summary["declared_entry_rows"])
    summary["verdict"] = summary["variant_density_gate_pass"].map({True: "PASS", False: "FAIL"})
    return summary.sort_values(["variant_density_gate_pass", "variant_id"], ascending=[False, True])


def _markdown(detail: pd.DataFrame, summary: pd.DataFrame) -> str:
    all_rows_pass = bool(detail["density_gate_pass"].all())
    all_variants_pass = bool(summary["variant_density_gate_pass"].all())
    verdict = "PASS" if all_rows_pass and all_variants_pass else "FAIL"
    lines = [
        f"# {CAMPAIGN_ID} density audit",
        "",
        f"Verdict: {verdict}.",
        "",
        "This is a pre-PnL density audit. It counts only signal availability from lagged real-yield/breakeven feature rows whose observation date is strictly before the NQ session date. It does not inspect stops, targets, trade outcomes, WFA, Monte Carlo, or prop-rule results.",
        "",
        f"- Detail CSV: `{DETAIL_CSV}`",
        f"- Summary CSV: `{SUMMARY_CSV}`",
        f"- Full-history threshold: >= {MIN_FULL_SIGNALS_PER_YEAR:.0f} signals/year",
        f"- Limited-core window: {LIMITED_START.isoformat()} through {LIMITED_END.isoformat()}, threshold >= {MIN_LIMITED_SIGNALS_PER_YEAR:.0f} signals/year",
        f"- Latest-252 threshold: >= {MIN_LATEST_252_SIGNALS} signals",
        f"- Density rows passing: {int(detail['density_gate_pass'].sum())}/{len(detail)}",
        f"- Variants passing all declared rows: {int(summary['variant_density_gate_pass'].sum())}/{len(summary)}",
        "",
        "| variant | rows | pass rows | min full/year | min limited/year | min latest 252 | verdict |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary.to_dict("records"):
        lines.append(
            "| {variant_id} | {declared_entry_rows} | {passing_entry_rows} | "
            "{min_full_signals_per_year:.2f} | {min_limited_core_signals_per_year:.2f} | "
            "{min_latest_252_signals} | {verdict} |".format(**row)
        )
    lines.append("")
    if verdict == "FAIL":
        lines.append("Conclusion: reject before staged PnL. The declared family does not clear the opportunity-count gate.")
    else:
        lines.append("Conclusion: density is sufficient to proceed to preflight and staged validation. This is not evidence of profitability.")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
