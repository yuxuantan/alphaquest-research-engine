from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd
import pytest

from alphaquest.backtest.engine import BacktestEngine
from alphaquest.backtest.event_replay import (
    CanonicalEventReplayStrategy,
    PositionDirective,
)
from alphaquest.validation import ValidationMetadata, write_validation_run
from alphaquest.validation.loaders import load_validation_run


@dataclass(frozen=True)
class _Session:
    session_date: date
    contract_symbol: str
    events: pd.DataFrame


def _config(*, commission: float = 0.0) -> dict:
    return {
        "strategy_name": "canonical_event_replay_test",
        "strategy": {},
        "core": {
            "tick_size": 0.25,
            "tick_value": 12.50,
            "point_value": 50.0,
            "commission_per_contract": commission,
            "slippage_ticks": 0.0,
            "contracts": 1,
            "initial_balance": 50_000.0,
            "entry_start": "09:30:00",
            "flatten_time": "11:00:00",
            "event_stop_market_fill_policy": "exact_requested_price",
        },
    }


def _session(
    prices: tuple[float, ...],
    *,
    session_date: date = date(2026, 5, 4),
    offsets_ms: tuple[int, ...] | None = None,
    ordinals: tuple[int, ...] | None = None,
) -> _Session:
    offsets_ms = offsets_ms or tuple(range(len(prices)))
    ordinals = ordinals or tuple(range(len(prices)))
    base = pd.Timestamp(session_date.isoformat() + " 09:30:00", tz="America/New_York")
    events = pd.DataFrame(
        {
            "timestamp": [base + pd.Timedelta(milliseconds=value) for value in offsets_ms],
            "source_ordinal": ordinals,
            "sequence": ordinals,
            "symbol": "ES",
            "contract_symbol": "ESM6",
            "price": prices,
            "size": 1,
            "side": "B",
            "signed_size": 1,
        }
    )
    return _Session(session_date=session_date, contract_symbol="ESM6", events=events)


class _RecordingStrategy(CanonicalEventReplayStrategy):
    def __init__(self):
        self.seen = []

    def on_event_start(self, event, broker) -> None:
        del broker
        self.seen.append((event.timestamp_ns, event.source_ordinal, event.event_index))


class _SubmitOnceStrategy(CanonicalEventReplayStrategy):
    def __init__(
        self,
        *,
        submit_on: int = 0,
        direction: str = "long",
        entry_tick: int = 401,
        stop_tick: int = 397,
        target_tick: int = 402,
    ):
        self.submit_on = submit_on
        self.direction = direction
        self.entry_tick = entry_tick
        self.stop_tick = stop_tick
        self.target_tick = target_tick
        self.submitted = False
        self.fills = []
        self.closes = []

    def on_session_start(self, session, broker) -> None:
        del session, broker
        self.submitted = False

    def after_event(self, event, broker, **_) -> None:
        if self.submitted or event.event_index != self.submit_on:
            return
        broker.submit_or_replace_entry(
            order_id="entry",
            direction=self.direction,
            entry_tick=self.entry_tick,
            stop_tick=self.stop_tick,
            target_tick=self.target_tick,
        )
        self.submitted = True

    def on_entry_filled(self, order, position, event, broker) -> None:
        del order, broker
        self.fills.append((event.event_index, event.source_ordinal, position.entry_reference_tick))

    def on_position_closed(self, position, trade, broker) -> None:
        del position, broker
        self.closes.append((trade["exit_event_index"], trade["exit_reason"], trade["exit_price"]))


def test_event_replay_canonicalizes_by_utc_timestamp_then_source_ordinal():
    session = _session(
        (100.50, 100.00, 100.25),
        offsets_ms=(1, 0, 0),
        ordinals=(2, 1, 0),
    )
    strategy = _RecordingStrategy()

    BacktestEngine(_config()).run_event_replay([session], strategy)

    assert [(ordinal, index) for _, ordinal, index in strategy.seen] == [(0, 0), (1, 1), (2, 2)]


