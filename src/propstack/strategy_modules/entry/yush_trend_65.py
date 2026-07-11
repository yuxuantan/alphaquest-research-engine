from __future__ import annotations

from dataclasses import replace

from propstack.strategy_modules.entry.yush_trend_31 import YushTrend31Entry


class YushTrend65Entry(YushTrend31Entry):
    name = "yush_trend_65"

    def _intrabar_video_signal(self, *args, **kwargs):
        signal = super()._intrabar_video_signal(*args, **kwargs)
        original_direction = signal.direction
        reversed_direction = "long" if original_direction == "short" else "short"
        fields = {
            "entry_trigger": "failed_lvn_continuation_reversal",
            "original_yush_direction": original_direction,
            "reversed_trade_direction": reversed_direction,
        }
        metadata = dict(signal.metadata)
        report_fields = dict(signal.report_fields)
        metadata.update(fields)
        report_fields.update(fields)
        return replace(
            signal,
            direction=reversed_direction,
            level_type=f"{signal.level_type}_failed_continuation_reversal",
            metadata=metadata,
            report_fields=report_fields,
        )
