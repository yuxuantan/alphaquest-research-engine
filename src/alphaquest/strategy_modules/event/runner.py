"""Generic data and execution adapter for certified canonical-event strategies."""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import ProcessPoolExecutor, as_completed
import copy
import json
from multiprocessing import get_context
from typing import Any

import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.backtest.metrics import EvaluationPeriod, calculate_metrics, daily_results
from alphaquest.data.databento_session_stream import iter_databento_trade_sessions
from alphaquest.data.sierra_session_stream import iter_sierra_trade_sessions
from alphaquest.strategy_modules.event import build_event_strategy


def iter_event_sessions(config: dict[str, Any], subset: dict[str, Any] | None) -> Iterable[Any]:
    data = config.get("data") or {}
    execution = data.get("execution_data") or {}
    source = str(execution.get("source") or "").lower()
    if not subset or not subset.get("start_date") or not subset.get("end_date"):
        raise ValueError("canonical event replay requires deterministic start_date and end_date bounds")
    if source in {"databento_zip_trades", "databento_trades_zip"}:
        archive = execution.get("archive")
        roll_calendar = execution.get("roll_calendar") or data.get("roll_calendar")
        if not archive or not roll_calendar:
            raise ValueError("Databento event replay requires execution_data.archive and roll_calendar")
        sessions = iter_databento_trade_sessions(
            archive,
            roll_calendar,
            start_date=subset["start_date"],
            end_date=subset["end_date"],
            root_symbol=str(execution.get("root_symbol") or config.get("symbol") or "ES"),
            reset_previous_levels_on_roll=bool(execution.get("reset_previous_levels_on_roll", True)),
            overnight_start=str(execution.get("overnight_start") or "16:00:00"),
            rth_end=str(execution.get("rth_end") or "11:00:00"),
        )
    elif source == "sierra_scid_records":
        sessions = iter_sierra_trade_sessions(
            execution,
            start_date=subset["start_date"],
            end_date=subset["end_date"],
        )
    else:
        raise ValueError(f"unsupported canonical event source: {source!r}")
    allowed_dates = {str(value) for value in subset.get("session_dates") or []}
    if not allowed_dates:
        return sessions
    return (session for session in sessions if str(session.session_date) in allowed_dates)


def run_registered_event_strategy(
    config: dict[str, Any],
    subset: dict[str, Any] | None,
    *,
    show_progress: bool = False,
) -> dict[str, Any]:
    """Replay a configured strategy without a strategy-specific backtest engine."""

    if str(config.get("engine_lane") or "") != "canonical_event_replay":
        raise ValueError("registered event strategy requires engine_lane=canonical_event_replay")
    sessions = iter_event_sessions(config, subset)
    return replay_event_sessions(config, sessions, show_progress=show_progress)


def replay_event_sessions(
    config: dict[str, Any],
    sessions: Iterable[Any],
    *,
    show_progress: bool = False,
    session_features: dict[str, Any] | None = None,
    strategy_instance: Any | None = None,
) -> dict[str, Any]:
    """Inject sessions into the same registry/engine path for deterministic tests."""

    strategy = strategy_instance if strategy_instance is not None else build_event_strategy(config)
    if session_features:
        strategy.bind_session_features(session_features)
    return BacktestEngine(config, show_progress=show_progress).run_event_replay(sessions, strategy)


def replay_event_sessions_parallel(
    config: dict[str, Any],
    sessions: Iterable[Any],
    *,
    workers: int,
    session_completed=None,
) -> dict[str, Any]:
    """Replay independent flat-intraday sessions and merge them deterministically."""

    materialized = list(sessions)
    if workers <= 1 or len(materialized) <= 1:
        return replay_event_sessions(config, materialized)
    _require_session_independent_sizing(config)
    ordered: list[dict[str, Any] | None] = [None] * len(materialized)
    # Use one process model on every supported platform.  In particular, fork
    # would inherit temporary in-process registry/certification state on Linux,
    # while spawn re-imports and revalidates the governed strategy package.
    with ProcessPoolExecutor(
        max_workers=min(int(workers), len(materialized)),
        mp_context=get_context("spawn"),
    ) as executor:
        futures = {
            executor.submit(_replay_one_event_session, config, session): index
            for index, session in enumerate(materialized)
        }
        for future in as_completed(futures):
            index = futures[future]
            ordered[index] = future.result()
            if session_completed is not None:
                session_completed(index, len(materialized))
    return _merge_event_session_results(
        config,
        [value for value in ordered if value is not None],
        workers=min(int(workers), len(materialized)),
    )


def _require_session_independent_sizing(config: dict[str, Any]) -> None:
    if _session_independent_sizing(config):
        return
    sizing_config = (config.get("core") or {}).get("position_sizing") or {}
    sizing = (
        sizing_config
        if isinstance(sizing_config, str)
        else sizing_config.get("mode", "fixed_contracts")
    )
    raise ValueError(
        "parallel event sessions require session-independent position sizing; "
        f"unsupported mode: {str(sizing).lower()}"
    )


def _session_independent_sizing(config: dict[str, Any]) -> bool:
    sizing_config = (config.get("core") or {}).get("position_sizing") or {}
    sizing = (
        sizing_config
        if isinstance(sizing_config, str)
        else sizing_config.get("mode", "fixed_contracts")
    )
    sizing_mode = str(sizing).lower()
    return sizing_mode in {
        "fixed",
        "fixed_contracts",
        "fixed_dollar_risk",
        "fixed_risk_budget",
    }


def _replay_one_event_session(config: dict[str, Any], session: Any) -> dict[str, Any]:
    return replay_event_sessions(config, [session], show_progress=False)


