from __future__ import annotations

from propstack.strategy_modules.entry.yush_trend_5 import YushTrend5Entry


class YushTrend6Entry(YushTrend5Entry):
    name = "yush_trend_6"

    def __init__(self, params: dict):
        super().__init__(params)
        raw = params.get("required_aoi_criteria", ("big_trades",))
        values = [raw] if isinstance(raw, str) else list(raw)
        self.required_aoi_criteria = {str(item).strip() for item in values if str(item).strip()}

    def _intrabar_aoi_confluence(self, bar, profile, direction, model, level, state):
        confluence = super()._intrabar_aoi_confluence(bar, profile, direction, model, level, state)
        criteria = set(confluence["criteria"])
        if not self.required_aoi_criteria.issubset(criteria):
            details = dict(confluence["details"])
            details["missing_required_aoi_criteria"] = ",".join(sorted(self.required_aoi_criteria - criteria))
            return {"criteria": [], "details": details}
        return confluence
