"""Generic data and execution adapter for certified canonical-event strategies."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from alphaquest.backtest.engine import BacktestEngine
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
) -> dict[str, Any]:
    """Inject sessions into the same registry/engine path for deterministic tests."""

    strategy = build_event_strategy(config)
    return BacktestEngine(config, show_progress=show_progress).run_event_replay(sessions, strategy)


__all__ = ["iter_event_sessions", "replay_event_sessions", "run_registered_event_strategy"]
