from __future__ import annotations

from copy import deepcopy
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from alphaquest.utils.hashing import file_sha256


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_PATH = PROJECT_ROOT / "config" / "research_settings.yaml"


@dataclass(frozen=True)
class ResearchPolicy:
    path: Path
    version: str
    file_hash: str
    acceptance_stage: str
    pre_acceptance_stage_order: tuple[str, ...]
    stage_criteria: dict[str, list[dict[str, Any]]]
    objective_floors: dict[str, Any]
    monkey_runs: int
    mechanics_validation: dict[str, Any]
    shortlist_data_window: dict[str, Any]
    wfa_data_window: dict[str, Any]
    core_grid: dict[str, Any]
    monkey: dict[str, Any]
    walk_forward_analysis: dict[str, Any]
    wfa_oos_monte_carlo: dict[str, Any]
    simulated_incubation: dict[str, Any]
    acceptance_oos: dict[str, Any]

    @property
    def stage_order(self) -> tuple[str, ...]:
        return (*self.pre_acceptance_stage_order, self.acceptance_stage)

    def stage_order_for(self, *, include_acceptance: bool = True) -> list[str]:
        order = list(self.pre_acceptance_stage_order)
        if include_acceptance:
            order.append(self.acceptance_stage)
        return order

    def criteria_for_stage(self, stage_name: str) -> list[dict[str, Any]]:
        return deepcopy(self.stage_criteria.get(stage_name, []))

    def validate_objectives(self, objectives: Mapping[str, Any]) -> None:
        """Reject campaign goals that are weaker than repository methodology."""

        floors = self.objective_floors
        minimums = {
            "evaluation_horizon_months": "minimum_evaluation_horizon_months",
            "minimum_complete_wfa_windows": "minimum_complete_wfa_windows",
            "minimum_wfa_oos_trades": "minimum_wfa_oos_trades",
            "minimum_acceptance_oos_trades": "minimum_acceptance_oos_trades",
            "minimum_mar": "minimum_mar",
            "monte_carlo_min_runs": "minimum_monte_carlo_runs",
            "monte_carlo_horizon_months": "minimum_monte_carlo_horizon_months",
            "minimum_net_profit_probability": "minimum_net_profit_probability",
            "forward_incubation_min_calendar_days": "minimum_forward_incubation_calendar_days",
            "forward_incubation_min_trades": "minimum_forward_incubation_trades",
        }
        maximums = {
            "maximum_drawdown_fraction": "maximum_drawdown_fraction",
            "maximum_account_breach_probability": "maximum_account_breach_probability",
            "maximum_variants": "maximum_variants",
        }
        violations: list[str] = []
        for field, floor_name in minimums.items():
            if field not in objectives:
                violations.append(f"{field} is missing")
                continue
            if float(objectives[field]) < float(floors[floor_name]):
                violations.append(f"{field} must be at least {floors[floor_name]}")
        for field, ceiling_name in maximums.items():
            if field not in objectives:
                violations.append(f"{field} is missing")
                continue
            if float(objectives[field]) > float(floors[ceiling_name]):
                violations.append(f"{field} must be no more than {floors[ceiling_name]}")
        if objectives.get("confirmed") is not True:
            violations.append("confirmed must be true")
        if violations:
            raise ValueError("research objectives violate repository policy: " + "; ".join(violations))

    def run_metadata(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "path": str(self.path.relative_to(PROJECT_ROOT) if self.path.is_relative_to(PROJECT_ROOT) else self.path),
            "hash": self.file_hash,
            "stage_order": list(self.stage_order),
            "acceptance_stage": self.acceptance_stage,
            "methodology": {
                "mechanics_validation": deepcopy(self.mechanics_validation),
                "shortlist_data_window": deepcopy(self.shortlist_data_window),
                "core_grid": deepcopy(self.core_grid),
                "monkey": deepcopy(self.monkey),
                "wfa_data_window": deepcopy(self.wfa_data_window),
                "walk_forward_analysis": deepcopy(self.walk_forward_analysis),
                "wfa_oos_monte_carlo": deepcopy(self.wfa_oos_monte_carlo),
                "simulated_incubation": deepcopy(self.simulated_incubation),
                "acceptance_oos": deepcopy(self.acceptance_oos),
                "objective_floors": deepcopy(self.objective_floors),
            },
        }


