"""Durable engineering handoffs for unsupported or event-driven ideas."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from alphaquest.research.storage import load_storage_layout


class ProposedEngineeringVariantV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    variant_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    mechanic: str = Field(min_length=1)
    material_difference: str = Field(min_length=1)


class EngineeringHandoffV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["alphaquest.engineering-handoff/v1"] = Field(
        default="alphaquest.engineering-handoff/v1", alias="schema"
    )
    campaign_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    created_at: str
    status: Literal["NEEDS MANUAL REVIEW"] = "NEEDS MANUAL REVIEW"
    reason_unsupported: str = Field(min_length=1)
    causal_timeline: list[str] = Field(min_length=1)
    required_data_granularity: str = Field(min_length=1)
    fill_and_ambiguity_rules: list[str] = Field(min_length=1)
    required_module_contract: list[str] = Field(min_length=1)
    required_tests: list[str] = Field(min_length=1)
    proposed_variants: list[ProposedEngineeringVariantV1] = Field(min_length=5, max_length=5)

    @model_validator(mode="after")
    def distinct_variants(self) -> "EngineeringHandoffV1":
        ids = [item.variant_id for item in self.proposed_variants]
        mechanics = [item.mechanic.strip().casefold() for item in self.proposed_variants]
        if len(set(ids)) != 5 or len(set(mechanics)) != 5:
            raise ValueError("handoff requires five distinct proposed variants")
        return self


def write_engineering_handoff(
    handoff: EngineeringHandoffV1,
    *,
    project_root: str | Path = ".",
) -> Path:
    root = Path(project_root).resolve()
    layout = load_storage_layout(root)
    handoff_root = Path(getattr(layout, "handoff_root", root / "research" / "handoffs"))
    path = handoff_root / handoff.campaign_id / "engineering_handoff.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = handoff.model_dump(mode="json", by_alias=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def new_handoff(
    *,
    campaign_id: str,
    reason_unsupported: str,
    causal_timeline: list[str],
    required_data_granularity: str,
    fill_and_ambiguity_rules: list[str],
    required_module_contract: list[str],
    required_tests: list[str],
    proposed_mechanics: list[str],
) -> EngineeringHandoffV1:
    return EngineeringHandoffV1(
        campaign_id=campaign_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        reason_unsupported=reason_unsupported,
        causal_timeline=causal_timeline,
        required_data_granularity=required_data_granularity,
        fill_and_ambiguity_rules=fill_and_ambiguity_rules,
        required_module_contract=required_module_contract,
        required_tests=required_tests,
        proposed_variants=[
            ProposedEngineeringVariantV1(
                variant_id=f"v{index:02d}",
                mechanic=mechanic,
                material_difference="Independent causal mechanic requiring a certified implementation before performance testing.",
            )
            for index, mechanic in enumerate(proposed_mechanics, start=1)
        ],
    )


__all__ = [
    "EngineeringHandoffV1",
    "ProposedEngineeringVariantV1",
    "new_handoff",
    "write_engineering_handoff",
]
