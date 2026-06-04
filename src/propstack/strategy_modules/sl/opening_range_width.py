from __future__ import annotations

import math


def opening_range_width_stop(
    signal,
    direction: str,
    tick_size: float,
    max_stop_points: float | None = 14.0,
    entry_price: float | None = None,
    stop_offset_ticks: int = 0,
) -> float | None:
    width = _signal_value(signal, "opening_range_width")
    if width is None or width <= 0:
        return None
    reference_price = _reference_price(signal, entry_price)
    if reference_price is None:
        return None

    stop_distance = width + (float(tick_size) * int(stop_offset_ticks))
    if max_stop_points is not None and stop_distance > float(max_stop_points):
        return None
    if direction == "long":
        return reference_price - stop_distance
    return reference_price + stop_distance


class OpeningRangeWidthStop:
    name = "opening_range_width"

    def __init__(self, params: dict):
        self.params = params

    def price(self, signal, direction: str, tick_size: float, entry_price: float | None = None) -> float | None:
        return opening_range_width_stop(
            signal,
            direction,
            tick_size,
            self.params.get("max_stop_points", 14.0),
            entry_price,
            int(self.params.get("stop_offset_ticks", 0)),
        )


def _signal_value(signal, key: str) -> float | None:
    value = getattr(signal, key, None)
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _reference_price(signal, entry_price: float | None) -> float | None:
    value = entry_price
    if value is None:
        try:
            value = signal.metadata.get("confirmation_close")
        except AttributeError:
            value = None
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None