@lru_cache(maxsize=4)
def load_research_policy(path: str | Path = DEFAULT_POLICY_PATH) -> ResearchPolicy:
    policy_path = Path(path)
    if not policy_path.is_file():
        raise FileNotFoundError(f"research policy file not found: {policy_path}")
    raw = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"research policy YAML must load to a mapping: {policy_path}")

    metadata = _mapping(raw.get("methodology_policy"), "methodology_policy")
    defaults = _mapping(raw.get("stage_defaults"), "stage_defaults")
    gates = _mapping(raw.get("stage_gates"), "stage_gates")

    acceptance_stage = str(defaults.get("acceptance_stage") or "acceptance_oos_test")
    pre_order = tuple(str(item) for item in defaults.get("pre_acceptance_stage_order") or ())
    if not pre_order:
        raise ValueError("stage_defaults.pre_acceptance_stage_order must be a non-empty list.")
    if acceptance_stage in pre_order:
        raise ValueError("acceptance stage must not appear in pre_acceptance_stage_order.")

    stage_criteria: dict[str, list[dict[str, Any]]] = {}
    for stage_name in (*pre_order, acceptance_stage):
        stage_gate = _mapping(gates.get(stage_name), f"stage_gates.{stage_name}")
        criteria = stage_gate.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            raise ValueError(f"stage_gates.{stage_name}.criteria must be a non-empty list.")
        normalized = []
        for index, item in enumerate(criteria, start=1):
            if not isinstance(item, dict) or not item.get("metric"):
                raise ValueError(f"stage_gates.{stage_name}.criteria[{index}] must define metric.")
            if item.get("decision_role") not in {
                "scientific_validity",
                "generic_objective",
            }:
                raise ValueError(
                    f"stage_gates.{stage_name}.criteria[{index}].decision_role must be "
                    "scientific_validity or generic_objective."
                )
            normalized.append(dict(item))
        stage_criteria[stage_name] = normalized

    mechanics_validation = deepcopy(
        _mapping(defaults.get("mechanics_validation"), "stage_defaults.mechanics_validation")
    )
    expected_mechanics = {
        "selection_mode": "latest_eligible_sessions",
        "session_count": 10,
        "parameter_mode": "declared_defaults",
        "manual_review_random_sample_size": 5,
    }
    for key, expected in expected_mechanics.items():
        if mechanics_validation.get(key) != expected:
            raise ValueError(
                f"stage_defaults.mechanics_validation.{key} must be {expected!r}."
            )
    if int(mechanics_validation.get("minimum_trade_samples", 0)) < int(
        mechanics_validation["manual_review_random_sample_size"]
    ):
        raise ValueError(
            "mechanics minimum_trade_samples cannot be below the manual review sample size."
        )

    walk_forward_analysis = deepcopy(
        _mapping(defaults.get("walk_forward_analysis"), "stage_defaults.walk_forward_analysis")
    )
    for key in ("train_months", "test_months", "step_months"):
        if int(walk_forward_analysis.get(key, 0)) <= 0:
            raise ValueError(f"stage_defaults.walk_forward_analysis.{key} must be positive.")

    objective_floors = deepcopy(
        _mapping(defaults.get("research_objective_floors"), "stage_defaults.research_objective_floors")
    )
    required_objective_floors = {
        "minimum_evaluation_horizon_months",
        "minimum_complete_wfa_windows",
        "minimum_wfa_oos_trades",
        "minimum_acceptance_oos_trades",
        "minimum_mar",
        "maximum_drawdown_fraction",
        "minimum_monte_carlo_runs",
        "minimum_monte_carlo_horizon_months",
        "minimum_net_profit_probability",
        "maximum_account_breach_probability",
        "minimum_forward_incubation_calendar_days",
        "minimum_forward_incubation_trades",
        "maximum_variants",
    }
    missing_objective_floors = sorted(required_objective_floors - set(objective_floors))
    if missing_objective_floors:
        raise ValueError(
            "stage_defaults.research_objective_floors is missing: "
            + ", ".join(missing_objective_floors)
        )
    positive_objective_floors = required_objective_floors - {
        "minimum_mar",
        "minimum_net_profit_probability",
        "maximum_account_breach_probability",
    }
    for key in positive_objective_floors:
        if float(objective_floors[key]) <= 0:
            raise ValueError(f"stage_defaults.research_objective_floors.{key} must be positive.")
    if float(objective_floors["minimum_mar"]) < 0:
        raise ValueError("stage_defaults.research_objective_floors.minimum_mar cannot be negative.")
    for key in (
        "maximum_drawdown_fraction",
        "minimum_net_profit_probability",
        "maximum_account_breach_probability",
    ):
        if not 0 <= float(objective_floors[key]) <= 1:
            raise ValueError(f"stage_defaults.research_objective_floors.{key} must be between 0 and 1.")
    if not 1 <= int(objective_floors["maximum_variants"]) <= 5:
        raise ValueError("stage_defaults.research_objective_floors.maximum_variants must be between 1 and 5.")

    return ResearchPolicy(
        path=policy_path,
        version=str(metadata.get("version") or "unversioned"),
        file_hash=file_sha256(policy_path),
        acceptance_stage=acceptance_stage,
        pre_acceptance_stage_order=pre_order,
        stage_criteria=stage_criteria,
        objective_floors=objective_floors,
        monkey_runs=int(defaults.get("monkey_runs", 8000)),
        mechanics_validation=mechanics_validation,
        shortlist_data_window=deepcopy(_mapping(defaults.get("shortlist_data_window"), "stage_defaults.shortlist_data_window")),
        wfa_data_window=deepcopy(_mapping(defaults.get("wfa_data_window"), "stage_defaults.wfa_data_window")),
        core_grid=deepcopy(_mapping(defaults.get("core_grid"), "stage_defaults.core_grid")),
        monkey=deepcopy(_mapping(defaults.get("monkey"), "stage_defaults.monkey")),
        walk_forward_analysis=walk_forward_analysis,
        wfa_oos_monte_carlo=deepcopy(
            _mapping(defaults.get("wfa_oos_monte_carlo"), "stage_defaults.wfa_oos_monte_carlo")
        ),
        simulated_incubation=deepcopy(_mapping(defaults.get("simulated_incubation"), "stage_defaults.simulated_incubation")),
        acceptance_oos=deepcopy(_mapping(defaults.get("acceptance_oos"), "stage_defaults.acceptance_oos")),
    )


def active_research_policy_metadata() -> dict[str, Any]:
    return load_research_policy().run_metadata()


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be configured as a mapping.")
    return value
