from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

from propstack.backtest.equity_report import write_equity_report
from propstack.prop.rules import PropRules
from propstack.research.monte_carlo import run_monte_carlo, run_monte_carlo_with_audit
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, write_json
from propstack.utils.hashing import file_sha256
from propstack.utils.reports import market_timezone, write_report_csv

CORE_TRADE_LOG = "trade_log.csv"
WFA_OOS_TRADE_LOG = "wfa_oos_trade_log.csv"
CORE_SOURCE_ALIASES = {"core", "core_trade_log", "core-trade-log", "core_trades"}
WFA_OOS_SOURCE_ALIASES = {"wfa_oos", "wfa-oos", "stitched_wfa_oos", "wfa_stitched_oos"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Accepted for command compatibility. Monte Carlo reads an existing report trade log.",
    )
    args = parser.parse_args()
    campaign = load_yaml(args.config)
    mc_cfg = {**campaign.get("benchmarks", {}), **campaign["monte_carlo"]}
    mc_cfg["_core"] = campaign.get("core", {})
    out = create_run_dir("monte_carlo", args.config, campaign)
    trades, input_hash, trade_source = load_monte_carlo_trade_source(campaign, mc_cfg, out, args.skip_validation)
    rules = PropRules.from_dict(campaign.get("prop_rules", {}))
    retain_path_trades = bool(mc_cfg.get("retain_path_trades", False))
    retain_path_events = bool(mc_cfg.get("retain_path_events", False))
    if retain_path_trades or retain_path_events:
        results, summary, path_trades, path_events = run_monte_carlo_with_audit(trades, mc_cfg, rules)
    else:
        results, summary = run_monte_carlo(trades, mc_cfg, rules)
        path_trades = pd.DataFrame()
        path_events = pd.DataFrame()
    summary["trade_source"] = trade_source
    report_timezone = market_timezone(campaign)
    write_report_csv(results, out / "monte_carlo_results.csv", report_timezone, index=False)
    if retain_path_trades:
        path_trades_path = out / "monte_carlo_path_trades.csv"
        write_report_csv(path_trades, path_trades_path, report_timezone, index=False)
        summary["path_trades_report"] = str(path_trades_path)
        summary.update(
            write_equity_report(
                path_trades,
                out,
                initial_balance=float(rules.starting_balance),
                timezone=report_timezone,
                title=(
                    f"{campaign.get('campaign_id', 'campaign')} / "
                    f"{campaign.get('variant_id', 'variant')} Monte Carlo path equity curves"
                ),
                run_column="run_id",
                pnl_column="sim_net_pnl",
                timestamp_column=None,
                sequence_columns=("path_index", "sample_index"),
            )
        )
    if retain_path_events:
        path_events_path = out / "monte_carlo_path_events.csv"
        write_report_csv(path_events, path_events_path, report_timezone, index=False)
        summary["path_events_report"] = str(path_events_path)
    write_json(out / "monte_carlo_summary.json", summary)
    record_campaign_result(out, campaign, args.config, input_hash, "monte_carlo", summary)
    print(out)


def load_monte_carlo_trade_source(
    campaign: dict,
    mc_cfg: dict,
    out: Path,
    skip_validation: bool = False,
) -> tuple[pd.DataFrame, str, dict]:
    source = _monte_carlo_trade_source(mc_cfg)
    if source == "core":
        path = _core_trade_log_path(campaign, mc_cfg, out)
        if not path.exists():
            raise FileNotFoundError(
                f"Core trade log not found at {path}. "
                f"Run core first; it writes core/{CORE_TRADE_LOG} for this variant."
            )
        trades = pd.read_csv(path)
        _validate_trade_log(trades, source)
        return trades, file_sha256(path), {"type": source, "path": _display_path(path)}

    if source == "wfa_oos":
        path = _wfa_oos_trade_log_path(campaign, mc_cfg, out)
        if not path.exists():
            raise FileNotFoundError(
                f"WFA OOS trade log not found at {path}. "
                f"Run WFA first; it writes wfa/{WFA_OOS_TRADE_LOG} for this variant."
            )
        trades = pd.read_csv(path)
        _validate_trade_log(trades, source)
        return trades, file_sha256(path), {"type": source, "path": _display_path(path)}

    raise ValueError("monte_carlo.trade_source must be one of: core, wfa_oos.")


def _monte_carlo_trade_source(mc_cfg: dict) -> str:
    source = mc_cfg.get("trade_source") or mc_cfg.get("source")
    if mc_cfg.get("trade_log"):
        raise ValueError(
            "monte_carlo.trade_log is no longer supported. "
            "Set monte_carlo.trade_source to 'core' or 'wfa_oos' and run that report first."
        )
    if not source:
        raise ValueError("monte_carlo.trade_source is required and must be one of: core, wfa_oos.")

    normalized = str(source).strip().lower()
    if normalized in CORE_SOURCE_ALIASES:
        return "core"
    if normalized in WFA_OOS_SOURCE_ALIASES:
        return "wfa_oos"
    raise ValueError("monte_carlo.trade_source must be one of: core, wfa_oos.")


def _core_trade_log_path(campaign: dict, mc_cfg: dict, out: Path) -> Path:
    explicit = mc_cfg.get("core_trade_log")
    if explicit:
        return Path(explicit)
    return Path(out).parent / "core" / CORE_TRADE_LOG


def _wfa_oos_trade_log_path(campaign: dict, mc_cfg: dict, out: Path) -> Path:
    explicit = mc_cfg.get("wfa_oos_trade_log")
    if explicit:
        return Path(explicit)
    return Path(out).parent / "wfa" / WFA_OOS_TRADE_LOG


def _validate_trade_log(trades: pd.DataFrame, source: str) -> None:
    if trades.empty:
        return
    missing = {"session_date", "net_pnl"} - set(trades.columns)
    if missing:
        columns = ", ".join(sorted(missing))
        raise ValueError(f"Monte Carlo {source} trade log is missing required column(s): {columns}.")


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    main()
