from __future__ import annotations

import argparse
import csv
from datetime import date
import json
from pathlib import Path
from typing import Any, Callable
import zipfile

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
from alphaquest.utils.hashing import file_sha256, object_sha256
from alphaquest.utils.reports import market_timezone, write_report_csv
from alphaquest.validation import ValidationMetadata, build_trade_summaries, write_validation_run
from alphaquest.validation.promotion_gate import validation_gate_config


STRUCTURED_PROGRESS_PREFIX = "ALPHAQUEST_PROGRESS "
ProgressReporter = Callable[..., None]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip writing cleaned/features validation CSVs before the run.",
    )
    parser.add_argument(
        "--mechanics-validation",
        action="store_true",
        help="Run only the declared small deterministic bar-lane validation slice into its generated evidence path.",
    )
    parser.add_argument(
        "--structured-progress",
        action="store_true",
        help=argparse.SUPPRESS,
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
    progress_reporter = _stdout_progress_reporter if args.structured_progress else None
    if args.mechanics_validation:
        _apply_mechanics_validation_contract(cfg)
    _apply_validation_export_args(cfg, args)
    if str(cfg.get("engine_lane") or "") == "canonical_event_replay":
        _run_canonical_event_core(cfg, args, progress_reporter=progress_reporter)
        return
    _report_progress(
        progress_reporter,
        phase="loading_bars",
        message="Loading validation bars",
        percent=10.0,
    )
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
    _report_progress(
        progress_reporter,
        phase="bar_replay",
        message="Replaying validation bars",
        percent=15.0,
    )
    result = BacktestEngine(cfg, show_progress=progress_reporter is None).run(
        data,
        detail_data=detail_data,
    )
    _report_progress(
        progress_reporter,
        phase="writing_results",
        message="Writing replay results",
        percent=88.0,
    )
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
        _report_progress(
            progress_reporter,
            phase="exporting_evidence",
            message="Exporting mechanics-review evidence",
            percent=92.0,
        )
        validation_output_dir = _validation_output_dir(validation_cfg, out)
        validation_metadata = _validation_metadata(
            cfg,
            args.config,
            input_hash,
            out,
            timeframe,
            report_timezone,
            source_trade_count=len(trades),
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
    _report_progress(
        progress_reporter,
        phase="core_complete",
        message="Mechanics evidence generated",
        percent=97.0,
    )
    print(out)


def _run_canonical_event_core(
    config: dict,
    args: argparse.Namespace,
    *,
    progress_reporter: ProgressReporter | None = None,
) -> None:
    """Run a registered event strategy through the governed core entrypoint."""

    from alphaquest.strategy_modules.event import build_event_strategy
    from alphaquest.strategy_modules.event.runner import iter_event_sessions

    timeframe = config_timeframe(config)
    core_cfg = config.get("core", {})
    _report_progress(
        progress_reporter,
        phase="loading_sessions",
        message="Loading replay sessions",
        percent=10.0,
    )
    out = create_run_dir("core", args.config, config)
    subset = subset_from_config(config, "core")
    input_hash = data_source_hash(config["data"], subset)

    sessions = iter_event_sessions(config, subset)
    total_sessions = _event_session_candidate_count(config, subset)
    replay_progress = _EventReplayProgress(
        total_sessions=total_sessions,
        reporter=progress_reporter,
    )
    tracked_sessions = _tracked_event_sessions(
        sessions,
        total=total_sessions,
        reporter=progress_reporter,
        progress_tracker=replay_progress,
    )
    strategy = build_event_strategy(config)
    _instrument_event_strategy_progress(strategy, replay_progress)
    result = BacktestEngine(config, show_progress=progress_reporter is None).run_event_replay(
        tracked_sessions,
        strategy,
    )
    _report_progress(
        progress_reporter,
        phase="writing_results",
        message="Writing replay results",
        percent=88.0,
    )
    trades = result["trades"]
    report_timezone = market_timezone(config)
    write_report_csv(trades, out / "trade_log.csv", report_timezone, index=False)
    write_report_csv(result["daily"], out / "daily_results.csv", report_timezone, index=False)
    write_report_csv(result["session_audits"], out / "session_audits.csv", report_timezone, index=False)
    write_report_csv(result["event_transitions"], out / "event_transitions.csv", report_timezone, index=False)
    metrics = {
        **result["metrics"],
        "data_subset": core_cfg.get("data_subset", {}),
        "diagnostics": result.get("diagnostics", {}),
        "reproducibility": result.get("reproducibility", {}),
    }
    metrics.update(
        write_equity_report(
            trades,
            out,
            initial_balance=float(core_cfg.get("initial_balance", 0.0)),
            timezone=report_timezone,
            title=f"{config.get('campaign_id', 'campaign')} / {config.get('variant_id', 'variant')} core equity curve",
        )
    )
    validation_cfg = _validation_export_config(config)
    if _validation_export_enabled(validation_cfg):
        _report_progress(
            progress_reporter,
            phase="exporting_evidence",
            message="Exporting mechanics-review evidence",
            percent=92.0,
        )
        validation_output_dir = _validation_output_dir(validation_cfg, out)
        metadata = _validation_metadata(
            config,
            args.config,
            input_hash,
            out,
            timeframe,
            report_timezone,
            source_trade_count=len(trades),
            validation_lane="event_replay",
        )
        summary = write_validation_run(
            validation_output_dir,
            metadata,
            trades=build_trade_summaries(trades, metadata),
            event_transitions=result["event_transitions"],
        )
        metrics["validation_artifacts"] = {
            "output_dir": str(validation_output_dir),
            "record_counts": summary.get("record_counts", {}),
            "artifact_files": summary.get("artifact_files", {}),
        }
    write_json(out / "metrics.json", metrics)
    sample = trades if len(trades) <= 20 else trades.sample(20, random_state=1)
    write_report_csv(sample, out / "sample_trades_for_tv_validation.csv", report_timezone, index=False)
    record_campaign_result(out, config, args.config, input_hash, "core", metrics)
    _report_progress(
        progress_reporter,
        phase="core_complete",
        message="Mechanics evidence generated",
        percent=97.0,
    )
    print(out)


def _stdout_progress_reporter(**payload: Any) -> None:
    print(
        STRUCTURED_PROGRESS_PREFIX + json.dumps(payload, sort_keys=True, separators=(",", ":")),
        flush=True,
    )


def _report_progress(reporter: ProgressReporter | None, **payload: Any) -> None:
    if reporter is not None:
        reporter(**payload)


def _tracked_event_sessions(
    sessions: Any,
    *,
    total: int,
    reporter: ProgressReporter | None,
    progress_tracker: "_EventReplayProgress | None" = None,
):
    completed = 0
    if progress_tracker is None:
        _report_event_replay_progress(reporter, completed=completed, total=total)
    else:
        progress_tracker.report_initial()
    for session in sessions:
        if progress_tracker is not None:
            progress_tracker.begin_session(session, completed=completed)
        yield session
        completed += 1
        if progress_tracker is None:
            _report_event_replay_progress(
                reporter,
                completed=completed,
                total=max(total, completed),
            )
        else:
            progress_tracker.complete_session(completed=completed)
    if progress_tracker is not None:
        progress_tracker.complete_replay(completed=completed)


class _EventReplayProgress:
    """Report replay work without changing the certified execution runtime."""

    def __init__(
        self,
        *,
        total_sessions: int,
        reporter: ProgressReporter | None,
        updates_per_session: int = 100,
    ) -> None:
        self.total_sessions = max(0, int(total_sessions))
        self.reporter = reporter
        self.updates_per_session = max(1, int(updates_per_session))
        self.completed_sessions = 0
        self.session_number = 0
        self.session_date = ""
        self.event_total = 0
        self.event_completed = 0
        self.event_stride = 1
        self.last_reported_event = 0

    def report_initial(self) -> None:
        self._report(message="Preparing market sessions", fraction=0.0)

    def begin_session(self, session: Any, *, completed: int) -> None:
        self.completed_sessions = max(0, int(completed))
        self.session_number = self.completed_sessions + 1
        self.session_date = str(getattr(session, "session_date", "") or "")
        self.event_total = _session_event_count(session)
        self.event_completed = 0
        self.last_reported_event = 0
        self.event_stride = max(1, self.event_total // self.updates_per_session)
        self._report(
            message=self._session_message(),
            fraction=self._overall_fraction(0.0),
        )

    def event_processed(self, event_index: Any) -> None:
        if self.reporter is None or self.session_number <= 0:
            return
        completed = max(0, int(event_index) + 1)
        completed = min(completed, self.event_total) if self.event_total > 0 else completed
        is_last = self.event_total > 0 and completed >= self.event_total
        if not is_last and completed - self.last_reported_event < self.event_stride:
            return
        self.event_completed = completed
        self.last_reported_event = completed
        event_fraction = completed / self.event_total if self.event_total > 0 else 0.0
        self._report(
            message=self._session_message(),
            fraction=self._overall_fraction(event_fraction),
        )

    def complete_session(self, *, completed: int) -> None:
        self.completed_sessions = max(0, int(completed))
        if self.event_total > 0:
            self.event_completed = self.event_total
        self._report(
            message=self._completed_session_message(),
            fraction=self._overall_fraction(0.0),
        )

    def complete_replay(self, *, completed: int) -> None:
        self.completed_sessions = max(0, int(completed))
        if self.total_sessions != self.completed_sessions:
            self.total_sessions = self.completed_sessions
        self._report(
            message=f"Replayed {self.completed_sessions} market sessions",
            fraction=1.0,
        )

    def _overall_fraction(self, event_fraction: float) -> float:
        if self.total_sessions <= 0:
            return 0.0
        work = self.completed_sessions + min(max(float(event_fraction), 0.0), 1.0)
        return min(max(work / self.total_sessions, 0.0), 1.0)

    def _session_message(self) -> str:
        session = (
            f"session {self.session_number}/{self.total_sessions}"
            if self.total_sessions > 0
            else f"session {self.session_number}"
        )
        event_detail = (
            f"{self.event_completed:,}/{self.event_total:,} events"
            if self.event_total > 0
            else f"{self.event_completed:,} events"
        )
        date_detail = f" · {self.session_date}" if self.session_date else ""
        return f"Replaying {session} · {event_detail}{date_detail}"

    def _completed_session_message(self) -> str:
        total = f"/{self.total_sessions}" if self.total_sessions > 0 else ""
        date_detail = f" · {self.session_date}" if self.session_date else ""
        return f"Completed session {self.completed_sessions}{total}{date_detail}"

    def _report(self, *, message: str, fraction: float) -> None:
        known_total = self.total_sessions if self.total_sessions > 0 else None
        _report_progress(
            self.reporter,
            phase="event_replay",
            message=message,
            percent=15.0 + 70.0 * min(max(float(fraction), 0.0), 1.0),
            completed=self.completed_sessions,
            total=known_total,
            unit="sessions",
        )


def _session_event_count(session: Any) -> int:
    events = getattr(session, "events", None)
    if events is None:
        return 0
    try:
        return max(0, int(len(events)))
    except TypeError:
        return 0


def _instrument_event_strategy_progress(
    strategy: Any,
    progress: _EventReplayProgress,
) -> None:
    """Observe completed strategy callbacks without mutating event or strategy state."""

    if progress.reporter is None:
        return
    original_on_event_start = strategy.on_event_start

    def on_event_start_with_progress(event: Any, broker: Any) -> None:
        original_on_event_start(event, broker)
        progress.event_processed(event.event_index)

    strategy.on_event_start = on_event_start_with_progress


def _report_event_replay_progress(
    reporter: ProgressReporter | None,
    *,
    completed: int,
    total: int,
) -> None:
    fraction = completed / total if total > 0 else 0.0
    _report_progress(
        reporter,
        phase="event_replay",
        message="Replaying market sessions",
        percent=15.0 + 70.0 * min(max(fraction, 0.0), 1.0),
        completed=completed,
        total=total,
        unit="sessions",
    )


def _event_session_candidate_count(config: dict, subset: dict) -> int:
    execution = ((config.get("data") or {}).get("execution_data") or {})
    source = str(execution.get("source") or "").lower()
    if source in {"sierra_scid_records", "scid_records", "sierra_scid"}:
        return _sierra_session_candidate_count(execution, subset)
    archive_value = execution.get("archive")
    if not archive_value:
        return 0
    start = date.fromisoformat(str(subset["start_date"]))
    end = date.fromisoformat(str(subset["end_date"]))
    allowed = {str(value) for value in subset.get("session_dates") or []}
    with zipfile.ZipFile(Path(str(archive_value))) as archive:
        candidate_dates = {
            member_date
            for member in archive.namelist()
            if member.endswith(".trades.dbn.zst")
            and (member_date := _archive_member_date(member)) is not None
            and start <= member_date <= end
            and (not allowed or member_date.isoformat() in allowed)
        }
    return len(candidate_dates)


def _sierra_session_candidate_count(execution: dict, subset: dict) -> int:
    manifest_path = Path(str(execution.get("quality_manifest") or ""))
    if not manifest_path.is_file():
        return 0
    required_capability = str(
        execution.get("required_capability") or "full_strategy_events"
    )
    start = date.fromisoformat(str(subset["start_date"]))
    end = date.fromisoformat(str(subset["end_date"]))
    allowed = {str(value) for value in subset.get("session_dates") or []}
    count = 0
    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("session_date") or "")
            if not text or (allowed and text not in allowed):
                continue
            try:
                session_date = date.fromisoformat(text)
            except ValueError:
                continue
            if start <= session_date <= end and _manifest_truthy(row.get(required_capability)):
                count += 1
    return count


def _manifest_truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "pass"}


def _archive_member_date(member: str) -> date | None:
    token = Path(member).name.split(".", maxsplit=1)[0].rsplit("-", maxsplit=1)[-1]
    if len(token) != 8 or not token.isdigit():
        return None
    return date(int(token[:4]), int(token[4:6]), int(token[6:]))


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


def _apply_mechanics_validation_contract(config: dict) -> None:
    authored_config_hash = object_sha256(config)[:12]
    gate = validation_gate_config(config)
    if not gate or gate.get("required") is not True:
        raise ValueError("mechanics validation requires research_metadata.validation_gate.required=true")
    lane = str(gate.get("lane") or "")
    if lane not in {"bar", "event_replay"}:
        raise ValueError("mechanics validation lane must be bar or event_replay")
    if lane == "event_replay" and str(config.get("engine_lane") or "") != "canonical_event_replay":
        raise ValueError("event_replay validation requires engine_lane=canonical_event_replay")
    subset = gate.get("data_subset")
    if not isinstance(subset, dict) or not subset.get("start_date") or not subset.get("end_date"):
        raise ValueError("validation_gate.data_subset must declare start_date and end_date")
    start = date.fromisoformat(str(subset["start_date"]))
    end = date.fromisoformat(str(subset["end_date"]))
    if end < start or (end - start).days > 14:
        raise ValueError("validation_gate.data_subset must span 0 to 14 calendar days")
    if config.get("attempt_id"):
        config["attempt_id"] = f"{config['attempt_id']}__mechanics_{authored_config_hash}"
        config["attempt_kind"] = "mechanics_validation"
        config["attempt_provenance"] = "generated_validation"
        config["parent_attempt_id"] = None
    config["test_run_id"] = f"mechanics_validation_{authored_config_hash}"
    core = config.setdefault("core", {})
    core["data_subset"] = dict(subset)
    core["validation_export"] = {
        "enabled": True,
        "output_dir": str(gate.get("evidence_dir")),
        "max_trades": 30,
    }
    if lane == "bar":
        core["validation_export"].update({"window_bars_before": 10, "window_bars_after": 20})


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
    source_trade_count: int,
    validation_lane: str = "bar",
) -> ValidationMetadata:
    from alphaquest.strategy_certification import strategy_identity_for_config

    core_cfg = config.get("core", {})
    tick_size = float(core_cfg.get("tick_size", 0.25))
    certification = strategy_identity_for_config(
        config,
        _project_root_from_config_path(Path(config_path)),
        require_declared_match=True,
    )
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
        strategy_implementation_version=(certification.implementation_version if certification else None),
        strategy_implementation_sha256=(certification.implementation_sha256 if certification else None),
        strategy_certification_manifest_sha256=(certification.manifest_sha256 if certification else None),
        validation_lane=validation_lane,
        source_data_type=(
            ((config.get("data") or {}).get("execution_data") or {}).get("source")
            if validation_lane == "event_replay"
            else (config.get("data") or {}).get("source")
        ),
        source_data_path=_source_data_path(config.get("data") or {}),
        source_trade_count=source_trade_count,
        commission_per_contract=core_cfg.get("commission_per_contract"),
        slippage_ticks=core_cfg.get("slippage_ticks"),
        point_value=core_cfg.get("point_value"),
        forced_flatten_time=(config.get("strategy") or {}).get("flatten_time") or core_cfg.get("flatten_time"),
        notes="Generated by run_core trade-level validation export.",
    )


def _project_root_from_config_path(config_path: Path) -> Path | None:
    resolved = config_path.resolve()
    for parent in (resolved.parent, *resolved.parents):
        if (parent / "pyproject.toml").is_file() and (parent / "src" / "alphaquest").is_dir():
            return parent
    return None


def _source_data_path(data: dict) -> str | None:
    execution = data.get("execution_data") or {}
    if execution.get("archive"):
        return str(execution["archive"])
    for key in ("raw_csv", "raw_parquet", "raw_dir", "archive"):
        if data.get(key):
            return str(data[key])
    return None


if __name__ == "__main__":
    main()
