from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from propstack.utils.hashing import file_sha256


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
    monkey_runs: int
    shortlist_data_window: dict[str, Any]
    wfa_data_window: dict[str, Any]
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

    def run_metadata(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "path": str(self.path.relative_to(PROJECT_ROOT) if self.path.is_relative_to(PROJECT_ROOT) else self.path),
            "hash": self.file_hash,
            "stage_order": list(self.stage_order),
            "acceptance_stage": self.acceptance_stage,
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
            normalized.append(dict(item))
        stage_criteria[stage_name] = normalized

    return ResearchPolicy(
        path=policy_path,
        version=str(metadata.get("version") or "unversioned"),
        file_hash=file_sha256(policy_path),
        acceptance_stage=acceptance_stage,
        pre_acceptance_stage_order=pre_order,
        stage_criteria=stage_criteria,
        monkey_runs=int(defaults.get("monkey_runs", 8000)),
        shortlist_data_window=deepcopy(_mapping(defaults.get("shortlist_data_window"), "stage_defaults.shortlist_data_window")),
        wfa_data_window=deepcopy(_mapping(defaults.get("wfa_data_window"), "stage_defaults.wfa_data_window")),
        simulated_incubation=deepcopy(_mapping(defaults.get("simulated_incubation"), "stage_defaults.simulated_incubation")),
        acceptance_oos=deepcopy(_mapping(defaults.get("acceptance_oos"), "stage_defaults.acceptance_oos")),
    )


def active_research_policy_metadata() -> dict[str, Any]:
    return load_research_policy().run_metadata()


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be configured as a mapping.")
    return value
