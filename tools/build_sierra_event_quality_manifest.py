from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from alphaquest.utils.hashing import file_sha256


DEFAULT_COMPARISON = Path(
    "data/reports/data_quality/ES/"
    "databento_sierra_tick_comparison_0930_1100_20250714_20260610/by_date.csv"
)
DEFAULT_PRIOR = Path(
    "data/reports/data_quality/ES/"
    "sierra_scid_event_usability_0930_1100_20101214_20260610_by_date.csv"
)
DEFAULT_OUTPUT = Path("data/reference/ES/event_quality/sierra_event_capabilities_0930_1100.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build fail-closed Sierra event capability manifest.")
    parser.add_argument("--comparison", type=Path, default=DEFAULT_COMPARISON)
    parser.add_argument("--prior-audit", type=Path, default=DEFAULT_PRIOR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def build_manifest(comparison: pd.DataFrame, prior: pd.DataFrame) -> pd.DataFrame:
    recent = comparison.copy()
    recent["session_date"] = recent["session_date"].astype(str)
    full = recent["comparison_status"].eq("DATABENTO_EVENT_EQUIVALENT")
    profile = (
        recent["payload_sequence_exact"].fillna(False)
        & recent["timestamp_all_within_1ms"].fillna(False)
        & recent["profile_volume_exact"].fillna(False)
        & recent["profile_delta_1tick_exact"].fillna(False)
        & recent["profile_delta_4tick_exact"].fillna(False)
        & recent["delta_state_transition_sequence_exact"].fillna(False)
    )
    recent_rows = pd.DataFrame(
        {
            "session_date": recent["session_date"],
            "contract": recent["sierra_contract"].astype(str),
            "reference_tier": "databento_compared",
            "minute_ohlcv": recent["minute_ohlcv_exact"].fillna(False).astype(bool),
            "profile_delta": profile.astype(bool),
            "big_trade_100ms": full.astype(bool),
            "full_strategy_events": full.astype(bool),
            "timestamp_precision_ns": 1_000_000,
            "timestamp_boundary_policy": "Databento trigger-sequence exact or reject",
            "reason": recent["failure_reason"].fillna("databento_event_equivalent"),
        }
    )

    old = prior.copy()
    old["session_date"] = old["session_date"].astype(str)
    old = old[~old["session_date"].isin(set(recent_rows["session_date"]))]
    contract_column = "contract" if "contract" in old else "sierra_contract"
    old_rows = pd.DataFrame(
        {
            "session_date": old["session_date"],
            "contract": old[contract_column].astype(str),
            "reference_tier": "structural_only_unverified",
            "minute_ohlcv": old["minute_parity_pass"].fillna(False).astype(bool),
            "profile_delta": False,
            "big_trade_100ms": False,
            "full_strategy_events": False,
            "timestamp_precision_ns": 1_000_000,
            "timestamp_boundary_policy": "unverified; event-sensitive use prohibited",
            "reason": "outside Databento overlap; sensitivity-only",
        }
    )
    return pd.concat([old_rows, recent_rows], ignore_index=True).sort_values("session_date").reset_index(drop=True)


def main() -> None:
    args = parse_args()
    comparison = pd.read_csv(args.comparison)
    prior = pd.read_csv(args.prior_audit)
    manifest = build_manifest(comparison, prior)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest.to_csv(args.output, index=False)
    metadata = {
        "verdict": "PASS",
        "scope": "Sierra ES 09:30-11:00 America/New_York event capabilities",
        "policy": "fail closed by requested capability and session date",
        "comparison": str(args.comparison),
        "comparison_sha256": file_sha256(args.comparison),
        "prior_audit": str(args.prior_audit),
        "prior_audit_sha256": file_sha256(args.prior_audit),
        "rows": int(len(manifest)),
        "full_strategy_dates": int(manifest["full_strategy_events"].sum()),
        "profile_delta_dates": int(manifest["profile_delta"].sum()),
        "minute_ohlcv_dates": int(manifest["minute_ohlcv"].sum()),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    args.output.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(manifest)} sessions)")


if __name__ == "__main__":
    main()
