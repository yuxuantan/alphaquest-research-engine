from __future__ import annotations

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.strategy_modules.entry.yush_range_31 import YushRange31Entry


class YushTrend81Entry(YushRange31Entry):
    name = "yush_trend_81"

    def _profile_is_balanced(self, profile: dict) -> bool:
        del profile
        return True

    def _range_is_stable(self, timestamp) -> bool:
        del timestamp
        self._latest_range_change_pct = None
        return True

    def _signal(self, **kwargs) -> Signal | None:
        signal = super()._signal(**kwargs)
        if signal is None:
            return None
        profile = kwargs["profile"]
        val = float(profile["val"])
        vah = float(profile["vah"])
        poc = float(profile["poc"])
        width = vah - val
        middle_third = False
        if width > 0:
            middle_third = val + width / 3.0 <= poc <= vah - width / 3.0
        fields = {
            "trend_branch": True,
            "range_condition_required": False,
            "profile_poc_middle_third_required": False,
            "profile_poc_middle_third": middle_third,
            "target_reference": "fixed_dollar_negative_rr_trend_acceptance",
        }
        signal.metadata.update(fields)
        signal.report_fields.update(fields)
        return signal
