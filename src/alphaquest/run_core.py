from __future__ import annotations

import argparse
from pathlib import Path

from alphaquest.backtest.equity_report import write_equity_report
from alphaquest.backtest.engine import BacktestEngine
from alphaquest.backtest.sizing import tick_value_from_core
from alphaquest.data.pipeline import prepare_data
from alphaquest.data.source import data_source_hash
from alphaquest.data.subset import subset_from_config
from alphaquest.utils.config import (
    config_timeframe,
    config_timeframe_minutes,
    create_run_dir,
    load_yaml,
    record_campaign_result,
    validation_dir,
    write_json,
)
from alphaquest.utils.hashing import file_sha256
from alphaquest.utils.reports import market_timezone, write_report_csv
from alphaquest.validation import ValidationMetadata, build_trade_summaries, write_validation_run


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip writing cleaned/features validation CSVs before the run.",
    )
    parser.add_argument(
        "--export-validation",
        action="store_true",
        help="Export trade-level validation artifacts for dashboard inspection.",
    )
    parser.add_argument(
        "--validation-output-dir",
        help="Directory for trade-level validation artifacts. Defaults to validation_runs/core under the campaign run root.",
    )
    parser.add_argument(
        "--validation-window-bars-before",
        type=int,
        help="Number of bars before each selected trade to include in validation bar/tick windows.",
    )
    parser.add_argument(
        "--validation-window-bars-after",
        type=int,
        help="Number of bars after each selected trade to include in validation bar/tick windows.",
    )
    parser.add_argument(
        "--validation-max-trades",
        type=int,
        help="Optional cap for heavy bar/tick windows. Trade summaries still export every closed trade.",
    )
    args = parser.parse_args()
    cfg = load_yaml(args.config)
    _apply_validation_export_args(cfg, args)
    timeframe = config_timeframe(cfg)
    core_cfg = cfg.get("core", {})
    out = create_run_dir("core", args.config, cfg)
    subset = subset_from_config(cfg, "core")
    output_dir = None if args.skip_validation else validation_dir(out)
    data, _, execution_data = prepare_data(
        cfg["data"],
        output_dir,
        subset,
        timeframe=timeframe,
        include_execution_data=True,
    )
    input_hash = data_source_hash(cfg["data"], subset)
    detail_data = execution_data if timeframe != "1m" else None
    result = BacktestEngine(cfg, show_progress=True).run(data, detail_data=detail_data)
    trades = result["trades"]
    report_timezone = market_timezone(cfg)
    write_report_csv(trades, out / "trade_log.csv", report_timezone, index=False)
    write_report_csv(result["daily"], out / "daily_results.csv", report_timezone, index=False)
    metrics = {**result["metrics"], "data_subset": core_cfg.get("data_subset", {})}
    metrics.update(
        write_equity_report(
            trades,
            out,
            initial_balance=float(core_cfg.get("initial_balance", 0.0)),
            timezone=report_timezone,
            title=f"{cfg.get('campaign_id', 'campaign')} / {cfg.get('variant_id', 'variant')} core equity curve",
        )
    )
    validation_cfg = _validation_export_config(cfg)
    if _validation_export_enabled(validation_cfg):
        validation_output_dir = _validation_output_dir(validation_cfg, out)
        validation_metadata = _validation_metadata(
            cfg,
            args.config,
            input_hash,
            out,
            timeframe,
            report_timezone,
        )
        validation_frames = result.get("validation", {})
        validation_summary = write_validation_run(
            validation_output_dir,
            validation_metadata,
            trades=build_trade_summaries(trades, validation_metadata),
            condition_snapshots=validation_frames.get("condition_snapshots"),
            bar_windows=validation_frames.get("bar_windows"),
            tick_windows=validation_frames.get("tick_windows"),
            exit_audits=validation_frames.get("exit_audits"),
        )
        metrics["validation_artifacts"] = {
            "output_dir": str(validation_output_dir),
            "record_counts": validation_summary.get("record_counts", {}),
            "artifact_files": validation_summary.get("artifact_files", {}),
        }
    write_json(out / "metrics.json", metrics)
    if len(trades):
        sample = trades.head(20)
        random = trades.sample(min(20, len(trades)), random_state=1)
        sample = sample._append(random).drop_duplicates(subset=["trade_id"])
    else:
        sample = trades
    write_report_csv(sample, out / "sample_trades_for_tv_validation.csv", report_timezone, index=False)
    record_campaign_result(out, cfg, args.config, input_hash, "core", metrics)
    print(out)

def _apply_validation_export_args(config: dict, args: argparse.Namespace) -> None:
    raw = _validation_export_config(config)
    if args.export_validation:
        raw["enabled"] = True
    if args.validation_output_dir:
        raw["output_dir"] = args.validation_output_dir
    if args.validation_window_bars_before is not None:
        raw["window_bars_before"] = args.validation_window_bars_before
    if args.validation_window_bars_after is not None:
        raw["window_bars_after"] = args.validation_window_bars_after
    if args.validation_max_trades is not None:
        raw["max_trades"] = args.validation_max_trades
    if raw:
        config.setdefault("core", {})["validation_export"] = raw


def _validation_export_config(config: dict) -> dict:
    raw = dict(config.get("validation_export") or {})
    raw.update(dict((config.get("core") or {}).get("validation_export") or {}))
    return raw


def _validation_export_enabled(config: dict) -> bool:
    return bool(config.get("enabled", False) or config.get("export", False))


def _validation_output_dir(config: dict, run_dir: Path) -> Path:
    if config.get("output_dir"):
        return Path(config["output_dir"])
    return run_dir.parent / "validation_runs" / run_dir.name


def _validation_metadata(
    config: dict,
    config_path: str,
    input_hash: str,
    run_dir: Path,
    timeframe: str,
    timezone: str,
) -> ValidationMetadata:
    core_cfg = config.get("core", {})
    tick_size = float(core_cfg.get("tick_size", 0.25))
    return ValidationMetadata(
        run_id=run_dir.parent.name,
        campaign_id=config.get("campaign_id"),
        strategy_id=config.get("strategy_name") or config.get("strategy", {}).get("strategy_name"),
        variant_id=config.get("variant_id"),
        symbol=config.get("symbol") or config.get("data", {}).get("symbol"),
        stage=run_dir.name,
        timezone=timezone,
        tick_size=tick_size,
        tick_value=tick_value_from_core(core_cfg, tick_size),
        timeframe=timeframe,
        timeframe_minutes=config_timeframe_minutes(config, required=False),
        source_run_dir=str(run_dir),
        source_trade_log=str(run_dir / "trade_log.csv"),
        config_hash=file_sha256(config_path),
        input_data_hash=input_hash,
        notes="Generated by run_core trade-level validation export.",
    )


if __name__ == "__main__":
    main()
