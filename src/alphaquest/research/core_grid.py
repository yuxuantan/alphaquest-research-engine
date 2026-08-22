from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import product
import os
from pathlib import Path
from typing import Any

import pandas as pd

from alphaquest.backtest.event_replay import canonicalize_event_session
from alphaquest.backtest.event_replay_cache import (
    load_event_replay_cache,
    write_event_replay_cache,
)
from alphaquest.backtest.metrics import benchmark
from alphaquest.data.source import data_source_hash
from alphaquest.research.execution import (
    event_subset_from_frame,
    run_research_backtest,
    uses_canonical_event_replay,
)
from alphaquest.strategy_modules.event.runner import (
    _merge_event_session_results,
    iter_event_sessions,
    replay_event_sessions,
)
from alphaquest.strategy_certification import (
    normalize_certified_event_params,
    resolve_factory,
    strategy_identity_for_config,
)
from alphaquest.utils.params import apply_dotted_params
from alphaquest.utils.progress import progress_bar
from alphaquest.utils.reports import market_timezone, write_report_csv
from alphaquest.utils.target_rr import require_minimum_target_rr

_WORKER_DATA = None
_WORKER_DETAIL_DATA = None
_WORKER_BASE_CONFIG = None
_WORKER_BENCHMARKS = None
_WORKER_INCLUDE_REPORTS = False
_EVENT_GRID_CONFIGS = None
_EVENT_GRID_REQUIRED_COLUMNS = ()
_EVENT_GRID_TICK_SIZE = None
_EVENT_GRID_STRATEGY_FACTORY = None
_EVENT_GRID_PARAMS_BY_RUN = None


def parameter_combinations(params: dict, label: str = "core_grid.parameters") -> list[dict]:
    _validate_parameter_grid(params, label)
    keys = list(params.keys())
    return [dict(zip(keys, values)) for values in product(*(params[k] for k in keys))]


