from __future__ import annotations

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.yush_range_1 import YushRange1Entry


class YushRange8Entry(YushRange1Entry):
    name = "yush_range_8"

    def __init__(self, params: dict):
        super().__init__(params)
        self.level_atr_multiple = float(params.get("level_atr_multiple", 2.0))
        if self.level_atr_multiple <= 0:
            raise ValueError("entry.params.level_atr_multiple must be greater than 0.")

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
        entry_price = float(tick_state["price"])
        stop_price = (
            entry_price + self.stop_points
            if self.stop_points is not None
            else confirmation["bucket_top"] + self.stop_offset_ticks * self.tick_size
        )
        fields = {
            "setup_mode": self.name,
            "entry_mode": "intrabar",
            "entry_reference_price": entry_price,
            "intrabar_entry_price": entry_price,
            "signal_stop_price": float(stop_price),
            "signal_timestamp": tick_state["timestamp"],
            "intended_entry_timestamp": tick_state["timestamp"],
            "signal_flatten_time": self.flatten_time.strftime("%H:%M:%S"),
            "market_level_type": sweep["market_level_type"],
            "market_level_price": sweep["market_level_price"],
            "market_sweep_window": sweep["market_sweep_window"],
            "market_sweep_source": sweep["market_sweep_source"],
            "pdl_reclaim_failure_profile_filter": "disabled",
            "pdl_reclaim_failure_range_filter": "disabled",
            "level_atr_multiple": self.level_atr_multiple,
            "distance_to_market_level": abs(entry_price - float(sweep["market_level_price"])),
            "atr_period": self.atr_period,
            "atr": atr,
            "delta_bucket_points": self.delta_bucket_points,
            "orderflow_confirmation_type": confirmation["confirmation_type"],
            "orderflow_bucket_bottom": confirmation["bucket_bottom"],
            "orderflow_bucket_top": confirmation["bucket_top"],
            "orderflow_bucket_delta": confirmation["delta"],
            "orderflow_hold_start": confirmation["hold_start"],
            "orderflow_confirmed_at": confirmation["confirmed_at"],
            "absorption_bucket_bottom": confirmation["bucket_bottom"],
            "absorption_bucket_top": confirmation["bucket_top"],
            "absorption_bucket_delta": confirmation["delta"],
            "absorption_hold_start": confirmation["hold_start"],
            "absorption_confirmed_at": confirmation["confirmed_at"],
            "absorption_hold_seconds": self.absorption_hold_seconds,
            "absorption_delta_threshold": self.absorption_delta_threshold,
            "confirmation_modes": ",".join(self.confirmation_modes),
            "stop_points": self.stop_points,
            "target_points": self.target_points,
            "intrabar_source": "sierra_scid_record_replay",
            "intrabar_source_quality_label": (
                "Sierra SCID record close-only replay; raw high/low are not treated as traded-price extrema; "
                "not exchange MBO sequencing."
            ),
            "confirmation_high": entry_price,
            "confirmation_low": entry_price,
        }
        if self.target_points is not None:
            fields["signal_target_price"] = entry_price - self.target_points
        else:
            fields["signal_target_r_multiple"] = 2.0
        return Signal(
            direction="short",
            level_type=f"{self.name}_short_PDL",
            swept_level=float(sweep["market_level_price"]),
            sweep_timestamp=tick_state["timestamp"],
            sweep_high=float(self.state.current_bar_high or tick_state["price"]),
            sweep_low=float(self.state.current_bar_low or tick_state["price"]),
            reclaim_timestamp=tick_state["timestamp"],
            breakout_level=float(confirmation["bucket_bottom"]),
            metadata=fields.copy(),
            report_fields=fields,
        )
