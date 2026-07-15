from __future__ import annotations

import itertools
import json
from pathlib import Path
import sys

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from alphaquest.strategy_modules.entry.es_term_structure_lead_lag import EsTermStructureLeadLagEntry  # noqa: E402


CAMPAIGN_ID = "nq_term_structure_lead_lag_feedback"
SOURCE_CAMPAIGN_ID = "es_term_structure_lead_lag_feedback"
DATA_PATH = Path("data/cache/orderflow/nq_term_structure_lead_lag_1m_20100607_20260529_full_rth_ny.parquet")
VALIDATION_PATH = Path("data/cache/orderflow/nq_term_structure_lead_lag_1m_20100607_20260529_full_rth_ny.validation.json")
ARTIFACT_ROOT = Path("research_artifacts")
AUDIT_DATE = "2026-06-30"
ARTIFACT_STAMP = "20260630"
LIMITED_START = pd.Timestamp("2011-02-22").date()
LIMITED_END = pd.Timestamp("2012-09-07").date()
MIN_TOTAL_SIGNALS = 80
MIN_FULL_SIGNALS_PER_YEAR = 10.0
MIN_LIMITED_SIGNALS_PER_YEAR = 10.0


VARIANTS = [
    {
        "variant_id": "front_premium_reversion_short_1000",
        "setup_mode": "front_premium_reversion_short",
        "entry_time": "10:00:00",
        "flatten_time": "11:30:00",
        "lookback_minutes": 30,
        "allow_long": False,
        "allow_short": True,
    },
    {
        "variant_id": "front_discount_reversion_long_1000",
        "setup_mode": "front_discount_reversion_long",
        "entry_time": "10:00:00",
        "flatten_time": "11:30:00",
        "lookback_minutes": 30,
        "allow_long": True,
        "allow_short": False,
    },
    {
        "variant_id": "late_morning_two_sided_spread_feedback_1130",
        "setup_mode": "two_sided_spread_feedback",
        "entry_time": "11:30:00",
        "flatten_time": "13:00:00",
        "lookback_minutes": 15,
        "allow_long": True,
        "allow_short": True,
    },
    {
        "variant_id": "afternoon_confirmed_spread_feedback_1400",
        "setup_mode": "two_sided_confirmed_feedback",
        "entry_time": "14:00:00",
        "flatten_time": "15:30:00",
        "lookback_minutes": 30,
        "allow_long": True,
        "allow_short": True,
    },
    {
        "variant_id": "late_day_two_sided_spread_feedback_1530",
        "setup_mode": "two_sided_spread_feedback",
        "entry_time": "15:30:00",
        "flatten_time": "15:55:00",
        "lookback_minutes": 30,
        "allow_long": True,
        "allow_short": True,
    },
]


ENTRY_GRID = {
    "min_front_return_bps": [4.0, 6.0, 8.0],
    "min_spread_gap_bps": [0.5, 1.0, 1.5],
}


def main() -> None:
    bars = _load_bars(DATA_PATH)
    sessions = sorted(bars["session_date"].dropna().unique())
    if not sessions:
        raise SystemExit(f"No sessions found in {DATA_PATH}.")
    validation = json.loads(VALIDATION_PATH.read_text()) if VALIDATION_PATH.exists() else {}

    rows = []
    for variant in VARIANTS:
        for min_front_return_bps, min_spread_gap_bps in itertools.product(
            ENTRY_GRID["min_front_return_bps"],
            ENTRY_GRID["min_spread_gap_bps"],
        ):
            params = {
                **variant,
                "bar_interval_minutes": 1,
                "max_trades_per_day": 1,
                "min_front_return_bps": min_front_return_bps,
                "min_spread_gap_bps": min_spread_gap_bps,
                "stop_pct": 0.0015,
                "target_r_multiple": 1.5,
            }
            signal_dates = _signal_dates(bars, params)
            full_count = len(signal_dates)
            limited_count = sum(LIMITED_START <= day <= LIMITED_END for day in signal_dates)
            latest_count = sum(day in set(sessions[-40:]) for day in signal_dates)
            full_per_year = _per_year(full_count, sessions[0], sessions[-1])
            limited_per_year = _per_year(limited_count, LIMITED_START, LIMITED_END)
            pass_gate = (
                full_count >= MIN_TOTAL_SIGNALS
                and full_per_year >= MIN_FULL_SIGNALS_PER_YEAR
                and limited_per_year >= MIN_LIMITED_SIGNALS_PER_YEAR
            )
            rows.append(
                {
                    "campaign_id": CAMPAIGN_ID,
                    "source_campaign_id": SOURCE_CAMPAIGN_ID,
                    "variant_id": variant["variant_id"],
                    "setup_mode": variant["setup_mode"],
                    "entry_time": variant["entry_time"],
                    "flatten_time": variant["flatten_time"],
                    "lookback_minutes": variant["lookback_minutes"],
                    "allow_long": variant["allow_long"],
                    "allow_short": variant["allow_short"],
                    "min_front_return_bps": min_front_return_bps,
                    "min_spread_gap_bps": min_spread_gap_bps,
                    "full_start_date": str(sessions[0]),
                    "full_end_date": str(sessions[-1]),
                    "eligible_sessions": len(sessions),
                    "full_signals": full_count,
                    "full_signals_per_year": full_per_year,
                    "limited_start_date": str(LIMITED_START),
                    "limited_end_date": str(LIMITED_END),
                    "limited_signals": limited_count,
                    "limited_signals_per_year": limited_per_year,
                    "latest_40_eligible_start_date": str(sessions[-40]),
                    "latest_40_eligible_end_date": str(sessions[-1]),
                    "latest_40_eligible_signals": latest_count,
                    "density_gate_pass": pass_gate,
                }
            )

    detail = pd.DataFrame(rows)
    summary = _summary(detail)
    machine_summary = _machine_summary(detail, summary, sessions, validation)

    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    detail_path = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.csv"
    summary_path = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_summary_{ARTIFACT_STAMP}.csv"
    markdown_path = ARTIFACT_ROOT / f"{CAMPAIGN_ID}_density_audit_{ARTIFACT_STAMP}.md"
    detail.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)
    markdown_path.write_text(_markdown(summary, machine_summary, detail_path, summary_path), encoding="utf-8")
    print(json.dumps(machine_summary, indent=2, sort_keys=True))


