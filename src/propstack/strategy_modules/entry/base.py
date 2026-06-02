from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Signal:
    direction: str
    level_type: str
    swept_level: float
    sweep_timestamp: object
    sweep_high: float
    sweep_low: float
    reclaim_timestamp: object
    opening_range_high: float | None = None
    opening_range_low: float | None = None
    opening_range_open: float | None = None
    opening_range_width: float | None = None
    breakout_level: float | None = None
    metadata: dict = field(default_factory=dict)
