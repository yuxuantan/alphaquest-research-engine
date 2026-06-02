from __future__ import annotations


def opening_range_edge_stop(
    signal,
    direction: str,
    tick_size: float,
    max_stop_points: float | None = 14.0,
    entry_price: float | None = None,
    stop_offset_ticks: int = 0,
) -> float | None:
    offset = tick_size * stop_offset_ticks
    if direction == "long":
        natural_stop = _signal_value(signal, "opening_range_low", "sweep_low") - offset
        return _validate_max_stop(natural_stop, entry_price, max_stop_points)

    natural_stop = _signal_value(signal, "opening_range_high", "sweep_high") + offset
    return _validate_max_stop(natural_stop, entry_price, max_stop_points)


class OpeningRangeEdgeStop:
    name = "opening_range_edge"

    def __init__(self, params: dict):
        self.params = params

    def price(self, signal, direction: str, tick_size: float, entry_price: float | None = None) -> float | None:
        return opening_range_edge_stop(
            signal,
            direction,
            tick_size,
            self.params.get("max_stop_points", 14.0),
            entry_price,
            int(self.params.get("stop_offset_ticks", 0)),
        )


def _signal_value(signal, primary: str, fallback: str) -> float:
    value = getattr(signal, primary, None)
    if value is None:
        value = getattr(signal, fallback)
    return float(value)


def _validate_max_stop(
    natural_stop: float,
    entry_price: float | None,
    max_stop_points: float | None,
) -> float | None:
    if entry_price is None or max_stop_points is None:
        return natural_stop
    if abs(float(entry_price) - natural_stop) > float(max_stop_points):
        return None
    return natural_stop