def run_core_grid(
    data: pd.DataFrame,
    base_config: dict,
    grid_config: dict,
    benchmarks: dict,
    report_dir: str | Path | None = None,
    parameter_label: str = "core_grid.parameters",
    detail_data: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, dict]:
    rows = []
    parameters = grid_config.get("parameters", {})
    combos = parameter_combinations(parameters, parameter_label)
    report_paths = _prepare_iteration_report_paths(report_dir)
    report_timezone = market_timezone(base_config)
    parallel = _parallel_settings(grid_config, len(combos))
    event_batch_enabled = _event_batch_grid_enabled(base_config, grid_config)
    execution_metadata = {
        "mode": "per_configuration",
        "shared_session_canonicalization": False,
        "idle_event_batching": False,
        "result_cache_hits": 0,
        "result_cache_misses": len(combos),
    }
    if event_batch_enabled:
        results, execution_metadata = _run_batched_event_core_grid(
            data,
            base_config,
            benchmarks,
            combos,
            workers=parallel["workers"] if parallel["enabled"] else 1,
            include_reports=report_paths is not None,
            grid_config=grid_config,
        )
        for row, trades, daily in sorted(results, key=lambda item: item[0]["run_id"]):
            rows.append(row)
            combo = {key: row[key] for key in parameters}
            _append_iteration_report(report_paths, "trades", trades, int(row["run_id"]), combo, report_timezone)
            _append_iteration_report(report_paths, "daily", daily, int(row["run_id"]), combo, report_timezone)
    elif parallel["enabled"]:
        results = _run_parallel_core_grid(
            data,
            detail_data,
            base_config,
            benchmarks,
            combos,
            parallel["workers"],
            include_reports=report_paths is not None,
        )
        for row, trades, daily in sorted(results, key=lambda item: item[0]["run_id"]):
            rows.append(row)
            combo = {key: row[key] for key in parameters}
            _append_iteration_report(report_paths, "trades", trades, int(row["run_id"]), combo, report_timezone)
            _append_iteration_report(report_paths, "daily", daily, int(row["run_id"]), combo, report_timezone)
    else:
        progress = progress_bar(len(combos), "core grid")
        progress.update(
            0,
            force=True,
            detail="1 active worker",
            active_workers=1,
            expected_workers=1,
        )
        for idx, combo in enumerate(combos, start=1):
            row, trades, daily = _evaluate_core_grid_combo(
                data,
                base_config,
                benchmarks,
                idx,
                combo,
                include_reports=True,
                detail_data=detail_data,
            )
            rows.append(row)
            _append_iteration_report(report_paths, "trades", trades, idx, combo, report_timezone)
            _append_iteration_report(report_paths, "daily", daily, idx, combo, report_timezone)
            progress.update(
                idx,
                force=True,
                detail=f"configuration {idx}/{len(combos)} · 1 active worker",
                active_workers=1,
                expected_workers=1,
            )
    df = pd.DataFrame(rows).sort_values("run_id").reset_index(drop=True)
    passing = int(df["benchmark_passed"].sum()) if len(df) else 0
    profitable = int(df["profitable"].sum()) if len(df) else 0
    apex_violating = int((df.get("apex_rule_violations", pd.Series(dtype=int)) > 0).sum()) if len(df) else 0
    profitable_rate = float(profitable / len(df)) if len(df) else 0.0
    profitable_threshold = _profitable_iteration_threshold(grid_config, benchmarks)
    top = df.sort_values(["benchmark_passed", "net_profit"], ascending=[False, False]).head(10)
    summary = {
        "parameter_mode": "fixed_config" if not parameters else "predeclared_optimization",
        "parameter_value_counts": {key: len(values) for key, values in parameters.items()},
        "expected_combinations": _expected_combination_count(parameters),
        "total_combinations_tested": int(len(df)),
        "number_passing_benchmark": passing,
        "percentage_passing_benchmark": float(passing / len(df)) if len(df) else 0.0,
        "profitable_iterations": profitable,
        "percentage_profitable_iterations": profitable_rate,
        "apex_rule_violating_iterations": apex_violating,
        "profitable_iteration_threshold": profitable_threshold,
        "meets_profitable_iteration_threshold": profitable_rate >= profitable_threshold,
        "top_10_combinations": top.to_dict(orient="records"),
        "stable_parameter_zones": summarize_stability(df),
        "signal_density": summarize_signal_density(df),
        "iteration_reports_retained": report_paths is not None,
        "iteration_report_files": _iteration_report_files(report_paths),
        "data_subset": grid_config.get("data_subset", {}),
        "parallel": {
            "enabled": bool(parallel["enabled"]),
            "workers": parallel["workers"] if parallel["enabled"] else 1,
            "scope": "grid",
        },
        "execution": execution_metadata,
    }
    return df, summary


def _event_batch_grid_enabled(base_config: dict, grid_config: dict) -> bool:
    if not uses_canonical_event_replay(base_config):
        return False
    if not bool(grid_config.get("batched_event_replay", True)):
        return False
    execution = ((base_config.get("data") or {}).get("execution_data") or {})
    return str(execution.get("source") or "").lower() in {
        "databento_zip_trades",
        "databento_trades_zip",
        "sierra_scid_records",
    }


