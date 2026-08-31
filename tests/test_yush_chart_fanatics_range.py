from __future__ import annotations

from datetime import date
from types import MappingProxyType, SimpleNamespace

import pandas as pd
import pytest

from alphaquest.backtest.event_replay import (
    CanonicalEvent,
    EventReplaySessionView,
)
from alphaquest.data.databento_session_stream import RthSummary
from alphaquest.strategy_modules.event.yush_chart_fanatics_range import (
    AoiScore,
    BigTradeThresholdSeed,
    ChartFanaticsRangeConfig,
    ChartFanaticsRangeEventStrategy,
    ChartFanaticsRangeState,
    CompletedBar,
    ProfileSnapshot,
    RegimeSnapshot,
    SweepEpisode,
    _classify_regime,
    _directional_breakout_trend,
    _failure_closed_back_inside,
    _nearest_rank,
    _post_target_stop_tick,
    _profile_snapshot,
    build_strategy,
)


def _view() -> EventReplaySessionView:
    return EventReplaySessionView(
        session_date=date(2026, 5, 14),
        contract_symbol="ESM26",
        metadata=MappingProxyType(
            {
                "previous_rth": RthSummary(
                    date(2026, 5, 13),
                    "ESM26",
                    107.0,
                    93.0,
                    101.0,
                ),
                "overnight_high": 106.0,
                "overnight_low": 94.0,
            }
        ),
        input_was_canonically_sorted=True,
    )


def _event(
    index: int,
    timestamp: str,
    tick: int,
    *,
    size: int = 1,
    side: str = "B",
) -> CanonicalEvent:
    value = pd.Timestamp(timestamp, tz="America/New_York")
    return CanonicalEvent(
        event_index=index,
        timestamp=value,
        timestamp_ns=int(value.value),
        source_ordinal=index,
        price=tick * 0.25,
        price_tick=tick,
        size=size,
        side=side,
        signed_size=size if side == "B" else -size,
    )


