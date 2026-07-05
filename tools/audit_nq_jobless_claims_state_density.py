from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


DEFAULT_FEATURES = "data/external/nq_jobless_claims_state_features_20110103_20260612.csv"
DEFAULT_DETAIL = "research_artifacts/nq_jobless_claims_state_density_audit_20260701.csv"
DEFAULT_SUMMARY = "research_artifacts/nq_jobless_claims_state_density_summary_20260701.csv"
DEFAULT_MD = "research_artifacts/nq_jobless_claims_state_density_audit_20260701.md"


@dataclass(frozen=True)
class Variant:
    variant_id: str
    setup_mode: str
    direction: str
    threshold_name: str
    thresholds: tuple[float, ...]
    rank_column: str


VARIANTS = [
    Variant("claims_low_long_1000", "claims_low_long", "long", "rank_max", (0.35, 0.40, 0.45), "initial_claims_4w_rank_156w"),
    Variant("claims_rising_short_1030", "claims_rising_short", "short", "rank_min", (0.55, 0.60, 0.65), "initial_claims_4w_change_4w_rank_156w"),
    Variant("claims_improving_long_1130", "claims_improving_long", "long", "rank_max", (0.35, 0.40, 0.45), "initial_claims_4w_change_1w_rank_156w"),
    Variant("continued_claims_rising_short_1200", "continued_claims_rising_short", "short", "rank_min", (0.50, 0.55, 0.60), "continued_claims_4w_change_1w_rank_156w"),
    Variant("continued_claims_improving_long_1330", "continued_claims_improving_long", "long", "rank_max", (0.35, 0.40, 0.45), "continued_claims_4w_change_4w_rank_156w"),
]


WINDOWS = {
    "full": ("2011-01-03", "2026-06-12"),
    "limited_core_proxy": ("2011-02-10", "2012-04-05"),
    "latest_year_proxy": ("2025-06-13", "2026-06-12"),
}


def audit(
    features_path: str | Path = DEFAULT_FEATURES,
    *,
    detail_path: str | Path = DEFAULT_DETAIL,
    summary_path: str | Path = DEFAULT_SUMMARY,
    md_path: str | Path = DEFAULT_MD,
    min_trades_per_year: float = 50.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    features = pd.read_csv(features_path)
    features["session_date"] = pd.to_datetime(features["session_date"])
    rows = []
    for variant in VARIANTS:
        for threshold in variant.thresholds:
            mask = _signal_mask(features, variant, threshold)
            for window_name, (start, end) in WINDOWS.items():
                window = features[
                    (features["session_date"] >= pd.Timestamp(start))
                    & (features["session_date"] <= pd.Timestamp(end))
                ]
                signals = int(mask.loc[window.index].sum())
                years = max((pd.Timestamp(end) - pd.Timestamp(start)).days / 365.25, 1 / 365.25)
                signals_per_year = signals / years
                rows.append(
                    {
                        "variant_id": variant.variant_id,
                        "setup_mode": variant.setup_mode,
                        "direction": variant.direction,
                        "threshold_name": variant.threshold_name,
                        "threshold": threshold,
                        "rank_column": variant.rank_column,
                        "window": window_name,
                        "start_date": start,
                        "end_date": end,
                        "signals": signals,
                        "signals_per_year": signals_per_year,
                        "density_pass": signals_per_year >= min_trades_per_year,
                    }
                )
    detail = pd.DataFrame(rows)
    summary = (
        detail.groupby("variant_id", as_index=False)
        .agg(
            rows=("density_pass", "size"),
            pass_rows=("density_pass", "sum"),
            min_signals_per_year=("signals_per_year", "min"),
            max_signals_per_year=("signals_per_year", "max"),
        )
        .sort_values("variant_id", kind="mergesort")
    )
    summary["variant_pass"] = summary["pass_rows"] == summary["rows"]

    Path(detail_path).parent.mkdir(parents=True, exist_ok=True)
    detail.to_csv(detail_path, index=False, quoting=csv.QUOTE_MINIMAL)
    summary.to_csv(summary_path, index=False, quoting=csv.QUOTE_MINIMAL)
    md_lines = [
        "# NQ Jobless Claims State Density Audit",
        "",
        "Pre-PnL signal-density screen only. No trade PnL, stops, targets, or equity curves were inspected.",
        "",
        f"- Detail CSV: `{detail_path}`",
        f"- Summary CSV: `{summary_path}`",
        f"- Feature CSV: `{features_path}`",
        f"- Density pass rows: {int(detail['density_pass'].sum())}/{len(detail)}",
        f"- Passing variants: {int(summary['variant_pass'].sum())}/{len(summary)}",
        f"- Minimum required signals per year: {min_trades_per_year}",
        "",
        "| Variant | Rows Passed | Min Signals/Yr | Max Signals/Yr | Verdict |",
        "|---|---:|---:|---:|---|",
    ]
    for row in summary.to_dict("records"):
        md_lines.append(
            "| {variant_id} | {pass_rows}/{rows} | {min_signals_per_year:.6f} | {max_signals_per_year:.6f} | {verdict} |".format(
                variant_id=row["variant_id"],
                pass_rows=int(row["pass_rows"]),
                rows=int(row["rows"]),
                min_signals_per_year=float(row["min_signals_per_year"]),
                max_signals_per_year=float(row["max_signals_per_year"]),
                verdict="PASS" if row["variant_pass"] else "FAIL",
            )
        )
    Path(md_path).write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return detail, summary


def _signal_mask(features: pd.DataFrame, variant: Variant, threshold: float) -> pd.Series:
    values = features[variant.rank_column]
    if variant.threshold_name == "rank_min":
        return values >= threshold
    return values <= threshold


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--features", default=DEFAULT_FEATURES)
    parser.add_argument("--detail", default=DEFAULT_DETAIL)
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    parser.add_argument("--md", default=DEFAULT_MD)
    parser.add_argument("--min-trades-per-year", type=float, default=50.0)
    args = parser.parse_args()
    detail, summary = audit(
        args.features,
        detail_path=args.detail,
        summary_path=args.summary,
        md_path=args.md,
        min_trades_per_year=args.min_trades_per_year,
    )
    print(f"wrote {args.detail}")
    print(f"wrote {args.summary}")
    print(f"wrote {args.md}")
    print(
        f"pass_rows={int(detail['density_pass'].sum())}/{len(detail)} "
        f"passing_variants={int(summary['variant_pass'].sum())}/{len(summary)}"
    )


if __name__ == "__main__":
    main()
