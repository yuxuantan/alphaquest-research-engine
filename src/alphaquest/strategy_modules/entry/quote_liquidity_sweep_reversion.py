from __future__ import annotations

import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class QuoteLiquiditySweepReversionEntry:
    name = "quote_liquidity_sweep_reversion"

    def __init__(self, params: dict):
        self.params = params
        self.level_set = str(params.get("level_set", "previous_rth")).lower()
        self.opening_range_minutes = int(params.get("opening_range_minutes", 30))
        self.start_time = parse_time(params.get("start_time", "09:35:00"))
        self.end_time = parse_time(params.get("end_time", "12:00:00"))
        self.flatten_time = parse_time(params.get("flatten_time", "15:45:00"))
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 1))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.min_sweep_ticks = float(params.get("min_sweep_ticks", 2))
        self.reclaim_buffer_ticks = float(params.get("reclaim_buffer_ticks", 0))
        self.reclaim_window_bars = int(params.get("reclaim_window_bars", 3))
        self.depth_window = int(params.get("depth_window", 3))
        self.min_refill_ratio = float(params.get("min_refill_ratio", 1.5))
        self.min_quote_imbalance = float(params.get("min_quote_imbalance", 0.10))
        self.max_spread_ticks = float(params.get("max_spread_ticks", 4.0))
        self.require_liquidity_demand = bool(params.get("require_liquidity_demand", False))
        self.min_failed_demand_imbalance = float(params.get("min_failed_demand_imbalance", 0.10))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.allow_long = bool(params.get("allow_long", True))
        self.allow_short = bool(params.get("allow_short", True))
        self.target_r_multiple = float(params.get("target_r_multiple", 1.5))
        self.state_by_day: dict = {}
        self._validate()

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        state = self._state(bar.get("session_date", timestamp.date()))
        self._update_opening_range(state, bar)

        t = timestamp.time()
        if t < self.start_time or t > self.end_time:
            return None

        bar_index = state["bar_index"]
        levels = self._levels(bar, state)
        for level in levels:
            signal = self._process_level(bar, level, bar_index)
            if signal is not None:
                return signal
        return None

    def _process_level(self, bar: pd.Series, level: dict, bar_index: int) -> Signal | None:
        state = self._state(bar.get("session_date", pd.Timestamp(bar["timestamp"]).date()))
        key = f"{level['direction']}:{level['level_type']}"
        sweep = state["sweeps"].get(key)
        if sweep is not None:
            sweep["sweep_low"] = min(sweep["sweep_low"], float(bar["low"]))
            sweep["sweep_high"] = max(sweep["sweep_high"], float(bar["high"]))

        threshold = self.min_sweep_ticks * self.tick_size
        if sweep is None:
            if level["direction"] == "long" and self.allow_long and float(bar["low"]) <= level["price"] - threshold:
                sweep = self._new_sweep(bar, level, bar_index)
                state["sweeps"][key] = sweep
            elif level["direction"] == "short" and self.allow_short and float(bar["high"]) >= level["price"] + threshold:
                sweep = self._new_sweep(bar, level, bar_index)
                state["sweeps"][key] = sweep

        if sweep is None:
            return None
        if bar_index - sweep["bar_index"] > self.reclaim_window_bars:
            state["sweeps"].pop(key, None)
            return None
        if not self._reclaimed(bar, sweep):
            return None
        if not self._quote_filter_passes(bar, sweep["direction"]):
            return None

        state["sweeps"].pop(key, None)
        return self._signal(bar, sweep)

    def _new_sweep(self, bar: pd.Series, level: dict, bar_index: int) -> dict:
        return {
            **level,
            "bar_index": bar_index,
            "sweep_timestamp": pd.Timestamp(bar["timestamp"]),
            "sweep_low": float(bar["low"]),
            "sweep_high": float(bar["high"]),
        }

    def _reclaimed(self, bar: pd.Series, sweep: dict) -> bool:
        buffer = self.reclaim_buffer_ticks * self.tick_size
        close = float(bar["close"])
        if sweep["direction"] == "long":
            return close >= sweep["price"] + buffer
        return close <= sweep["price"] - buffer

    def _quote_filter_passes(self, bar: pd.Series, direction: str) -> bool:
        spread = _finite_float(bar.get(f"tbbo_spread_ticks_max_{self.depth_window}"))
        if spread is None or spread > self.max_spread_ticks:
            return False

        quote_imbalance = _finite_float(bar.get("tbbo_quote_imbalance_close"))
        if quote_imbalance is None:
            return False

        demand = _finite_float(bar.get(f"tbbo_aggressive_imbalance_{self.depth_window}"))
        if direction == "long":
            refill = _finite_float(bar.get(f"tbbo_bid_refill_ratio_{self.depth_window}"))
            if refill is None or refill < self.min_refill_ratio:
                return False
            if quote_imbalance < self.min_quote_imbalance:
                return False
            if self.require_liquidity_demand and (
                demand is None or demand > -self.min_failed_demand_imbalance
            ):
                return False
        else:
            refill = _finite_float(bar.get(f"tbbo_ask_refill_ratio_{self.depth_window}"))
            if refill is None or refill < self.min_refill_ratio:
                return False
            if quote_imbalance > -self.min_quote_imbalance:
                return False
            if self.require_liquidity_demand and (
                demand is None or demand < self.min_failed_demand_imbalance
            ):
                return False
        return True

    def _signal(self, bar: pd.Series, sweep: dict) -> Signal:
        timestamp = pd.Timestamp(bar["timestamp"])
        signal_timestamp = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        flatten_label = self.flatten_time.strftime("%H:%M:%S")
        report_fields = {
            "setup_mode": "quote_liquidity_sweep_reversion",
            "academic_source_key": "order_book_price_pressure_mean_reversion",
            "feature_method": "databento_tbbo_top_of_book_liquidity",
            "level_set": self.level_set,
            "level_type": sweep["level_type"],
            "swept_level": sweep["price"],
            "sweep_timestamp": sweep["sweep_timestamp"],
            "sweep_high": sweep["sweep_high"],
            "sweep_low": sweep["sweep_low"],
            "reclaim_timestamp": signal_timestamp,
            "tbbo_quote_imbalance_close": _finite_float(bar.get("tbbo_quote_imbalance_close")),
            f"tbbo_bid_refill_ratio_{self.depth_window}": _finite_float(
                bar.get(f"tbbo_bid_refill_ratio_{self.depth_window}")
            ),
            f"tbbo_ask_refill_ratio_{self.depth_window}": _finite_float(
                bar.get(f"tbbo_ask_refill_ratio_{self.depth_window}")
            ),
            f"tbbo_aggressive_imbalance_{self.depth_window}": _finite_float(
                bar.get(f"tbbo_aggressive_imbalance_{self.depth_window}")
            ),
            f"tbbo_spread_ticks_max_{self.depth_window}": _finite_float(
                bar.get(f"tbbo_spread_ticks_max_{self.depth_window}")
            ),
            "signal_target_r_multiple": self.target_r_multiple,
            "signal_flatten_time": flatten_label,
        }
        return Signal(
            direction=sweep["direction"],
            level_type=sweep["level_type"],
            swept_level=sweep["price"],
            sweep_timestamp=sweep["sweep_timestamp"],
            sweep_high=sweep["sweep_high"],
            sweep_low=sweep["sweep_low"],
            reclaim_timestamp=signal_timestamp,
            opening_range_high=sweep.get("opening_range_high"),
            opening_range_low=sweep.get("opening_range_low"),
            opening_range_open=sweep.get("opening_range_open"),
            opening_range_width=sweep.get("opening_range_width"),
            metadata={
                "target_r_multiple": self.target_r_multiple,
                "flatten_time": flatten_label,
                "depth_window": self.depth_window,
                "min_refill_ratio": self.min_refill_ratio,
                "min_quote_imbalance": self.min_quote_imbalance,
                "max_spread_ticks": self.max_spread_ticks,
            },
            report_fields=report_fields,
        )

    def _levels(self, bar: pd.Series, state: dict) -> list[dict]:
        levels = []
        if self.level_set in {"previous_rth", "pdh_pdl", "both"}:
            prev_low = _finite_float(bar.get("prev_rth_low"))
            prev_high = _finite_float(bar.get("prev_rth_high"))
            if prev_low is not None:
                levels.append({"direction": "long", "level_type": "previous_rth_low", "price": prev_low})
            if prev_high is not None:
                levels.append({"direction": "short", "level_type": "previous_rth_high", "price": prev_high})
        if self.level_set in {"opening_range", "or", "both"} and state["opening_range"] is not None:
            opening_range = state["opening_range"]
            levels.extend(
                [
                    {
                        "direction": "long",
                        "level_type": f"opening_range_{self.opening_range_minutes}m_low",
                        "price": opening_range["low"],
                        **opening_range,
                    },
                    {
                        "direction": "short",
                        "level_type": f"opening_range_{self.opening_range_minutes}m_high",
                        "price": opening_range["high"],
                        **opening_range,
                    },
                ]
            )
        return levels

    def _update_opening_range(self, state: dict, bar: pd.Series) -> None:
        timestamp = pd.Timestamp(bar["timestamp"])
        state["bar_index"] += 1
        session_start = timestamp.replace(
            hour=parse_time(self.params.get("rth_start", "09:30:00")).hour,
            minute=parse_time(self.params.get("rth_start", "09:30:00")).minute,
            second=0,
            microsecond=0,
        )
        opening_end = session_start + pd.Timedelta(minutes=self.opening_range_minutes)
        if timestamp < opening_end:
            state["opening_bars"].append(bar.copy())
            return
        if state["opening_range"] is not None or not state["opening_bars"]:
            return
        frame = pd.DataFrame(state["opening_bars"])
        high = float(pd.to_numeric(frame["high"], errors="coerce").max())
        low = float(pd.to_numeric(frame["low"], errors="coerce").min())
        opening = float(pd.to_numeric(frame["open"], errors="coerce").iloc[0])
        state["opening_range"] = {
            "opening_range_high": high,
            "opening_range_low": low,
            "opening_range_open": opening,
            "opening_range_width": high - low,
            "high": high,
            "low": low,
            "open": opening,
        }

    def _state(self, session_date) -> dict:
        return self.state_by_day.setdefault(
            session_date,
            {
                "bar_index": -1,
                "opening_bars": [],
                "opening_range": None,
                "sweeps": {},
            },
        )

    def _validate(self) -> None:
        valid_level_sets = {"previous_rth", "pdh_pdl", "opening_range", "or", "both"}
        if self.level_set not in valid_level_sets:
            raise ValueError(f"level_set must be one of: {sorted(valid_level_sets)}.")
        if self.opening_range_minutes <= 0:
            raise ValueError("opening_range_minutes must be positive.")
        if self.tick_size <= 0 or self.bar_interval_minutes <= 0:
            raise ValueError("tick_size and bar_interval_minutes must be positive.")
        if self.reclaim_window_bars < 0 or self.depth_window <= 0:
            raise ValueError("reclaim_window_bars must be non-negative and depth_window must be positive.")
        if self.min_sweep_ticks < 0 or self.reclaim_buffer_ticks < 0:
            raise ValueError("min_sweep_ticks and reclaim_buffer_ticks must be non-negative.")
        if self.min_refill_ratio <= 0 or self.max_spread_ticks <= 0 or self.target_r_multiple <= 0:
            raise ValueError("refill, spread, and target parameters must be positive.")


def _finite_float(value) -> float | None:
    if value is None or pd.isna(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