def _bar(
    index: int,
    *,
    close: int,
    low: int | None = None,
    high: int | None = None,
    volume: int = 1_000,
    delta: int = 0,
    bins: dict[int, int] | None = None,
) -> CompletedBar:
    low = close - 2 if low is None else low
    high = close + 2 if high is None else high
    start = pd.Timestamp(
        "2026-05-14 09:30:00",
        tz="America/New_York",
    ) + pd.Timedelta(minutes=3 * index)
    return CompletedBar(
        index=index,
        start_ns=int(start.value),
        end_ns=int((start + pd.Timedelta(minutes=3)).value),
        open_tick=close,
        high_tick=high,
        low_tick=low,
        close_tick=close,
        volume=volume,
        delta=delta,
        bin_volume=bins or {close // 4: volume},
        bin_delta={close // 4: delta},
        true_range_ticks=high - low,
        atr_ticks=20.0,
    )


def _aoi(
    edge_tick: int = 420,
    *,
    big_trade: bool = True,
    delta: bool = False,
    market_level: bool = True,
) -> AoiScore:
    footprint = (
        "adaptive_large_execution_and_top_decile_delta"
        if big_trade and delta
        else "adaptive_large_execution"
        if big_trade
        else "top_decile_delta"
        if delta
        else "none"
    )
    return AoiScore(
        edge_tick=edge_tick,
        institutional_footprint_kind=footprint,
        market_level_point=market_level,
        big_trade_point=big_trade,
        delta_profile_point=delta,
        nearest_market_level_type="PDH" if market_level else None,
        nearest_market_level_tick=edge_tick if market_level else None,
        big_trade_burst_id=1 if big_trade else None,
    )


def test_factory_freezes_replacement_mechanics() -> None:
    strategy = build_strategy({})

    assert isinstance(strategy, ChartFanaticsRangeEventStrategy)
    assert strategy.cfg.big_trade_reference_percentile == 0.995
    assert strategy.cfg.big_trade_lookback_sessions == 20
    assert strategy.cfg.big_trade_interval_ms == 100
    assert strategy.cfg.big_trade_price_bucket_ticks == 1
    assert strategy.cfg.value_area_method == "motivewave_standard"
    assert strategy.cfg.sweep_minimum_ticks == 2
    assert strategy.cfg.failure_confirmation_bars == 3
    assert strategy.cfg.morning_entry_start == "09:33:00"
    assert strategy.cfg.morning_entry_end == "11:30:00"
    assert strategy.cfg.afternoon_entry_start == "13:30:00"
    assert strategy.cfg.afternoon_entry_end == "15:30:00"
    assert strategy.cfg.minimum_stop_ticks == 6
    assert strategy.cfg.maximum_stop_ticks == 60
    assert strategy.cfg.maximum_entries_per_aoi == 1
    assert strategy.cfg.risk_budget_dollars == 1600.0

    with pytest.raises(ValueError, match="unknown"):
        build_strategy({"future_leak": True})
    with pytest.raises(ValueError, match="big_trade_reference_percentile"):
        build_strategy({"big_trade_reference_percentile": 0.999})


@pytest.mark.parametrize(
    ("name", "values"),
    (
        ("sweep_minimum_ticks", (2, 4, 6)),
        ("failure_confirmation_bars", (2, 3)),
        ("maximum_stop_atr_multiple", (1.0, 1.25, 1.5)),
        ("maximum_holding_bars", (8, 12, 16)),
    ),
)
def test_factory_accepts_only_predeclared_regime_grid_values(name, values) -> None:
    for value in values:
        assert getattr(build_strategy({name: value}).cfg, name) == value

    invalid = {
        "sweep_minimum_ticks": 3,
        "failure_confirmation_bars": 1,
        "maximum_stop_atr_multiple": 1.4,
        "maximum_holding_bars": 10,
    }[name]
    with pytest.raises(ValueError, match="uncertified Chart Fanatics v02 tunable value"):
        build_strategy({name: invalid})


def test_post_target_stop_is_one_tick_beyond_the_filled_entry() -> None:
    assert (
        _post_target_stop_tick(
            entry_price=100.50,
            direction="long",
            tick_size=0.25,
        )
        == 403
    )
    assert (
        _post_target_stop_tick(
            entry_price=100.50,
            direction="short",
            tick_size=0.25,
        )
        == 401
    )


def test_signal_windows_include_morning_and_afternoon_only() -> None:
    state = ChartFanaticsRangeState(_view(), ChartFanaticsRangeConfig())

    def timestamp(value: str) -> int:
        return int(
            pd.Timestamp(
                f"2026-05-14 {value}",
                tz="America/New_York",
            ).value
        )

    assert state._within_signal_window(timestamp("09:33:00"))
    assert state._within_signal_window(timestamp("11:30:00"))
    assert not state._within_signal_window(timestamp("12:30:00"))
    assert state._within_signal_window(timestamp("13:30:00"))
    assert state._within_signal_window(timestamp("15:30:00"))
    assert not state._within_signal_window(timestamp("15:30:01"))


def test_only_direction_aligned_breakout_trend_vetoes_entry() -> None:
    assert _directional_breakout_trend("short", "bullish_trend")
    assert _directional_breakout_trend("long", "bearish_trend")
    assert not _directional_breakout_trend(
        "short",
        "no_directional_breakout_trend",
    )
    assert not _directional_breakout_trend(
        "short",
        "insufficient_trend_history",
    )
    assert not _directional_breakout_trend("short", "bearish_trend")


def test_aoi_direction_uses_frozen_profile_location_not_level_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = ChartFanaticsRangeState(_view(), ChartFanaticsRangeConfig())
    profile = ProfileSnapshot(
        poc_bin=100,
        val_bin=95,
        vah_bin=105,
        poc_tick=400,
        val_tick=380,
        vah_tick=420,
        midpoint_tick=400,
        poc_volume=1_000,
        total_volume=10_000,
    )
    monkeypatch.setattr(
        state,
        "_market_levels",
        lambda: [("PDL", 420)],
    )
    monkeypatch.setattr(
        state,
        "_score_price",
        lambda tick, _profile, *, as_of_ns: _aoi(
            tick,
            big_trade=True,
            delta=tick >= 410,
        ),
    )

    long_aoi = state._best_aoi("long", profile, as_of_ns=1)
    short_aoi = state._best_aoi("short", profile, as_of_ns=1)

    assert long_aoi is not None
    assert long_aoi.edge_tick < 390
    assert short_aoi is not None
    assert short_aoi.edge_tick > 410


def test_market_level_without_institutional_footprint_cannot_qualify_aoi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = ChartFanaticsRangeState(_view(), ChartFanaticsRangeConfig())
    profile = ProfileSnapshot(
        poc_bin=100,
        val_bin=95,
        vah_bin=105,
        poc_tick=400,
        val_tick=380,
        vah_tick=420,
        midpoint_tick=400,
        poc_volume=1_000,
        total_volume=10_000,
    )
    monkeypatch.setattr(
        state,
        "_score_price",
        lambda tick, _profile, *, as_of_ns: _aoi(
            tick,
            big_trade=False,
            delta=False,
            market_level=True,
        ),
    )

    assert state._best_aoi("short", profile, as_of_ns=1) is None
    assert state._best_aoi("long", profile, as_of_ns=1) is None


def test_institutional_footprint_aoi_freezes_without_directional_trend(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = ChartFanaticsRangeState(_view(), ChartFanaticsRangeConfig())
    profile = ProfileSnapshot(
        poc_bin=100,
        val_bin=95,
        vah_bin=105,
        poc_tick=400,
        val_tick=380,
        vah_tick=420,
        midpoint_tick=400,
        poc_volume=1_000,
        total_volume=10_000,
    )
    regime = RegimeSnapshot(
        "no_directional_breakout_trend",
        0.4,
        400,
        402,
        400,
        401,
        0.4,
        410,
    )
    bar = _bar(20, close=410, low=405, high=415)
    state.published_profile = profile
    state.published_regime = regime
    monkeypatch.setattr(
        state,
        "_best_aoi",
        lambda direction, _profile, *, as_of_ns: _aoi(
            420 if direction == "short" else 380,
            big_trade=True,
            delta=True,
        ),
    )

    state._advance_frozen_aois(bar)

    assert state.frozen_aois["short"] is not None
    assert state.frozen_aois["long"] is not None
    assert state.diagnostics["frozen_aoi_candidates"] == 2


def test_big_trade_burst_uses_fixed_100ms_price_and_side_cell() -> None:
    state = ChartFanaticsRangeState(_view(), ChartFanaticsRangeConfig())
    state.big_trade_seed = BigTradeThresholdSeed(
        threshold_volume=200,
        reference_percentile=0.995,
        lookback_sessions=20,
        reference_observation_count=1_000,
        reference_start_session="2026-04-15",
        reference_end_session="2026-05-13",
        percentile_method="nearest_rank",
    )
    state.ingest(_event(0, "2026-05-14 09:30:00.000", 400, size=80))
    state.ingest(_event(1, "2026-05-14 09:30:00.050", 400, size=70))
    state.ingest(_event(2, "2026-05-14 09:30:00.090", 400, size=60))
    assert not state.bursts

    state.ingest(_event(3, "2026-05-14 09:30:00.200", 404, size=1))

    assert len(state.bursts) == 1
    burst = state.bursts[0]
    assert burst.side == "B"
    assert burst.price_low_tick == 400
    assert burst.price_high_tick == 400
    assert burst.size == 210
    assert burst.qualified_at_ns > burst.ended_at_ns


def test_developing_profile_publishes_only_after_bar_close() -> None:
    state = ChartFanaticsRangeState(_view(), ChartFanaticsRangeConfig())
    state.ingest(_event(0, "2026-05-14 09:30:00.000", 400, size=100))
    state.ingest(_event(1, "2026-05-14 09:32:59.000", 404, size=100))

    assert state.published_profile is None

    state.ingest(_event(2, "2026-05-14 09:33:00.000", 408, size=1))

    assert state.published_profile is not None
    assert state.diagnostics["completed_3m_bars"] == 1
    assert state.published_profile.total_volume == 200


def test_profile_and_nearest_rank_rules_are_deterministic() -> None:
    profile = _profile_snapshot(
        {100: 10, 101: 50, 102: 30, 103: 10},
        4,
    )

    assert profile is not None
    assert profile.poc_bin == 101
    assert profile.val_bin == 101
    assert profile.vah_bin == 103
    assert profile.val_tick == 404
    assert profile.vah_tick == 416
    assert profile.midpoint_tick == 410
    assert _nearest_rank([1, 2, 3, 4], 0.75) == 3
    assert _nearest_rank([], 0.90) is None


def test_motivewave_standard_pair_tie_deterministically_selects_lower_pair() -> None:
    profile = _profile_snapshot(
        {
            98: 20,
            99: 20,
            100: 60,
            101: 20,
            102: 20,
        },
        4,
        0.70,
        "motivewave_standard",
    )

    assert profile is not None
    assert profile.poc_bin == 100
    assert profile.val_bin == 98
    assert profile.vah_bin == 100
    assert profile.val_tick == 392
    assert profile.vah_tick == 404


def test_may_12_1345_profile_matches_motivewave_standard_boundaries() -> None:
    # Frozen ESM26 RTH bucket volumes from 09:30:00 through 13:44:59.999
    # New York on 2026-05-12.  The user independently reconciled these row
    # volumes in MotiveWave with Tick Interval=4 and Range=70%.
    volumes = {
        7363: 1511,
        7364: 10300,
        7365: 22009,
        7366: 15554,
        7367: 14691,
        7368: 15074,
        7369: 13999,
        7370: 12497,
        7371: 18832,
        7372: 24201,
        7373: 32101,
        7374: 27296,
        7375: 23979,
        7376: 24395,
        7377: 26732,
        7378: 18357,
        7379: 14686,
        7380: 21204,
        7381: 17201,
        7382: 23085,
        7383: 19843,
        7384: 20323,
        7385: 16928,
        7386: 15142,
        7387: 15910,
        7388: 18502,
        7389: 23209,
        7390: 17591,
        7391: 12074,
        7392: 20141,
        7393: 22039,
        7394: 21705,
        7395: 16637,
        7396: 14157,
        7397: 17548,
        7398: 14063,
        7399: 14863,
        7400: 14888,
        7401: 12281,
        7402: 20322,
        7403: 18163,
        7404: 16874,
        7405: 14766,
        7406: 16985,
        7407: 14799,
        7408: 13810,
        7409: 10521,
        7410: 6206,
        7411: 8583,
        7412: 10762,
        7413: 2264,
        7414: 2212,
        7415: 1219,
        7416: 1449,
        7417: 358,
    }

    profile = _profile_snapshot(volumes, 4, 0.70, "motivewave_standard")

    assert profile is not None
    assert profile.total_volume == 864841
    assert profile.poc_bin == 7373
    assert profile.poc_volume == 32101
    assert profile.val_bin == 7371
    assert profile.vah_bin == 7403
    assert profile.val_tick * 0.25 == 7371.0
    assert profile.vah_tick * 0.25 == 7404.0
    assert profile.midpoint_tick * 0.25 == 7387.5


def test_delta_footprint_at_vah_uses_highest_included_profile_row() -> None:
    state = ChartFanaticsRangeState(_view(), ChartFanaticsRangeConfig())
    state.profile_delta = {100: 1, 101: 10}
    profile = ProfileSnapshot(
        poc_bin=100,
        val_bin=100,
        vah_bin=101,
        poc_tick=400,
        val_tick=400,
        vah_tick=408,
        midpoint_tick=404,
        poc_volume=1_000,
        total_volume=2_000,
    )

    score = state._score_price(
        profile.vah_tick,
        profile,
        as_of_ns=int(pd.Timestamp("2026-05-14 10:00", tz="America/New_York").value),
    )

    assert score.delta_profile_point
    assert score.delta_profile_bin_low_tick == 404
    assert score.delta_profile_bin_high_tick == 407
    assert score.delta_profile_abs_delta == 10


def test_non_trending_regime_uses_two_completed_thirty_minute_windows() -> None:
    config = ChartFanaticsRangeConfig()
    bars = [
        _bar(
            index,
            close=400 + (index % 2),
            bins={99: 100, 100: 500, 101: 100},
        )
        for index in range(20)
    ]

    regime = _classify_regime(bars, config)

    assert regime.label == "no_directional_breakout_trend"
    assert regime.overlap == 1.0
    assert regime.efficiency <= 0.35


def test_trend_state_discloses_insufficient_completed_history() -> None:
    regime = _classify_regime(
        [_bar(index, close=400) for index in range(19)],
        ChartFanaticsRangeConfig(),
    )

    assert regime.label == "insufficient_trend_history"


def test_failure_signal_requires_reward_and_stop_constraints() -> None:
    state = ChartFanaticsRangeState(_view(), ChartFanaticsRangeConfig())
    profile = ProfileSnapshot(
        poc_bin=98,
        val_bin=90,
        vah_bin=105,
        poc_tick=392,
        val_tick=360,
        vah_tick=423,
        midpoint_tick=391.5,
        poc_volume=1_000,
        total_volume=10_000,
    )
    regime = RegimeSnapshot(
        label="no_directional_breakout_trend",
        overlap=0.8,
        poc_a_tick=392,
        poc_b_tick=392,
        midpoint_a_tick=391.5,
        midpoint_b_tick=391.5,
        efficiency=0.2,
        close_tick=410,
    )
    episode = SweepEpisode(
        episode_id=1,
        direction="short",
        aoi=_aoi(420, big_trade=True),
        sweep_bar_index=20,
        sweep_bar_high_tick=424,
        sweep_bar_low_tick=418,
        highest_tick_since_sweep=424,
        lowest_tick_since_sweep=414,
        starting_profile=profile,
        starting_regime=regime,
    )
    failure = _bar(
        21,
        close=414,
        low=413,
        high=421,
        delta=-100,
    )

    signal = state._build_pending_signal(
        episode,
        failure,
        profile,
        regime,
    )

    assert signal is not None
    assert signal.entry_tick == 419
    assert signal.stop_tick == 426
    assert signal.risk_ticks == 7
    assert signal.target_1_tick == 392
    assert signal.target_2_tick == 360


def test_failure_reclaim_uses_close_inside_without_delta_sign_gate() -> None:
    profile = ProfileSnapshot(
        poc_bin=100,
        val_bin=95,
        vah_bin=105,
        poc_tick=400,
        val_tick=380,
        vah_tick=423,
        midpoint_tick=401.5,
        poc_volume=1_000,
        total_volume=10_000,
    )
    regime = RegimeSnapshot(
        "no_directional_breakout_trend",
        0.8,
        400,
        400,
        401.5,
        401.5,
        0.2,
        402,
    )
    episode = SweepEpisode(
        episode_id=1,
        direction="short",
        aoi=_aoi(420, big_trade=True),
        sweep_bar_index=20,
        sweep_bar_high_tick=432,
        sweep_bar_low_tick=418,
        highest_tick_since_sweep=432,
        lowest_tick_since_sweep=410,
        starting_profile=profile,
        starting_regime=regime,
    )
    failure = _bar(
        22,
        close=419,
        low=418,
        high=432,
        delta=-50,
    )

    assert failure.close_location is not None
    assert failure.close_location < 0.20
    assert _failure_closed_back_inside(episode, failure)
    failure.close_tick = episode.aoi.edge_tick
    assert not _failure_closed_back_inside(episode, failure)


def test_failure_confirmation_depends_only_on_price_reclaim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = ChartFanaticsRangeState(_view(), ChartFanaticsRangeConfig())
    profile = ProfileSnapshot(
        poc_bin=98,
        val_bin=90,
        vah_bin=105,
        poc_tick=392,
        val_tick=360,
        vah_tick=423,
        midpoint_tick=391.5,
        poc_volume=1_000,
        total_volume=10_000,
    )
    regime = RegimeSnapshot(
        "no_directional_breakout_trend",
        0.8,
        392,
        392,
        391.5,
        391.5,
        0.2,
        410,
    )
    episode = SweepEpisode(
        episode_id=1,
        direction="short",
        aoi=_aoi(420, big_trade=True),
        sweep_bar_index=20,
        sweep_bar_high_tick=424,
        sweep_bar_low_tick=418,
        highest_tick_since_sweep=424,
        lowest_tick_since_sweep=418,
        starting_profile=profile,
        starting_regime=regime,
    )
    failure = _bar(21, close=419, low=417, high=422, delta=-20)
    signal = SimpleNamespace(order_id="order-1")
    state.published_profile = profile
    state.published_regime = regime
    state.episodes["short"] = episode
    monkeypatch.setattr(
        state,
        "_build_pending_signal",
        lambda *_args: signal,
    )

    state._process_existing_episodes(failure)

    assert state.pending == {"order-1": signal}
    assert state.diagnostics["failure_confirmations"] == 1


def test_failure_signal_rejects_insufficient_midpoint_reward() -> None:
    state = ChartFanaticsRangeState(_view(), ChartFanaticsRangeConfig())
    profile = ProfileSnapshot(
        poc_bin=100,
        val_bin=95,
        vah_bin=105,
        poc_tick=400,
        val_tick=380,
        vah_tick=423,
        midpoint_tick=401.5,
        poc_volume=1_000,
        total_volume=10_000,
    )
    regime = RegimeSnapshot(
        "no_directional_breakout_trend",
        0.8,
        400,
        400,
        401.5,
        401.5,
        0.2,
        402,
    )
    episode = SweepEpisode(
        episode_id=1,
        direction="short",
        aoi=_aoi(405, big_trade=True),
        sweep_bar_index=20,
        sweep_bar_high_tick=410,
        sweep_bar_low_tick=403,
        highest_tick_since_sweep=410,
        lowest_tick_since_sweep=400,
        starting_profile=profile,
        starting_regime=regime,
    )
    failure = _bar(21, close=402, low=401, high=408)

    assert (
        state._build_pending_signal(
            episode,
            failure,
            profile,
            regime,
        )
        is None
    )
    assert state.diagnostics["signal_target_1_reward_rejections"] == 1


def test_each_aoi_allows_only_one_filled_entry() -> None:
    state = ChartFanaticsRangeState(_view(), ChartFanaticsRangeConfig())

    assert state._aoi_entry_count("short", 420) == 0
    state.record_aoi_entry("short", 420)

    assert state._aoi_entry_count("short", 420) == 1
    assert state._aoi_entry_count("long", 420) == 0
    assert state._aoi_entry_count("short", 421) == 0
