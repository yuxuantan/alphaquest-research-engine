"""Count v02 mechanics paths without reporting or selecting on PnL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import yaml

from alphaquest.strategy_modules.event.runner import (
    iter_event_sessions,
    replay_event_sessions_parallel,
)


DIAGNOSTIC_FIELDS = (
    "failed_auction_episodes",
    "failed_auction_expired",
    "failed_auction_insufficient_excursion",
    "failed_auction_missing_aggression",
    "failed_auction_reclaims",
    "failed_auction_orders",
    "failed_auction_fill_rejections",
    "failed_auction_time_exits",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--set", action="append", default=[], metavar="NAME=JSON_VALUE")
    args = parser.parse_args()

    path = Path(args.config)
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    event = ((config.get("strategy") or {}).get("event") or {}).get("params")
    mechanics = (
        (((config.get("strategy") or {}).get("entry") or {}).get("params") or {})
        .get("mechanics")
    )
    if not isinstance(event, dict) or not isinstance(mechanics, dict):
        raise ValueError("diagnostic requires mirrored certified event mechanics")

    overrides: dict[str, Any] = {}
    for raw in args.set:
        name, separator, encoded = raw.partition("=")
        if not separator or name not in event or name not in mechanics:
            raise ValueError(f"unknown or malformed certified event override: {raw}")
        value = json.loads(encoded)
        event[name] = value
        mechanics[name] = value
        overrides[name] = value

    subset = {"start_date": args.start_date, "end_date": args.end_date}
    result = replay_event_sessions_parallel(
        config,
        iter_event_sessions(config, subset),
        workers=max(1, int(args.workers)),
    )
    audits = result["session_audits"]
    diagnostics = {
        field: int(audits[field].sum()) if field in audits else 0
        for field in DIAGNOSTIC_FIELDS
    }
    print(
        json.dumps(
            {
                "schema": "alphaquest.failed-auction-frequency-diagnostic/v1",
                "diagnostic_only": True,
                "pnl_inspected": False,
                "config": str(path.resolve()),
                "data_subset": subset,
                "overrides": overrides,
                "sessions": int(len(audits)),
                "trades": int(len(result["trades"])),
                "diagnostics": diagnostics,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
