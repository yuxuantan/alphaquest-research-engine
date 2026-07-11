from __future__ import annotations

from propstack.strategy_modules.entry.yush_trend_6 import YushTrend6Entry


class YushTrend12Entry(YushTrend6Entry):
    name = "yush_trend_12"

    def __init__(self, params: dict):
        super().__init__(params)
        raw = params.get("forbidden_aoi_criteria", ("market_level",))
        values = [raw] if isinstance(raw, str) else list(raw)
        self.forbidden_aoi_criteria = {str(item).strip() for item in values if str(item).strip()}

    def _intrabar_aoi_confluence(self, bar, profile, direction, model, level, state):
        confluence = super()._intrabar_aoi_confluence(bar, profile, direction, model, level, state)
        criteria = set(confluence["criteria"])
        forbidden = self.forbidden_aoi_criteria.intersection(criteria)
        if forbidden:
            details = dict(confluence["details"])
            details["forbidden_aoi_criteria"] = ",".join(sorted(forbidden))
            return {"criteria": [], "details": details}
        return confluence
