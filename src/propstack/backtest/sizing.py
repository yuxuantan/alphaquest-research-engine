from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PositionSize:
    contracts: int
    mode: str
    net_liq: float | None = None
    target_risk_amount: float | None = None
    dollar_risk_per_contract: float | None = None
    unrounded_contracts: float | None = None
    planned_dollar_risk: float | None = None

    def report_fields(self) -> dict:
        if self.target_risk_amount is None:
            return {"position_sizing_mode": self.mode}
        return {
            "position_sizing_mode": self.mode,
            "position_sizing_net_liq": self.net_liq,
            "target_risk_amount": self.target_risk_amount,
            "dollar_risk_per_contract": self.dollar_risk_per_contract,
            "unrounded_contracts": self.unrounded_contracts,
            "planned_dollar_risk": self.planned_dollar_risk,
        }


def size_position(
    core_config: dict,
    risk_points: float,
    tick_size: float,
    tick_value: float,
    net_liq: float | None = None,
) -> PositionSize:
    sizing = core_config.get("position_sizing", {})
    if isinstance(sizing, str):
        sizing = {"mode": sizing}
    if sizing is None:
        sizing = {}
    if not isinstance(sizing, dict):
        raise ValueError("core.position_sizing must be a mapping or mode string.")

    mode = str(sizing.get("mode", "fixed_contracts")).lower()
    if mode in {"fixed", "fixed_contracts"}:
        contracts = int(core_config.get("contracts", sizing.get("contracts", 1)))
        if contracts < 1:
            raise ValueError("core.contracts must be at least 1 for fixed position sizing.")
        return PositionSize(contracts=contracts, mode="fixed_contracts")

    if mode not in {
        "risk_percent_initial_balance",
        "initial_balance_risk",
        "risk_pct_initial_balance",
        "risk_percent_net_liq",
        "net_liq_risk",
        "risk_pct_net_liq",
    }:
        raise ValueError(f"Unsupported core.position_sizing.mode: {mode}")

    initial_balance = float(core_config.get("initial_balance", 0.0))
    if initial_balance <= 0:
        raise ValueError("core.initial_balance must be greater than 0 for risk-percent position sizing.")

    risk_pct = _risk_pct(sizing)
    dollar_risk_per_contract = _dollar_risk_per_contract(risk_points, tick_size, tick_value)
    risk_base = initial_balance if net_liq is None else float(net_liq)
    if risk_base <= 0:
        return PositionSize(
            contracts=0,
            mode="risk_percent_net_liq",
            net_liq=risk_base,
            target_risk_amount=0.0,
            dollar_risk_per_contract=dollar_risk_per_contract,
            unrounded_contracts=0.0,
            planned_dollar_risk=0.0,
        )
    target_risk_amount = risk_base * risk_pct
    unrounded = target_risk_amount / dollar_risk_per_contract
    contracts = _round_contracts(unrounded, str(sizing.get("rounding", "floor")).lower())

    max_contracts = sizing.get("max_contracts")
    if max_contracts is not None:
        contracts = min(contracts, int(max_contracts))

    min_contracts = int(sizing.get("min_contracts", 1))
    if contracts < min_contracts:
        contracts = 0

    return PositionSize(
        contracts=contracts,
        mode="risk_percent_net_liq",
        net_liq=risk_base,
        target_risk_amount=target_risk_amount,
        dollar_risk_per_contract=dollar_risk_per_contract,
        unrounded_contracts=unrounded,
        planned_dollar_risk=dollar_risk_per_contract * contracts,
    )


def _risk_pct(sizing: dict) -> float:
    if "risk_pct" in sizing:
        risk_pct = float(sizing["risk_pct"])
    elif "risk_fraction" in sizing:
        risk_pct = float(sizing["risk_fraction"])
    elif "risk_percent" in sizing:
        risk_pct = float(sizing["risk_percent"]) / 100.0
    else:
        risk_pct = 0.01
    if risk_pct <= 0:
        raise ValueError("core.position_sizing risk percentage must be greater than 0.")
    return risk_pct


def _dollar_risk_per_contract(risk_points: float, tick_size: float, tick_value: float) -> float:
    risk = float(risk_points)
    tick_size = float(tick_size)
    tick_value = float(tick_value)
    if risk <= 0:
        raise ValueError("risk_points must be greater than 0 for risk-percent position sizing.")
    if tick_size <= 0:
        raise ValueError("core.tick_size must be greater than 0.")
    if tick_value <= 0:
        raise ValueError("core.tick_value must be greater than 0.")
    return risk / tick_size * tick_value


def _round_contracts(unrounded: float, rounding: str) -> int:
    if rounding == "floor":
        return math.floor(unrounded)
    if rounding == "ceil":
        return math.ceil(unrounded)
    if rounding == "nearest":
        return math.floor(unrounded + 0.5)
    raise ValueError("core.position_sizing.rounding must be one of: floor, nearest, ceil.")
