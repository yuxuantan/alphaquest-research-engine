from __future__ import annotations

import math


class PointsFromEntryStop:
    name = "points_from_entry"

    def __init__(self, params: dict):
        self.params = params
        self.stop_points = float(params.get("stop_points", 1.0))
        self.round_to_tick = bool(params.get("round_to_tick", True))
        if self.stop_points <= 0:
            raise ValueError("sl.params.stop_points must be greater than 0.")

    def price(self, signal, direction: str, tick_size: float, entry_price: float | None = None) -> float | None:
        if entry_price is None:
            return None
        raw = float(entry_price) - self.stop_points if direction == "long" else float(entry_price) + self.stop_points
        if not self.round_to_tick:
            return raw
        return _round_price(raw, tick_size, "floor" if direction == "long" else "ceil")


def _round_price(price: float, tick_size: float, mode: str) -> float:
    if tick_size <= 0:
        raise ValueError("tick_size must be greater than 0.")
    scaled = price / tick_size
    if mode == "floor":
        return math.floor(scaled + 1e-12) * tick_size
    if mode == "ceil":
        return math.ceil(scaled - 1e-12) * tick_size
    raise ValueError(f"Unsupported rounding mode: {mode}")
