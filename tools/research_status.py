from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3

from propstack.research.registry import registry_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the institutional research registry.")
    parser.add_argument("--database", default="catalogs/research_registry.sqlite")
    parser.add_argument("--state", choices=("active", "review_queue", "candidate", "closed"))
    parser.add_argument("--campaign")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    database = Path(args.database)
    if not database.is_file():
        raise SystemExit(f"registry missing: {database}; run `make research-registry`")

    if args.campaign:
        payload = _campaign(database, args.campaign, args.limit)
    elif args.state:
        payload = _campaigns(database, args.state, args.limit)
    else:
        payload = registry_summary(database)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print(payload)
    return 0


def _campaigns(database: Path, state: str, limit: int) -> list[dict[str, object]]:
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT campaign_id, lifecycle_state, authored_decision, run_count,
                   variant_count, latest_updated_at
            FROM campaigns WHERE lifecycle_state = ?
            ORDER BY COALESCE(latest_updated_at, '') DESC, campaign_id LIMIT ?
            """,
            (state, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def _campaign(database: Path, campaign_id: str, limit: int) -> dict[str, object]:
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        campaign = connection.execute("SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,)).fetchone()
        if not campaign:
            raise SystemExit(f"unknown campaign: {campaign_id}")
        runs = connection.execute(
            """
            SELECT run_uid, variant_id, test_run_id, verdict, failed_stage, updated_at, summary_path
            FROM runs WHERE campaign_id = ?
            ORDER BY COALESCE(updated_at, '') DESC LIMIT ?
            """,
            (campaign_id, limit),
        ).fetchall()
    return {"campaign": dict(campaign), "runs": [dict(row) for row in runs]}


def _print(payload: object) -> None:
    if isinstance(payload, list):
        for row in payload:
            print(" | ".join(f"{key}={value}" for key, value in row.items()))
        return
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
