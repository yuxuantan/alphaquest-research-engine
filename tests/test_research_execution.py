from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from alphaquest.research import execution
from alphaquest.run_core import (
    _EventReplayProgress,
    _event_session_candidate_count,
    _instrument_event_strategy_progress,
    _tracked_event_sessions,
)
from alphaquest.strategy_modules.event import runner as event_runner


def _market(*timestamps: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(list(timestamps), utc=True),
            "session_date": [pd.Timestamp(value).date().isoformat() for value in timestamps],
        }
    )


def test_bar_research_execution_preserves_existing_engine_path(monkeypatch):
    seen = {}

    class FakeBacktestEngine:
        def __init__(self, config):
            seen["config"] = config

        def run(self, data, detail_data=None):
            seen["data"] = data
            seen["detail"] = detail_data
            return {"metrics": {"total_trades": 0}}

    monkeypatch.setattr(execution, "BacktestEngine", FakeBacktestEngine)
    market = _market("2026-01-02 14:30:00+00:00")
    detail = market.copy()

    result = execution.run_research_backtest({"engine_lane": "bar"}, market, detail_data=detail)

    assert result["metrics"]["total_trades"] == 0
    assert seen["data"] is market
    assert seen["detail"] is detail


def test_event_research_execution_uses_exact_staged_session_allowlist(monkeypatch):
    seen = {}

    def fake_run(config, subset, show_progress=False):
        seen["config"] = config
        seen["subset"] = subset
        seen["show_progress"] = show_progress
        return {"metrics": {"total_trades": 0}, "reproducibility": {}}

    monkeypatch.setattr(execution, "run_registered_event_strategy", fake_run)
    market = _market(
        "2026-01-02 14:30:00+00:00",
        "2026-01-02 14:31:00+00:00",
        "2026-01-05 14:30:00+00:00",
    )
    config = {"engine_lane": "canonical_event_replay"}

    result = execution.run_research_backtest(config, market, show_progress=True)

    expected = {
        "start_date": "2026-01-02",
        "end_date": "2026-01-05",
        "session_dates": ["2026-01-02", "2026-01-05"],
    }
    assert seen == {"config": config, "subset": expected, "show_progress": True}
    assert result["reproducibility"]["research_execution_subset"] == expected


def test_event_session_loader_filters_dates_absent_from_staged_slice(monkeypatch):
    sessions = [
        SimpleNamespace(session_date=pd.Timestamp("2026-01-02").date()),
        SimpleNamespace(session_date=pd.Timestamp("2026-01-03").date()),
        SimpleNamespace(session_date=pd.Timestamp("2026-01-05").date()),
    ]
    monkeypatch.setattr(event_runner, "iter_databento_trade_sessions", lambda *args, **kwargs: iter(sessions))
    config = {
        "data": {
            "execution_data": {
                "source": "databento_zip_trades",
                "archive": "archive.zip",
                "roll_calendar": "rolls.csv",
            }
        }
    }

    selected = list(
        event_runner.iter_event_sessions(
            config,
            {
                "start_date": "2026-01-02",
                "end_date": "2026-01-05",
                "session_dates": ["2026-01-02", "2026-01-05"],
            },
        )
    )

    assert [str(session.session_date) for session in selected] == ["2026-01-02", "2026-01-05"]


def test_operational_wrapper_reports_completed_event_sessions_without_changing_values():
    sessions = [SimpleNamespace(session_date="2026-01-02"), SimpleNamespace(session_date="2026-01-05")]
    updates = []

    observed = list(_tracked_event_sessions(iter(sessions), total=2, reporter=lambda **item: updates.append(item)))

    assert observed == sessions
    assert [(item["completed"], item["total"]) for item in updates] == [(0, 2), (1, 2), (2, 2)]
    assert [item["percent"] for item in updates] == [15.0, 50.0, 85.0]


def test_event_replay_progress_advances_within_a_long_session_without_changing_strategy_callback():
    updates = []
    progress = _EventReplayProgress(
        total_sessions=2,
        reporter=lambda **item: updates.append(item),
        updates_per_session=4,
    )

    class Strategy:
        def __init__(self):
            self.seen = []

        def on_event_start(self, event, broker):
            self.seen.append((event.event_index, broker))

    strategy = Strategy()
    _instrument_event_strategy_progress(strategy, progress)
    session = SimpleNamespace(
        session_date="2026-01-02",
        events=pd.DataFrame({"price": range(100)}),
    )
    tracked = _tracked_event_sessions(
        iter([session]),
        total=2,
        reporter=lambda **item: updates.append(item),
        progress_tracker=progress,
    )

    observed = next(tracked)
    assert observed is session
    broker = object()
    for index in range(100):
        strategy.on_event_start(SimpleNamespace(event_index=index), broker)
    try:
        next(tracked)
    except StopIteration:
        pass

    assert strategy.seen == [(index, broker) for index in range(100)]
    event_updates = [
        item
        for item in updates
        if item["message"].startswith("Replaying session") and item["percent"] > 15.0
    ]
    assert [round(item["percent"], 2) for item in event_updates] == [23.75, 32.5, 41.25, 50.0]
    assert "100/100 events" in event_updates[-1]["message"]
    assert updates[-1]["message"] == "Replayed 1 market sessions"
    assert updates[-1]["percent"] == 85.0


def test_sierra_progress_total_counts_only_eligible_requested_sessions(tmp_path):
    manifest = tmp_path / "capabilities.csv"
    manifest.write_text(
        "session_date,contract,full_strategy_events_extrapolated\n"
        "2026-01-02,ESH26,True\n"
        "2026-01-05,ESH26,False\n"
        "2026-01-06,ESH26,True\n"
        "2026-01-07,ESH26,True\n",
        encoding="utf-8",
    )
    config = {
        "data": {
            "execution_data": {
                "source": "sierra_scid_records",
                "quality_manifest": str(manifest),
                "required_capability": "full_strategy_events_extrapolated",
            }
        }
    }

    assert _event_session_candidate_count(
        config,
        {
            "start_date": "2026-01-02",
            "end_date": "2026-01-07",
            "session_dates": ["2026-01-02", "2026-01-05", "2026-01-06"],
        },
    ) == 2