def test_session_callbacks_expose_metadata_but_never_the_future_event_frame():
    class _SessionViewStrategy(_RecordingStrategy):
        def on_session_start(self, session, broker) -> None:
            assert not hasattr(session, "events")
            assert not hasattr(session, "source_session")
            assert broker.current_session is session
            assert session.session_date == date(2026, 5, 4)

    BacktestEngine(_config()).run_event_replay([_session((100.0,))], _SessionViewStrategy())


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda rows: rows.assign(timestamp=pd.Timestamp("2026-05-04 09:30:00")), "timezone-aware"),
        (lambda rows: rows.assign(price=[100.0, float("nan")]), "price.*finite"),
        (lambda rows: rows.assign(price=[100.0, 100.10]), "off.*tick"),
        (lambda rows: rows.assign(size=[1, -1]), "size.*non-negative"),
    ],
)
def test_event_replay_rejects_invalid_event_contract(mutation, message):
    session = _session((100.0, 100.25))
    invalid = _Session(session.session_date, session.contract_symbol, mutation(session.events.copy()))

    with pytest.raises(ValueError, match=message):
        BacktestEngine(_config()).run_event_replay([invalid], _RecordingStrategy())


def test_event_replay_rejects_duplicate_canonical_key():
    session = _session((100.0, 100.25), offsets_ms=(0, 0), ordinals=(0, 0))

    with pytest.raises(ValueError, match="duplicate.*timestamp.*source_ordinal"):
        BacktestEngine(_config()).run_event_replay([session], _RecordingStrategy())


def test_event_replay_rejects_sessions_without_canonical_identity():
    events = _session((100.0,)).events

    with pytest.raises(ValueError, match="missing: contract_symbol"):
        BacktestEngine(_config()).run_event_replay(
            [type("IncompleteSession", (), {"session_date": date(2026, 5, 4), "events": events})()],
            _RecordingStrategy(),
        )


def test_order_activates_on_next_event_and_equal_timestamp_later_ordinal_can_fill():
    session = _session((100.25, 100.25, 100.50), offsets_ms=(0, 0, 1), ordinals=(0, 1, 2))
    strategy = _SubmitOnceStrategy()

    result = BacktestEngine(_config()).run_event_replay([session], strategy)

    assert strategy.fills == [(1, 1, 401)]
    trade = result["trades"].iloc[0]
    assert trade["entry_event_index"] == 1
    assert trade["entry_timestamp"] == session.events.loc[0, "timestamp"]


def test_entry_start_blocks_prestart_fills_but_allows_the_first_later_event():
    session = _session(
        (100.0, 100.25, 100.25),
        offsets_ms=(-1_800_000, -1_799_999, 0),
    )
    strategy = _SubmitOnceStrategy()

    result = BacktestEngine(_config()).run_event_replay([session], strategy)

    assert result["trades"].iloc[0]["entry_event_index"] == 2
    assert result["diagnostics"]["entry_events_blocked_before_start"] == 2


class _RepriceStrategy(_SubmitOnceStrategy):
    def after_event(self, event, broker, **kwargs) -> None:
        super().after_event(event, broker, **kwargs)
        if event.event_index == 1 and not self.fills:
            broker.submit_or_replace_entry(
                order_id="entry",
                direction="long",
                entry_tick=400,
                stop_tick=396,
                target_tick=402,
            )


def test_repriced_order_does_not_fill_until_event_after_repricing():
    session = _session((99.75, 100.0, 100.0, 100.50))
    strategy = _RepriceStrategy(entry_tick=401)

    BacktestEngine(_config()).run_event_replay([session], strategy)

    assert strategy.fills[0][0] == 2


def test_suspended_order_is_retained_without_liveness_or_fill_evaluation():
    class _SuspendThenRelease(_SubmitOnceStrategy):
        def __init__(self):
            super().__init__()
            self.suspended = True
            self.cancelled = []

        def entry_order_is_suspended(self, order, event, broker):
            del order, event, broker
            return self.suspended

        def entry_order_is_live(self, order, event, broker):
            del order, event, broker
            assert not self.suspended, "A suspended order must not be liveness-checked."
            return True

        def after_event(self, event, broker, **kwargs):
            super().after_event(event, broker, **kwargs)
            if event.event_index == 1:
                self.suspended = False

        def on_order_cancelled(self, order, reason, event, broker):
            del order, event, broker
            self.cancelled.append(reason)

    strategy = _SuspendThenRelease()
    result = BacktestEngine(_config()).run_event_replay(
        [_session((100.0, 100.25, 100.25, 100.50))],
        strategy,
    )

    assert result["trades"].iloc[0]["entry_event_index"] == 2
    assert strategy.cancelled == []


