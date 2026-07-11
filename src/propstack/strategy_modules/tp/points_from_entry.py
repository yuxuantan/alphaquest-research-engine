from __future__ import annotations

import math


class PointsFromEntryTarget:
    name = "points_from_entry"

    def __init__(self, params: dict):
        self.params = params
        self.target_points = float(params.get("target_points", 1.0))
        self.round_to_tick = bool(params.get("round_to_tick", True))
        if self.target_points <= 0:
            raise ValueError("tp.params.target_points must be greater than 0.")

    def price(self, entry_price: float, stop_price: float, direction: str, signal=None) -> float:
        raw = (
            float(entry_price) + self.target_points
            if direction == "long"
            else float(entry_price) - self.target_points
        )
        if not self.round_to_tick:
            return raw
        tick_size = _tick_size_from_signal(signal) or float(self.params.get("tick_size", 0.25))
        return _round_price(raw, tick_size, "ceil" if direction == "long" else "floor")


def _tick_size_from_signal(signal) -> float | None:
    if signal is None:
        return None
    try:
        value = signal.metadata.get("tick_size")
    except AttributeError:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) and out > 0 else None


def _round_price(price: float, tick_size: float, mode: str) -> float:
    if tick_size <= 0:
        raise ValueError("tick_size must be greater than 0.")
    scaled = price / tick_size
    if mode == "ceil":
        return math.ceil(scaled - 1e-12) * tick_size
    if mode == "floor":
        return math.floor(scaled + 1e-12) * tick_size
    raise ValueError(f"Unsupported rounding mode: {mode}")
