"""Benchmark the result-invariant canonical-event core-grid executor.

This is a diagnostic runtime tool. It does not create campaign evidence and
disables exact-result cache reads/writes so repeated measurements remain honest.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

import pandas as pd
import yaml

from alphaquest.research.core_grid import (
    _run_batched_event_core_grid,
    parameter_combinations,
)
from alphaquest.strategy_certification import get_strategy_certification
from alphaquest.utils.params import apply_dotted_params


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--max-combinations", type=int, default=100)
    parser.add_argument("--project-sessions", type=int, default=365)
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text(encoding="utf-8")) or {}
    strategy_id = str((((config.get("strategy") or {}).get("event") or {}).get("module") or ""))
    certification = get_strategy_certification(strategy_id, require_current=True)
    identity = certification.public_record()
    config["strategy_certification"] = {
        key: identity[key]
        for key in (
            "strategy_id",
            "implementation_version",
            "implementation_sha256",
            "manifest_sha256",
        )
    }
    parameters = dict((config.get("core_grid") or {}).get("parameters") or {})
    combinations = parameter_combinations(parameters)[: max(1, int(args.max_combinations))]
    # Validate every selected combination against the current certification
    # before starting the timed section.
    for combination in combinations:
        apply_dotted_params(config, combination)

    session_dates = [
        value.date().isoformat()
        for value in pd.date_range(args.start_date, args.end_date, freq="B")
    ]
    market = pd.DataFrame({"session_date": session_dates})
    started = time.perf_counter()
    _results, metadata = _run_batched_event_core_grid(
        market,
        config,
        config.get("benchmarks") or {},
        combinations,
        workers=max(1, int(args.workers)),
        include_reports=False,
        grid_config={
            **dict(config.get("core_grid") or {}),
            "event_replay_result_cache": False,
        },
    )
    elapsed = time.perf_counter() - started
    measured_sessions = max(len(session_dates), 1)
    projected_sessions = max(1, int(args.project_sessions))
    measured_parallelism = min(max(1, int(args.workers)), measured_sessions)
    projected_parallelism = min(max(1, int(args.workers)), projected_sessions)
    projected = (
        elapsed
        * projected_sessions
        / measured_sessions
        * measured_parallelism
        / projected_parallelism
    )
    print(
        json.dumps(
            {
                "schema": "alphaquest.event-core-grid-benchmark/v1",
                "diagnostic_only": True,
                "config": str(Path(args.config).resolve()),
                "start_date": args.start_date,
                "end_date": args.end_date,
                "requested_sessions": measured_sessions,
                "combinations": len(combinations),
                "workers": max(1, int(args.workers)),
                "elapsed_seconds": elapsed,
                "projected_sessions": projected_sessions,
                "projected_elapsed_seconds": projected,
                "projected_under_one_hour": projected < 3600.0,
                "execution": metadata,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
