from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
import sys
from typing import Any, Iterable

import yaml

from propstack.research.campaign_stages import run_campaign_stage_tests
from propstack.research.definitions import write_definition_manifests
from propstack.research.registry import build_registry, export_registry_csvs, generate_views, registry_summary
from propstack.research.run_store import backfill_run_uids, build_run_store_index


DEFAULT_DATABASE = Path("catalogs/research_registry.sqlite")


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not getattr(args, "handler", None):
        parser.print_help()
        return 0
    try:
        return int(args.handler(args) or 0)
    except (FileNotFoundError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="propstack", description="Institutional futures research operations CLI.")
    parser.add_argument("--version", action="version", version="propstack 0.1.0")
    commands = parser.add_subparsers(dest="command")

    workspace = commands.add_parser("workspace", help="Build generated indexes and views.")
    workspace_commands = workspace.add_subparsers(dest="workspace_command")
    workspace_build = workspace_commands.add_parser("build", help="Rebuild the registry, views, and run-store index.")
    workspace_build.add_argument("--project-root", default=".")
    workspace_build.set_defaults(handler=_workspace_build)

    research = commands.add_parser("research", help="Query research state.")
    research_commands = research.add_subparsers(dest="research_command")
    status = research_commands.add_parser("status", help="Show registry summary.")
    _database_argument(status)
    status.add_argument("--json", action="store_true")
    status.set_defaults(handler=_research_status)
    search = research_commands.add_parser("search", help="Search campaigns and run outcomes.")
    _database_argument(search)
    search.add_argument("--query", help="Substring in campaign ID, title, or edge family.")
    search.add_argument("--symbol", choices=("ES", "NQ"))
    search.add_argument("--state", choices=("active", "review_queue", "candidate", "closed"))
    search.add_argument("--verdict", choices=("PASS", "FAIL", "NEEDS_MANUAL_REVIEW"))
    search.add_argument("--failed-stage")
    search.add_argument("--edge-family")
    search.add_argument("--since", help="Minimum run update timestamp or date.")
    search.add_argument("--limit", type=int, default=30)
    search.add_argument("--json", action="store_true")
    search.set_defaults(handler=_research_search)

    campaign = commands.add_parser("campaign", help="Create, validate, inspect, or run a campaign.")
    campaign_commands = campaign.add_subparsers(dest="campaign_command")
    show = campaign_commands.add_parser("show", help="Show campaign source and latest run state.")
    show.add_argument("campaign_id")
    _database_argument(show)
    show.add_argument("--limit", type=int, default=10)
    show.add_argument("--json", action="store_true")
    show.set_defaults(handler=_campaign_show)
    new = campaign_commands.add_parser("new", help="Create a five-variant authored campaign scaffold.")
    new.add_argument("campaign_id")
    new.add_argument("--symbol", required=True, choices=("ES", "NQ"))
    new.add_argument("--edge-family", required=True)
    new.add_argument("--timeframe", default="1m")
    new.add_argument("--dataset-id")
    new.add_argument("--data-path")
    new.add_argument("--campaign-root", default="campaigns")
    new.set_defaults(handler=_campaign_new)
    validate = campaign_commands.add_parser("validate", help="Run fail-closed preflight on one campaign.")
    validate.add_argument("campaign_id")
    validate.add_argument("--campaign-root", default="campaigns")
    validate.add_argument("--skip-tests", action="store_true")
    validate.add_argument("--json", action="store_true")
    validate.set_defaults(handler=_campaign_validate)
    run = campaign_commands.add_parser("run", help="Run the staged workflow for one authored variant.")
    run.add_argument("campaign_id")
    run.add_argument("--variant", required=True)
    run.add_argument("--campaign-root", default="campaigns")
    run.add_argument("--skip-validation", action="store_true")
    run.add_argument("--continue-on-failure", action="store_true")
    run.add_argument("--no-acceptance", action="store_true")
    run.add_argument("--fast-runtime-defaults", action="store_true")
    run.set_defaults(handler=_campaign_run)

    data = commands.add_parser("data", help="Inspect declared datasets or local files.")
    data_commands = data.add_subparsers(dest="data_command")
    inspect = data_commands.add_parser("inspect", help="Inspect a file path or dataset ID.")
    inspect.add_argument("value")
    inspect.add_argument("--database", default=str(DEFAULT_DATABASE))
    inspect.add_argument("--json", action="store_true")
    inspect.set_defaults(handler=_data_inspect)

    artifacts = commands.add_parser("artifacts", help="Resolve generated evidence from the registry.")
    artifact_commands = artifacts.add_subparsers(dest="artifact_command")
    find = artifact_commands.add_parser("find", help="Find critical artifacts for a run or campaign.")
    find.add_argument("run_uid", nargs="?")
    find.add_argument("--campaign")
    _database_argument(find)
    find.add_argument("--limit", type=int, default=100)
    find.add_argument("--json", action="store_true")
    find.set_defaults(handler=_artifacts_find)

    tutorial = commands.add_parser("tutorial", help="Generate and run the synthetic onboarding campaign.")
    tutorial.add_argument("--output-root", default="examples/tutorial_campaign/generated")
    tutorial.add_argument("--no-run", action="store_true")
    tutorial.set_defaults(handler=_tutorial)
    return parser


