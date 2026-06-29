from __future__ import annotations

import math

from propstack.strategy_modules.tp.fixed_r import fixed_r_target


class SignalPriceTarget:
    name = "signal_price"

    def __init__(self, params: dict):
        self.params = params
        self.metadata_key = str(params.get("metadata_key", "signal_target_price"))
        self.fallback_target_r_multiple = float(params.get("fallback_target_r_multiple", 2.0))
        self.min_signal_target_r_multiple = float(params.get("min_signal_target_r_multiple", 0.0))
        self.tick_size = float(params.get("tick_size", 0.25))
        self.round_to_tick = bool(params.get("round_to_tick", True))

    def price(self, entry_price: float, stop_price: float, direction: str, signal=None) -> float:
        target = None
        if signal is not None:
            target = getattr(signal, "metadata", {}).get(self.metadata_key)
        target = _finite_float(target)
        if (
            target is None
            or not _target_is_beyond_entry(target, entry_price, direction)
            or not _target_meets_min_r(
                target,
                entry_price,
                stop_price,
                self.min_signal_target_r_multiple,
            )
        ):
            target = fixed_r_target(entry_price, stop_price, direction, self.fallback_target_r_multiple)
        if not self.round_to_tick:
            return float(target)
        return _round_price(float(target), self.tick_size, "ceil" if direction == "long" else "floor")


def _target_is_beyond_entry(target: float, entry_price: float, direction: str) -> bool:
    if direction == "long":
        return target > entry_price
    return target < entry_price


def _target_meets_min_r(
    target: float,
    entry_price: float,
    stop_price: float,
    min_r_multiple: float,
) -> bool:
    if min_r_multiple <= 0:
        return True
    risk = abs(entry_price - stop_price)
    if risk <= 0:
        return False
    return abs(target - entry_price) >= risk * min_r_multiple


def _round_price(price: float, tick_size: float, mode: str) -> float:
    if tick_size <= 0:
        return price
    scaled = price / tick_size
    if mode == "ceil":
        return math.ceil(scaled - 1e-12) * tick_size
    return math.floor(scaled + 1e-12) * tick_size


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
