from __future__ import annotations

import math

import pandas as pd

from propstack.strategy_modules.entry.base import Signal
from propstack.strategy_modules.entry.yush_range_10 import YushRange10Entry


class YushRange17Entry(YushRange10Entry):
    name = "yush_range_17"

    def __init__(self, params: dict):
        super().__init__(params)
        self.max_signal_risk_points = float(params.get("max_signal_risk_points", 4.0))
        if not math.isfinite(self.max_signal_risk_points) or self.max_signal_risk_points <= 0:
            raise ValueError("entry.params.max_signal_risk_points must be greater than 0.")

    def on_bar_intrabar(
        self,
        bar: pd.Series,
        detail_rows: pd.DataFrame,
        trades_today: int = 0,
    ) -> Signal | None:
        self._roll_session(bar)
        if detail_rows is None or detail_rows.empty:
            return None

        levels = [level for level in self._market_levels(bar) if level["type"] == "PDL"]
        previous_bar = self.current_session_bars[-1] if self.current_session_bars else None
        atr = self._atr()
        session_key = self.session_key
        can_emit = (
            bool(bar.get("is_rth", False))
            and self.allow_short
            and trades_today < self.max_trades_per_day
            and self.signals_by_session.get(session_key, 0) < self.max_trades_per_day
            and atr is not None
            and bool(levels)
        )
        if (
            not can_emit
            or not self._detail_window_can_sweep(levels, previous_bar, detail_rows)
            or not self._detail_window_can_absorb(detail_rows)
        ):
            self.state.update_bar_aggregate(
                detail_rows,
                bar_timestamp=pd.Timestamp(bar["timestamp"]),
                profile_bucket_points=self.profile_bucket_points,
                range_snapshot_minutes=self.range_snapshot_minutes,
            )
            return None

        for tick in detail_rows.itertuples(index=False):
            tick_state = self.state.update_tick(
                tick,
                bar_timestamp=pd.Timestamp(bar["timestamp"]),
                profile_bucket_points=self.profile_bucket_points,
                delta_bucket_points=self.delta_bucket_points,
                absorption_delta_threshold=self.absorption_delta_threshold,
                hold_seconds=self.absorption_hold_seconds,
                range_snapshot_minutes=self.range_snapshot_minutes,
            )
            if tick_state is None:
                continue
            tick_time = tick_state["timestamp"].time()
            if tick_time < self.start_time or tick_time > self.end_time:
                continue

            sweep = self._market_sweep("short", levels, previous_bar)
            if sweep is None or sweep["market_level_type"] != "PDL":
                continue
            if abs(float(tick_state["price"]) - float(sweep["market_level_price"])) > self.level_atr_multiple * atr:
                continue
            confirmation = self.state.confirmed_orderflow("short", self.confirmation_modes)
            if confirmation is None:
                continue
            signal = self._pdl_reclaim_failure_signal(bar, tick_state, sweep, confirmation, atr)
            if signal.metadata["signal_risk_points"] > self.max_signal_risk_points:
                continue
            self.signals_by_session[session_key] = self.signals_by_session.get(session_key, 0) + 1
            return signal
        return None

    def _pdl_reclaim_failure_signal(
        self,
        bar: pd.Series,
        tick_state: dict,
        sweep: dict,
        confirmation: dict,
        atr: float,
    ) -> Signal:
        signal = super()._pdl_reclaim_failure_signal(bar, tick_state, sweep, confirmation, atr)
        risk_points = abs(float(signal.report_fields["entry_reference_price"]) - float(signal.report_fields["signal_stop_price"]))
        signal.metadata["max_signal_risk_points"] = self.max_signal_risk_points
        signal.metadata["signal_risk_points"] = risk_points
        signal.report_fields["max_signal_risk_points"] = self.max_signal_risk_points
        signal.report_fields["signal_risk_points"] = risk_points
        return signal