def _database_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))


def _workspace_build(args: argparse.Namespace) -> int:
    root = Path(args.project_root).resolve()
    counts: dict[str, int] = {}
    counts.update({f"uids_{key}": value for key, value in backfill_run_uids(project_root=root, apply=True).items()})
    counts.update(
        {
            f"definitions_{key}": value
            for key, value in write_definition_manifests(project_root=root, apply=True).items()
        }
    )
    counts.update(build_registry(project_root=root))
    counts.update({f"export_{key}": value for key, value in export_registry_csvs(project_root=root).items()})
    counts.update({f"view_{key}": value for key, value in generate_views(project_root=root).items()})
    counts.update({f"store_{key}": value for key, value in build_run_store_index(project_root=root, apply=True).items()})
    _print_mapping(counts)
    return 0


def _research_status(args: argparse.Namespace) -> int:
    database = _require_database(args.database)
    _warn_if_stale(database)
    payload = registry_summary(database)
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        rows = [
            {"metric": "built_at", "value": payload.get("built_at")},
            {"metric": "campaigns", "value": payload.get("campaigns")},
            {"metric": "variants", "value": payload.get("variants")},
            {"metric": "attempts", "value": payload.get("attempts")},
            {"metric": "runs", "value": payload.get("runs")},
            {"metric": "campaign_lifecycle", "value": json.dumps(payload.get("campaign_lifecycle"), sort_keys=True)},
            {"metric": "run_verdicts", "value": json.dumps(payload.get("run_verdicts"), sort_keys=True)},
        ]
        _print_table(rows, ("metric", "value"))
    return 0


def _research_search(args: argparse.Namespace) -> int:
    database = _require_database(args.database)
    _warn_if_stale(database)
    where: list[str] = []
    params: list[Any] = []
    if args.query:
        where.append("(c.campaign_id LIKE ? OR c.title LIKE ? OR c.edge_family LIKE ?)")
        value = f"%{args.query}%"
        params.extend((value, value, value))
    if args.symbol:
        where.append("c.campaign_id LIKE ?")
        params.append(f"{args.symbol.lower()}_%")
    if args.state:
        where.append("c.lifecycle_state = ?")
        params.append(args.state)
    if args.edge_family:
        where.append("c.edge_family LIKE ?")
        params.append(f"%{args.edge_family}%")
    verdict = args.verdict.replace("_", " ") if args.verdict else None
    if verdict:
        where.append("EXISTS (SELECT 1 FROM runs r WHERE r.campaign_id = c.campaign_id AND r.verdict = ?)")
        params.append(verdict)
    if args.failed_stage:
        where.append("EXISTS (SELECT 1 FROM runs r WHERE r.campaign_id = c.campaign_id AND r.failed_stage = ?)")
        params.append(args.failed_stage)
    if args.since:
        where.append("EXISTS (SELECT 1 FROM runs r WHERE r.campaign_id = c.campaign_id AND r.updated_at >= ?)")
        params.append(args.since)
    clause = " WHERE " + " AND ".join(where) if where else ""
    query = (
        "SELECT c.campaign_id, c.lifecycle_state, c.edge_family, c.run_count, "
        "c.latest_updated_at, c.definition_path FROM campaigns c"
        f"{clause} ORDER BY COALESCE(c.latest_updated_at, '') DESC, c.campaign_id LIMIT ?"
    )
    params.append(max(1, args.limit))
    rows = _query(database, query, params)
    _emit_rows(rows, args.json)
    return 0