def _merge_event_session_results(
    config: dict[str, Any],
    results: list[dict[str, Any]],
    *,
    workers: int,
) -> dict[str, Any]:
    if not results:
        return replay_event_sessions(config, [])
    trade_refs: list[tuple[pd.Timestamp, int, int]] = []
    for result_index, value in enumerate(results):
        for row in value["trades"].itertuples(index=False):
            trade_refs.append(
                (
                    pd.Timestamp(row.entry_timestamp),
                    result_index,
                    int(row.trade_id),
                )
            )
    trade_refs.sort(key=lambda item: (item[0], item[1], item[2]))
    trade_id_map = {
        (result_index, local_trade_id): global_trade_id
        for global_trade_id, (_timestamp, result_index, local_trade_id) in enumerate(
            trade_refs,
            start=1,
        )
    }
    trade_parts: list[pd.DataFrame] = []
    transition_parts: list[pd.DataFrame] = []
    for result_index, value in enumerate(results):
        if not value["trades"].empty:
            trade_part = value["trades"].copy()
            trade_part["trade_id"] = trade_part["trade_id"].map(
                lambda local: trade_id_map[(result_index, int(local))]
            )
            trade_parts.append(trade_part)
        if not value["event_transitions"].empty:
            transition_part = value["event_transitions"].copy()
            if "trade_id" in transition_part.columns:
                transition_part["trade_id"] = transition_part["trade_id"].map(
                    lambda local: (
                        trade_id_map[(result_index, int(local))]
                        if pd.notna(local)
                        else local
                    )
                )
            if "state_json" in transition_part.columns:
                transition_part["state_json"] = transition_part["state_json"].map(
                    lambda value: _remap_transition_state_trade_id(
                        value,
                        result_index=result_index,
                        trade_id_map=trade_id_map,
                    )
                )
            transition_parts.append(transition_part)

    trades = pd.concat(trade_parts, ignore_index=True) if trade_parts else pd.DataFrame()
    if not trades.empty:
        trades = trades.sort_values(["entry_timestamp", "exit_timestamp"], kind="mergesort").reset_index(drop=True)
        initial_balance = float((config.get("core") or {}).get("initial_balance", 0.0))
        trades["net_liq_after"] = initial_balance + pd.to_numeric(trades["net_pnl"]).cumsum()
    audit_parts = [value["session_audits"] for value in results if not value["session_audits"].empty]
    session_audits = (
        pd.concat(audit_parts, ignore_index=True)
        if audit_parts
        else pd.DataFrame()
    )
    diagnostics: dict[str, int] = {}
    for value in results:
        for name, count in (value.get("diagnostics") or {}).items():
            diagnostics[name] = diagnostics.get(name, 0) + int(count)
    reproducibility = copy.deepcopy(results[0].get("reproducibility") or {})
    reproducibility.update(
        {
            "sessions": int(len(session_audits)),
            "events": int(diagnostics.get("events", 0)),
            "session_parallel": True,
            "session_workers": int(workers),
            "canonical_session_cache": _canonical_session_cache_summary(session_audits),
        }
    )
    initial_balance = float((config.get("core") or {}).get("initial_balance", 0.0))
    evaluation_period = (
        EvaluationPeriod.from_session_dates(
            session_audits["session_date"],
            source="canonical_event_replay_sessions",
        )
        if not session_audits.empty and "session_date" in session_audits
        else None
    )
    return {
        "trades": trades,
        "daily": daily_results(trades),
        "metrics": calculate_metrics(
            trades,
            initial_balance=initial_balance,
            evaluation_period=evaluation_period,
        ),
        "session_audits": session_audits,
        "event_transitions": (
            pd.concat(transition_parts, ignore_index=True) if transition_parts else pd.DataFrame()
        ),
        "diagnostics": diagnostics,
        "reproducibility": reproducibility,
    }


def _remap_transition_state_trade_id(
    value: Any,
    *,
    result_index: int,
    trade_id_map: dict[tuple[int, int], int],
) -> Any:
    if not isinstance(value, str) or not value:
        return value
    try:
        state = json.loads(value)
    except json.JSONDecodeError:
        return value
    if not isinstance(state, dict) or state.get("position_trade_id") is None:
        return value
    local_trade_id = int(state["position_trade_id"])
    state["position_trade_id"] = trade_id_map[(result_index, local_trade_id)]
    return json.dumps(state, sort_keys=True)


def _canonical_session_cache_summary(audits: pd.DataFrame) -> dict[str, Any]:
    if audits.empty or "canonical_session_cache_key" not in audits:
        return {"sessions_bound": 0, "hits": 0, "misses": 0, "schemas": []}
    bound = audits["canonical_session_cache_key"].notna()
    hits = (
        audits.loc[bound, "canonical_session_cache_hit"].fillna(False).astype(bool)
        if "canonical_session_cache_hit" in audits
        else pd.Series(False, index=audits.index[bound])
    )
    schemas = (
        sorted(
            {
                str(value)
                for value in audits.loc[bound, "canonical_session_cache_schema"].dropna()
            }
        )
        if "canonical_session_cache_schema" in audits
        else []
    )
    return {
        "sessions_bound": int(bound.sum()),
        "hits": int(hits.sum()),
        "misses": int(bound.sum() - hits.sum()),
        "schemas": schemas,
    }


__all__ = [
    "iter_event_sessions",
    "replay_event_sessions",
    "replay_event_sessions_parallel",
    "run_registered_event_strategy",
    "_session_independent_sizing",
]