def _run_batched_event_core_grid(
    data: pd.DataFrame,
    base_config: dict,
    benchmarks: dict,
    combos: list[dict],
    *,
    workers: int,
    include_reports: bool,
    grid_config: dict,
) -> tuple[list[tuple[dict, pd.DataFrame, pd.DataFrame]], dict]:
    """Evaluate a canonical grid by session chunks with exact deterministic merge."""

    subset = event_subset_from_frame(data)
    input_hash = data_source_hash(base_config["data"], subset)
    cache_enabled = bool(grid_config.get("event_replay_result_cache", True))
    cached: dict[int, dict] = {}
    misses: list[tuple[int, dict, dict]] = []
    for idx, combo in enumerate(combos, start=1):
        config = apply_dotted_params(base_config, combo)
        config.setdefault("core", {})["event_replay_collect_transitions"] = bool(include_reports)
        result = load_event_replay_cache(config, input_hash) if cache_enabled else None
        if result is None:
            misses.append((idx, combo, config))
        else:
            cached[idx] = result

    active_workers = min(max(1, int(workers)), max(len(subset["session_dates"]), 1))
    chunks = _event_session_chunks(subset["session_dates"], active_workers)
    chunk_results: dict[int, list[tuple[int, dict]]] = {}
    if misses:
        miss_configs = [(idx, combo, config) for idx, combo, config in misses]
        if active_workers > 1 and len(chunks) > 1:
            executor = ProcessPoolExecutor(
                max_workers=active_workers,
                initializer=_init_event_grid_worker,
                initargs=(base_config, miss_configs),
            )
            pending: dict[Any, int] = {}
            remaining = iter(enumerate(chunks))

            def submit_next() -> bool:
                try:
                    chunk_index, chunk_subset = next(remaining)
                except StopIteration:
                    return False
                pending[executor.submit(_run_event_grid_chunk_worker, chunk_index, chunk_subset)] = chunk_index
                return True

            progress = progress_bar(len(chunks), "core grid")
            try:
                for _ in range(active_workers):
                    if not submit_next():
                        break
                progress.update(
                    0,
                    force=True,
                    detail=f"{active_workers} session workers · {len(misses)} uncached configurations",
                    active_workers=active_workers,
                    expected_workers=active_workers,
                )
                completed = 0
                while pending:
                    future = next(as_completed(pending))
                    pending.pop(future)
                    chunk_index, values = future.result()
                    chunk_results[chunk_index] = values
                    completed += 1
                    progress.update(
                        completed,
                        force=True,
                        detail=f"session chunk {completed}/{len(chunks)} · {active_workers} active workers",
                        active_workers=active_workers,
                        expected_workers=active_workers,
                    )
                    submit_next()
            except BaseException:
                for future in pending:
                    future.cancel()
                _terminate_executor_processes(executor)
                executor.shutdown(wait=True, cancel_futures=True)
                raise
            else:
                executor.shutdown(wait=True, cancel_futures=False)
        else:
            _init_event_grid_worker(base_config, miss_configs)
            progress = progress_bar(len(chunks), "core grid")
            progress.update(
                0,
                force=True,
                detail=f"1 session worker · {len(misses)} uncached configurations",
                active_workers=1,
                expected_workers=1,
            )
            for chunk_index, chunk_subset in enumerate(chunks):
                resolved_index, values = _run_event_grid_chunk_worker(chunk_index, chunk_subset)
                chunk_results[resolved_index] = values
                progress.update(
                    chunk_index + 1,
                    force=True,
                    detail=f"session chunk {chunk_index + 1}/{len(chunks)} · 1 active worker",
                    active_workers=1,
                    expected_workers=1,
                )

    partial_by_run: dict[int, list[dict]] = {idx: [] for idx, _, _ in misses}
    for chunk_index in sorted(chunk_results):
        for idx, result in chunk_results[chunk_index]:
            partial_by_run[idx].append(result)

    complete = dict(cached)
    config_by_run = {idx: config for idx, _, config in misses}
    for idx, partials in partial_by_run.items():
        config = config_by_run[idx]
        result = _merge_event_session_results(
            config,
            partials,
            workers=active_workers,
        )
        result.setdefault("reproducibility", {}).update(
            {
                "grid_execution_mode": "session_chunk_batch",
                "grid_session_workers": active_workers,
                "grid_session_chunks": len(chunks),
                "shared_session_canonicalization": True,
            }
        )
        if cache_enabled:
            cache_key = write_event_replay_cache(config, input_hash, result)
            result["reproducibility"]["result_cache_key"] = cache_key
            result["reproducibility"]["result_cache_hit"] = False
        complete[idx] = result

    output = []
    for idx, combo in enumerate(combos, start=1):
        result = complete[idx]
        row = _core_grid_row(result, benchmarks, idx, combo)
        output.append(
            (
                row,
                result["trades"] if include_reports else pd.DataFrame(),
                result["daily"] if include_reports else pd.DataFrame(),
            )
        )
    return output, {
        "mode": "session_chunk_batch",
        "shared_session_canonicalization": True,
        "idle_event_batching": True,
        "session_workers": active_workers,
        "session_chunks": len(chunks),
        "result_cache_enabled": cache_enabled,
        "result_cache_hits": len(cached),
        "result_cache_misses": len(misses),
        "input_data_hash": input_hash,
    }