def _campaign_show(args: argparse.Namespace) -> int:
    database = _require_database(args.database)
    campaign_rows = _query(database, "SELECT * FROM campaigns WHERE campaign_id = ?", [args.campaign_id])
    if not campaign_rows:
        raise ValueError(f"unknown campaign: {args.campaign_id}")
    variants = _query(
        database,
        "SELECT variant_id, symbol, timeframe, dataset_id, definition_path FROM variants "
        "WHERE campaign_id = ? ORDER BY variant_id",
        [args.campaign_id],
    )
    runs = _query(
        database,
        "SELECT run_uid, variant_id, test_run_id, verdict, failed_stage, updated_at, summary_path "
        "FROM runs WHERE campaign_id = ? ORDER BY COALESCE(updated_at, '') DESC LIMIT ?",
        [args.campaign_id, max(1, args.limit)],
    )
    payload = {"campaign": campaign_rows[0], "variants": variants, "latest_runs": runs}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        _print_mapping(payload["campaign"])
        print("\nVariants")
        _print_table(variants, ("variant_id", "symbol", "timeframe", "dataset_id", "definition_path"))
        print("\nLatest runs")
        _print_table(runs, ("run_uid", "variant_id", "test_run_id", "verdict", "failed_stage", "updated_at"))
    return 0


def _campaign_new(args: argparse.Namespace) -> int:
    if re.fullmatch(r"[a-z0-9][a-z0-9_]*", args.campaign_id) is None:
        raise ValueError("campaign ID must contain only lowercase letters, digits, and underscores")
    campaign_root = Path(args.campaign_root)
    campaign_dir = campaign_root / args.campaign_id
    if campaign_dir.exists():
        raise ValueError(f"campaign already exists: {campaign_dir}")
    dataset_id = args.dataset_id or f"{args.campaign_id}_{args.timeframe}_dataset"
    data_path = args.data_path or f"data/raw/{args.symbol}/{args.symbol.lower()}_{args.timeframe}.csv"
    campaign_dir.mkdir(parents=True)
    campaign = {
        "campaign_id": args.campaign_id,
        "title": args.campaign_id.replace("_", " ").title(),
        "status": "authored_for_testing",
        "created_at": datetime.now(timezone.utc).date().isoformat(),
        "instrument": args.symbol,
        "timeframe": args.timeframe,
        "edge_family": args.edge_family,
        "hypothesis": "TODO: state the market behavior, mechanism, and falsifiable expectation.",
        "sources": [
            {
                "title": "TODO",
                "authors": "TODO",
                "year": "TODO",
                "link": "TODO",
                "relevance": "TODO: explain why this source supports the edge.",
            }
        ],
        "variants": [f"v{index:02d}" for index in range(1, 6)],
        "rescue_policy": {"allowed": False, "max_rescues_per_failed_variant": 1},
    }
    _write_yaml(campaign_dir / "campaign.yaml", campaign)
    for index in range(1, 6):
        variant_id = f"v{index:02d}"
        variant_dir = campaign_dir / "variants" / variant_id
        variant_dir.mkdir(parents=True)
        _write_yaml(
            variant_dir / "config.yaml",
            _variant_scaffold(args, dataset_id=dataset_id, data_path=data_path, variant_id=variant_id),
        )
        modules_dir = variant_dir / "strategy_modules"
        modules_dir.mkdir()
        (modules_dir / "README.md").write_text(
            "# Strategy Modules\n\nRecord the entry, stop, target, and timeframe rationale for this variant.\n",
            encoding="utf-8",
        )
        for filename, binding in (("entry.py", "ENTRY_MODULE"), ("stop.py", "STOP_MODULE"), ("target.py", "TARGET_MODULE")):
            (modules_dir / filename).write_text(
                f'"""Bind this variant to its reviewed strategy module."""\n\n{binding} = None\n',
                encoding="utf-8",
            )
    print(campaign_dir)
    print("Complete TODO fields and strategy modules, then run `propstack campaign validate`.")
    return 0


