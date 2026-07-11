from __future__ import annotations

import pandas as pd

from propstack.strategy_modules.entry.yush_trend_31 import YushTrend31Entry
from propstack.utils.time import parse_time


class YushTrend39Entry(YushTrend31Entry):
    name = "yush_trend_39"

    def __init__(self, params: dict):
        super().__init__(params)
        self.blocked_start_time = parse_time(params.get("blocked_start_time", "12:00:00"))
        self.blocked_end_time = parse_time(params.get("blocked_end_time", "12:59:59"))
        if self.blocked_start_time > self.blocked_end_time:
            raise ValueError("entry.params blocked time window must not wrap across midnight.")

    def on_bar_intrabar(self, bar: pd.Series, detail_rows: pd.DataFrame, trades_today: int = 0):
        if detail_rows is None or detail_rows.empty or "timestamp" not in detail_rows:
            return super().on_bar_intrabar(bar, detail_rows, trades_today=trades_today)
        bar_window = self._bar_block_window(bar)
        if bar_window == "outside":
            return super().on_bar_intrabar(bar, detail_rows, trades_today=trades_today)
        if bar_window == "inside":
            return None
        timestamps = pd.to_datetime(detail_rows["timestamp"], errors="coerce")
        blocked = timestamps.map(self._timestamp_is_blocked)
        if bool(blocked.all()):
            return None
        if not bool(blocked.any()):
            return super().on_bar_intrabar(bar, detail_rows, trades_today=trades_today)
        filtered = detail_rows.loc[~blocked].copy()
        filtered.attrs.update(getattr(detail_rows, "attrs", {}))
        return super().on_bar_intrabar(bar, filtered, trades_today=trades_today)

    def _timestamp_is_blocked(self, timestamp) -> bool:
        if pd.isna(timestamp):
            return False
        candidate_time = pd.Timestamp(timestamp).time()
        return self.blocked_start_time <= candidate_time <= self.blocked_end_time

    def _bar_block_window(self, bar: pd.Series) -> str:
        timestamp = pd.Timestamp(bar.get("timestamp"))
        start_time = timestamp.time()
        interval = int(bar.get("bar_interval_minutes", getattr(self, "bar_interval_minutes", 3)) or 3)
        end_time = (timestamp + pd.Timedelta(minutes=interval)).time()
        if start_time > end_time:
            return "overlap"
        if end_time < self.blocked_start_time or start_time > self.blocked_end_time:
            return "outside"
        if start_time >= self.blocked_start_time and end_time <= self.blocked_end_time:
            return "inside"
        return "overlap"
