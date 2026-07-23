from __future__ import annotations

from copy import deepcopy
from typing import Any

import pandas as pd

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.strategy_modules.event.runner import run_registered_event_strategy


CANONICAL_EVENT_REPLAY_LANE = "canonical_event_replay"


def uses_canonical_event_replay(config: dict[str, Any]) -> bool:
    """Return whether a strategy must execute from canonical trade events."""

    return str(config.get("engine_lane") or "") == CANONICAL_EVENT_REPLAY_LANE


def run_research_backtest(
    config: dict[str, Any],
    data: pd.DataFrame,
    *,
    detail_data: pd.DataFrame | None = None,
    show_progress: bool = False,
    bar_engine_cls=None,
) -> dict[str, Any]:
    """Execute one research run through its declared engine lane.

    Staged research still uses the prepared bar frame as its chronological
    window index. Event strategies derive an exact session allowlist from that
    frame, then load and replay their separately declared trade-event source.
    Bar strategies retain the established OHLC/detail-data path unchanged.
    """

    if not uses_canonical_event_replay(config):
        bar_engine_cls = bar_engine_cls or BacktestEngine
        engine = bar_engine_cls(config, show_progress=True) if show_progress else bar_engine_cls(config)
        return engine.run(data, detail_data=detail_data)

    subset = event_subset_from_frame(data)
    result = run_registered_event_strategy(config, subset, show_progress=show_progress)
    reproducibility = result.setdefault("reproducibility", {})
    reproducibility["research_execution_subset"] = deepcopy(subset)
    return result


def event_subset_from_frame(data: pd.DataFrame) -> dict[str, Any]:
    """Build inclusive event-source bounds from the exact staged bar slice."""

    if data is None or data.empty:
        raise ValueError("canonical event replay requires a non-empty staged data slice")

    if "session_date" in data.columns:
        dates = pd.to_datetime(data["session_date"], errors="raise").dt.date
    elif "timestamp" in data.columns:
        timestamps = pd.to_datetime(data["timestamp"], errors="raise", utc=True)
        dates = timestamps.dt.tz_convert("America/New_York").dt.date
    else:
        raise ValueError("canonical event replay staged data requires session_date or timestamp")

    session_dates = sorted({value.isoformat() for value in dates if not pd.isna(value)})
    if not session_dates:
        raise ValueError("canonical event replay staged data contains no valid session dates")
    return {
        "start_date": session_dates[0],
        "end_date": session_dates[-1],
        "session_dates": session_dates,
    }


__all__ = [
    "CANONICAL_EVENT_REPLAY_LANE",
    "event_subset_from_frame",
    "run_research_backtest",
    "uses_canonical_event_replay",
]