def _variant_scaffold(args: argparse.Namespace, *, dataset_id: str, data_path: str, variant_id: str) -> dict[str, Any]:
    data_key = "raw_parquet" if data_path.endswith(".parquet") else "raw_csv"
    return {
        "campaign_id": args.campaign_id,
        "variant_id": variant_id,
        "strategy_name": variant_id,
        "symbol": args.symbol,
        "dataset_id": dataset_id,
        "timeframe": args.timeframe,
        "research_metadata": {
            "mechanics_review_required": True,
            "mechanics_review_version": 1,
            "mechanics_review": {
                "mechanic_expresses_edge": "TODO: explain in at least 80 characters how this variant expresses the campaign edge.",
                "entry_logic_rationale": "TODO: explain in at least 80 characters why the entry is causal, testable, and economically justified.",
                "stop_loss_rationale": "TODO: explain in at least 80 characters why this stop represents mechanical invalidation.",
                "target_exit_rationale": "TODO: explain in at least 80 characters why the target and flatten rules fit the edge.",
                "profitability_rationale": "TODO: explain in at least 80 characters why the expected payoff may survive modeled costs.",
                "known_failure_modes": "TODO: explain in at least 80 characters how this edge may fail or become unstable.",
                "pre_test_decision": "needs_completion",
            },
        },
        "data": {
            "dataset_id": dataset_id,
            "source": "parquet" if data_key == "raw_parquet" else "csv",
            data_key: data_path,
            "symbol": args.symbol,
            "timezone": "America/New_York",
            "exchange_timezone": "America/New_York",
        },
        "core": {
            "initial_balance": 150000,
            "tick_size": 0.25,
            "point_value": 50.0 if args.symbol == "ES" else 20.0,
            "tick_value": 12.5 if args.symbol == "ES" else 5.0,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "flatten_time": "15:55:00",
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
        },
        "apex_rules": {
            "enabled": True,
            "force_flatten_enabled": True,
            "force_flatten_time": "15:55:00",
            "latest_flat_time": "15:56:00",
            "latest_entry_time": "15:45:00",
            "no_overnight_positions": True,
        },
        "strategy": {
            "entry": {"module": "TODO_entry_module", "params": {}},
            "sl": {"module": "TODO_stop_module", "params": {}},
            "tp": {"module": "TODO_target_module", "params": {}},
            "flatten_time": "15:55:00",
        },
        "test_run_id": "run1",
    }


def _campaign_validate(args: argparse.Namespace) -> int:
    from propstack.research.preflight import run_preflight

    campaign_dir = Path(args.campaign_root) / args.campaign_id
    configs = _campaign_configs(campaign_dir)
    result = run_preflight(config_paths=configs, run_tests=not args.skip_tests)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("PASS" if result["passed"] else "FAIL")
        print(f"Configs checked: {len(result['configs_checked'])}")
        print(f"Distinct data sources: {result['data_sources_checked']}")
        for warning in result["warnings"][:20]:
            print(f"WARNING: {warning}")
        if len(result["warnings"]) > 20:
            print(f"WARNING: {len(result['warnings']) - 20} additional warnings; use --json for all details.")
        for failure in result["failures"]:
            print(f"FAIL: {failure}")
    return 0 if result["passed"] else 1


def _campaign_run(args: argparse.Namespace) -> int:
    config = Path(args.campaign_root) / args.campaign_id / "variants" / args.variant / "config.yaml"
    if not config.is_file():
        raise FileNotFoundError(f"variant config not found: {config}")
    summary = run_campaign_stage_tests(
        config,
        skip_validation=args.skip_validation,
        continue_on_failure=args.continue_on_failure,
        include_acceptance=not args.no_acceptance,
        fast_runtime_defaults=args.fast_runtime_defaults,
    )
    print(json.dumps({key: summary.get(key) for key in ("run_uid", "campaign_id", "variant_id", "test_run_id", "passed", "halted", "output_dir")}, indent=2))
    return 0 if summary.get("passed") else 1


def _data_inspect(args: argparse.Namespace) -> int:
    path = Path(args.value)
    if path.exists():
        payload = _inspect_path(path)
    else:
        database = _require_database(args.database)
        rows = _query(
            database,
            "SELECT campaign_id, variant_id, dataset_id, symbol, timeframe, definition_path "
            "FROM variants WHERE dataset_id = ? ORDER BY campaign_id, variant_id",
            [args.value],
        )
        if not rows:
            raise ValueError(f"no local path or registered dataset found: {args.value}")
        payload = {"dataset_id": args.value, "definitions": rows}
    if args.json:
        print(json.dumps(payload, indent=2))
    elif isinstance(payload, dict) and "definitions" in payload:
        _print_table(payload["definitions"], tuple(payload["definitions"][0]))
    else:
        _print_mapping(payload)
    return 0


