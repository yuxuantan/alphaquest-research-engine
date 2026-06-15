from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from propstack.backtest.equity_report import write_equity_report_from_trade_log
from propstack.utils.config import load_yaml, variant_root
from propstack.utils.reports import market_timezone


@dataclass(frozen=True)
class TradeLogSpec:
    title: str
    pnl_column: str = "net_pnl"
    run_column: str | None = None
    timestamp_column: str | None = "exit_timestamp"
    sequence_columns: tuple[str, ...] = ("trade_id",)
    balance_source: str = "core"


TRADE_LOG_SPECS = {
    "trade_log.csv": TradeLogSpec("core equity curve"),
    "wfa_oos_trade_log.csv": TradeLogSpec("WFA OOS equity curve"),
    "core_grid_iteration_trades.csv": TradeLogSpec("core grid equity curves", run_column="run_id"),
    "monkey_iteration_trades.csv": TradeLogSpec("monkey equity curves", run_column="run_id"),
    "monte_carlo_path_trades.csv": TradeLogSpec(
        "Monte Carlo path equity curves",
        pnl_column="sim_net_pnl",
        run_column="run_id",
        timestamp_column=None,
        sequence_columns=("path_index", "sample_index"),
        balance_source="prop_rules",
    ),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        help="Run config.yaml. When set, only trade logs under that campaign variant run folder are rendered.",
    )
    parser.add_argument(
        "--report-dir",
        default="backtest-campaigns",
        help="Report root to scan when --config and --trade-log are not set.",
    )
    parser.add_argument(
        "--trade-log",
        action="append",
        help="Specific trade log to render. May be passed more than once.",
    )
    parser.add_argument(
        "--initial-balance",
        type=float,
        help="Override the initial balance used for every rendered curve.",
    )
    parser.add_argument("--timezone", help="Override report timestamp display timezone.")
    parser.add_argument("--title", help="Custom title. Only used when one --trade-log is rendered.")
    args = parser.parse_args()

    explicit_config = load_yaml(args.config) if args.config else None
    explicit_config_path = Path(args.config) if args.config else None
    paths = _selected_trade_logs(args, explicit_config, explicit_config_path)
    if not paths:
        print("No supported trade logs found.")
        return

    for path in paths:
        spec = _trade_log_spec(path)
        config = explicit_config or _config_for_trade_log(path)
        report = write_equity_report_from_trade_log(
            path,
            initial_balance=_initial_balance(config, spec, args.initial_balance),
            timezone=args.timezone or market_timezone(config),
            title=_title(path, spec, config, args.title if len(paths) == 1 else None),
            run_column=spec.run_column,
            pnl_column=spec.pnl_column,
            timestamp_column=spec.timestamp_column,
            sequence_columns=spec.sequence_columns,
        )
        print(report["equity_curve_html"])


def discover_trade_logs(root: str | Path) -> list[Path]:
    base = Path(root)
    if base.is_file():
        return [base] if base.name in TRADE_LOG_SPECS else []
    paths = []
    for name in TRADE_LOG_SPECS:
        paths.extend(base.rglob(name))
    return sorted(set(paths))


def _selected_trade_logs(
    args: argparse.Namespace,
    explicit_config: dict | None,
    explicit_config_path: Path | None = None,
) -> list[Path]:
    if args.trade_log:
        return [Path(path) for path in args.trade_log]
    if explicit_config:
        return discover_trade_logs(variant_root(explicit_config, config_path=explicit_config_path))
    return discover_trade_logs(args.report_dir)


def _trade_log_spec(path: Path) -> TradeLogSpec:
    try:
        return TRADE_LOG_SPECS[path.name]
    except KeyError as exc:
        supported = ", ".join(sorted(TRADE_LOG_SPECS))
        raise ValueError(f"Unsupported trade log name: {path.name}. Supported names: {supported}.") from exc


def _config_for_trade_log(path: Path) -> dict:
    for candidate in _config_candidates_for_trade_log(path):
        if candidate.exists():
            return load_yaml(candidate)
    return {}


def _config_candidates_for_trade_log(path: Path) -> list[Path]:
    candidates = []
    seen = set()
    for parent in [path.parent, *path.parent.parents]:
        for name in ["config.yaml", "config_snapshot.yaml", "variant_config.yaml"]:
            candidate = parent / name
            if candidate in seen:
                continue
            seen.add(candidate)
            candidates.append(candidate)
    return candidates


def _initial_balance(config: dict, spec: TradeLogSpec, override: float | None) -> float:
    if override is not None:
        return float(override)
    if spec.balance_source == "prop_rules":
        return float(config.get("prop_rules", {}).get("starting_balance", 0.0))
    return float(config.get("core", {}).get("initial_balance", 0.0))


def _title(path: Path, spec: TradeLogSpec, config: dict, override: str | None) -> str:
    if override:
        return override
    campaign = config.get("campaign_id")
    variant = config.get("variant_id")
    if campaign and variant:
        return f"{campaign} / {variant} {spec.title}"
    return f"{path.parent.name} {spec.title}"


if __name__ == "__main__":
    main()