class _OldPriceWinsStrategy(_SubmitOnceStrategy):
    def after_event(self, event, broker, **kwargs) -> None:
        super().after_event(event, broker, **kwargs)
        if event.event_index == 1 and not self.fills:
            broker.submit_or_replace_entry(
                order_id="entry",
                direction="long",
                entry_tick=405,
                stop_tick=397,
                target_tick=406,
            )


def test_active_old_order_fills_before_same_event_repricing_phase():
    session = _session((100.0, 100.25, 100.50))
    strategy = _OldPriceWinsStrategy()

    BacktestEngine(_config()).run_event_replay([session], strategy)

    assert strategy.fills[0] == (1, 1, 401)


class _ResubmitAfterCloseStrategy(_SubmitOnceStrategy):
    def after_event(self, event, broker, **kwargs) -> None:
        super().after_event(event, broker, **kwargs)
        if self.closes and len(self.fills) == 1:
            broker.submit_or_replace_entry(
                order_id="second",
                direction="short",
                entry_tick=402,
                stop_tick=406,
                target_tick=400,
            )


def test_position_exit_precedes_order_updates_but_same_event_reentry_is_forbidden():
    session = _session((100.0, 100.25, 100.50, 100.50, 100.0))
    strategy = _ResubmitAfterCloseStrategy()

    BacktestEngine(_config()).run_event_replay([session], strategy)

    assert strategy.closes[0][0] == 2
    assert [fill[0] for fill in strategy.fills] == [1, 3]


class _MoveBracketStrategy(_SubmitOnceStrategy):
    def position_directive(self, event, position, broker):
        del position, broker
        if event.event_index == 2:
            return PositionDirective(stop_tick=400, target_tick=403, allow_marketable_bracket=True)
        return PositionDirective()


def test_dynamic_bracket_change_is_only_active_on_the_next_event():
    session = _session((100.0, 100.25, 100.75, 100.75))
    strategy = _MoveBracketStrategy(target_tick=410)

    result = BacktestEngine(_config()).run_event_replay([session], strategy)

    trade = result["trades"].iloc[0]
    assert trade["exit_event_index"] == 3
    assert trade["exit_reason"] == "target"
    assert trade["exit_price"] == 100.75


class _OnePassSessions:
    def __init__(self, sessions):
        self.sessions = sessions
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        if self.iterations > 1:
            raise AssertionError("session stream was consumed more than once")
        yield from self.sessions


def test_trade_ids_and_accounting_carry_across_one_pass_session_stream():
    sessions = _OnePassSessions(
        [
            _session((100.0, 100.25, 100.50), session_date=date(2026, 5, 4)),
            _session((100.0, 100.25, 100.50), session_date=date(2026, 5, 5)),
        ]
    )
    strategy = _SubmitOnceStrategy()

    result = BacktestEngine(_config(commission=2.0)).run_event_replay(sessions, strategy)

    trades = result["trades"]
    assert sessions.iterations == 1
    assert trades["trade_id"].tolist() == [1, 2]
    assert trades["gross_pnl"].tolist() == pytest.approx([12.50, 12.50])
    assert trades["commission"].tolist() == pytest.approx([4.0, 4.0])
    assert trades["net_pnl"].tolist() == pytest.approx([8.50, 8.50])
    assert trades["net_liq_after"].tolist() == pytest.approx([50_008.50, 50_017.00])


@pytest.mark.parametrize(
    "sessions",
    [
        [
            _session((100.0,), session_date=date(2026, 5, 5)),
            _session((100.0,), session_date=date(2026, 5, 4)),
        ],
        [
            _session((100.0,), session_date=date(2026, 5, 4)),
            _session((100.0,), session_date=date(2026, 5, 4)),
        ],
    ],
)
def test_sessions_must_be_unique_and_strictly_chronological(sessions):
    with pytest.raises(ValueError, match="unique and strictly chronological"):
        BacktestEngine(_config()).run_event_replay(sessions, _RecordingStrategy())


