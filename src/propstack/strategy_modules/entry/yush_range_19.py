from __future__ import annotations

from propstack.strategy_modules.entry.yush_range_16 import YushRange16Entry


class YushRange19Entry(YushRange16Entry):
    name = "yush_range_19"

    def __init__(self, params: dict):
        super().__init__(params)
        raw = params.get("required_aoi_criteria", ("market_level",))
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
