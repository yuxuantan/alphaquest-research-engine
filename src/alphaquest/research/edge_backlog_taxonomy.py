"""Immutable, versioned economic-concept contracts for the P2 Edge Backlog."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Annotated, Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, model_validator


TAXONOMY_SCHEMA = "alphaquest.economic-edge-taxonomy/v1"
TAXONOMY_ID = "alphaquest-economic-edge"
FINGERPRINT_SCHEMA = "alphaquest.edge-backlog-fingerprint/v1"
TAXONOMY_FILENAME_PATTERN = "economic-edge-taxonomy-v{version}.json"

ConceptCode = Annotated[str, Field(pattern=r"^[A-Z][A-Z0-9_]{1,63}$")]
Sha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
NonBlank = Annotated[str, Field(min_length=1)]
DimensionField = Literal[
    "instrument_ids",
    "market_behavior_code",
    "causal_mechanism_code",
    "beneficiary_counterparty_codes",
    "cost_bearer_counterparty_codes",
    "transfer_rationale_code",
    "information_input_codes",
    "information_availability_code",
    "expected_effect_code",
    "holding_horizon_code",
    "market_context_codes",
]
ClassificationStatus = Literal["CLASSIFIED", "NEEDS_CLASSIFICATION"]
UnclassifiedReason = Literal[
    "AMBIGUOUS_CAUSAL_MECHANISM",
    "CONFLICTING_OBSERVATIONS",
    "INSUFFICIENT_SOURCE_CONTEXT",
    "MIXED_ECONOMIC_PHENOMENA",
    "NOVEL_CONCEPT_NOT_IN_TAXONOMY",
]

DIMENSION_SPECS: tuple[tuple[str, str, str], ...] = (
    ("instrument_ids", "instrument", "SORTED_SET"),
    ("market_behavior_code", "market_behavior", "SINGLE"),
    ("causal_mechanism_code", "causal_mechanism", "SINGLE"),
    ("beneficiary_counterparty_codes", "counterparty", "SORTED_SET"),
    ("cost_bearer_counterparty_codes", "counterparty", "SORTED_SET"),
    ("transfer_rationale_code", "transfer_rationale", "SINGLE"),
    ("information_input_codes", "information_input", "SORTED_SET"),
    ("information_availability_code", "information_availability", "SINGLE"),
    ("expected_effect_code", "expected_effect", "SINGLE"),
    ("holding_horizon_code", "holding_horizon", "SINGLE"),
    ("market_context_codes", "market_context", "SORTED_SET"),
)
DIMENSION_FIELDS = tuple(item[0] for item in DIMENSION_SPECS)


class StrictTaxonomyModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class TaxonomyRefV1(StrictTaxonomyModel):
    taxonomy_id: Literal[TAXONOMY_ID]
    taxonomy_version: Annotated[int, Field(ge=1)]
    taxonomy_sha256: Sha256


class EconomicConceptsV1(StrictTaxonomyModel):
    instrument_ids: Annotated[list[ConceptCode], Field(min_length=1)]
    market_behavior_code: ConceptCode
    causal_mechanism_code: ConceptCode
    beneficiary_counterparty_codes: Annotated[list[ConceptCode], Field(min_length=1)]
    cost_bearer_counterparty_codes: Annotated[list[ConceptCode], Field(min_length=1)]
    transfer_rationale_code: ConceptCode
    information_input_codes: Annotated[list[ConceptCode], Field(min_length=1)]
    information_availability_code: ConceptCode
    expected_effect_code: ConceptCode
    holding_horizon_code: ConceptCode
    market_context_codes: Annotated[list[ConceptCode], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_sorted_sets(self) -> "EconomicConceptsV1":
        for field, _code_set, cardinality in DIMENSION_SPECS:
            if cardinality != "SORTED_SET":
                continue
            values = getattr(self, field)
            if values != sorted(set(values)):
                raise ValueError(f"{field} must be a sorted set of unique concept codes")
        if set(self.beneficiary_counterparty_codes) & set(self.cost_bearer_counterparty_codes):
            raise ValueError("beneficiary and cost-bearer counterparties must be disjoint")
        return self


class EconomicEdgeFingerprintV1(EconomicConceptsV1):
    schema_name: Literal[FINGERPRINT_SCHEMA] = Field(
        default=FINGERPRINT_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    taxonomy_id: Literal[TAXONOMY_ID]


class TaxonomyCodeV1(StrictTaxonomyModel):
    code: ConceptCode
    definition: NonBlank
    display_label: NonBlank
    recall_aliases: list[NonBlank] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_aliases(self) -> "TaxonomyCodeV1":
        if self.recall_aliases != sorted(set(self.recall_aliases), key=str.casefold):
            raise ValueError("recall_aliases must be a case-insensitively sorted set")
        return self


class EconomicCodeSetsV1(StrictTaxonomyModel):
    instrument: list[TaxonomyCodeV1]
    market_behavior: list[TaxonomyCodeV1]
    causal_mechanism: list[TaxonomyCodeV1]
    counterparty: list[TaxonomyCodeV1]
    transfer_rationale: list[TaxonomyCodeV1]
    information_input: list[TaxonomyCodeV1]
    information_availability: list[TaxonomyCodeV1]
    expected_effect: list[TaxonomyCodeV1]
    holding_horizon: list[TaxonomyCodeV1]
    market_context: list[TaxonomyCodeV1]


class TaxonomyDimensionV1(StrictTaxonomyModel):
    field: DimensionField
    code_set: Literal[
        "instrument",
        "market_behavior",
        "causal_mechanism",
        "counterparty",
        "transfer_rationale",
        "information_input",
        "information_availability",
        "expected_effect",
        "holding_horizon",
        "market_context",
    ]
    cardinality: Literal["SINGLE", "SORTED_SET"]
    required_for_classification: Literal[True]


class TaxonomySelectionV1(StrictTaxonomyModel):
    field: DimensionField
    codes: Annotated[list[ConceptCode], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_codes(self) -> "TaxonomySelectionV1":
        if self.codes != sorted(set(self.codes)):
            raise ValueError("invariant codes must be a sorted set")
        return self


class CrossFieldInvariantV1(StrictTaxonomyModel):
    invariant_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{2,127}$")]
    definition: NonBlank
    if_any: Annotated[list[TaxonomySelectionV1], Field(min_length=1)]
    require_all: list[TaxonomySelectionV1] = Field(default_factory=list)
    require_any: list[TaxonomySelectionV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_consequence(self) -> "CrossFieldInvariantV1":
        if not self.require_all and not self.require_any:
            raise ValueError("cross-field invariants require at least one consequence")
        return self


class TaxonomyHashGenerationV1(StrictTaxonomyModel):
    canonicalization: Literal["UTF8_SORTED_KEYS_COMPACT_JSON_NO_NAN"]
    digest: Literal["SHA256_LOWERCASE_HEX"]
    hash_scope: Literal["COMPLETE_VALIDATED_TAXONOMY_DOCUMENT"]


ProhibitedCategory = Literal[
    "COSMETIC_TIMEFRAMES",
    "ENTRY_OR_EXIT_RULES",
    "INDICATORS",
    "PARAMETER_VALUES",
    "STOPS",
    "STRATEGY_MODULES",
    "TARGETS",
    "THRESHOLDS",
]


class EconomicEdgeTaxonomyV1(StrictTaxonomyModel):
    schema_name: Literal[TAXONOMY_SCHEMA] = Field(
        default=TAXONOMY_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    taxonomy_id: Literal[TAXONOMY_ID]
    taxonomy_version: Annotated[int, Field(ge=1)]
    previous_taxonomy_sha256: Sha256 | None
    description: NonBlank
    fingerprint_schema: Literal[FINGERPRINT_SCHEMA]
    dimensions: list[TaxonomyDimensionV1]
    code_sets: EconomicCodeSetsV1
    unclassified_reason_codes: list[UnclassifiedReason]
    cross_field_invariants: list[CrossFieldInvariantV1]
    prohibited_concept_categories: list[ProhibitedCategory]
    taxonomy_hash_generation: TaxonomyHashGenerationV1

    @model_validator(mode="after")
    def validate_contract(self) -> "EconomicEdgeTaxonomyV1":
        actual_dimensions = tuple(
            (item.field, item.code_set, item.cardinality) for item in self.dimensions
        )
        if actual_dimensions != DIMENSION_SPECS:
            raise ValueError("taxonomy dimensions must exactly match the final v1 entry contract")
        if self.taxonomy_version == 1 and self.previous_taxonomy_sha256 is not None:
            raise ValueError("taxonomy v1 cannot claim a previous taxonomy")
        if self.taxonomy_version > 1 and self.previous_taxonomy_sha256 is None:
            raise ValueError("additive taxonomy versions must bind the previous taxonomy hash")
        expected_reasons = sorted(UnclassifiedReason.__args__)
        if self.unclassified_reason_codes != expected_reasons:
            raise ValueError("unclassified reason codes must be complete and sorted")
        expected_prohibited = sorted(ProhibitedCategory.__args__)
        if self.prohibited_concept_categories != expected_prohibited:
            raise ValueError("prohibited concept categories must be complete and sorted")
        code_sets = self.code_sets.model_dump()
        for name, codes in code_sets.items():
            code_values = [item["code"] for item in codes]
            if code_values != sorted(set(code_values)):
                raise ValueError(f"taxonomy code set {name} must be sorted and unique")
        known_fields = {field: code_set for field, code_set, _cardinality in DIMENSION_SPECS}
        for invariant in self.cross_field_invariants:
            for selection in (*invariant.if_any, *invariant.require_all, *invariant.require_any):
                code_set_name = known_fields[selection.field]
                known_codes = {item["code"] for item in code_sets[code_set_name]}
                if not set(selection.codes).issubset(known_codes):
                    raise ValueError(
                        f"invariant {invariant.invariant_id} references an unknown code for {selection.field}"
                    )
        invariant_ids = [item.invariant_id for item in self.cross_field_invariants]
        if invariant_ids != sorted(set(invariant_ids)):
            raise ValueError("cross-field invariants must be sorted and unique")
        return self


def canonical_taxonomy_bytes(value: BaseModel | Mapping[str, Any]) -> bytes:
    payload = value.model_dump(mode="json", by_alias=True) if isinstance(value, BaseModel) else dict(value)
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def taxonomy_sha256(value: EconomicEdgeTaxonomyV1 | Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_taxonomy_bytes(value)).hexdigest()


def taxonomy_ref(value: EconomicEdgeTaxonomyV1) -> TaxonomyRefV1:
    return TaxonomyRefV1(
        taxonomy_id=value.taxonomy_id,
        taxonomy_version=value.taxonomy_version,
        taxonomy_sha256=taxonomy_sha256(value),
    )


def load_taxonomy_catalog(directory: str | Path) -> dict[int, EconomicEdgeTaxonomyV1]:
    """Load every published version and prove its additive immutable lineage."""

    root = Path(directory)
    paths = sorted(root.glob("economic-edge-taxonomy-v*.json"))
    if not paths:
        raise ValueError(f"no economic-edge taxonomy contracts found under {root}")
    catalog: dict[int, EconomicEdgeTaxonomyV1] = {}
    for path in paths:
        try:
            raw = json.loads(path.read_bytes())
            taxonomy = EconomicEdgeTaxonomyV1.model_validate(raw)
        except (OSError, ValueError) as exc:
            raise ValueError(f"invalid economic-edge taxonomy {path}: {exc}") from exc
        expected_name = TAXONOMY_FILENAME_PATTERN.format(version=taxonomy.taxonomy_version)
        if path.name != expected_name:
            raise ValueError(f"taxonomy filename/version mismatch: {path}")
        if taxonomy.taxonomy_version in catalog:
            raise ValueError(f"duplicate taxonomy version {taxonomy.taxonomy_version}")
        catalog[taxonomy.taxonomy_version] = taxonomy
    versions = sorted(catalog)
    if versions != list(range(1, versions[-1] + 1)):
        raise ValueError("taxonomy versions must be contiguous from v1")
    for version in versions[1:]:
        previous = catalog[version - 1]
        current = catalog[version]
        if current.previous_taxonomy_sha256 != taxonomy_sha256(previous):
            raise ValueError(f"taxonomy v{version} does not bind the exact v{version - 1} hash")
        _validate_additive_evolution(previous, current)
    return catalog


def resolve_taxonomy(
    catalog: Mapping[int, EconomicEdgeTaxonomyV1],
    reference: TaxonomyRefV1,
) -> EconomicEdgeTaxonomyV1:
    taxonomy = catalog.get(reference.taxonomy_version)
    if taxonomy is None:
        raise ValueError(f"taxonomy version {reference.taxonomy_version} is not published")
    if taxonomy.taxonomy_id != reference.taxonomy_id or taxonomy_sha256(taxonomy) != reference.taxonomy_sha256:
        raise ValueError("taxonomy_ref does not bind the exact published taxonomy")
    return taxonomy


def validate_concepts(taxonomy: EconomicEdgeTaxonomyV1, concepts: EconomicConceptsV1) -> None:
    code_sets = {
        name: {item.code for item in getattr(taxonomy.code_sets, name)}
        for name in EconomicCodeSetsV1.model_fields
    }
    selected = concepts.model_dump()
    for field, code_set, _cardinality in DIMENSION_SPECS:
        raw = selected[field]
        values = raw if isinstance(raw, list) else [raw]
        unknown = sorted(set(values) - code_sets[code_set])
        if unknown:
            raise ValueError(f"{field} contains codes absent from the bound taxonomy: {', '.join(unknown)}")
    for invariant in taxonomy.cross_field_invariants:
        if not any(_selection_matches(selected, item) for item in invariant.if_any):
            continue
        if any(not _selection_matches(selected, item) for item in invariant.require_all):
            raise ValueError(f"economic concepts violate {invariant.invariant_id}")
        if invariant.require_any and not any(
            _selection_matches(selected, item) for item in invariant.require_any
        ):
            raise ValueError(f"economic concepts violate {invariant.invariant_id}")


def fingerprint_document(taxonomy_id: str, concepts: EconomicConceptsV1) -> EconomicEdgeFingerprintV1:
    return EconomicEdgeFingerprintV1.model_validate(
        {"schema": FINGERPRINT_SCHEMA, "taxonomy_id": taxonomy_id, **concepts.model_dump()}
    )


def fingerprint_sha256(taxonomy_id: str, concepts: EconomicConceptsV1) -> str:
    return hashlib.sha256(canonical_taxonomy_bytes(fingerprint_document(taxonomy_id, concepts))).hexdigest()


def derived_display_label(taxonomy: EconomicEdgeTaxonomyV1, concepts: EconomicConceptsV1) -> str:
    labels = _code_lookup(taxonomy)
    return " · ".join(
        (
            labels["market_behavior"][concepts.market_behavior_code].display_label,
            labels["causal_mechanism"][concepts.causal_mechanism_code].display_label,
            labels["expected_effect"][concepts.expected_effect_code].display_label,
        )
    )


def matcher_dimensions(taxonomy: EconomicEdgeTaxonomyV1, concepts: EconomicConceptsV1) -> dict[str, list[str]]:
    lookup = _code_lookup(taxonomy)
    result: dict[str, list[str]] = {}
    for field, code_set, _cardinality in DIMENSION_SPECS:
        raw = getattr(concepts, field)
        values = raw if isinstance(raw, list) else [raw]
        terms: list[str] = []
        for code in values:
            concept = lookup[code_set][code]
            terms.extend((concept.code, concept.display_label, *concept.recall_aliases))
        result[field] = terms
    return result


def _selection_matches(selected: Mapping[str, Any], selection: TaxonomySelectionV1) -> bool:
    raw = selected[selection.field]
    values = set(raw if isinstance(raw, list) else [raw])
    return bool(values.intersection(selection.codes))


def _code_lookup(taxonomy: EconomicEdgeTaxonomyV1) -> dict[str, dict[str, TaxonomyCodeV1]]:
    return {
        name: {item.code: item for item in getattr(taxonomy.code_sets, name)}
        for name in EconomicCodeSetsV1.model_fields
    }


def _validate_additive_evolution(
    previous: EconomicEdgeTaxonomyV1,
    current: EconomicEdgeTaxonomyV1,
) -> None:
    if previous.taxonomy_id != current.taxonomy_id:
        raise ValueError("taxonomy namespace cannot change within an additive lineage")
    if previous.dimensions != current.dimensions:
        raise ValueError("taxonomy dimensions cannot change within the final v1 record contract")
    if previous.fingerprint_schema != current.fingerprint_schema:
        raise ValueError("taxonomy fingerprint schema cannot change")
    previous_sets = _code_lookup(previous)
    current_sets = _code_lookup(current)
    for set_name, old_codes in previous_sets.items():
        new_codes = current_sets[set_name]
        for code, old in old_codes.items():
            new = new_codes.get(code)
            if new is None:
                raise ValueError(f"taxonomy v{current.taxonomy_version} removes {set_name}.{code}")
            if old.definition != new.definition or old.display_label != new.display_label:
                raise ValueError(f"taxonomy v{current.taxonomy_version} redefines {set_name}.{code}")
            if not set(old.recall_aliases).issubset(new.recall_aliases):
                raise ValueError(f"taxonomy v{current.taxonomy_version} removes recall aliases from {set_name}.{code}")
    old_invariants = {item.invariant_id: item for item in previous.cross_field_invariants}
    new_invariants = {item.invariant_id: item for item in current.cross_field_invariants}
    for invariant_id, old in old_invariants.items():
        if new_invariants.get(invariant_id) != old:
            raise ValueError(f"taxonomy v{current.taxonomy_version} changes or removes invariant {invariant_id}")
    if not set(previous.prohibited_concept_categories).issubset(current.prohibited_concept_categories):
        raise ValueError("taxonomy evolution cannot remove prohibited concept categories")
    if previous.taxonomy_hash_generation != current.taxonomy_hash_generation:
        raise ValueError("taxonomy hash-generation rules cannot change")


def bundled_taxonomy_root() -> Path:
    return Path(__file__).resolve().parents[3] / "research" / "edge_backlog" / "contracts"


def bundled_taxonomy_ref(version: int = 1) -> TaxonomyRefV1:
    catalog = load_taxonomy_catalog(bundled_taxonomy_root())
    try:
        taxonomy = catalog[version]
    except KeyError as exc:
        raise ValueError(f"bundled taxonomy version {version} is unavailable") from exc
    return taxonomy_ref(taxonomy)


__all__ = [
    "ClassificationStatus",
    "DIMENSION_FIELDS",
    "EconomicConceptsV1",
    "EconomicEdgeFingerprintV1",
    "EconomicEdgeTaxonomyV1",
    "FINGERPRINT_SCHEMA",
    "TAXONOMY_ID",
    "TAXONOMY_SCHEMA",
    "TaxonomyRefV1",
    "UnclassifiedReason",
    "bundled_taxonomy_ref",
    "bundled_taxonomy_root",
    "derived_display_label",
    "fingerprint_document",
    "fingerprint_sha256",
    "load_taxonomy_catalog",
    "matcher_dimensions",
    "resolve_taxonomy",
    "taxonomy_ref",
    "taxonomy_sha256",
    "validate_concepts",
]