@pytest.mark.parametrize(
    ("strategy", "message"),
    [
        (
            type(
                "SubmitDuringStateUpdate",
                (CanonicalEventReplayStrategy,),
                {
                    "on_event_start": lambda self, event, broker: broker.submit_or_replace_entry(
                        order_id="bad",
                        direction="long",
                        entry_tick=401,
                        stop_tick=397,
                    )
                },
            )(),
            "only submit or replace.*after_event",
        ),
    ],
)
def test_broker_order_mutations_are_callback_phase_gated(strategy, message):
    with pytest.raises(RuntimeError, match=message):
        BacktestEngine(_config()).run_event_replay([_session((100.0,))], strategy)


def test_fill_validator_cannot_cancel_the_order_snapshot_it_is_validating():
    class _InvalidFillGate(_SubmitOnceStrategy):
        def entry_fill_allowed(self, order, event, broker):
            broker.cancel_entry(order.order_id)
            return True

    with pytest.raises(RuntimeError, match="only cancel.*after_event"):
        BacktestEngine(_config()).run_event_replay(
            [_session((100.0, 100.25))],
            _InvalidFillGate(),
        )


@pytest.mark.parametrize(
    ("direction", "prices", "entry_tick", "stop_tick", "target_tick", "entry", "exit_"),
    [
        ("long", (100.0, 101.0, 98.0), 401, 397, 420, 101.0, 98.0),
        ("short", (101.0, 99.0, 103.0), 400, 404, 380, 99.0, 103.0),
    ],
)
def test_gap_aware_stop_market_policy_uses_the_trade_event_price(
    direction,
    prices,
    entry_tick,
    stop_tick,
    target_tick,
    entry,
    exit_,
):
    config = _config()
    config["core"]["event_stop_market_fill_policy"] = "trade_event_price_on_gap"
    strategy = _SubmitOnceStrategy(
        direction=direction,
        entry_tick=entry_tick,
        stop_tick=stop_tick,
        target_tick=target_tick,
    )

    trade = BacktestEngine(config).run_event_replay([_session(prices)], strategy)["trades"].iloc[0]

    assert trade["entry_trigger_price"] == entry_tick * 0.25
    assert trade["entry_price"] == entry
    assert trade["exit_price"] == exit_


def test_exact_requested_stop_market_policy_preserves_explicit_optimistic_assumption():
    strategy = _SubmitOnceStrategy(entry_tick=401, stop_tick=397, target_tick=420)

    trade = BacktestEngine(_config()).run_event_replay(
        [_session((100.0, 101.0, 98.0))],
        strategy,
    )["trades"].iloc[0]

    assert trade["entry_trigger_price"] == 100.25
    assert trade["entry_price"] == 100.25
    assert trade["exit_price"] == 99.25


def test_event_lane_requires_an_explicit_stop_market_fill_policy():
    config = _config()
    config["core"].pop("event_stop_market_fill_policy")

    with pytest.raises(ValueError, match="event_stop_market_fill_policy is required"):
        BacktestEngine(config).run_event_replay([_session((100.0,))], _RecordingStrategy())


class _MutateReturnedOrderStrategy(_SubmitOnceStrategy):
    def after_event(self, event, broker, **kwargs) -> None:
        if self.submitted or event.event_index != self.submit_on:
            return
        returned = broker.submit_or_replace_entry(
            order_id="entry",
            direction="long",
            entry_tick=401,
            stop_tick=397,
            target_tick=402,
        )
        returned.entry_tick = 999
        returned.active_from_event_index = 999
        self.submitted = True


def test_mutating_returned_order_cannot_change_engine_owned_order():
    strategy = _MutateReturnedOrderStrategy()

    BacktestEngine(_config()).run_event_replay([_session((100.0, 100.25, 100.50))], strategy)

    assert strategy.fills == [(1, 1, 401)]