def _load_bars(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"NQ term-structure cache not found: {path}")
    bars = pd.read_parquet(path)
    bars = bars.sort_values("timestamp").reset_index(drop=True)
    bars["timestamp"] = pd.to_datetime(bars["timestamp"])
    bars["session_date"] = bars["timestamp"].dt.date
    bars["is_rth"] = True
    return bars


def _signal_dates(bars: pd.DataFrame, params: dict) -> list:
    entry = EsTermStructureLeadLagEntry(params)
    dates = []
    for row in bars.itertuples(index=False):
        signal = entry.on_bar_close(pd.Series(row._asdict()), trades_today=0)
        if signal is not None:
            dates.append(row.session_date)
    return dates


def _summary(detail: pd.DataFrame) -> pd.DataFrame:
    return (
        detail.sort_values(
            ["density_gate_pass", "full_signals_per_year", "limited_signals_per_year", "full_signals"],
            ascending=[False, False, False, False],
        )
        .groupby("variant_id", as_index=False, sort=False)
        .head(1)
        .sort_values(["density_gate_pass", "full_signals_per_year"], ascending=[False, False])
        .reset_index(drop=True)
    )


def _machine_summary(
    detail: pd.DataFrame,
    summary: pd.DataFrame,
    sessions: list,
    validation: dict,
) -> dict:
    return {
        "campaign_id": CAMPAIGN_ID,
        "source_campaign_id": SOURCE_CAMPAIGN_ID,
        "audit_date": AUDIT_DATE,
        "decision": "PASS" if bool(detail["density_gate_pass"].any()) else "FAIL",
        "reason": (
            "At least one fixed variant/entry-grid row met the pre-PnL density gate."
            if bool(detail["density_gate_pass"].any())
            else "No fixed variant/entry-grid row met total, full-period, and limited-period signal density gates."
        ),
        "data_path": str(DATA_PATH),
        "validation_path": str(VALIDATION_PATH),
        "eligible_sessions": len(sessions),
        "full_start_date": str(sessions[0]),
        "full_end_date": str(sessions[-1]),
        "density_gate": {
            "min_total_signals": MIN_TOTAL_SIGNALS,
            "min_full_signals_per_year": MIN_FULL_SIGNALS_PER_YEAR,
            "min_limited_signals_per_year": MIN_LIMITED_SIGNALS_PER_YEAR,
            "limited_start_date": str(LIMITED_START),
            "limited_end_date": str(LIMITED_END),
        },
        "rows_tested": int(len(detail)),
        "rows_passing": int(detail["density_gate_pass"].sum()),
        "best_rows": summary.head(5).to_dict(orient="records"),
        "cache_validation": validation.get("validation", validation),
    }


def _markdown(
    summary: pd.DataFrame,
    machine_summary: dict,
    detail_path: Path,
    summary_path: Path,
) -> str:
    lines = [
        f"# {CAMPAIGN_ID} Density Audit",
        "",
        f"Date: {AUDIT_DATE}",
        "",
        f"Decision: {machine_summary['decision']}",
        "",
        "This is a pre-PnL density audit. It counts only signal availability from completed front-vs-next-contract NQ feature rows. It does not inspect stops, targets, trade outcomes, or equity.",
        "",
        "## Gate",
        "",
        f"- Minimum total signals: {MIN_TOTAL_SIGNALS}",
        f"- Minimum full-period signals/year: {MIN_FULL_SIGNALS_PER_YEAR}",
        f"- Minimum limited-period signals/year: {MIN_LIMITED_SIGNALS_PER_YEAR}",
        f"- Limited period: {LIMITED_START} to {LIMITED_END}",
        "",
        "## Data",
        "",
        f"- Feature cache: `{DATA_PATH}`",
        f"- Validation: `{VALIDATION_PATH}`",
        f"- Eligible sessions: {machine_summary['eligible_sessions']}",
        f"- Full period: {machine_summary['full_start_date']} to {machine_summary['full_end_date']}",
        f"- Cache validation: `{machine_summary['cache_validation']}`",
        "",
        "## Best Row Per Variant",
        "",
        _markdown_table(summary),
        "",
        "## Artifacts",
        "",
        f"- Detail CSV: `{detail_path}`",
        f"- Summary CSV: `{summary_path}`",
        "",
    ]
    return "\n".join(lines)


def _markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_No rows._"
    out = df.copy()
    out = out.astype(str)
    columns = list(out.columns)
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in out.itertuples(index=False):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def _per_year(count: int, start_date, end_date) -> float:
    years = max((pd.Timestamp(end_date) - pd.Timestamp(start_date)).days / 365.25, 1e-9)
    return float(count) / years


if __name__ == "__main__":
    main()
