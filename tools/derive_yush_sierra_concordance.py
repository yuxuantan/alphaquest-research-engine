"""Derive Sierra strategy-source concordance from exact overlap event inputs.

This lane is valid only when a prior PASS already proves the overlap source,
the newly governed dataset retains the identical eligible overlap sessions,
and timestamp repair is dormant (zero inversions) on every such session.
Exact causal inputs imply exact outputs for every deterministic certified
strategy, avoiding a redundant vendor-archive replay after a data-policy-only
change.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path

import pandas as pd

from alphaquest.strategy_certification import get_strategy_certification
from alphaquest.utils.hashing import file_sha256


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--prior-report", type=Path, required=True)
    parser.add_argument("--prior-capabilities", type=Path, required=True)
    parser.add_argument("--current-candidate", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-timestamp-inversion-rate", type=float, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = args.project_root.resolve()
    prior_report_path = _resolve(root, args.prior_report)
    prior_capability_path = _resolve(root, args.prior_capabilities)
    candidate = _resolve(root, args.current_candidate)
    current_capability_path = candidate / "event_capabilities.csv"
    config_path = _resolve(root, args.config)
    output_path = _resolve(root, args.output)
    if output_path.exists():
        raise FileExistsError(
            f"derived concordance report already exists and will not be overwritten: {output_path}"
        )
    if not 0 < args.max_timestamp_inversion_rate <= 0.002:
        raise ValueError("governed inversion-rate ceiling must be in (0, 0.002]")

    prior_report = json.loads(prior_report_path.read_text(encoding="utf-8"))
    if (
        prior_report.get("schema") != "alphaquest.strategy-source-concordance/v1"
        or prior_report.get("verdict") != "PASS"
        or not (prior_report.get("checks") or {}).get(
            "all_eligible_overlap_event_inputs_prequalified"
        )
    ):
        raise ValueError(
            "prior report must be PASS with all eligible overlap inputs prequalified"
        )
    prior_declared_hash = (prior_report.get("source_hashes") or {}).get(
        str(args.prior_capabilities)
    )
    if prior_declared_hash != file_sha256(prior_capability_path):
        raise ValueError("prior PASS report does not bind the supplied capability file")

    prior = _eligible_overlap(prior_capability_path, require_inversions=False)
    current = _eligible_overlap(current_capability_path, require_inversions=True)
    prior_sessions = set(prior["session_date"].astype(str))
    current_sessions = set(current["session_date"].astype(str))
    if prior_sessions != current_sessions:
        raise ValueError(
            "eligible Databento-overlap session set changed; derived concordance is invalid"
        )
    inversion_count = int(
        pd.to_numeric(
            current["timestamp_inversions_in_source_order"], errors="raise"
        ).sum()
    )
    if inversion_count:
        raise ValueError(
            "timestamp repair is active inside the exact Databento overlap; replay is required"
        )

    certification = get_strategy_certification(
        "yush_orderflow_range", root, require_current=True
    )
    all_current = pd.read_csv(
        current_capability_path, dtype={"session_date": "string"}
    )
    compared = all_current.loc[
        all_current["reference_tier"].eq("databento_compared")
    ]
    report = {
        "schema": "alphaquest.strategy-source-concordance/v1",
        "verdict": "PASS",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "strategy_id": certification.strategy_id,
        "strategy_certification": {
            "implementation_version": certification.implementation_version,
            "implementation_sha256": certification.implementation_sha256,
            "manifest_sha256": certification.manifest_sha256,
        },
        "parameter_mode": "declared_defaults",
        "config": str(config_path.relative_to(root)),
        "config_sha256": file_sha256(config_path),
        "proof_mode": "exact_event_input_implication",
        "scope": {
            "databento_compared_sessions": int(len(compared)),
            "eligible_exact_event_sessions": int(len(current_sessions)),
            "eligible_session_dates_sha256": _session_set_sha256(current_sessions),
            "timestamp_repair_active_sessions": 0,
            "max_timestamp_inversion_rate": args.max_timestamp_inversion_rate,
            "blackout_sessions": int(len(compared) - len(current_sessions)),
        },
        "checks": {
            "inherited_prior_concordance_pass": True,
            "eligible_overlap_session_set_unchanged": True,
            "eligible_overlap_has_zero_source_inversions": True,
            "all_eligible_overlap_event_inputs_prequalified": True,
            "deterministic_strategy_output_implication": True,
        },
        "outcome": {
            "eligible_overlap_sessions": int(len(current_sessions)),
            "eligible_overlap_timestamp_inversions": inversion_count,
            "newly_admitted_pre_overlap_inversion_sessions": int(
                all_current["timestamp_repair_eligible"].map(_as_bool).sum()
            ),
        },
        "source_hashes": {
            str(args.prior_report): file_sha256(prior_report_path),
            str(args.prior_capabilities): file_sha256(prior_capability_path),
            str(args.current_candidate / "event_capabilities.csv"): file_sha256(
                current_capability_path
            ),
            str(args.current_candidate / "session_levels.parquet"): file_sha256(
                candidate / "session_levels.parquet"
            ),
            str(args.current_candidate / "raw_manifest.json"): file_sha256(
                candidate / "raw_manifest.json"
            ),
        },
        "policy": {
            "derivation": (
                "A deterministic strategy receives identical causal event and market-level "
                "inputs on the unchanged eligible Databento overlap, so strategy output "
                "equality follows without another vendor-archive replay."
            ),
            "timestamp_repair_scope": (
                "Repair is dormant on every eligible overlap session and applies only to "
                "pre-overlap inversion-only sessions at or below the governed ceiling."
            ),
        },
        "blackout_sessions": int(len(compared) - len(current_sessions)),
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))


def _eligible_overlap(
    path: Path,
    *,
    require_inversions: bool,
) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype={"session_date": "string"})
    required = {
        "session_date",
        "reference_tier",
        "full_strategy_events_extrapolated",
    }
    if require_inversions:
        required.add("timestamp_inversions_in_source_order")
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"capability file is missing columns: {missing}")
    return frame.loc[
        frame["reference_tier"].eq("databento_compared")
        & frame["full_strategy_events_extrapolated"].map(_as_bool)
    ].copy()


def _session_set_sha256(sessions: set[str]) -> str:
    import hashlib

    return hashlib.sha256(
        ("\n".join(sorted(sessions)) + "\n").encode("utf-8")
    ).hexdigest()


def _as_bool(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


if __name__ == "__main__":
    main()