def test_strategy_report_fields_cannot_overwrite_engine_accounting():
    class _InvalidReportStrategy(_SubmitOnceStrategy):
        def after_event(self, event, broker, **kwargs) -> None:
            if event.event_index == 0:
                broker.submit_or_replace_entry(
                    order_id="entry",
                    direction="long",
                    entry_tick=401,
                    stop_tick=397,
                    report_fields={"net_pnl": 1_000_000},
                )

    with pytest.raises(ValueError, match="engine-owned.*net_pnl"):
        BacktestEngine(_config()).run_event_replay([_session((100.0, 100.25))], _InvalidReportStrategy())


def test_nested_strategy_evidence_is_copied_at_broker_and_close_boundaries():
    class _NestedEvidenceStrategy(_SubmitOnceStrategy):
        def __init__(self):
            super().__init__()
            self.source_evidence = {"value": 1}

        def after_event(self, event, broker, **_):
            if self.submitted or event.event_index != 0:
                return
            broker.submit_or_replace_entry(
                order_id="entry",
                direction="long",
                entry_tick=401,
                stop_tick=397,
                target_tick=402,
                report_fields={"nested_evidence": self.source_evidence},
            )
            self.source_evidence["value"] = 2
            self.submitted = True

        def on_position_closed(self, position, trade, broker):
            del position, broker
            trade["nested_evidence"]["value"] = 3

    strategy = _NestedEvidenceStrategy()
    result = BacktestEngine(_config()).run_event_replay(
        [_session((100.0, 100.25, 100.50))],
        strategy,
    )

    assert result["trades"].iloc[0]["nested_evidence"] == {"value": 1}


def test_cutoff_skips_at_and_after_cutoff_events_and_flattens_with_synthetic_cutoff_event():
    session = _session(
        (100.0, 100.25, 110.0),
        offsets_ms=(5_398_000, 5_399_000, 5_400_000),
    )
    strategy = _SubmitOnceStrategy(target_tick=999)

    result = BacktestEngine(_config()).run_event_replay([session], strategy)

    trade = result["trades"].iloc[0]
    assert trade["entry_event_index"] == 1
    assert trade["exit_event_index"] == 2
    assert pd.Timestamp(trade["exit_timestamp"]).time() == pd.Timestamp("11:00:00").time()
    assert result["diagnostics"]["events_at_or_after_cutoff_skipped"] == 1
    assert result["session_audits"].loc[0, "events"] == 2


def test_event_contract_rejects_aggressor_side_signed_size_inconsistency():
    session = _session((100.0, 100.25))
    session.events.loc[1, "signed_size"] = -1

    with pytest.raises(ValueError, match="signed_size is inconsistent"):
        BacktestEngine(_config()).run_event_replay([session], _RecordingStrategy())


def test_engine_transitions_round_trip_through_validation_schema(tmp_path):
    result = BacktestEngine(_config()).run_event_replay(
        [_session((100.0, 100.25, 100.50))],
        _SubmitOnceStrategy(),
    )
    run_dir = tmp_path / "validation"
    write_validation_run(
        run_dir,
        ValidationMetadata(run_id="event-test", tick_size=0.25),
        event_transitions=result["event_transitions"],
    )

    loaded = load_validation_run(run_dir)
    assert list(result["event_transitions"].columns)[-2:] == ["state_json", "evidence_json"]
    assert result["event_transitions"]["state_json"].notna().all()
    assert result["event_transitions"]["evidence_json"].notna().all()
    assert not loaded.event_transitions.empty
    assert set(loaded.event_transitions["contract"].dropna()) == {"ESM6"}
    assert "entry_filled" in set(loaded.event_transitions["transition"])


@pytest.mark.parametrize(
    ("section", "message"),
    [
        ({"apex_rules": {"enabled": True}}, "does not yet implement apex_rules"),
        ({"event_filters": {"enabled": True}}, "does not yet implement generic event_filters"),
        ({"validation_export": {"enabled": True}}, "validation must be exported"),
    ],
)
def test_event_lane_fails_closed_for_unimplemented_bar_lane_policies(section, message):
    config = _config()
    config.update(section)

    with pytest.raises(ValueError, match=message):
        BacktestEngine(config).run_event_replay([_session((100.0, 100.25))], _RecordingStrategy())
