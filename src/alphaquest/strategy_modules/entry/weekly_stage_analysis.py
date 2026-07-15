from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import math
from statistics import fmean

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


@dataclass(frozen=True)
class _DailyBar:
    session_date: date
    open: float
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class _WeeklyStageState:
    week_start: date
    week_end: date
    open: float
    high: float
    low: float
    close: float
    ma10: float
    ma20: float
    ma30: float
    ma40: float
    prev_ma10: float
    prev_ma20: float
    stage2_score: int
    stage4_score: int


class WeeklyStageAnalysisEntry:
    name = "weekly_stage_analysis"

    def __init__(self, params: dict):
        self.params = dict(params)
        self.setup_mode = str(params.get("setup_mode", "stage2_opening_range_breakout")).lower()
        self.rth_start = parse_time(params.get("rth_start", "09:30:00"))
        self.start_time = parse_time(params.get("start_time", "09:45:00"))
        self.end_time = parse_time(params.get("end_time", "12:30:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:55:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.opening_range_minutes = float(params.get("opening_range_minutes", 15))
        self.stage_strength_threshold = int(params.get("stage_strength_threshold", 5))
        self.min_breakout_ticks = float(params.get("min_breakout_ticks", 0.0))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.consolidation_lookback_days = int(params.get("consolidation_lookback_days", 5))
        self.consolidation_max_range_pct = float(params.get("consolidation_max_range_pct", 0.025))
        self.support_proximity_pct = float(params.get("support_proximity_pct", 0.0125))
        self.state_by_day: dict[date, dict] = {}
        self.session_stats: dict[date, dict] = {}
        self._stage_cache: dict[date, _WeeklyStageState | None] = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        session_date = _date(bar.get("session_date", timestamp.date()))
        state = self._state(session_date)
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)

        try:
            self._update_opening_range(bar, state, timestamp)
            if state["signaled"] or trades_today >= self.max_trades_per_day:
                return None
            if bar_close.time() < self.start_time or bar_close.time() > self.end_time:
                return None

            stage = self._stage_for_session(session_date)
            if stage is None or stage.stage2_score < self.stage_strength_threshold:
                return None
            if stage.stage4_score >= self.stage_strength_threshold:
                return None

            signal = self._signal_for_mode(bar, bar_close, session_date, stage, state)
            if signal is not None:
                state["signaled"] = True
            return signal
        finally:
            self._record_session_bar(bar, session_date)

    def _signal_for_mode(
        self,
        bar: pd.Series,
        bar_close: pd.Timestamp,
        session_date: date,
        stage: _WeeklyStageState,
        state: dict,
    ) -> Signal | None:
        mode = self.setup_mode
        if mode == "stage2_opening_range_breakout":
            opening_range = state["opening_range"]
            if opening_range is None:
                return None
            close = _required_float(bar.get("close"), "close")
            level = float(opening_range["high"])
            if close < level + self._buffer:
                return None
            return self._signal(bar, bar_close, stage, "stage2_opening_range_breakout", level)

        if mode == "stage2_prior_high_reclaim":
            prior = self._prior_daily_bar(session_date)
            if prior is None:
                return None
            high = _required_float(bar.get("high"), "high")
            close = _required_float(bar.get("close"), "close")
            if high < prior.high + self._buffer or close < prior.high:
                return None
            return self._signal(bar, bar_close, stage, "stage2_prior_high_reclaim", prior.high)

        if mode == "stage2_prior_close_reclaim":
            prior = self._prior_daily_bar(session_date)
            if prior is None:
                return None
            low = _required_float(bar.get("low"), "low")
            close = _required_float(bar.get("close"), "close")
            if low > prior.close or close < prior.close + self._buffer:
                return None
            return self._signal(bar, bar_close, stage, "stage2_prior_close_reclaim", prior.close)

        if mode == "stage2_weekly_support_reclaim":
            prior = self._prior_daily_bar(session_date)
            if prior is None:
                return None
            low = _required_float(bar.get("low"), "low")
            close = _required_float(bar.get("close"), "close")
            support = max(stage.ma10, stage.ma20)
            if min(prior.low, low) > support * (1.0 + self.support_proximity_pct):
                return None
            if close < prior.close + self._buffer:
                return None
            return self._signal(bar, bar_close, stage, "stage2_weekly_support_reclaim", support)

        if mode == "stage2_compression_breakout":
            recent = self._prior_daily_bars(session_date, self.consolidation_lookback_days)
            if len(recent) < self.consolidation_lookback_days:
                return None
            range_high = max(day.high for day in recent)
            range_low = min(day.low for day in recent)
            midpoint = (range_high + range_low) / 2.0
            if midpoint <= 0:
                return None
            if (range_high - range_low) / midpoint > self.consolidation_max_range_pct:
                return None
            close = _required_float(bar.get("close"), "close")
            if close < range_high + self._buffer:
                return None
            return self._signal(bar, bar_close, stage, "stage2_compression_breakout", range_high)

        raise ValueError(f"Unknown weekly_stage_analysis setup_mode: {self.setup_mode}")

    def _signal(
        self,
        bar: pd.Series,
        bar_close: pd.Timestamp,
        stage: _WeeklyStageState,
        level_type: str,
        swept_level: float,
    ) -> Signal:
        high = _required_float(bar.get("high"), "high")
        low = _required_float(bar.get("low"), "low")
        close = _required_float(bar.get("close"), "close")
        report_fields = {
            "setup_mode": self.setup_mode,
            "weekly_stage_week_start": stage.week_start.isoformat(),
            "weekly_stage_week_end": stage.week_end.isoformat(),
            "weekly_stage_close": stage.close,
            "weekly_stage_ma10": stage.ma10,
            "weekly_stage_ma20": stage.ma20,
            "weekly_stage_ma30": stage.ma30,
            "weekly_stage_ma40": stage.ma40,
            "weekly_stage2_score": stage.stage2_score,
            "weekly_stage4_score": stage.stage4_score,
            "stage_strength_threshold": self.stage_strength_threshold,
            "min_breakout_ticks": self.min_breakout_ticks,
            "signal_close": close,
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
        }
        return Signal(
            direction="long",
            level_type=level_type,
            swept_level=swept_level,
            sweep_timestamp=bar_close,
            sweep_high=high,
            sweep_low=low,
            reclaim_timestamp=bar_close,
            metadata={
                "setup_mode": self.setup_mode,
                "weekly_stage2_score": stage.stage2_score,
                "weekly_stage_week_end": stage.week_end.isoformat(),
                "flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            },
            report_fields=report_fields,
        )

    def _stage_for_session(self, session_date: date) -> _WeeklyStageState | None:
        if session_date in self._stage_cache:
            return self._stage_cache[session_date]
        weekly = self._weekly_bars_before(session_date)
        if len(weekly) < 41:
            self._stage_cache[session_date] = None
            return None

        closes = [item.close for item in weekly]
        last = weekly[-1]
        ma10 = fmean(closes[-10:])
        ma20 = fmean(closes[-20:])
        ma30 = fmean(closes[-30:])
        ma40 = fmean(closes[-40:])
        prev_ma10 = fmean(closes[-11:-1])
        prev_ma20 = fmean(closes[-21:-1])
        prior_four = weekly[-5:-1]

        stage2_score = sum(
            [
                last.close > ma10,
                last.close > ma20,
                last.close > ma30,
                last.close > ma40,
                ma10 > ma20 > ma30,
                ma10 > prev_ma10,
                ma20 > prev_ma20,
                last.high >= max(item.high for item in prior_four),
            ]
        )
        stage4_score = sum(
            [
                last.close < ma10,
                last.close < ma20,
                last.close < ma30,
                last.close < ma40,
                ma10 < ma20 < ma30,
                ma10 < prev_ma10,
                ma20 < prev_ma20,
                last.low <= min(item.low for item in prior_four),
            ]
        )

        state = _WeeklyStageState(
            week_start=last.session_date,
            week_end=last.session_date,
            open=last.open,
            high=last.high,
            low=last.low,
            close=last.close,
            ma10=ma10,
            ma20=ma20,
            ma30=ma30,
            ma40=ma40,
            prev_ma10=prev_ma10,
            prev_ma20=prev_ma20,
            stage2_score=int(stage2_score),
            stage4_score=int(stage4_score),
        )
        self._stage_cache[session_date] = state
        return state

    def _weekly_bars_before(self, session_date: date) -> list[_DailyBar]:
        if not self.session_stats:
            return []
        current_period = pd.Timestamp(session_date).to_period("W-FRI")
        grouped: dict[pd.Period, list[_DailyBar]] = {}
        for day in sorted(self.session_stats):
            if day >= session_date:
                continue
            period = pd.Timestamp(day).to_period("W-FRI")
            if period >= current_period:
                continue
            stats = self.session_stats[day]
            grouped.setdefault(period, []).append(
                _DailyBar(
                    session_date=day,
                    open=_required_float(stats.get("open"), "open"),
                    high=_required_float(stats.get("high"), "high"),
                    low=_required_float(stats.get("low"), "low"),
                    close=_required_float(stats.get("close"), "close"),
                )
            )

        weekly: list[_DailyBar] = []
        for period in sorted(grouped):
            days = grouped[period]
            weekly.append(
                _DailyBar(
                    session_date=period.end_time.date(),
                    open=days[0].open,
                    high=max(day.high for day in days),
                    low=min(day.low for day in days),
                    close=days[-1].close,
                )
            )
        return weekly

    def _prior_daily_bar(self, session_date: date) -> _DailyBar | None:
        bars = self._prior_daily_bars(session_date, 1)
        return bars[-1] if bars else None

    def _prior_daily_bars(self, session_date: date, count: int) -> list[_DailyBar]:
        days = sorted(day for day in self.session_stats if day < session_date)
        out: list[_DailyBar] = []
        for day in days[-count:]:
            stats = self.session_stats[day]
            out.append(
                _DailyBar(
                    session_date=day,
                    open=_required_float(stats.get("open"), "open"),
                    high=_required_float(stats.get("high"), "high"),
                    low=_required_float(stats.get("low"), "low"),
                    close=_required_float(stats.get("close"), "close"),
                )
            )
        return out

    def _update_opening_range(self, bar: pd.Series, state: dict, timestamp: pd.Timestamp) -> None:
        if state["opening_range"] is not None:
            return
        elapsed = self._elapsed_minutes(timestamp)
        if elapsed < 0:
            return
        if elapsed < self.opening_range_minutes:
            state["opening_bars"].append(bar)
            if self._opening_bars_complete(state["opening_bars"]):
                state["opening_range"] = self._build_opening_range(state["opening_bars"])
            return
        if state["opening_bars"]:
            state["opening_range"] = self._build_opening_range(state["opening_bars"])

    def _opening_bars_complete(self, bars: list[pd.Series]) -> bool:
        required = max(1, int(math.ceil(self.opening_range_minutes / self.bar_interval_minutes)))
        return len(bars) >= required

    def _build_opening_range(self, bars: list[pd.Series]) -> dict | None:
        if not bars:
            return None
        highs = [_finite_float(bar.get("high")) for bar in bars]
        lows = [_finite_float(bar.get("low")) for bar in bars]
        opens = [_finite_float(bar.get("open")) for bar in bars]
        if any(value is None for value in [*highs, *lows, *opens]):
            return None
        return {
            "open": opens[0],
            "high": max(highs),
            "low": min(lows),
            "start_timestamp": bars[0]["timestamp"],
            "end_timestamp": pd.Timestamp(bars[-1]["timestamp"]) + pd.Timedelta(minutes=self.bar_interval_minutes),
        }

    def _record_session_bar(self, bar: pd.Series, session_date: date) -> None:
        high = _finite_float(bar.get("high"))
        low = _finite_float(bar.get("low"))
        close = _finite_float(bar.get("close"))
        open_ = _finite_float(bar.get("open"))
        if high is None or low is None or close is None or open_ is None:
            return
        stats = self.session_stats.get(session_date)
        if stats is None:
            self.session_stats[session_date] = {
                "session_date": session_date,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
            }
            return
        stats["high"] = max(float(stats["high"]), high)
        stats["low"] = min(float(stats["low"]), low)
        stats["close"] = close

    @property
    def _buffer(self) -> float:
        return self.min_breakout_ticks * self.tick_size

    def _elapsed_minutes(self, timestamp: pd.Timestamp) -> float:
        start = pd.Timestamp(datetime.combine(timestamp.date(), self.rth_start))
        if timestamp.tzinfo is not None:
            start = start.tz_localize(timestamp.tzinfo)
        return (timestamp - start).total_seconds() / 60.0

    def _state(self, session_date: date) -> dict:
        return self.state_by_day.setdefault(
            session_date,
            {
                "signaled": False,
                "opening_bars": [],
                "opening_range": None,
            },
        )

    def _validate(self) -> None:
        allowed_modes = {
            "stage2_opening_range_breakout",
            "stage2_prior_high_reclaim",
            "stage2_prior_close_reclaim",
            "stage2_weekly_support_reclaim",
            "stage2_compression_breakout",
        }
        if self.setup_mode not in allowed_modes:
            raise ValueError(f"setup_mode must be one of {sorted(allowed_modes)}.")
        if self.tick_size <= 0:
            raise ValueError("tick_size must be greater than 0.")
        if self.bar_interval_minutes <= 0 or self.opening_range_minutes <= 0:
            raise ValueError("bar_interval_minutes and opening_range_minutes must be greater than 0.")
        if not 1 <= self.stage_strength_threshold <= 8:
            raise ValueError("stage_strength_threshold must be between 1 and 8.")
        if self.max_trades_per_day <= 0:
            raise ValueError("max_trades_per_day must be greater than 0.")
        if self.consolidation_lookback_days < 2:
            raise ValueError("consolidation_lookback_days must be at least 2.")
        if self.consolidation_max_range_pct <= 0:
            raise ValueError("consolidation_max_range_pct must be positive.")
        if self.support_proximity_pct < 0:
            raise ValueError("support_proximity_pct must be non-negative.")


def _date(value) -> date:
    if isinstance(value, date):
        return value
    return pd.Timestamp(value).date()


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _required_float(value, name: str) -> float:
    out = _finite_float(value)
    if out is None:
        raise ValueError(f"entry bar is missing finite {name}.")
    return out
