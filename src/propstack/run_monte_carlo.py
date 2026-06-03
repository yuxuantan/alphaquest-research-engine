from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

from propstack.backtest.engine import BacktestEngine
from propstack.data.pipeline import prepare_data
from propstack.data.source import data_source_hash
from propstack.data.subset import subset_from_config
from propstack.prop.rules import PropRules
from propstack.research.monte_carlo import run_monte_carlo
from propstack.utils.config import create_run_dir, load_yaml, record_campaign_result, validation_dir, variant_root, write_json
from propstack.utils.hashing import file_sha256
from propstack.utils.reports import market_timezone, write_report_csv

WFA_OOS_TRADE_LOG = "wfa_oos_trade_log.csv"
WFA_OOS_SOURCE_ALIASES = {"wfa_oos", "wfa-oos", "stitched_wfa_oos", "wfa_stitched_oos"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip writing cleaned/features validation CSVs before the run.",
    )
    args = parser.parse_args()
    campaign = load_yaml(args.config)
    mc_cfg = {**campaign.get("benchmarks", {}), **campaign["monte_carlo"]}
    out = create_run_dir("monte_carlo", args.config, campaign)
    trades, input_hash, trade_source = load_monte_carlo_trade_source(campaign, mc_cfg, out, args.skip_validation)
    rules = PropRules.from_dict(campaign.get("prop_rules", {}))
    results, summary = run_monte_carlo(trades, mc_cfg, rules)
    summary["trade_source"] = trade_source
    write_report_csv(results, out / "monte_carlo_results.csv", market_timezone(campaign), index=False)
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
    if source == "wfa_oos":
        path = _wfa_oos_trade_log_path(campaign, mc_cfg)
        if not path.exists():
            raise FileNotFoundError(
                f"WFA OOS trade log not found at {path}. "
                f"Run WFA first; it writes wfa/{WFA_OOS_TRADE_LOG} for this variant."
            )
        trades = pd.read_csv(path)
        _validate_trade_log(trades, source)
        return trades, file_sha256(path), {"type": source, "path": str(path)}

    if source == "trade_log":
        path = Path(mc_cfg["trade_log"])
        trades = pd.read_csv(path)
        _validate_trade_log(trades, source)
        return trades, file_sha256(path), {"type": source, "path": str(path)}

    subset = subset_from_config(campaign, "monte_carlo", fallback_sections=("core",))
    output_dir = None if skip_validation else validation_dir(out)
    data, _ = prepare_data(campaign["data"], output_dir, subset)
    trades = BacktestEngine(campaign).run(data)["trades"]
    source_path = out / "source_trade_log.csv"
    write_report_csv(trades, source_path, market_timezone(campaign), index=False)
    _validate_trade_log(trades, source)
    return (
        trades,
        data_source_hash(campaign["data"], subset),
        {"type": source, "path": str(source_path), "data_subset": subset or {}},
    )


def _monte_carlo_trade_source(mc_cfg: dict) -> str:
    source = mc_cfg.get("trade_source") or mc_cfg.get("source")
    trade_log = mc_cfg.get("trade_log")
    if mc_cfg.get("wfa_oos_trade_log"):
        return "wfa_oos"
    if _is_wfa_oos_source_alias(trade_log):
        return "wfa_oos"

    if source:
        normalized = str(source).strip().lower()
        if normalized in WFA_OOS_SOURCE_ALIASES:
            return "wfa_oos"
        if normalized in {"strategy", "backtest", "variant"}:
            return "strategy"
        if normalized in {"trade_log", "file", "csv"}:
            if not trade_log:
                raise ValueError("monte_carlo.trade_source is 'trade_log' but monte_carlo.trade_log is blank.")
            return "trade_log"
        raise ValueError("monte_carlo.trade_source must be one of: strategy, trade_log, wfa_oos.")

    return "trade_log" if trade_log else "strategy"


def _wfa_oos_trade_log_path(campaign: dict, mc_cfg: dict) -> Path:
    explicit = mc_cfg.get("wfa_oos_trade_log")
    trade_log = mc_cfg.get("trade_log")
    if not explicit and trade_log and not _is_wfa_oos_source_alias(trade_log):
        explicit = trade_log
    if explicit:
        return Path(explicit)
    return variant_root(campaign) / "wfa" / WFA_OOS_TRADE_LOG


def _is_wfa_oos_source_alias(value) -> bool:
    return isinstance(value, str) and value.strip().lower() in WFA_OOS_SOURCE_ALIASES


def _validate_trade_log(trades: pd.DataFrame, source: str) -> None:
    if trades.empty:
        return
    missing = {"session_date", "net_pnl"} - set(trades.columns)
    if missing:
        columns = ", ".join(sorted(missing))
        raise ValueError(f"Monte Carlo {source} trade log is missing required column(s): {columns}.")


if __name__ == "__main__":
    main()