def _inspect_path(path: Path) -> dict[str, Any]:
    stat = path.stat()
    payload: dict[str, Any] = {
        "path": str(path),
        "size_bytes": stat.st_size,
        "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
    }
    if path.suffix.lower() == ".parquet":
        import pyarrow.parquet as pq

        parquet = pq.ParquetFile(path)
        payload.update({"format": "parquet", "rows": parquet.metadata.num_rows, "columns": parquet.schema.names})
    elif path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            payload.update({"format": "csv", "columns": next(reader, [])})
    else:
        payload["format"] = path.suffix.lower().lstrip(".") or "unknown"
    return payload


def _artifacts_find(args: argparse.Namespace) -> int:
    if not args.run_uid and not args.campaign:
        raise ValueError("provide a run UID or --campaign")
    database = _require_database(args.database)
    where = "a.run_uid = ?" if args.run_uid else "r.campaign_id = ?"
    value = args.run_uid or args.campaign
    rows = _query(
        database,
        "SELECT r.run_uid, r.campaign_id, r.variant_id, r.test_run_id, r.verdict, "
        "a.artifact_kind, a.path, a.sha256 FROM artifacts a JOIN runs r ON r.run_uid = a.run_uid "
        f"WHERE {where} ORDER BY r.updated_at DESC, a.artifact_kind LIMIT ?",
        [value, max(1, args.limit)],
    )
    _emit_rows(rows, args.json)
    return 0


def _tutorial(args: argparse.Namespace) -> int:
    from propstack.tutorial import run_tutorial

    result = run_tutorial(output_root=args.output_root, execute=not args.no_run)
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "PASS" else 1


def _campaign_configs(campaign_dir: Path) -> list[Path]:
    if not campaign_dir.is_dir():
        raise FileNotFoundError(f"campaign not found: {campaign_dir}")
    paths = [
        *campaign_dir.glob("variants/*/config.yaml"),
        *campaign_dir.glob("rescue_attempts/*/*/config.yaml"),
    ]
    if not paths:
        raise FileNotFoundError(f"no authored configs found: {campaign_dir}")
    return sorted(paths)


def _require_database(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_file():
        raise FileNotFoundError(f"registry missing: {path}; run `propstack workspace build`")
    return path


def _query(database: Path, query: str, params: Iterable[Any]) -> list[dict[str, Any]]:
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        return [dict(row) for row in connection.execute(query, tuple(params)).fetchall()]


def _emit_rows(rows: list[dict[str, Any]], as_json: bool) -> None:
    if as_json:
        print(json.dumps(rows, indent=2))
    elif rows:
        _print_table(rows, tuple(rows[0]))
    else:
        print("No matching records.")


def _print_mapping(payload: dict[str, Any]) -> None:
    _print_table([{"field": key, "value": _display_value(value)} for key, value in payload.items()], ("field", "value"))


def _print_table(rows: Iterable[dict[str, Any]], columns: tuple[str, ...]) -> None:
    rows = list(rows)
    widths = {column: len(column) for column in columns}
    for row in rows:
        for column in columns:
            widths[column] = min(60, max(widths[column], len(_display_value(row.get(column)))))
    print("  ".join(column.ljust(widths[column]) for column in columns))
    print("  ".join("-" * widths[column] for column in columns))
    for row in rows:
        print("  ".join(_display_value(row.get(column))[: widths[column]].ljust(widths[column]) for column in columns))


def _display_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return str(value).replace("\n", " ")


def _write_yaml(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, width=120), encoding="utf-8")


def _warn_if_stale(database: Path) -> None:
    database_mtime = database.stat().st_mtime
    candidates = [
        *Path("campaigns").glob("*/campaign.yaml"),
        *Path("campaigns").glob("*/variants/*/config.yaml"),
        *Path("backtest-campaigns").glob("*/*/*/*/campaign_test_summary.json"),
        *Path("backtest-campaigns").glob("*/*/*/*/variant_test_summary.json"),
    ]
    latest = max((path.stat().st_mtime for path in candidates if path.is_file()), default=0.0)
    if latest > database_mtime:
        print("WARNING: registry is older than authored campaign source; run `propstack workspace build`.", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