def _event_session_chunks(session_dates: list[str], workers: int) -> list[dict]:
    if not session_dates:
        return []
    max_sessions_per_chunk = 8
    minimum_chunks = max(1, int(workers)) * 4
    bounded_chunks = (
        len(session_dates) + max_sessions_per_chunk - 1
    ) // max_sessions_per_chunk
    target_chunks = max(
        1,
        min(len(session_dates), max(minimum_chunks, bounded_chunks)),
    )
    chunk_size = max(1, (len(session_dates) + target_chunks - 1) // target_chunks)
    chunks = []
    for start in range(0, len(session_dates), chunk_size):
        values = list(session_dates[start : start + chunk_size])
        chunks.append(
            {
                "start_date": values[0],
                "end_date": values[-1],
                "session_dates": values,
            }
        )
    return chunks


def _init_event_grid_worker(
    base_config: dict,
    configs: list[tuple[int, dict, dict]],
) -> None:
    global _EVENT_GRID_CONFIGS, _EVENT_GRID_REQUIRED_COLUMNS, _EVENT_GRID_TICK_SIZE
    global _EVENT_GRID_STRATEGY_FACTORY, _EVENT_GRID_PARAMS_BY_RUN
    _EVENT_GRID_CONFIGS = configs
    certification = strategy_identity_for_config(base_config, require_declared_match=True)
    if certification is None:
        raise ValueError("batched event core grid requires a certified event strategy")
    _EVENT_GRID_STRATEGY_FACTORY = resolve_factory(certification.factory)
    _EVENT_GRID_PARAMS_BY_RUN = {}
    for idx, _combo, config in configs:
        strategy = config.get("strategy") if isinstance(config.get("strategy"), dict) else {}
        declaration = strategy.get("event") if isinstance(strategy.get("event"), dict) else {}
        if str(declaration.get("module") or "") != certification.strategy_id:
            raise ValueError("batched event core grid configurations must use one certified strategy")
        params = declaration.get("params")
        if params is not None and not isinstance(params, dict):
            raise ValueError("strategy.event.params must be a mapping")
        _EVENT_GRID_PARAMS_BY_RUN[idx] = normalize_certified_event_params(
            certification,
            dict(params or {}),
        )
    strategy = _EVENT_GRID_STRATEGY_FACTORY(_EVENT_GRID_PARAMS_BY_RUN[configs[0][0]])
    _EVENT_GRID_REQUIRED_COLUMNS = tuple(strategy.required_event_columns)
    _EVENT_GRID_TICK_SIZE = float((base_config.get("core") or {}).get("tick_size"))


def _run_event_grid_chunk_worker(
    chunk_index: int,
    subset: dict,
) -> tuple[int, list[tuple[int, dict]]]:
    if (
        _EVENT_GRID_CONFIGS is None
        or _EVENT_GRID_TICK_SIZE is None
        or _EVENT_GRID_STRATEGY_FACTORY is None
        or _EVENT_GRID_PARAMS_BY_RUN is None
    ):
        raise RuntimeError("Event grid worker was not initialized.")
    base_config = _EVENT_GRID_CONFIGS[0][2]
    first_idx = _EVENT_GRID_CONFIGS[0][0]
    feature_strategy = _EVENT_GRID_STRATEGY_FACTORY(_EVENT_GRID_PARAMS_BY_RUN[first_idx])
    canonical_sessions = []
    session_features = {}
    for source_session in iter_event_sessions(base_config, subset):
        canonical = canonicalize_event_session(
            source_session,
            tick_size=_EVENT_GRID_TICK_SIZE,
            required_columns=_EVENT_GRID_REQUIRED_COLUMNS,
        )
        prepared = feature_strategy.prepare_session_features(canonical)
        canonical_sessions.append(canonical)
        if prepared is not None:
            session_features[str(canonical.session_date)] = prepared
    values = []
    for idx, _combo, config in _EVENT_GRID_CONFIGS:
        values.append(
            (
                idx,
                replay_event_sessions(
                    config,
                    canonical_sessions,
                    show_progress=False,
                    session_features=session_features or None,
                    strategy_instance=_EVENT_GRID_STRATEGY_FACTORY(
                        _EVENT_GRID_PARAMS_BY_RUN[idx]
                    ),
                ),
            )
        )
    return chunk_index, values


def _run_parallel_core_grid(
    data: pd.DataFrame,
    detail_data: pd.DataFrame | None,
    base_config: dict,
    benchmarks: dict,
    combos: list[dict],
    workers: int,
    include_reports: bool = False,
) -> list[tuple[dict, pd.DataFrame, pd.DataFrame]]:
    results = []
    progress = progress_bar(len(combos), "core grid")
    active_workers = min(max(1, int(workers)), len(combos))
    executor = ProcessPoolExecutor(
        max_workers=active_workers,
        initializer=_init_core_grid_worker,
        initargs=(data, detail_data, base_config, benchmarks, include_reports),
    )
    pending: dict[Any, int] = {}
    remaining = iter(enumerate(combos, start=1))

    def submit_next() -> bool:
        try:
            idx, combo = next(remaining)
        except StopIteration:
            return False
        pending[executor.submit(_run_core_grid_worker, idx, combo)] = idx
        return True

    try:
        for _ in range(active_workers):
            if not submit_next():
                break
        progress.update(
            0,
            force=True,
            detail=f"{active_workers} active workers",
            active_workers=active_workers,
            expected_workers=active_workers,
        )
        completed = 0
        while pending:
            future = next(as_completed(pending))
            pending.pop(future)
            results.append(future.result())
            completed += 1
            progress.update(
                completed,
                force=True,
                detail=(f"configuration {completed}/{len(combos)}" f" · {active_workers} active workers"),
                active_workers=active_workers,
                expected_workers=active_workers,
            )
            submit_next()
    except BaseException:
        for future in pending:
            future.cancel()
        _terminate_executor_processes(executor)
        executor.shutdown(wait=True, cancel_futures=True)
        raise
    else:
        executor.shutdown(wait=True, cancel_futures=False)
    return results


def _terminate_executor_processes(executor: ProcessPoolExecutor) -> None:
    """Best-effort immediate cleanup when a grid owner is interrupted."""

    processes = list((getattr(executor, "_processes", None) or {}).values())
    for process in processes:
        if process.is_alive():
            process.terminate()
    for process in processes:
        process.join(timeout=2.0)
    for process in processes:
        if process.is_alive():
            process.kill()
            process.join(timeout=2.0)


def _init_core_grid_worker(
    data: pd.DataFrame,
    detail_data: pd.DataFrame | None,
    base_config: dict,
    benchmarks: dict,
    include_reports: bool,
) -> None:
    global _WORKER_DATA, _WORKER_DETAIL_DATA, _WORKER_BASE_CONFIG, _WORKER_BENCHMARKS, _WORKER_INCLUDE_REPORTS
    _WORKER_DATA = data
    _WORKER_DETAIL_DATA = detail_data
    _WORKER_BASE_CONFIG = base_config
    _WORKER_BENCHMARKS = benchmarks
    _WORKER_INCLUDE_REPORTS = include_reports


def _run_core_grid_worker(idx: int, combo: dict) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    if _WORKER_DATA is None or _WORKER_BASE_CONFIG is None or _WORKER_BENCHMARKS is None:
        raise RuntimeError("Core grid worker was not initialized.")
    return _evaluate_core_grid_combo(
        _WORKER_DATA,
        _WORKER_BASE_CONFIG,
        _WORKER_BENCHMARKS,
        idx,
        combo,
        include_reports=_WORKER_INCLUDE_REPORTS,
        detail_data=_WORKER_DETAIL_DATA,
    )


def _evaluate_core_grid_combo(
    data: pd.DataFrame,
    base_config: dict,
    benchmarks: dict,
    idx: int,
    combo: dict,
    include_reports: bool = False,
    detail_data: pd.DataFrame | None = None,
) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    cfg = apply_dotted_params(base_config, combo)
    result = run_research_backtest(cfg, data, detail_data=detail_data)
    row = _core_grid_row(result, benchmarks, idx, combo)
    if not include_reports:
        return row, pd.DataFrame(), pd.DataFrame()
    return row, result["trades"], result["daily"]


def _core_grid_row(
    result: dict,
    benchmarks: dict,
    idx: int,
    combo: dict,
) -> dict:
    metrics = result["metrics"]
    diagnostics = result.get("diagnostics", {})
    rejects = diagnostics.get("rejects", {}) if isinstance(diagnostics, dict) else {}
    passed, reason = benchmark(metrics, benchmarks)
    row = {
        "run_id": idx,
        **combo,
        "signals_generated": int(diagnostics.get("signals_generated", 0)) if isinstance(diagnostics, dict) else 0,
        "entries_opened": int(diagnostics.get("entries_opened", 0)) if isinstance(diagnostics, dict) else 0,
        "trades_closed": int(diagnostics.get("trades_closed", metrics["total_trades"]))
        if isinstance(diagnostics, dict)
        else metrics["total_trades"],
        "entry_rejections_total": _sum_rejects(rejects),
        "reject_missing_stop": int(rejects.get("missing_stop", 0)),
        "reject_target_already_reached": int(rejects.get("target_already_reached", 0)),
        "reject_position_sizing": int(rejects.get("position_sizing", 0)),
        "reject_daily_risk_lockout": int(rejects.get("daily_risk_lockout", 0)),
        "reject_apex_latest_entry_time": int(rejects.get("apex_latest_entry_time", 0)),
        "reject_event_no_trade_window": int(rejects.get("event_no_trade_window", 0)),
        "total_trades": metrics["total_trades"],
        "trades_per_year": metrics["trades_per_year"],
        "net_profit": metrics["net_profit"],
        "profit_factor": metrics["profit_factor"],
        "expectancy_r": metrics["expectancy_r"],
        "max_drawdown": metrics["max_drawdown"],
        "max_drawdown_pct": metrics["max_drawdown_pct"],
        "cagr": metrics["cagr"],
        "mar": metrics["mar"],
        "win_rate": metrics["win_rate"],
        "apex_rule_violations": metrics.get("apex_rule_violations", 0),
        "apex_forced_flatten_trades": metrics.get("apex_forced_flatten_trades", 0),
        "profitable": metrics["net_profit"] > 0,
        "worst_day": metrics["worst_day"],
        "best_day_concentration": metrics["best_day_concentration"],
        "consecutive_losses": metrics["max_consecutive_losses"],
        "benchmark_passed": passed,
        "failure_reason": reason,
    }
    return row


def summarize_stability(df: pd.DataFrame) -> dict:
    if df.empty or "benchmark_passed" not in df:
        return {}
    zones = {}
    for col in [
        "entry.params.reclaim_window_bars",
        "entry.params.max_opening_range_pct_of_open",
        "entry.params.confirmation_minutes",
        "tp.params.target_r_multiple",
        "tp.params.extension_fraction",
        "sl.params.stop_offset_ticks",
        "sl.params.max_stop_points",
        "entry.params.max_trades_per_day",
    ]:
        if col in df.columns:
            grouped = df.groupby(col)["benchmark_passed"].mean().sort_values(ascending=False)
            zones[col] = grouped.to_dict()
    return zones


def summarize_signal_density(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "total_combinations": 0,
            "combinations_with_signals": 0,
            "combinations_with_trades": 0,
            "combinations_meeting_50_trades_per_year": 0,
            "all_combinations_zero_signals": True,
            "all_combinations_zero_trades": True,
        }
    signals = pd.to_numeric(df.get("signals_generated", pd.Series(0, index=df.index)), errors="coerce").fillna(0)
    entries = pd.to_numeric(df.get("entries_opened", pd.Series(0, index=df.index)), errors="coerce").fillna(0)
    trades = pd.to_numeric(df.get("total_trades", pd.Series(0, index=df.index)), errors="coerce").fillna(0)
    trades_per_year = pd.to_numeric(df.get("trades_per_year", pd.Series(0.0, index=df.index)), errors="coerce").fillna(
        0.0
    )
    total = int(len(df))
    combinations_with_signals = int((signals > 0).sum())
    combinations_with_trades = int((trades > 0).sum())
    combinations_meeting_density = int((trades_per_year >= 50).sum())
    positive_tpy = trades_per_year[trades_per_year > 0]
    return {
        "total_combinations": total,
        "combinations_with_signals": combinations_with_signals,
        "percentage_combinations_with_signals": float(combinations_with_signals / total) if total else 0.0,
        "zero_signal_combinations": int(total - combinations_with_signals),
        "all_combinations_zero_signals": combinations_with_signals == 0,
        "max_signals_generated": int(signals.max()) if total else 0,
        "median_signals_generated": float(signals.median()) if total else 0.0,
        "combinations_with_entries": int((entries > 0).sum()),
        "max_entries_opened": int(entries.max()) if total else 0,
        "median_entries_opened": float(entries.median()) if total else 0.0,
        "combinations_with_trades": combinations_with_trades,
        "percentage_combinations_with_trades": float(combinations_with_trades / total) if total else 0.0,
        "zero_trade_combinations": int(total - combinations_with_trades),
        "all_combinations_zero_trades": combinations_with_trades == 0,
        "max_total_trades": int(trades.max()) if total else 0,
        "median_total_trades": float(trades.median()) if total else 0.0,
        "max_trades_per_year": float(trades_per_year.max()) if total else 0.0,
        "median_trades_per_year": float(trades_per_year.median()) if total else 0.0,
        "min_positive_trades_per_year": float(positive_tpy.min()) if not positive_tpy.empty else 0.0,
        "combinations_meeting_50_trades_per_year": combinations_meeting_density,
        "percentage_combinations_meeting_50_trades_per_year": float(combinations_meeting_density / total)
        if total
        else 0.0,
    }


def _sum_rejects(rejects: dict) -> int:
    total = 0
    for value in rejects.values():
        try:
            total += int(value)
        except (TypeError, ValueError):
            continue
    return total


def _validate_parameter_grid(params: dict, label: str) -> None:
    if not isinstance(params, dict):
        raise ValueError(f"{label} must be a mapping of dotted parameter paths to value lists.")
    require_minimum_target_rr(params, context=label)
    for key, values in params.items():
        if not isinstance(values, list):
            raise ValueError(f"{label}.{key} must be a list of values.")
        if not values:
            raise ValueError(f"{label}.{key} must define at least one value.")


def _expected_combination_count(params: dict) -> int:
    total = 1
    for values in params.values():
        total *= len(values)
    return total


def _profitable_iteration_threshold(grid_config: dict, benchmarks: dict) -> float:
    return float(
        grid_config.get(
            "min_profitable_iteration_rate",
            benchmarks.get("min_core_grid_profitable_iteration_rate", 0.70),
        )
    )


def _parallel_settings(grid_config: dict, combo_count: int) -> dict:
    parallel = grid_config.get("parallel") or {}
    if isinstance(parallel, bool):
        enabled = parallel
        requested_workers = os.cpu_count() or 1
        scope = "grid"
    elif isinstance(parallel, dict):
        enabled = bool(parallel.get("enabled", False))
        requested_workers = int(parallel.get("workers") or os.cpu_count() or 1)
        scope = str(parallel.get("scope", "grid")).lower()
    else:
        raise ValueError("core_grid.parallel must be a boolean or mapping.")

    if scope != "grid":
        raise ValueError("core_grid.parallel.scope must be 'grid'.")
    max_cpus = os.cpu_count() or requested_workers
    workers = max(1, min(requested_workers, max_cpus, max(combo_count, 1)))
    return {
        "enabled": enabled and workers > 1 and combo_count > 1,
        "workers": workers,
        "scope": scope,
    }


def _prepare_iteration_report_paths(report_dir: str | Path | None) -> dict[str, Path] | None:
    if report_dir is None:
        return None
    root = Path(report_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths = {
        "trades": root / "core_grid_iteration_trades.csv",
        "daily": root / "core_grid_iteration_daily.csv",
    }
    for path in paths.values():
        if path.exists():
            path.unlink()
    return paths


def _append_iteration_report(
    paths: dict[str, Path] | None,
    name: str,
    frame: pd.DataFrame,
    run_id: int,
    combo: dict,
    timezone: str | None = None,
) -> None:
    if paths is None or frame.empty:
        return
    out = frame.copy()
    out.insert(0, "run_id", run_id)
    for offset, (key, value) in enumerate(combo.items(), start=1):
        out.insert(offset, key, value)
    path = paths[name]
    write_report_csv(out, path, timezone, mode="a", header=not path.exists(), index=False)


def _iteration_report_files(paths: dict[str, Path] | None) -> list[str]:
    if paths is None:
        return []
    return [str(path) for path in paths.values()]
