from __future__ import annotations


class DailyRisk:
    def __init__(self, config: dict):
        self.daily_loss_limit = float(config.get("daily_loss_limit", 10**12))
        self.daily_profit_stop = float(config.get("daily_profit_stop", 10**12))
        self.max_trades_per_day = int(config.get("max_trades_per_day", 999))
        self.state = {}

    def _day(self, session_date):
        return self.state.setdefault(session_date, {"pnl": 0.0, "trades": 0, "locked": False})

    def allow_new_trade(self, session_date) -> bool:
        day = self._day(session_date)
        return not day["locked"] and day["trades"] < self.max_trades_per_day

    def record_entry(self, session_date) -> None:
        self._day(session_date)["trades"] += 1

    def record_exit(self, session_date, pnl: float) -> None:
        day = self._day(session_date)
        day["pnl"] += pnl
        if day["pnl"] <= -self.daily_loss_limit or day["pnl"] >= self.daily_profit_stop:
            day["locked"] = True

    def trades_today(self, session_date) -> int:
        return self._day(session_date)["trades"]
